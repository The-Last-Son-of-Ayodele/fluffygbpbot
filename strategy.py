"""
CrossInTrend strategy logic, ported from the MQL5 EA.

Entry (M15): when 9/21 EMA cross AND market is trending (ADX filter passes)
  - Uptrend cross  -> SELL
  - Downtrend cross -> BUY
Exit (M5): when 9/21 EMA cross in the opposite direction of the open position

Candles are built locally from live polled prices (see CandleBuilder) because
MetaApi's get_historical_candles REST endpoint only works on legacy G1
infrastructure and returns a 500 error on G2 MT5 accounts.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

FAST_PERIOD = 9
SLOW_PERIOD = 21
ADX_PERIOD = 14
ADX_MIN_TREND = 22.0


def ema_series(values, period):
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    series = [sum(values[:period]) / period]
    for price in values[period:]:
        series.append(price * k + series[-1] * (1 - k))
    return series


def check_cross(closes, fast_period=FAST_PERIOD, slow_period=SLOW_PERIOD):
    fast = ema_series(closes, fast_period)
    slow = ema_series(closes, slow_period)
    if len(fast) < 2 or len(slow) < 2:
        return False
    f0, f1 = fast[-1], fast[-2]
    s0, s1 = slow[-1], slow[-2]
    return (f1 - s1) * (f0 - s0) < 0.0


def is_uptrend(closes, slow_period=SLOW_PERIOD):
    s = ema_series(closes, slow_period)
    if len(s) < 2:
        return False
    return s[-1] > s[-2] and closes[-1] > s[-1]


def is_downtrend(closes, slow_period=SLOW_PERIOD):
    s = ema_series(closes, slow_period)
    if len(s) < 2:
        return False
    return s[-1] < s[-2] and closes[-1] < s[-1]


def _true_range(high, low, prev_close):
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def _wilder_smooth(values, period):
    if len(values) < period:
        return []
    smoothed = [sum(values[:period])]
    for v in values[period:]:
        smoothed.append(smoothed[-1] - (smoothed[-1] / period) + v)
    return smoothed


def calculate_adx(candles, period=ADX_PERIOD):
    if len(candles) < period * 2 + 1:
        return None

    highs = [c['high'] for c in candles]
    lows = [c['low'] for c in candles]
    closes = [c['close'] for c in candles]

    trs, plus_dm, minus_dm = [], [], []
    for i in range(1, len(candles)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
        trs.append(_true_range(highs[i], lows[i], closes[i - 1]))

    tr_s = _wilder_smooth(trs, period)
    pdm_s = _wilder_smooth(plus_dm, period)
    mdm_s = _wilder_smooth(minus_dm, period)

    if not tr_s or not pdm_s or not mdm_s:
        return None

    plus_di = [100 * (p / t) if t else 0.0 for p, t in zip(pdm_s, tr_s)]
    minus_di = [100 * (m / t) if t else 0.0 for m, t in zip(mdm_s, tr_s)]
    dx = [100 * abs(p - m) / (p + m) if (p + m) else 0.0 for p, m in zip(plus_di, minus_di)]

    if len(dx) < period:
        return None

    adx = sum(dx[:period]) / period
    for d in dx[period:]:
        adx = ((adx * (period - 1)) + d) / period

    return adx


def is_trending_market(candles, adx_min=ADX_MIN_TREND):
    adx = calculate_adx(candles)
    if adx is None:
        return False
    return adx >= adx_min


class CandleBuilder:
    def __init__(self, timeframe_minutes, max_candles=150):
        self.timeframe_minutes = timeframe_minutes
        self.max_candles = max_candles
        self.candles = []
        self.current = None

    def _bucket_start(self, dt):
        minute = (dt.minute // self.timeframe_minutes) * self.timeframe_minutes
        return dt.replace(minute=minute, second=0, microsecond=0)

    def add_price(self, price, dt=None):
        dt = dt or datetime.now(timezone.utc)
        bucket = self._bucket_start(dt)

        if self.current is None:
            self.current = {'time': bucket, 'open': price, 'high': price, 'low': price, 'close': price}
        elif bucket == self.current['time']:
            self.current['high'] = max(self.current['high'], price)
            self.current['low'] = min(self.current['low'], price)
            self.current['close'] = price
        else:
            self.candles.append(self.current)
            if len(self.candles) > self.max_candles:
                self.candles.pop(0)
            self.current = {'time': bucket, 'open': price, 'high': price, 'low': price, 'close': price}

    def closed_candles(self):
        return list(self.candles)

    def latest_closed_time(self):
        return self.candles[-1]['time'] if self.candles else None
