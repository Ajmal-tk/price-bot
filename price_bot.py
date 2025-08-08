import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import requests
from bs4 import BeautifulSoup
import re

import threading, http.server, socketserver, os

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
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_product))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a personalised message when the command /start is issued."""
        user_first_name = update.effective_user.first_name if update.effective_user else "there"
        await update.message.reply_text(
            f'Hi {user_first_name}! I am your Price Comparison Bot.\n'
            'Send me a product name to compare prices across Indian online stores.\n'
            'Example: iPhone 13'
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
        """Search for product prices when a text message is received."""
        product_name = update.message.text
        
        # Get prices from different stores
        flipkart_result = await self.get_flipkart_price(product_name)
        amazon_result = await self.get_amazon_price(product_name)
        
        # Format and send the response
        response = f"Price Comparison for: {product_name}\n\n"
        
        if flipkart_result:
            response += f"Flipkart: {flipkart_result}\n"
        else:
            response += "Flipkart: Not found\n"
        
        if amazon_result:
            response += f"Amazon: {amazon_result}\n"
        else:
            response += "Amazon: Not found\n"
        
        await update.message.reply_text(response)

    async def get_flipkart_price(self, product_name: str) -> str:
        """Get price from Flipkart."""
        try:
            search_url = f'https://www.flipkart.com/search?q={product_name.replace(" ", "+")}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract first product title & price
            title_elem = soup.find('div', {'class': '_4rR01T'}) or soup.find('a', {'class': 's1Q9rs'})
            price_elem = soup.find('div', {'class': '_30jeq3 _1_WHN1'})
            if title_elem and price_elem:
                title = title_elem.text.strip()
                price = price_elem.text.strip()
                return f"{title} - {price}"
            return None
        except Exception as e:
            print(f"Error fetching Flipkart price: {e}")
            return None

    async def get_amazon_price(self, product_name: str) -> str:
        """Get price from Amazon."""
        try:
            search_url = f'https://www.amazon.in/s?k={product_name.replace(" ", "+")}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(search_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract first product title & price
            title_elem = soup.find('span', {'class': 'a-size-medium a-color-base a-text-normal'})
            price_elem = soup.find('span', {'class': 'a-price-whole'})
            if title_elem and price_elem:
                title = title_elem.text.strip()
                price = price_elem.text.strip()
                return f"{title} - {price}"
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
