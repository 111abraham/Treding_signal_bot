import os
import sys
import logging
from typing import Dict, Any, Optional, List
import datetime

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


# Global MT5 bridge singleton
mt5_bridge = MT5Bridge()
