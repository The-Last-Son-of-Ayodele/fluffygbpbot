import os
import asyncio
import logging
from metaapi_cloud_sdk import MetaApi
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
SYMBOL = "GBPUSD"
LOT_SIZE = 0.10

# Global
account = None
is_active = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_active
    is_active = True
    await update.message.reply_text("✅ CrossInTrend Bot Started on GBPUSD")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_active
    is_active = False
    await update.message.reply_text("⛔ Bot Stopped")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        balance = await account.get_balance()
        positions = await account.get_positions()
        await update.message.reply_text(f"💰 Balance: ${balance:.2f}\n📊 Positions: {len(positions)}")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def main():
    global account
    try:
        api = MetaApi(METAAPI_TOKEN)
        account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
        await account.wait_connected()
        logger.info("✅ Successfully connected to MetaApi")
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Keep alive
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
