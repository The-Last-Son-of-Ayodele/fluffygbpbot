
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

TOKEN = os.getenv("TELEGRAM_TOKEN")
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
PORT = int(os.getenv("PORT", 8000))

account = None
connection = None  # RPC connection - required for get_account_information/get_positions
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
    if not connection:
        await update.message.reply_text("Not connected.")
        return

    try:
        info = await connection.get_account_information()
        # info is a dict, not an object - use dict access
        balance = info.get('balance', 'N/A')
    except Exception as e:
        logger.error(f"get_account_information failed: {e}")
        balance = 'N/A'

    try:
        positions = await connection.get_positions()
        pos_count = len(positions)
    except Exception as e:
        logger.error(f"get_positions failed: {e}")
        pos_count = 'N/A'

    await update.message.reply_text(f"Balance: ${balance}\nPositions: {pos_count}")

async def main():
    global account, connection
    try:
        api = MetaApi(METAAPI_TOKEN)
        account = await api.metatrader_account_api.get_account(ACCOUNT_ID)

        # Make sure the MetaTrader terminal is deployed and running
        if account.state not in ('DEPLOYING', 'DEPLOYED'):
            logger.info("Deploying account...")
            await account.deploy()

        logger.info("Waiting for broker connection...")
        await account.wait_connected()

        # This is the missing piece: get_account_information() and
        # get_positions() live on the RPC connection, not on `account`.
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()

        logger.info("✅ Connected to MetaApi (RPC)")
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

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, stop_event.set)
        loop.add_signal_handler(signal.SIGINT, stop_event.set)
    except NotImplementedError:
        pass  # Windows fallback, not relevant on Railway

    await stop_event.wait()

    logger.info("Shutting down...")
    await app.updater.stop()
    await app.stop()
    await app.shutdown()

# Health check server
class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # silence noisy access logs

def run_health_server():
    with socketserver.TCPServer(("", PORT), HealthHandler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    asyncio.run(main())
