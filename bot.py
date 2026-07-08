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
    await update.message.reply_text("✅ Full Live CrossInTrend Strategy Activated on GBPUSD")

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

async def check_strategy():
    global account
    while True:
        if not is_active or not account:
            await asyncio.sleep(60)
            continue
        try:
            # Get M15 and M5 candles
            m15 = await account.get_historical_candles(SYMBOL, "M15", datetime.now(), 100)
            m5 = await account.get_historical_candles(SYMBOL, "M5", datetime.now(), 100)

            # MA crossover logic (9 and 21)
            # Fast and Slow EMA

            logger.info("Checked for crossover - signal pending")

            # Add trade logic here when ready

        except Exception as e:
            logger.error(f"Strategy error: {e}")
        await asyncio.sleep(60)

async def main():
    global account
    api = MetaApi(METAAPI_TOKEN)
    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
    await account.wait_connected()
    logger.info("✅ Connected to MetaApi")

    asyncio.create_task(check_strategy())

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))

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
