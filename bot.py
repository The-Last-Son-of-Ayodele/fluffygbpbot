import os
import asyncio
import logging
from metaapi_cloud_sdk import MetaApi
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# =========================
# Logging
# =========================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================
# Environment Variables
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

# =========================
# Global Variables
# =========================
account = None
connection = None
is_active = False


# =========================
# Telegram Commands
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_active

    is_active = True
    await update.message.reply_text(
        "✅ CrossInTrend Bot Started\n"
        "Monitoring market..."
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_active

    is_active = False
    await update.message.reply_text("⛔ Bot Stopped")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global connection

    try:
        if connection is None:
            await update.message.reply_text("❌ MetaApi not connected.")
            return

        account_info = await connection.get_account_information()
        positions = await connection.get_positions()

        message = (
            "📈 CrossInTrend Bot Status\n\n"
            f"💰 Balance: ${account_info['balance']:.2f}\n"
            f"📊 Equity: ${account_info['equity']:.2f}\n"
            f"🛡 Free Margin: ${account_info['freeMargin']:.2f}\n"
            f"📌 Open Positions: {len(positions)}\n"
            f"🤖 Trading: {'ON' if is_active else 'OFF'}"
        )

        await update.message.reply_text(message)

    except Exception as e:
        logger.exception(e)
        await update.message.reply_text(f"❌ Error:\n{e}")


# =========================
# MetaApi Connection
# =========================
async def connect_metaapi():
    global account, connection

    api = MetaApi(METAAPI_TOKEN)

    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)

    if account.state != "DEPLOYED":
        logger.info("Deploying account...")
        await account.deploy()

    logger.info("Waiting for broker connection...")
    await account.wait_connected()

    connection = account.get_rpc_connection()

    await connection.connect()
    await connection.wait_synchronized()

    logger.info("✅ MetaApi Connected Successfully")


# =========================
# Main
# =========================
async def main():

    await connect_metaapi()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))

    logger.info("🤖 Telegram Bot Started")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Keep bot alive
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
