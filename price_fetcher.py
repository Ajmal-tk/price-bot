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

class PriceFetcher:
    def __init__(self):
        # Initialize Selenium WebDriver with better options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.wait = WebDriverWait(self.driver, 10)

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

    def search_flipkart(self, query: str) -> dict:
        """Search for product on Flipkart"""
        url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        
        try:
            self.driver.get(url)
            
            # Wait for products to load
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-id]")))
            
            # Try multiple selectors for better reliability
            product_name = None
            price = None
            
            # Method 1: Try common selectors
            try:
                # Product name selectors
                product_selectors = [
                    "div._4rR01T",  # Mobile phones
                    "a.s1Q9rs",     # Electronics
                    "a.IRpwTa",     # Fashion
                    "div.KzDlHZ",   # New selector
                    "a._2UzuFa",    # Alternative
                    "div._2WkVRV a", # Another variant
                ]
                
                for selector in product_selectors:
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if element and element.text:
                            product_name = element.text
                            break
                    except:
                        continue
                
                # Price selectors
                price_selectors = [
                    "div._30jeq3._1_WHN1",  # Common price selector
                    "div._30jeq3",          # Alternative
                    "div._1_WHN1",          # Another variant
                    "div._25b18c div:first-child", # Price container
                ]
                
                for selector in price_selectors:
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR
