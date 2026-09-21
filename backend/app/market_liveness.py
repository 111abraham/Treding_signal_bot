import datetime
import logging
from typing import Dict, Any, Optional, Tuple
import pandas as pd
from app.mt5_bridge import mt5_bridge, MT5_AVAILABLE

if MT5_AVAILABLE:
    import MetaTrader5 as mt5
else:
    mt5 = None

logger = logging.getLogger(__name__)


class MarketLivenessGuard:
    """
    Intelligent liveness and stagnation guard that verifies whether an asset's market
    is actively open and quoting live price action on the active broker.
    
    Guards against:
    1. Broker-disabled symbols (MT5 trade_mode DISABLED or CLOSEONLY).
    2. Broker quote freezes (stale tick stream on weekend or bank holidays).
    3. Stale candle feeds (historical data not advancing).
    4. Zero-volatility flatlines (frozen bid/ask quotes).
    5. Standard weekend market closure (Forex, Metals, Indices).
    """

    CRYPTO_BASE_SYMBOLS = {
        "BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX", "DOT", "MATIC", "LINK", "LTC"
    }

    MAX_CANDLE_AGE_SECONDS = {
        "1m": 600,       # 10 mins
        "5m": 1500,      # 25 mins
        "15m": 3000,     # 50 mins
        "30m": 6000,     # 100 mins
        "1h": 10800,     # 3 hours
        "4h": 36000,     # 10 hours
        "1d": 172800,    # 48 hours
    }

    @staticmethod
    def is_crypto_symbol(symbol: str) -> bool:
        """Determines if the symbol belongs to cryptocurrency asset class."""
        clean = symbol.upper().replace("/", "").replace("-", "").replace(".RAW", "").replace(".PRO", "")
        for base in MarketLivenessGuard.CRYPTO_BASE_SYMBOLS:
            if clean.startswith(base) or base in clean:
                return True
        return False

    @staticmethod
    def is_weekend_closure_active(symbol: str, dt_utc: Optional[datetime.datetime] = None) -> Tuple[bool, str]:
        """
        Checks standard weekend closure (Friday 21:00 UTC to Sunday 21:00 UTC).
        Crypto trades 24/7 globally, but non-crypto assets (Forex, Metals, Indices) are closed.
        """
        now = dt_utc or datetime.datetime.now(datetime.timezone.utc)
        weekday = now.weekday()  # Monday is 0, Sunday is 6, Friday is 4, Saturday is 5
        hour = now.hour + now.minute / 60.0

        # Friday post-market close (21:00 UTC onwards)
        if weekday == 4 and hour >= 21.0:
            if not MarketLivenessGuard.is_crypto_symbol(symbol):
                return True, "Weekend Market Closure (Friday post 21:00 UTC)"

        # Saturday (All day)
        if weekday == 5:
            if not MarketLivenessGuard.is_crypto_symbol(symbol):
                return True, "Weekend Market Closure (Saturday)"

        # Sunday pre-market open (Before 21:00 UTC)
        if weekday == 6 and hour < 21.0:
            if not MarketLivenessGuard.is_crypto_symbol(symbol):
                return True, "Weekend Market Closure (Sunday pre 21:00 UTC)"

        return False, ""

    @staticmethod
    def check_broker_direct_liveness(symbol: str) -> Dict[str, Any]:
        """
        Queries MetaTrader 5 directly for live broker trade permission, tick freshness, and spread sanity.
        Returns:
            dict with {is_active: bool, reason: str, trade_mode: str, tick_age_sec: Optional[float]}
        """
        if not mt5_bridge.is_connected or mt5 is None:
            return {
                "is_active": True,
                "reason": "MT5 not connected (fallback to candle feed inspection)",
                "trade_mode": "UNKNOWN",
                "tick_age_sec": None
            }

        broker_sym = mt5_bridge._resolve_broker_symbol(symbol)
        if not broker_sym:
            return {
                "is_active": False,
                "reason": f"Symbol '{symbol}' not recognized by broker terminal",
                "trade_mode": "NOT_FOUND",
                "tick_age_sec": None
            }

        try:
            sym_info = mt5.symbol_info(broker_sym)
            if sym_info is None:
                return {
                    "is_active": False,
                    "reason": f"Failed to retrieve symbol_info from broker for '{broker_sym}'",
                    "trade_mode": "NOT_FOUND",
                    "tick_age_sec": None
                }

            # 1. Inspect Broker Trade Permission Mode
            trade_mode = getattr(sym_info, "trade_mode", None)
            # SYMBOL_TRADE_MODE_DISABLED = 0
            # SYMBOL_TRADE_MODE_LONGONLY = 1
            # SYMBOL_TRADE_MODE_SHORTONLY = 2
            # SYMBOL_TRADE_MODE_CLOSEONLY = 3
            # SYMBOL_TRADE_MODE_FULL = 4
            if trade_mode == 0:  # DISABLED
                return {
                    "is_active": False,
                    "reason": f"Broker disabled trading for '{broker_sym}' (TRADE_MODE_DISABLED)",
                    "trade_mode": "DISABLED",
                    "tick_age_sec": None
                }
            elif trade_mode == 3:  # CLOSEONLY
                return {
                    "is_active": False,
                    "reason": f"Broker set '{broker_sym}' to close-only (TRADE_MODE_CLOSEONLY)",
                    "trade_mode": "CLOSEONLY",
                    "tick_age_sec": None
                }

            # 2. Inspect Live Tick Quotes
            tick = mt5.symbol_info_tick(broker_sym)
            if tick is None or getattr(tick, "bid", 0) <= 0 or getattr(tick, "ask", 0) <= 0:
                return {
                    "is_active": False,
                    "reason": f"Broker has no live bid/ask quotes for '{broker_sym}'",
                    "trade_mode": "FULL" if trade_mode == 4 else str(trade_mode),
                    "tick_age_sec": None
                }

            # 3. Inspect Tick Freshness (Quote Streaming)
            now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
            tick_time = getattr(tick, "time", 0)
            tick_age = max(0, now_ts - tick_time)

            # Max allowed tick staleness: 900 seconds (15 mins) for liquid assets
            # If tick is hours or days old, broker market is definitely closed / quote stream halted
            if tick_age > 900:
                age_mins = int(tick_age // 60)
                return {
                    "is_active": False,
                    "reason": f"Broker quotes frozen (last tick was {age_mins} mins ago)",
                    "trade_mode": "FULL" if trade_mode == 4 else str(trade_mode),
                    "tick_age_sec": round(tick_age, 1)
                }

            # 4. Spread Sanity Check
            bid = float(tick.bid)
            ask = float(tick.ask)
            if ask <= bid:
                return {
                    "is_active": False,
                    "reason": f"Broker spread invalid (Ask {ask} <= Bid {bid})",
                    "trade_mode": "FULL",
                    "tick_age_sec": round(tick_age, 1)
                }

            return {
                "is_active": True,
                "reason": "Broker trading active & quoting live",
                "trade_mode": "FULL",
                "tick_age_sec": round(tick_age, 1)
            }

        except Exception as e:
            logger.debug(f"Error checking MT5 direct liveness for {symbol}: {e}")
            return {
                "is_active": True,
                "reason": f"MT5 liveness check exception: {e}",
                "trade_mode": "EXCEPTION",
                "tick_age_sec": None
            }

    @staticmethod
    def check_candle_freshness(df: pd.DataFrame, timeframe: str = "1h") -> Tuple[bool, str, Optional[float]]:
        """
        Inspects the timestamp of the latest candle in df and detects flatlines/stagnation.
        Returns:
            (is_fresh: bool, reason: str, age_seconds: Optional[float])
        """
        if df is None or df.empty or len(df) < 5:
            return False, "Insufficient candle data to determine liveness", None

        # Standardize Time column
        time_col = "Time" if "Time" in df.columns else df.columns[0]
        try:
            last_time_val = df[time_col].iloc[-1]
            if isinstance(last_time_val, (int, float)):
                last_dt = datetime.datetime.fromtimestamp(last_time_val, datetime.timezone.utc)
            else:
                last_dt = pd.to_datetime(last_time_val)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.tz_localize(datetime.timezone.utc)
                else:
                    last_dt = last_dt.tz_convert(datetime.timezone.utc)

            now_utc = datetime.datetime.now(datetime.timezone.utc)
            age_sec = (now_utc - last_dt).total_seconds()

            max_allowed = MarketLivenessGuard.MAX_CANDLE_AGE_SECONDS.get(timeframe.lower(), 10800)
            if age_sec > max_allowed:
                age_hrs = round(age_sec / 3600, 1)
                return False, f"Stale candle feed: latest {timeframe} bar is {age_hrs} hours old", age_sec

        except Exception as ex:
            logger.debug(f"Error parsing candle timestamp freshness: {ex}")

        # Flatline / Zero Volatility Detection
        # If the last 3 candles have High == Low or Close doesn't change, feed is dead
        try:
            tail_3 = df.tail(3)
            highs = tail_3["High"].values
            lows = tail_3["Low"].values
            closes = tail_3["Close"].values

            # All 3 bars have zero candle range
            if all(highs[i] == lows[i] for i in range(len(tail_3))):
                return False, "Zero volatility flatline: High == Low across last 3 bars", None

            # Or Close has zero change and High == Low on last 2 bars
            if len(tail_3) >= 2 and highs[-1] == lows[-1] and closes[-1] == closes[-2]:
                return False, "Market frozen: zero price change on recent bars", None

        except Exception as ex_flat:
            logger.debug(f"Error in flatline detection: {ex_flat}")

        return True, "Candle feed is fresh and active", None

    @classmethod
    def check_liveness(
        cls,
        symbol: str,
        timeframe: str = "1h",
        df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Unified multi-layer market liveness evaluation.
        Evaluates Broker Direct state -> Weekend Calendar -> Candle Freshness.
        """
        clean_sym = symbol.upper().replace("/", "").replace("-", "")

        # 1. Standard Weekend Closure Check (Non-Crypto)
        is_weekend, weekend_reason = cls.is_weekend_closure_active(clean_sym)
        if is_weekend:
            return {
                "symbol": clean_sym,
                "timeframe": timeframe,
                "is_open": False,
                "reason": weekend_reason,
                "source": "Calendar Weekend Guard"
            }

        # 2. Broker Direct Check (MT5 Connection)
        broker_res = cls.check_broker_direct_liveness(clean_sym)
        if not broker_res["is_active"]:
            return {
                "symbol": clean_sym,
                "timeframe": timeframe,
                "is_open": False,
                "reason": broker_res["reason"],
                "trade_mode": broker_res.get("trade_mode"),
                "tick_age_sec": broker_res.get("tick_age_sec"),
                "source": "Broker Direct MT5"
            }

        # 3. Candle Feed Freshness & Flatline Check
        if df is not None and not df.empty:
            is_fresh, candle_reason, age_sec = cls.check_candle_freshness(df, timeframe)
            if not is_fresh:
                return {
                    "symbol": clean_sym,
                    "timeframe": timeframe,
                    "is_open": False,
                    "reason": candle_reason,
                    "candle_age_sec": age_sec,
                    "source": "Candle Feed Inspection"
                }

        # Market is confirmed Open and actively trading
        return {
            "symbol": clean_sym,
            "timeframe": timeframe,
            "is_open": True,
            "reason": "Market is live and actively trading",
            "source": "Unified Liveness Guard"
        }


# Global singleton instance
market_liveness = MarketLivenessGuard()
