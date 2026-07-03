import os
import asyncio
import logging
import signal
import http.server
import socketserver
import threading
from metaapi_cloud_sdk import MetaApi
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
TOKEN = os.getenv("TELEGRAM_TOKEN")
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
SYMBOL = "GBPUSD"

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
        if not account:
            await update.message.reply_text("Not connected to broker.")
            return

        info = await account.get_account_information()
        positions = await account.get_positions()
        balance = getattr(info, 'balance', 'N/A')
        await update.message.reply_text(f"Balance: ${balance}\nPositions: {len(positions)}")
    except Exception as e:
        logger.error(f"Status error: {e}")
        await update.message.reply_text(f"Error: {str(e)[:150]}")

async def main():
    global account
    try:
        api = MetaApi(METAAPI_TOKEN)
        account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
        await account.wait_connected()
        logger.info("✅ Connected to MetaApi")
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return

    # Telegram Bot
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

# Health check server for Railway
class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_health_server():
    with socketserver.TCPServer(("", 8000), HealthHandler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    # Start health check in background
    threading.Thread(target=run_health_server, daemon=True).start()
    # Handle graceful shutdown
    signal.signal(signal.SIGTERM, lambda s, f: asyncio.get_event_loop().stop())
    asyncio.run(main())
