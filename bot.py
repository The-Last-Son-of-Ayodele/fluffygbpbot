import os
import asyncio
import logging
from metaapi_cloud_sdk import MetaApi
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

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

        # Get account info safely
        try:
            info = await account.get_account_information()
            balance = getattr(info, 'balance', 'N/A')
        except:
            balance = 'N/A'

        # Get positions safely
        try:
            positions = await account.get_positions()
            pos_count = len(positions)
        except:
            pos_count = 'N/A'

        await update.message.reply_text(f"Balance: ${balance}\nPositions: {pos_count}")
    except Exception as e:
        await update.message.reply_text(f"Status error: {str(e)[:120]}")

async def main():
    global account
    while True:
        try:
            if account is None:
                api = MetaApi(METAAPI_TOKEN)
                account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
                await account.wait_connected()
                logger.info("✅ Reconnected to MetaApi")
            
            # Keep connection alive
            await account.get_account_information()
            
        except Exception as e:
            logger.error(f"Reconnect error: {e}")
            account = None
            await asyncio.sleep(10)
            # Keep alive for Railway
