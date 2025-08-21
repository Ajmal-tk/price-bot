The issue is likely due to incorrect selectors or bot detection. Here's a completely revised solution with better selectors and debugging:

## Updated Price Fetcher with Debugging:

```python
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import random

class PriceFetcher:
    def __init__(self):
        # Initialize Selenium WebDriver with stealth options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Execute script to remove webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 10)

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

    def search_flipkart(self, query: str) -> dict:
        """Search for product on Flipkart with BeautifulSoup fallback"""
        url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        
        try:
            print(f"Fetching Flipkart URL: {url}")
            self.driver.get(url)
            
            # Random delay to appear more human-like
            time.sleep(random.uniform(2, 4))
            
            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Debug: Save HTML for inspection
            with open('flipkart_debug.html', 'w', encoding='utf-8') as f:
                f.write(page_source[:5000])  # Save first 5000 chars for debugging
            
            product_name = None
            price = None
            
            # Method 1: Try with BeautifulSoup
            # Search for product containers
            product_containers = soup.find_all('div', {'data-id': True})
            
            if not product_containers:
                # Try alternative container selectors
                product_containers = soup.find_all('div', class_='_1AtVbE')
                
            if not product_containers:
                product_containers = soup.find_all('div', class_='_2kHMtA')
                
            if not product_containers:
                product_containers = soup.find_all('div', class_='_13oc-S')
            
            print(f"Found {len(product_containers)} product containers")
            
            if product_containers:
                first_product = product_containers[0]
                
                # Look for product name
                name_tags = [
                    first_product.find('div', class_='_4rR01T'),
                    first_product.find('a', class_='s1Q9rs'),
                    first_product.find('a', class_='IRpwTa'),
                    first_product.find('div', class_='KzDlHZ'),
                    first_product.find('a', class_='_2UzuFa'),
                ]
                
                for tag in name_tags:
                    if tag and tag.text.strip():
                        product_name = tag.text.strip()
                        print(f"Found product name: {product_name[:50]}...")
                        break
                
                # Look for price
                price_tags = [
                    first_product.find('div', class_='_30jeq3'),
                    first_product.find('div', class_='_1_WHN1'),
                    first_product.find('div', class_='_25b18c'),
                ]
                
                for tag in price_tags:
                    if tag and tag.text.strip():
                        price = tag.text.strip()
                        print(f"Found price: {price}")
                        break
            
            # Method 2: If BeautifulSoup fails, try Selenium
            if not product_name or not price:
                print("BeautifulSoup failed, trying Selenium selectors...")
                
                # Try using XPath
                try:
                    # For mobiles/electronics
                    product_element = self.driver.find_element(By.XPATH, "//div[@class='_4rR01T']")
                    product_name = product_element.text
                except:
                    try:
                        # For other products
                        product_element = self.driver.find_element(By.XPATH, "//a[contains(@class, 's1Q9rs') or contains(@class, 'IRpwTa')]")
                        product_name = product_element.text
                    except:
                        pass
                
                try:
                    price_element = self.driver.find_element(By.XPATH, "//div[contains(@class, '_30jeq3')]")
                    price = price_element.text
                except:
                    pass
            
            if product_name and price:
                return {
                    "store": "Flipkart",
                    "product_name": product_name,
                    "price": price,
                    "url": url
                }
            else:
                print(f"Failed to find product or price. Product: {product_name}, Price: {price}")
                return None
            
        except Exception as e:
            print(f"Error fetching from Flipkart: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def search_amazon(self, query: str) -> dict:
        """Search for product on Amazon with BeautifulSoup fallback"""
        url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        
        try:
            print(f"Fetching Amazon URL: {url}")
            self.driver.get(url)
            
            # Random delay
            time.sleep(random.uniform(2, 4))
            
            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Debug: Save HTML for inspection
            with open('amazon_debug.html', 'w', encoding='utf-8') as f:
                f.write(page_source[:5000])
            
            product_name = None
            price = None
            
            # Check for CAPTCHA
            if "captcha" in page_source.lower() or "security check" in page_source.lower():
                print("Amazon CAPTCHA detected!")
                return None
            
            # Method 1: BeautifulSoup
            # Find product containers
            product_containers = soup.find_all('div', {'data-component-type': 's-search-result'})
            
            print(f"Found {len(product_containers)} product containers")
            
            if product_containers:
                first_product = product_containers[0]
                
                # Look for product name
                name_tag = first_product.find('h2', class_='s-size-mini s-spacing-none s-color-base')
                if not name_tag:
                    name_tag = first_product.find('h2')
                if name_tag:
                    span = name_tag.find('span')
                    if span:
                        product_name = span.text.strip()
                        print(f"Found product name: {product_name[:50]}...")
                
                # Look for price
                price_tag = first_product.find('span', class_='a-price-whole')
                if not price_tag:
                    price_tag = first_product.find('span', class_='a-price')
                    if price_tag:
                        price_tag = price_tag.find('span')
                
                if price_tag:
                    price = price_tag.text.strip()
                    print(f"Found price: {price}")
            
            # Method 2: Selenium if BeautifulSoup fails
            if not product_name or not price:
                print("BeautifulSoup failed, trying Selenium...")
                
                try:
                    # Wait for products to load
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-component-type='s-search-result']")))
                    
                    # Get first product name
                    product_element = self.driver.find_element(By.CSS_SELECTOR, "[data-component-type='s-search-result'] h2 span")
                    product_name = product_element.text
                    
                    # Get price
                    price_element = self
