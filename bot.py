import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

# Initialize bot
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("Please set the TELEGRAM_BOT_TOKEN environment variable")

# Initialize application
application = Application.builder().token(BOT_TOKEN).build()

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Hi! I can help you compare prices across Indian e-commerce stores.\n'
        'Just send me the product name you want to search for!'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        'Send me the name of the product you want to search for.\n'
        'For example: "iPhone 14 Pro Max"\n\n'
        'I can search across multiple Indian e-commerce stores:\n'
        '- Flipkart\n'
        '- Amazon\n'
        '- Others (coming soon)'
    )

# Message handler
from price_fetcher import PriceFetcher

# Initialize price fetcher
price_fetcher = PriceFetcher()

async def search_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle product search requests."""
    query = update.message.text
    
    # Show loading message
    await update.message.reply_text(f"🔍 Searching for '{query}' across stores...")
    
    try:
        # Get price information from all stores
        results = price_fetcher.search_all(query)
        
        if not results:
            await update.message.reply_text("❌ No results found for your search.")
            return
            
        # Format results
        response = "Here are the prices I found:\n\n"
        for result in results:
            response += f"• {result['store']}\n"
            response += f"  Product: {result['product_name']}\n"
            response += f"  Price: {result['price']}\n"
            response += f"  Link: {result['url']}\n\n"
            
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error occurred: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    print(f"Update {update} caused error {context.error}")

async def main() -> None:
    """Run the bot."""
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_product))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
