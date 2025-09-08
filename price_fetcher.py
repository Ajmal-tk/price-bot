import requests
from bs4 import BeautifulSoup
import random
from urllib.parse import quote_plus
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENTS = [
    # A small pool of modern desktop UAs to reduce trivial blocking
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def build_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "close",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }

def build_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def resilient_get(session: requests.Session, url: str, headers: dict, timeout_read: float = 35.0):
    """Perform a GET with manual retries and jitter to reduce transient timeouts."""
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            # Vary UA across attempts a bit
            attempt_headers = dict(headers)
            attempt_headers["User-Agent"] = random.choice(USER_AGENTS)
            # (connect timeout, read timeout)
            resp = session.get(url, headers=attempt_headers, timeout=(5.0, timeout_read))
            return resp
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.RequestException):
            if attempt == attempts:
                raise
            try:
                import time
                time.sleep(0.6 + random.random() * 0.6)
            except Exception:
                pass
    return None

class PriceFetcher:

    def search_flipkart(self, query: str) -> dict | None:
        """Search for product on Flipkart"""
        url = f"https://www.flipkart.com/search?q={quote_plus(query)}"

        try:
            session = build_session()
            res = resilient_get(session, url, headers=build_headers(), timeout_read=40.0)
            soup = BeautifulSoup(res.text, "html.parser")

            # Basic anti-bot/captcha guard
            page_text = soup.get_text(" ", strip=True).lower()
            if "captcha" in page_text or "unusual traffic" in page_text:
                return None

            # First product title
            # Flipkart has multiple card layouts; try several selectors
            title_candidates = [
                # Large card layout (mobiles and many categories)
                "div._4rR01T",
                # Small tile layout (electronics)
                "a.s1Q9rs",
                # Newer small tile title class
                "div.KzDlHZ",
                # Another common anchor title class
                "a.IRpwTa",
            ]
            price_candidates = [
                # Common price class in large layout
                "div._30jeq3",
                # Newer price class observed in small tiles
                "div.Nx9bqj",
                # Sometimes nested inside price container
                "div._25b18c > div._30jeq3",
                # Fallback: any element with rupee symbol near title
            ]

            title = None
            price = None
            # Try direct selectors first
            for sel in title_candidates:
                node = soup.select_one(sel)
                if node and node.get_text(strip=True):
                    title = node
                    break
            if title:
                # Prefer price close to title
                container = title.find_parent()
                if container:
                    for psel in price_candidates:
                        price_node = container.select_one(psel)
                        if price_node and price_node.get_text(strip=True):
                            price = price_node
                            break
            # Fallback: page-wide price search
            if not price:
                for psel in price_candidates:
                    price_node = soup.select_one(psel)
                    if price_node and price_node.get_text(strip=True):
                        price = price_node
                        break

            if not title or not price:
                return None

            return {
                "store": "Flipkart",
                "product_name": title.get_text(strip=True),
                "price": price.get_text(strip=True),
                "url": url
            }

        except Exception as e:
            print(f"Flipkart error: {e}")
            return None

    def search_amazon(self, query: str) -> dict | None:
        """Search for product on Amazon India"""
        url = f"https://www.amazon.in/s?k={quote_plus(query)}"

        try:
            session = build_session()
            headers = build_headers()
            # Hint to Amazon locale
            headers["Accept-Language"] = "en-IN,en;q=0.9"
            res = resilient_get(session, url, headers=headers, timeout_read=40.0)
            soup = BeautifulSoup(res.text, "html.parser")

            # Basic anti-bot page guard
            page_text = soup.get_text(" ", strip=True).lower()
            if "robot check" in page_text or "enter the characters" in page_text or "captcha" in page_text:
                return None

            # Prefer using first search result container for consistent extraction
            result = soup.select_one('div.s-main-slot div[data-component-type="s-search-result"]')
            title = None
            price = None
            if result:
                title = (
                    result.select_one("h2 a span") or
                    result.select_one("span.a-size-medium.a-color-base.a-text-normal") or
                    result.select_one("span.a-size-base-plus.a-color-base.a-text-normal")
                )
                # Multiple price markups possible
                price = (
                    result.select_one("span.a-price > span.a-offscreen") or
                    result.select_one("span.a-price-whole") or
                    result.select_one("span.a-price .a-offscreen")
                )
            else:
                # Fallback: page-wide selectors
                title = (
                    soup.select_one("h2 a span") or
                    soup.select_one("span.a-size-medium.a-color-base.a-text-normal") or
                    soup.select_one("span.a-size-base-plus.a-color-base.a-text-normal")
                )
                price = (
                    soup.select_one("span.a-price > span.a-offscreen") or
                    soup.select_one("span.a-price-whole") or
                    soup.select_one("span.a-price .a-offscreen")
                )

            if not title or not price:
                return None

            return {
                "store": "Amazon",
                "product_name": title.get_text(strip=True),
                "price": price.get_text(strip=True),
                "url": url
            }

        except Exception as e:
            print(f"Amazon error: {e}")
            return None

    def search_all(self, query: str) -> list:
        """Search across all stores"""
        results = []

        flipkart = self.search_flipkart(query)
        if flipkart:
            results.append(flipkart)

        amazon = self.search_amazon(query)
        if amazon:
            results.append(amazon)

        return results
