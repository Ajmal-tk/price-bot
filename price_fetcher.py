import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

class PriceFetcher:
    def __init__(self):
        # Initialize Selenium WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

    def search_flipkart(self, query: str) -> dict:
        """Search for product on Flipkart"""
        url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        
        try:
            self.driver.get(url)
            time.sleep(3)  # Wait for page to load
            
            # Get first product details
            product = self.driver.find_element(By.CLASS_NAME, "_4rR01T")
            price = self.driver.find_element(By.CLASS_NAME, "_30jeq3._1_WHN1")
            
            return {
                "store": "Flipkart",
                "product_name": product.text,
                "price": price.text,
                "url": url
            }
            
        except Exception as e:
            print(f"Error fetching from Flipkart: {str(e)}")
            return None

    def search_amazon(self, query: str) -> dict:
        """Search for product on Amazon"""
        url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        
        try:
            self.driver.get(url)
            time.sleep(3)  # Wait for page to load
            
            # Get first product details
            product = self.driver.find_element(By.CLASS_NAME, "a-size-medium.a-color-base.a-text-normal")
            price = self.driver.find_element(By.CLASS_NAME, "a-price-whole")
            
            return {
                "store": "Amazon",
                "product_name": product.text,
                "price": price.text,
                "url": url
            }
            
        except Exception as e:
            print(f"Error fetching from Amazon: {str(e)}")
            return None

    def search_all(self, query: str) -> list:
        """Search across all stores"""
        results = []
        
        # Search Flipkart
        flipkart_result = self.search_flipkart(query)
        if flipkart_result:
            results.append(flipkart_result)
            
        # Search Amazon
        amazon_result = self.search_amazon(query)
        if amazon_result:
            results.append(amazon_result)
            
        return results
