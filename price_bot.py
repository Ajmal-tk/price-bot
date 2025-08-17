import os
import asyncio
import aiohttp
import random
import time
import json
import threading
import http.server
import socketserver
from datetime import datetime, timedelta
from functools import lru_cache
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from telegram import Update, BotCommand, ReplyKeyboardMarkup, MenuButtonCommands
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from bs4 import BeautifulSoup

# List of user agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

# Cache for storing request timestamps to avoid rate limiting
request_timestamps = []

class RateLimiter:
    def __init__(self, max_requests=5, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window  # in seconds
        self.requests = []

    async def wait_if_needed(self):
        now = time.time()
        # Remove requests older than the time window
        self.requests = [t for t in self.requests if now - t < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            # Calculate how long to wait until the oldest request falls out of the window
            oldest_request = self.requests[0]
            wait_time = (oldest_request + self.time_window) - now
            if wait_time > 0:
                print(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
        
        self.requests.append(time.time())

# Global rate limiter
rate_limiter = RateLimiter(max_requests=3, time_window=60)  # 3 requests per minute

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def start_http_server():
    port = int(os.getenv("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Health-check server running on port {port}")
        httpd.serve_forever()



class PriceBot:
    def __init__(self):
        load_dotenv()
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.application = Application.builder().token(self.token).build()
        
        # Register bot commands for slash menu (will be set up after the application starts)
        self.setup_commands = [
            BotCommand("start", "Greet & show instructions"),
            BotCommand("help", "How to use the bot"),
        ]
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_product))
        
        # Add post_init to set up commands after the application starts
        self.application.post_init = self.post_init
        
    async def post_init(self, application):
        """Set up bot commands and menu button after application starts."""
        try:
            await application.bot.set_my_commands(self.setup_commands)
            await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        except Exception as e:
            print(f"Warning: Could not set up bot commands/menu: {e}")
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_product))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a personalised message and show quick-command buttons."""
        user_first_name = update.effective_user.first_name or "there"

        keyboard = ReplyKeyboardMarkup([
            ["/help"]
        ], resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            f'Hi {user_first_name}! I am your Price Comparison Bot.\n'
            'Send me a product name to compare prices across Indian online stores.\n'
            'Example: iPhone 13',
            reply_markup=keyboard
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        await update.message.reply_text(
            'To use this bot:\n'
            '1. Send a product name\n'
            '2. I will search for the product on Flipkart and Amazon\n'
            '3. I will send you the price comparison\n\n'
            'Example: iPhone 13'
        )

    async def search_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search for a product and return prices with parallel requests."""
        product_name = update.message.text
        
        # Send typing action to show the bot is working
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action='typing'
        )
        
        # Run both price checks in parallel with individual timeouts
        try:
            flipkart_result = await asyncio.wait_for(self.get_flipkart_price(product_name), timeout=5)
        except asyncio.TimeoutError:
            flipkart_result = None
            
        try:
            amazon_result = await asyncio.wait_for(self.get_amazon_price(product_name), timeout=5)
        except asyncio.TimeoutError:
            amazon_result = None
        
        # Build the response
        response = f"🔍 *Price Comparison for: {product_name}*\n\n"
        
        if flipkart_result:
            response += f"🛒 *Flipkart*: {flipkart_result}\n"
        else:
            response += "❌ *Flipkart*: Not available\n"
        
        if amazon_result:
            response += f"📦 *Amazon*: {amazon_result}\n"
        else:
            response += "❌ *Amazon*: Not available\n"
        
        # Add a note about caching
        response += "\n_Note: Prices are cached for 1 hour_"
        
        # Send as plain text to avoid markdown parsing issues
        await update.message.reply_text(
            response,
            parse_mode=None  # Disable markdown parsing
        )

    async def get_flipkart_price(self, product_name: str) -> str:
        """Get price from Flipkart using Playwright to avoid bot detection."""
        try:
            # Create a cache key based on the product name
            cache_key = f"_flipkart_cache_{product_name}"
            
            # Check if we have a cached result
            if hasattr(self, cache_key):
                cached_result = getattr(self, cache_key)
                # Check if cache is still fresh (30 minutes)
                if hasattr(self, f"{cache_key}_time"):
                    cache_time = getattr(self, f"{cache_key}_time")
                    if (time.time() - cache_time) < 1800:  # 30 minutes cache
                        return cached_result
            
            # Apply rate limiting
            await rate_limiter.wait_if_needed()
            
            # If not in cache or cache expired, fetch the price using Playwright
            search_url = f'https://www.flipkart.com/search?q={product_name.replace(" ", "+")}'
            
            async with async_playwright() as p:
                # Launch browser with anti-detection measures
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-infobars',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-site-isolation-trials'
                    ]
                )
                
                # Create a new browser context with a random viewport and user agent
                context = await browser.new_context(
                    viewport={
                        'width': random.randint(1200, 1920),
                        'height': random.randint(800, 1080)
                    },
                    user_agent=get_random_user_agent(),
                    locale='en-US',
                    timezone_id='Asia/Kolkata',
                    permissions=['geolocation'],
                    color_scheme='light',
                    java_script_enabled=True,
                    has_touch=False,
                    is_mobile=False,
                    reduced_motion='reduce',
                    screen={
                        'width': 1920,
                        'height': 1080,
                        'device_scale_factor': 1
                    },
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Referer': 'https://www.google.com/'
                    }
                )
                
                # Create a new page
                page = await context.new_page()
                
                try:
                    # Navigate to the search page with a timeout
                    await page.goto(search_url, timeout=60000)  # 60 second timeout
                    
                    # Wait for the search results to load
                    try:
                        # Wait for either the product list or the "No results" message
                        await page.wait_for_selector('div._1AtVbE, div._2kHMtA, div._4ddWXP, div._2tDhp2', timeout=10000)
                    except PlaywrightTimeoutError:
                        # If we don't find any products, try to get the page content anyway
                        print("Warning: Could not find product list, continuing with page content")
                    
                    # Get the page content
                    content = await page.content()
                    
                    # Debug: Print a small snippet of the HTML
                    print(f"FLIPKART HTML snippet: {content[:500]}")
                    
                    # Check for bot detection
                    if "bot detected" in content.lower() or "access denied" in content.lower():
                        print("Flipkart bot detection triggered")
                        return "Error: Bot detection triggered on Flipkart"
                    
                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Try to find the product card with more specific selectors
                    product_card = (soup.select_one('div._1AtVbE') or 
                                  soup.select_one('div._2kHMtA') or 
                                  soup.select_one('div._4ddWXP') or
                                  soup.select_one('div._2tDhp2'))
                    
                    if not product_card:
                        print("No product card found with any selector")
                        return None
                    
                    # Try to find title and price with multiple selectors
                    title_elem = product_card.select_one('div._4rR01T, a.s1Q9rs, a.IRpwTa')
                    price_elem = product_card.select_one('div._30jeq3, div._30jeq3._1_WHN1')
                    
                    if not title_elem or not price_elem:
                        print(f"Title found: {bool(title_elem)}, Price found: {bool(price_elem)}")
                        return None
                    
                    title = title_elem.text.strip()
                    price = price_elem.text.strip()
                    result = f"{title} - {price}"
                    
                    # Cache the result
                    setattr(self, cache_key, result)
                    setattr(self, f"{cache_key}_time", time.time())
                    return result
                    
                except Exception as e:
                    print(f"Error in get_flipkart_price: {str(e)}")
                    return None
            
            # Try different product card selectors
            product_card = None
            selectors = [
                'div._1AtVbE',  # Main product card
                'div._13oc-S',  # Grid item
                'div._1xHGtK',  # Another grid item variant
                'div._4ddWXP'   # List item variant
            ]
            
            for selector in selectors:
                product_card = main_container.select_one(selector)
                if product_card:
                    print(f"Found product card with selector: {selector}")
                    break
            
            if not product_card:
                print("No product card found with any selector")
                return None
                
            # Try to find title and price with multiple selectors
            title_elem = product_card.select_one('div._4rR01T, a.s1Q9rs, a.IRpwTa')
            price_elem = product_card.select_one('div._30jeq3, div._30jeq3._1_WHN1')
            
            if not title_elem or not price_elem:
                print(f"Title found: {bool(title_elem)}, Price found: {bool(price_elem)}")
                return None
                
            title = title_elem.text.strip()
            price = price_elem.text.strip()
            result = f"{title} - {price}"
            
            # Cache the result
            setattr(self, cache_key, result)
            return result
            
        except asyncio.TimeoutError:
            print("Flipkart request timed out")
            return None
        except Exception as e:
            print(f"Error in get_flipkart_price: {str(e)}")
            return None

    async def get_amazon_price(self, product_name: str) -> str:
        """Get price from Amazon using Playwright to avoid bot detection."""
        try:
            # Create a cache key based on the product name
            cache_key = f"_amazon_cache_{product_name}"
            
            # Check if we have a cached result
            if hasattr(self, cache_key):
                cached_result = getattr(self, cache_key)
                # Check if cache is still fresh (30 minutes)
                if hasattr(self, f"{cache_key}_time"):
                    cache_time = getattr(self, f"{cache_key}_time")
                    if (time.time() - cache_time) < 1800:  # 30 minutes cache
                        return cached_result
            
            # Apply rate limiting
            await rate_limiter.wait_if_needed()
            
            # If not in cache or cache expired, fetch the price using Playwright
            search_url = f'https://www.amazon.in/s?k={product_name.replace(" ", "+")}'
            
            async with async_playwright() as p:
                # Launch browser with anti-detection measures
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-infobars',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-site-isolation-trials'
                    ]
                )
                
                # Create a new browser context with a random viewport and user agent
                context = await browser.new_context(
                    viewport={
                        'width': random.randint(1200, 1920),
                        'height': random.randint(800, 1080)
                    },
                    user_agent=get_random_user_agent(),
                    locale='en-US',
                    timezone_id='Asia/Kolkata',
                    permissions=['geolocation'],
                    color_scheme='light',
                    java_script_enabled=True,
                    has_touch=False,
                    is_mobile=False,
                    reduced_motion='reduce',
                    screen={
                        'width': 1920,
                        'height': 1080,
                        'device_scale_factor': 1
                    },
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Referer': 'https://www.google.com/'
                    }
                )
                
                # Create a new page
                page = await context.new_page()
                
                try:
                    # Navigate to the search page with a timeout
                    await page.goto(search_url, timeout=60000)  # 60 second timeout
                    
                    # Wait for the search results to load
                    try:
                        # Wait for either the product list or the "No results" message
                        await page.wait_for_selector('div[data-component-type="s-search-result"], div.s-no-outline', timeout=10000)
                    except PlaywrightTimeoutError:
                        # If we don't find any products, try to get the page content anyway
                        print("Warning: Could not find product list, continuing with page content")
                    
                    # Get the page content
                    content = await page.content()
                    
                    # Debug: Print a small snippet of the HTML
                    print(f"AMAZON HTML snippet: {content[:500]}")
                    
                    # Check for bot detection
                    if "bot detected" in content.lower() or "captcha" in content.lower() or "security check" in content.lower():
                        print("Amazon bot detection triggered")
                        return "Error: Bot detection triggered on Amazon"
                    
                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Try to find the results container
                    results = (soup.select_one('div.s-main-slot') or 
                             soup.select_one('div.s-result-list') or
                             soup.select_one('div[data-component-type="s-search-result"]'))
                    
                    if not results:
                        print("No results container found")
                        return None
                    
                    # Try to find the first product
                    product = results.select_one('div[data-component-type="s-search-result"]')
                    
                    if not product:
                        print("No product found")
                        return None
                    
                    # Try to find title and price with multiple selectors
                    title_elem = product.select_one('h2 span')
                    price_elem = product.select_one('span.a-price-whole, span.a-price > span')
                    
                    if not title_elem or not price_elem:
                        print(f"Title found: {bool(title_elem)}, Price found: {bool(price_elem)}")
                        return None
                    
                    title = title_elem.text.strip()
                    price = price_elem.text.strip()
                    result = f"{title} - {price}"
                    
                    # Cache the result
                    setattr(self, cache_key, result)
                    setattr(self, f"{cache_key}_time", time.time())
                    return result
                    
                except Exception as e:
                    print(f"Error fetching Amazon price: {e}")
                    return None
            
        except asyncio.TimeoutError:
            print("Amazon request timed out")
            return None
        except Exception as e:
            print(f"Error fetching Amazon price: {e}")
            return None

    def run(self):
        """Start the bot."""
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    threading.Thread(target=start_http_server, daemon=True).start()
    bot = PriceBot()
    bot.run()
