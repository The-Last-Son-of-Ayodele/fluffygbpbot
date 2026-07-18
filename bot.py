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
from dotenv import load_dotenv
import strategy

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
SYMBOL = "GBPUSDm"
LOT = 0.10

account = None
is_active = False

m5_builder = strategy.CandleBuilder(timeframe_minutes=5)
m15_builder = strategy.CandleBuilder(timeframe_minutes=15)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_active
    is_active = True
    await update.message.reply_text("✅ Strategy Activated on GBPUSD")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_active
    is_active = False
    await update.message.reply_text("⛔ Strategy Stopped")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if account:
            m5_count = len(m5_builder.closed_candles())
            m15_count = len(m15_builder.closed_candles())
            await update.message.reply_text(
                "✅ Connected.\nTrading: " + ("Active" if is_active else "Paused") +
                f"\nCandles built - M5: {m5_count}, M15: {m15_count}"
            )
        else:
            await update.message.reply_text("Not connected.")
    except:
        await update.message.reply_text("Bot is running.")

async def test_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if account:
            await account.create_market_buy(SYMBOL, LOT)
            await update.message.reply_text("🟢 Test BUY placed on GBPUSD")
        else:
            await update.message.reply_text("Not connected.")
    except Exception as e:
        await update.message.reply_text(f"Test BUY failed: {str(e)}")

async def test_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if account:
            await account.create_market_sell(SYMBOL, LOT)
            await update.message.reply_text("🔴 Test SELL placed on GBPUSD")
        else:
            await update.message.reply_text("Not connected.")
    except Exception as e:
        await update.message.reply_text(f"Test SELL failed: {str(e)}")


async def price_feed_loop(connection):
    while True:
        try:
            price = await connection.get_symbol_price(symbol=SYMBOL)
            mid = (price['bid'] + price['ask']) / 2
            m5_builder.add_price(mid)
            m15_builder.add_price(mid)
        except Exception as e:
            logger.error(f"Price feed error: {e}")
        await asyncio.sleep(10)


async def strategy_loop(connection):
    last_entry_bar = None
    last_exit_bar = None

    while True:
        try:
            if is_active and account:
                exit_candles = m5_builder.closed_candles()
                if exit_candles:
                    m5_time = exit_candles[-1]['time']
                    if m5_time != last_exit_bar:
                        last_exit_bar = m5_time
                        exit_closes = [c['close'] for c in exit_candles]
                        positions = await connection.get_positions()
                        my_pos = next((p for p in positions if p['symbol'] == SYMBOL), None)
                        if my_pos:
                            if my_pos['type'] == 'POSITION_TYPE_SELL' and \
                               strategy.check_cross(exit_closes) and strategy.is_downtrend(exit_closes):
                                await connection.close_position(position_id=my_pos['id'])
                                logger.info("Closed SELL on M5 downtrend cross")
                            elif my_pos['type'] == 'POSITION_TYPE_BUY' and \
                                 strategy.check_cross(exit_closes) and strategy.is_uptrend(exit_closes):
                                await connection.close_position(position_id=my_pos['id'])
                                logger.info("Closed BUY on M5 uptrend cross")

                entry_candles = m15_builder.closed_candles()
                if entry_candles:
                    m15_time = entry_candles[-1]['time']
                    if m15_time != last_entry_bar:
                        last_entry_bar = m15_time
                        entry_closes = [c['close'] for c in entry_candles]
                        positions = await connection.get_positions()
                        my_pos = next((p for p in positions if p['symbol'] == SYMBOL), None)
                        if not my_pos:
                            if len(entry_candles) < strategy.ADX_PERIOD * 2 + 1:
                                logger.info(
                                    f"Warming up - {len(entry_candles)} M15 candles built so far, "
                                    f"need {strategy.ADX_PERIOD * 2 + 1}"
                                )
                            elif not strategy.is_trending_market(entry_candles):
                                logger.info("Skipping entry - market ranging (ADX filter)")
                            elif strategy.check_cross(entry_closes):
                                if strategy.is_uptrend(entry_closes):
                                    await connection.create_market_sell_order(symbol=SYMBOL, volume=LOT)
                                    logger.info("Opened SELL on M15 uptrend cross")
                                elif strategy.is_downtrend(entry_closes):
                                    await connection.create_market_buy_order(symbol=SYMBOL, volume=LOT)
                                    logger.info("Opened BUY on M15 downtrend cross")
        except Exception as e:
            logger.error(f"Strategy loop error: {e}")

        await asyncio.sleep(30)


async def main():
    global account
    api = MetaApi(METAAPI_TOKEN)
    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
    await account.wait_connected()
    logger.info("✅ Connected to MetaApi")

    connection = account.get_rpc_connection()
    await connection.connect()
    await connection.wait_synchronized()
    logger.info("✅ RPC connection synchronized")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("test_buy", test_buy))
    app.add_handler(CommandHandler("test_sell", test_sell))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    asyncio.create_task(price_feed_loop(connection))
    asyncio.create_task(strategy_loop(connection))

    while True:
        await asyncio.sleep(60)

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
