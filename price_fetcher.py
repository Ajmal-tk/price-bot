import requests
from bs4 import BeautifulSoup
import random

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

class PriceFetcher:

    def search_flipkart(self, query: str) -> dict | None:
        """Search for product on Flipkart"""
        url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"

        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            # First product title
            title = soup.select_one("div._4rR01T") or soup.select_one("a.s1Q9rs")  # mobiles OR electronics
            price = soup.select_one("div._30jeq3")

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
        url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"

        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            # First product title and price
            title = soup.select_one("h2 a span")
            price = soup.select_one("span.a-price-whole")

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
