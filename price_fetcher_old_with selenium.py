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
import logging

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceFetcher:
    def __init__(self):
        # Initialize Selenium WebDriver with better options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.wait = WebDriverWait(self.driver, 15)

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

    def search_flipkart(self, query: str) -> dict:
        """Search for product on Flipkart with improved selectors"""
        url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        
        try:
            logger.info(f"Fetching Flipkart URL: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Take screenshot for debugging (optional)
            # self.driver.save_screenshot("flipkart_debug.png")
            
            # Get page source and parse with BeautifulSoup as backup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            product_name = None
            price = None
            
            # Method 1: Try Selenium selectors
            try:
                # Wait for any product element
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div._1YokD2")))
                
                # Try multiple approaches for product name
                name_selectors = [
                    "div._4rR01T",           # Mobiles
                    "a.s1Q9rs",              # Electronics  
                    "a.IRpwTa",              # Other products
                    "div.KzDlHZ",            # New format
                    "a._2mylT6",             # Alternative
                    "h1.yhB1nd",             # Product page title
                    "span._2_R_DZ",          # Another variant
                ]
                
                for selector in name_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements and elements[0].text.strip():
                            product_name = elements[0].text.strip()
                            logger.info(f"Found product name with selector {selector}: {product_name[:50]}...")
                            break
                    except Exception as e:
                        continue
                
                # Try multiple approaches for price
                price_selectors = [
                    "div._30jeq3._1_WHN1",   # Common price
                    "div._30jeq3",           # Price without old price
                    "div._1_WHN1",           # Alternative price
                    "div._25b18c div",       # Price in container
                    "span._2_R_DZ",          # Another price format
                ]
                
                for selector in price_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            text = elem.text.strip()
                            if text and ("₹" in text or text.replace(",", "").replace(".", "").isdigit()):
                                price = text
                                logger.info(f"Found price with selector {selector}: {price}")
                                break
                        if price:
                            break
                    except Exception as e:
                        continue
            
            except Exception as e:
                logger.error(f"Selenium error: {str(e)}")
            
            # Method 2: Try BeautifulSoup as fallback
            if not product_name or not price:
                logger.info("Trying BeautifulSoup method...")
                
                # Find all divs that might contain products
                product_containers = soup.find_all('div', {'data-id': True})
                
                if not product_containers:
                    # Try alternative containers
                    product_containers = soup.find_all('div', class_='_1At
