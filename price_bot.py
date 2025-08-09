import os
import asyncio
import aiohttp
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from functools import lru_cache
from dotenv import load_dotenv
from telegram import Update, BotCommand, ReplyKeyboardMarkup, MenuButtonCommands
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
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
        
        # Create tasks for both price checks to run in parallel
        flipkart_task = asyncio.create_task(self.get_flipkart_price(product_name))
        amazon_task = asyncio.create_task(self.get_amazon_price(product_name))
        
        # Wait for both tasks to complete with a timeout
        done, pending = await asyncio.wait(
            [flipkart_task, amazon_task],
            timeout=10,  # Max 10 seconds total for both requests
            return_when=asyncio.ALL_COMPLETED
        )
        
        # Cancel any pending tasks
        for task in pending:
            task.cancel()
        
        # Get results (or None if tasks were cancelled or timed out)
        flipkart_result = flipkart_task.result() if flipkart_task.done() and not flipkart_task.cancelled() else None
        amazon_result = amazon_task.result() if amazon_task.done() and not amazon_task.cancelled() else None
        
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
        
        # Send the response with markdown formatting
        await update.message.reply_text(
            response,
            parse_mode='Markdown'
        )

    @lru_cache(maxsize=100)
    async def get_flipkart_price(self, product_name: str) -> str:
        """Get price from Flipkart with caching and timeout."""
        try:
            search_url = f'https://www.flipkart.com/search?q={product_name.replace(" ", "+")}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, timeout=5) as response:
                    if response.status != 200:
                        return None
                    html = await response.text()
                    
            soup = BeautifulSoup(html, 'html.parser')
            product_block = soup.select_one('div._1AtVbE div._4rR01T, div._1AtVbE a.s1Q9rs')
            title_elem = product_block
            price_elem = product_block.find_next('div', {'class': '_30jeq3'}) if product_block else None
            
            if title_elem and price_elem:
                title = title_elem.text.strip()
                price = price_elem.text.strip()
                return f"{title} - {price}"
            return None
            
        except asyncio.TimeoutError:
            print("Timeout while fetching from Flipkart")
            return None
        except Exception as e:
            print(f"Error fetching Flipkart price: {e}")
            return None

    @lru_cache(maxsize=100)
    async def get_amazon_price(self, product_name: str) -> str:
        """Get price from Amazon with caching and timeout."""
        try:
            search_url = f'https://www.amazon.in/s?k={product_name.replace(" ", "+")}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, timeout=5) as response:
                    if response.status != 200:
                        return None
                    html = await response.text()
            
            soup = BeautifulSoup(html, 'html.parser')
            result = soup.select_one('div.s-result-item')
            title_elem = result.select_one('span.a-size-medium') if result else None
            price_elem = result.select_one('span.a-price-whole') if result else None
            
            if title_elem and price_elem:
                title = title_elem.text.strip()
                price = price_elem.text.strip()
                return f"{title} - {price}"
            return None
            
        except asyncio.TimeoutError:
            print("Timeout while fetching from Amazon")
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
