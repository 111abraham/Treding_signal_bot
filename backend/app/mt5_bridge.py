import os
import sys
import logging
from typing import Dict, Any, Optional, List
import datetime
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False


class MT5Bridge:
    """
    Direct bridge to MetaTrader 5 terminal for FundedNext and other prop firm accounts.
    Pulls live ticking Bid/Ask quotes, exact floating broker spreads, and account telemetry.
    """

    def __init__(self):
        self.is_connected = False
        self.terminal_info: Dict[str, Any] = {}
        self.account_info: Dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self._symbol_cache: Dict[str, str] = {}  # Maps standard symbol e.g. EURUSD -> broker symbol e.g. EURUSD.raw

    def initialize(self, path: Optional[str] = None) -> bool:
        """Initializes connection to local MT5 terminal."""
        if not MT5_AVAILABLE:
            self.last_error = "MetaTrader5 Python library is not installed."
            logger.warning(self.last_error)
            return False

        try:
            init_kwargs = {}
            if path and os.path.exists(path):
                init_kwargs["path"] = path

            # Attempt to connect to running or default MT5 terminal
            if not mt5.initialize(**init_kwargs):
                err = mt5.last_error()
                self.last_error = f"MT5 initialize failed: {err}"
                self.is_connected = False
                logger.info(f"MT5 terminal not detected: {self.last_error}")
                return False

            term = mt5.terminal_info()
            acc = mt5.account_info()

            if term is not None:
                self.terminal_info = {
                    "name": term.name,
                    "company": term.company,
                    "path": term.path,
                    "connected": term.connected,
                    "trade_allowed": term.trade_allowed
                }

            if acc is not None:
                self.account_info = {
                    "login": acc.login,
                    "server": acc.server,
                    "name": acc.name,
                    "balance": acc.balance,
                    "equity": acc.equity,
                    "currency": acc.currency,
                    "leverage": acc.leverage
                }

            self.is_connected = True
            self.last_error = None
            logger.info(f"Connected to MT5 ({self.account_info.get('server', 'Demo')}) - Account: {self.account_info.get('login', 'N/A')}")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"MT5 bridge initialization exception: {e}")
            return False

    def shutdown(self):
        """Disconnects from MT5 terminal."""
        if MT5_AVAILABLE and self.is_connected:
            try:
                mt5.shutdown()
            except Exception:
                pass
        self.is_connected = False

    def get_status(self) -> Dict[str, Any]:
        """Returns connection and account status."""
        if not self.is_connected:
            # Try auto-connecting once if terminal is open
            self.initialize()

        return {
            "is_available": MT5_AVAILABLE,
            "is_connected": self.is_connected,
            "account": self.account_info,
            "terminal": self.terminal_info,
            "last_error": self.last_error
        }

    def _resolve_broker_symbol(self, standard_symbol: str) -> Optional[str]:
        """
        Resolves standard ticker (e.g. 'EURUSD', 'XAUUSD', 'US30') to broker's exact symbol name.
        FundedNext or other brokers sometimes append suffixes like '.pro', '.raw', or use 'GOLD' for XAUUSD.
        """
        if not self.is_connected:
            return None

        clean_sym = standard_symbol.upper().replace("/", "").replace("-", "")

        if clean_sym in self._symbol_cache:
            return self._symbol_cache[clean_sym]

        # Check direct match
        info = mt5.symbol_info(clean_sym)
        if info is not None:
            self._symbol_cache[clean_sym] = clean_sym
            mt5.symbol_select(clean_sym, True)
            return clean_sym

        # Common aliases & broker suffix searches
        alias_candidates = [
            clean_sym,
            clean_sym + ".raw",
            clean_sym + ".pro",
            clean_sym + ".f",
            clean_sym + "m"
        ]

        # Specific commodity & index aliases
        if clean_sym in ["XAUUSD", "GOLD"]:
            alias_candidates.extend(["GOLD", "XAUUSD", "XAUUSD.raw", "GOLD.pro"])
        elif clean_sym in ["XAGUSD", "SILVER"]:
            alias_candidates.extend(["SILVER", "XAGUSD", "XAGUSD.raw"])
        elif clean_sym in ["US30", "DJI", "WS30"]:
            alias_candidates.extend(["US30", "US30.cash", "DJ30", "WALLSTREET30"])
        elif clean_sym in ["SPX500", "US500", "SP500"]:
            alias_candidates.extend(["US500", "SPX500", "SP500.cash"])
        elif clean_sym in ["NAS100", "US100", "NDX"]:
            alias_candidates.extend(["US100", "NAS100", "USTEC", "NAS100.cash"])

        for cand in alias_candidates:
            cand_info = mt5.symbol_info(cand)
            if cand_info is not None:
                self._symbol_cache[clean_sym] = cand
                mt5.symbol_select(cand, True)
                return cand

        # Fallback: scan all available symbols in terminal
        all_symbols = mt5.symbols_get()
        if all_symbols:
            for s in all_symbols:
                if clean_sym in s.name.upper():
                    self._symbol_cache[clean_sym] = s.name
                    mt5.symbol_select(s.name, True)
                    return s.name

        return None

    def get_live_spread(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves real-time live ticking Bid/Ask quotes and exact floating spread
        directly from FundedNext's MT5 server.
        """
        if not self.is_connected:
            return None

        broker_sym = self._resolve_broker_symbol(symbol)
        if not broker_sym:
            return None

        try:
            tick = mt5.symbol_info_tick(broker_sym)
            sym_info = mt5.symbol_info(broker_sym)

            if tick is None or sym_info is None:
                return None

            bid = float(tick.bid)
            ask = float(tick.ask)
            if ask <= 0 or bid <= 0:
                return None

            point = float(sym_info.point) if sym_info.point > 0 else 0.00001
            digits = int(sym_info.digits)
            spread_value = round(ask - bid, digits)
            spread_points = int(round(spread_value / point)) if point > 0 else int(sym_info.spread)
            spread_pct = round((spread_value / ask) * 100, 5)

            return {
                "symbol": symbol,
                "broker_symbol": broker_sym,
                "bid": bid,
                "ask": ask,
                "spread_value": spread_value,
                "spread_points": spread_points,
                "spread_pct": spread_pct,
                "digits": digits,
                "point": point,
                "time": datetime.datetime.fromtimestamp(tick.time, datetime.timezone.utc).strftime("%H:%M:%S UTC"),
                "is_live": True,
                "source": "FundedNext MT5 Live"
            }

        except Exception as e:
            logger.debug(f"Error fetching live tick for {symbol}: {e}")
            return None

    def get_candles_from_mt5(
        self,
        symbol: str,
        timeframe: str = "1h",
        count: int = 500
    ) -> Optional[pd.DataFrame]:
        """
        Fetches exact historical OHLCV candles directly from FundedNext's MT5 server.
        Takes ~0.03s and contains broker-accurate prices, wicks, and floating spreads.
        """
        if not self.is_connected:
            self.initialize()
        if not self.is_connected:
            return None

        tf_map = {
            "1m": mt5.TIMEFRAME_M1,
            "5m": mt5.TIMEFRAME_M5,
            "15m": mt5.TIMEFRAME_M15,
            "30m": mt5.TIMEFRAME_M30,
            "1h": mt5.TIMEFRAME_H1,
            "4h": mt5.TIMEFRAME_H4,
            "1d": mt5.TIMEFRAME_D1,
        }
        mt5_tf = tf_map.get(timeframe.lower(), mt5.TIMEFRAME_H1)
        broker_sym = self._resolve_broker_symbol(symbol)
        if not broker_sym:
            return None

        try:
            rates = mt5.copy_rates_from_pos(broker_sym, mt5_tf, 0, count)
            if rates is None or len(rates) == 0:
                mt5.symbol_select(broker_sym, True)
                rates = mt5.copy_rates_from_pos(broker_sym, mt5_tf, 0, count)

            if rates is None or len(rates) == 0:
                return None

            df = pd.DataFrame(rates)
            df['Time'] = pd.to_datetime(df['time'], unit='s')
            df['Open'] = df['open'].astype(float)
            df['High'] = df['high'].astype(float)
            df['Low'] = df['low'].astype(float)
            df['Close'] = df['close'].astype(float)
            df['Volume'] = df['tick_volume'].astype(float)
            if 'spread' in df.columns:
                df['SpreadPoints'] = df['spread']

            keep_cols = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
            if 'SpreadPoints' in df.columns:
                keep_cols.append('SpreadPoints')
            df = df[keep_cols]

            df.attrs["symbol"] = symbol
            df.attrs["data_source"] = "FundedNext MT5"
            return df

        except Exception as e:
            logger.error(f"Error fetching MT5 candles for {symbol} ({timeframe}): {e}")
            return None

    def sync_watchlist_from_mt5(self) -> List[Dict[str, Any]]:
        """
        Queries all symbols from FundedNext MT5 terminal and updates the watchlist in config.
        Classifies assets into Forex (48), Commodities (5), Indices (14), Crypto (9), and Stocks (20).
        """
        if not self.is_connected:
            self.initialize()
        if not self.is_connected:
            return []

        symbols = mt5.symbols_get()
        if not symbols:
            return []

        watchlist = []
        for s in symbols:
            folder = s.path.split('\\')[0] if hasattr(s, 'path') and s.path else 'General'
            if folder == 'Cryptocurrencies':
                category = 'Crypto'
            elif folder == 'Stock CFD':
                category = 'Stocks'
            elif folder in ['Forex', 'Commodities', 'Indices']:
                category = folder
            else:
                category = folder

            bid = float(s.bid) if s.bid else 1.0
            spread_val = float(s.spread * s.point) if s.point else 0.0001
            est_spread_pct = round((spread_val / max(0.0001, bid)) * 100, 4)
            est_spread_pct = max(0.005, min(0.5, est_spread_pct))

            watchlist.append({
                "symbol": s.name,
                "name": s.description if s.description else s.name,
                "category": category,
                "active": True,
                "est_spread_pct": est_spread_pct
            })

        cat_order = {"Forex": 1, "Commodities": 2, "Indices": 3, "Crypto": 4, "Stocks": 5}
        watchlist.sort(key=lambda item: (cat_order.get(item["category"], 99), item["symbol"]))

        from app.config import config_manager
        config_manager.update({"watchlist": watchlist})
        logger.info(f"Successfully synced {len(watchlist)} assets directly from FundedNext MT5!")
        return watchlist


# Global MT5 bridge singleton
mt5_bridge = MT5Bridge()
