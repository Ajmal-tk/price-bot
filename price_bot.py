import os
import asyncio
import threading
import http.server
import socketserver
from dotenv import load_dotenv
from telegram import Update, BotCommand, ReplyKeyboardMarkup, MenuButtonCommands
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from urllib.parse import quote_plus

BOT_WEBHOOK_URL = os.getenv("BOT_WEBHOOK_URL")  # Optional: set to run via webhook instead of polling
# Import our BS4-based fetcher
from price_fetcher import PriceFetcher


def start_http_server():
    """Simple HTTP server for Render health check"""
    port = int(os.getenv("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Health-check server running on port {port}")
        httpd.serve_forever()


class PriceBot:
    def __init__(self):
        load_dotenv()
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.application = Application.builder().token(self.token).build()

        # Our price fetcher instance
        self.fetcher = PriceFetcher()

        # Register bot commands
        self.setup_commands = [
            BotCommand("start", "Greet & show instructions"),
            BotCommand("help", "How to use the bot"),
        ]

        # Handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_product)
        )

        # Post init
        self.application.post_init = self.post_init

    async def post_init(self, application):
        try:
            await application.bot.set_my_commands(self.setup_commands)
            await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        except Exception as e:
            print(f"Warning: Could not set up bot commands/menu: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user_first_name = update.effective_user.first_name or "there"
        keyboard = ReplyKeyboardMarkup([["/help"]], resize_keyboard=True)
        await update.message.reply_text(
            f"Hi {user_first_name}! I am your Price Comparison Bot.\n"
            "Send me a product name to compare prices across Amazon & Flipkart.\n"
            "Example: iPhone 13",
            reply_markup=keyboard,
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help instructions"""
        await update.message.reply_text(
            "To use this bot:\n"
            "1. Send a product name\n"
            "2. I'll search Amazon and Flipkart\n"
            "3. I'll send you the price comparison\n\n"
            "Example: iPhone 13"
        )

    async def search_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search product on Amazon & Flipkart"""
        product_name = update.message.text

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Search in parallel with asyncio
        flipkart_result, amazon_result = await asyncio.gather(
            self.get_flipkart_price(product_name), self.get_amazon_price(product_name)
        )

        response = f"🔍 *Price Comparison for: {product_name}*\n\n"

        response += f"🛒 *Flipkart*: {flipkart_result}\n"
        response += f"📦 *Amazon*: {amazon_result}\n"

        # Note
        response += "\n_Note: Results may vary, prices are live._"

        await update.message.reply_text(response, parse_mode="Markdown")

    async def get_flipkart_price(self, product_name: str) -> str:
        url = f"https://www.flipkart.com/search?q={quote_plus(product_name)}"
        result = self.fetcher.search_flipkart(product_name)
        if result:
            img = f"\n[Image]({result['image_url']})" if result.get('image_url') else ""
            return f"{result['product_name']} - {result['price']} (Link: {url}){img}"
        return f"Not available (Link: {url})"

    async def get_amazon_price(self, product_name: str) -> str:
        url = f"https://www.amazon.in/s?k={quote_plus(product_name)}"
        result = self.fetcher.search_amazon(product_name)
        if result:
            img = f"\n[Image]({result['image_url']})" if result.get('image_url') else ""
            return f"{result['product_name']} - {result['price']} (Link: {url}){img}"
        return f"Not available (Link: {url})"

    async def run_webhook(self):
        # Run as webhook if BOT_WEBHOOK_URL is provided
        port = int(os.getenv("PORT", 8080))
        url_path = self.token
        await self.application.start()
        await self.application.bot.set_webhook(url=f"{BOT_WEBHOOK_URL}/{url_path}")
        await self.application.updater.start_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=url_path,
            webhook_url=f"{BOT_WEBHOOK_URL}/{url_path}",
        )
        await self.application.updater.idle()

    def run(self):
        if BOT_WEBHOOK_URL:
            asyncio.run(self.run_webhook())
        else:
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Start health check server
    threading.Thread(target=start_http_server, daemon=True).start()

    bot = PriceBot()
    bot.run()
