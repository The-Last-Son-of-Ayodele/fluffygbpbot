import os
import asyncio
import logging
import signal
import http.server
import socketserver
import threading
from datetime import datetime
from metaapi_cloud_sdk import MetaApi
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
SYMBOL = "GBPUSD"
LOT = 0.10

account = None
is_active = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_active
    is_active = True
    await update.message.reply_text("✅ Strategy Activated")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_active
    is_active = False
    await update.message.reply_text("⛔ Strategy Stopped")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if account:
            await update.message.reply_text("✅ Connected.\nTrading: " + ("Active" if is_active else "Paused"))
        else:
            await update.message.reply_text("Not connected.")
    except:
        await update.message.reply_text("Bot is running.")

async def test_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if account:
            await account.create_market_buy(SYMBOL, LOT)
            await update.message.reply_text("🟢 Test BUY order placed on GBPUSD")
        else:
            await update.message.reply_text("Not connected.")
    except Exception as e:
        await update.message.reply_text(f"Test BUY failed: {str(e)}")

async def test_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if account:
            await account.create_market_sell(SYMBOL, LOT)
            await update.message.reply_text("🔴 Test SELL order placed on GBPUSD")
        else:
            await update.message.reply_text("Not connected.")
    except Exception as e:
        await update.message.reply_text(f"Test SELL failed: {str(e)}")

async def main():
    global account
    api = MetaApi(METAAPI_TOKEN)
    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
    await account.wait_connected()
    logger.info("✅ Connected to MetaApi")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("test_buy", test_buy))
    app.add_handler(CommandHandler("test_sell", test_sell))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(60)

# Health check
class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_health_server():
    with socketserver.TCPServer(("", 8000), HealthHandler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda s, f: asyncio.get_event_loop().stop())
    asyncio.run(main())
