import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "app_name": "AI Quant Trading Forecast Terminal",
    "version": "1.0.0",
    "timeframe": "1h",  # Active chart view default: '5m', '15m', '1h', '4h', '1d'
    "scan_timeframes": ["5m", "15m", "1h", "4h"],  # Timeframes scanned by automated engine
    "lookback_candles": 500,
    "forecast_candles": 5,
    "scan_interval_minutes": 15,
    "auto_scan_enabled": True,
    "strategy": {
        "max_spread_to_sl_ratio": 0.05,  # User rule: spread must be < 5% of (Entry - StopLoss)
        "require_london_ny_overlap": False,  # If True, only triggers during 13:00 - 16:30 UTC
        "highlight_session_overlap": True,
        "min_conviction": 65.0,  # Minimum confidence score % (0-100)
        "min_risk_reward": 1.5,
        "atr_sl_multiplier": 1.5,
        "atr_tp_multiplier": 2.5,
        "show_countdown_timers": True
    },
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
        "notify_on_all_scans": False,
        "notify_only_high_conviction": True
    },
    "timesfm": {
        "enabled": True,
        "min_candidate_conviction": 65.0,
        "conviction_boost": 12.0,
        "suppress_on_conflict": False,
        "device": "cpu"
    },
    "watchlist": [
        # Forex (48)
        {"symbol": "EURUSD", "name": "EUR/USD", "category": "Forex", "active": True, "est_spread_pct": 0.008},
        {"symbol": "GBPUSD", "name": "GBP/USD", "category": "Forex", "active": True, "est_spread_pct": 0.012},
        {"symbol": "USDJPY", "name": "USD/JPY", "category": "Forex", "active": True, "est_spread_pct": 0.010},
        {"symbol": "AUDUSD", "name": "AUD/USD", "category": "Forex", "active": True, "est_spread_pct": 0.012},
        {"symbol": "USDCAD", "name": "USD/CAD", "category": "Forex", "active": True, "est_spread_pct": 0.015},
        {"symbol": "USDCHF", "name": "USD/CHF", "category": "Forex", "active": True, "est_spread_pct": 0.015},
        {"symbol": "NZDUSD", "name": "NZD/USD", "category": "Forex", "active": True, "est_spread_pct": 0.018},
        {"symbol": "EURGBP", "name": "EUR/GBP", "category": "Forex", "active": True, "est_spread_pct": 0.015},
        {"symbol": "EURJPY", "name": "EUR/JPY", "category": "Forex", "active": True, "est_spread_pct": 0.015},
        {"symbol": "GBPJPY", "name": "GBP/JPY", "category": "Forex", "active": True, "est_spread_pct": 0.018},
        {"symbol": "AUDJPY", "name": "AUD/JPY", "category": "Forex", "active": True, "est_spread_pct": 0.018},
        {"symbol": "CADJPY", "name": "CAD/JPY", "category": "Forex", "active": True, "est_spread_pct": 0.020},
        {"symbol": "CHFJPY", "name": "CHF/JPY", "category": "Forex", "active": True, "est_spread_pct": 0.020},
        {"symbol": "EURAUD", "name": "EUR/AUD", "category": "Forex", "active": True, "est_spread_pct": 0.020},
        {"symbol": "EURCAD", "name": "EUR/CAD", "category": "Forex", "active": True, "est_spread_pct": 0.020},
        {"symbol": "EURCHF", "name": "EUR/CHF", "category": "Forex", "active": True, "est_spread_pct": 0.018},
        {"symbol": "EURNZD", "name": "EUR/NZD", "category": "Forex", "active": True, "est_spread_pct": 0.025},
        {"symbol": "GBPAUD", "name": "GBP/AUD", "category": "Forex", "active": True, "est_spread_pct": 0.022},
        {"symbol": "GBPCAD", "name": "GBP/CAD", "category": "Forex", "active": True, "est_spread_pct": 0.022},
        {"symbol": "GBPCHF", "name": "GBP/CHF", "category": "Forex", "active": True, "est_spread_pct": 0.022},
        {"symbol": "GBPNZD", "name": "GBP/NZD", "category": "Forex", "active": True, "est_spread_pct": 0.028},
        {"symbol": "AUDCAD", "name": "AUD/CAD", "category": "Forex", "active": True, "est_spread_pct": 0.020},
        {"symbol": "AUDCHF", "name": "AUD/CHF", "category": "Forex", "active": True, "est_spread_pct": 0.020},
        {"symbol": "AUDNZD", "name": "AUD/NZD", "category": "Forex", "active": True, "est_spread_pct": 0.022},
        {"symbol": "AUDSGD", "name": "AUD/SGD", "category": "Forex", "active": True, "est_spread_pct": 0.025},
        {"symbol": "CADCHF", "name": "CAD/CHF", "category": "Forex", "active": True, "est_spread_pct": 0.022},
        {"symbol": "NZDCAD", "name": "NZD/CAD", "category": "Forex", "active": True, "est_spread_pct": 0.022},
        {"symbol": "NZDCHF", "name": "NZD/CHF", "category": "Forex", "active": True, "est_spread_pct": 0.022},
        {"symbol": "NZDJPY", "name": "NZD/JPY", "category": "Forex", "active": True, "est_spread_pct": 0.022},
        {"symbol": "NZDSGD", "name": "NZD/SGD", "category": "Forex", "active": True, "est_spread_pct": 0.028},
        {"symbol": "SGDJPY", "name": "SGD/JPY", "category": "Forex", "active": True, "est_spread_pct": 0.025},
        {"symbol": "EURHKD", "name": "EUR/HKD", "category": "Forex", "active": True, "est_spread_pct": 0.030},
        {"symbol": "EURNOK", "name": "EUR/NOK", "category": "Forex", "active": True, "est_spread_pct": 0.035},
        {"symbol": "EURSGD", "name": "EUR/SGD", "category": "Forex", "active": True, "est_spread_pct": 0.025},
        {"symbol": "EURPLN", "name": "EUR/PLN", "category": "Forex", "active": True, "est_spread_pct": 0.035},
        {"symbol": "EURTRY", "name": "EUR/TRY", "category": "Forex", "active": True, "est_spread_pct": 0.050},
        {"symbol": "EURSEK", "name": "EUR/SEK", "category": "Forex", "active": True, "est_spread_pct": 0.035},
        {"symbol": "GBPSGD", "name": "GBP/SGD", "category": "Forex", "active": True, "est_spread_pct": 0.028},
        {"symbol": "USDCNH", "name": "USD/CNH", "category": "Forex", "active": True, "est_spread_pct": 0.025},
        {"symbol": "USDDKK", "name": "USD/DKK", "category": "Forex", "active": True, "est_spread_pct": 0.030},
        {"symbol": "USDHUF", "name": "USD/HUF", "category": "Forex", "active": True, "est_spread_pct": 0.035},
        {"symbol": "USDMXN", "name": "USD/MXN", "category": "Forex", "active": True, "est_spread_pct": 0.030},
        {"symbol": "USDNOK", "name": "USD/NOK", "category": "Forex", "active": True, "est_spread_pct": 0.035},
        {"symbol": "USDSGD", "name": "USD/SGD", "category": "Forex", "active": True, "est_spread_pct": 0.022},
        {"symbol": "USDZAR", "name": "USD/ZAR", "category": "Forex", "active": True, "est_spread_pct": 0.035},
        {"symbol": "USDSEK", "name": "USD/SEK", "category": "Forex", "active": True, "est_spread_pct": 0.035},
        {"symbol": "USDPLN", "name": "USD/PLN", "category": "Forex", "active": True, "est_spread_pct": 0.035},
        {"symbol": "USDTRY", "name": "USD/TRY", "category": "Forex", "active": True, "est_spread_pct": 0.050},
        
        # Indices (14)
        {"symbol": "US30", "name": "Wall Street 30 (Dow)", "category": "Indices", "active": True, "est_spread_pct": 0.010},
        {"symbol": "NAS100", "name": "US Tech 100 (Nasdaq)", "category": "Indices", "active": True, "est_spread_pct": 0.012},
        {"symbol": "SPX500", "name": "US 500 (S&P)", "category": "Indices", "active": True, "est_spread_pct": 0.008},
        {"symbol": "GER40", "name": "Germany 40 (DAX)", "category": "Indices", "active": True, "est_spread_pct": 0.012},
        {"symbol": "UK100", "name": "UK 100 (FTSE)", "category": "Indices", "active": True, "est_spread_pct": 0.015},
        {"symbol": "FRA40", "name": "France 40 (CAC)", "category": "Indices", "active": True, "est_spread_pct": 0.015},
        {"symbol": "EUSTX50", "name": "Euro Stoxx 50", "category": "Indices", "active": True, "est_spread_pct": 0.015},
        {"symbol": "JP225", "name": "Japan 225 (Nikkei)", "category": "Indices", "active": True, "est_spread_pct": 0.018},
        {"symbol": "HK50", "name": "Hong Kong 50 (Hang Seng)", "category": "Indices", "active": True, "est_spread_pct": 0.025},
        {"symbol": "AUS200", "name": "Australia 200", "category": "Indices", "active": True, "est_spread_pct": 0.018},
        {"symbol": "US2000", "name": "US Small Cap 2000", "category": "Indices", "active": True, "est_spread_pct": 0.020},
        {"symbol": "SWI20", "name": "Switzerland 20", "category": "Indices", "active": True, "est_spread_pct": 0.020},
        {"symbol": "NTH25", "name": "Netherlands 25", "category": "Indices", "active": True, "est_spread_pct": 0.020},
        {"symbol": "ESP35", "name": "Spain 35 (IBEX)", "category": "Indices", "active": True, "est_spread_pct": 0.025},
        
        # Commodities & Metals (5)
        {"symbol": "XAUUSD", "name": "Gold vs US-Dollar", "category": "Commodities", "active": True, "est_spread_pct": 0.012},
        {"symbol": "XAGUSD", "name": "Silver vs US-Dollar", "category": "Commodities", "active": True, "est_spread_pct": 0.015},
        {"symbol": "XPTUSD", "name": "Platinum vs US-Dollar", "category": "Commodities", "active": True, "est_spread_pct": 0.020},
        {"symbol": "USOUSD", "name": "WTI Crude Oil", "category": "Commodities", "active": True, "est_spread_pct": 0.018},
        {"symbol": "UKOUSD", "name": "Brent Crude Oil", "category": "Commodities", "active": True, "est_spread_pct": 0.018},
        
        # Crypto (9)
        {"symbol": "BTCUSD", "name": "Bitcoin", "category": "Crypto", "active": True, "est_spread_pct": 0.020},
        {"symbol": "ETHUSD", "name": "Ethereum", "category": "Crypto", "active": True, "est_spread_pct": 0.025},
        {"symbol": "LTCUSD", "name": "Litecoin", "category": "Crypto", "active": True, "est_spread_pct": 0.035},
        {"symbol": "XRPUSD", "name": "Ripple", "category": "Crypto", "active": True, "est_spread_pct": 0.040},
        {"symbol": "ADAUSD", "name": "Cardano", "category": "Crypto", "active": True, "est_spread_pct": 0.040},
        {"symbol": "DOGUSD", "name": "Dogecoin", "category": "Crypto", "active": True, "est_spread_pct": 0.045},
        {"symbol": "XLMUSD", "name": "Stellar Lumens", "category": "Crypto", "active": True, "est_spread_pct": 0.045},
        {"symbol": "LNKUSD", "name": "Chainlink", "category": "Crypto", "active": True, "est_spread_pct": 0.040},
        {"symbol": "XMRUSD", "name": "Monero", "category": "Crypto", "active": True, "est_spread_pct": 0.050},
        
        # Stocks (20)
        {"symbol": "AAPL", "name": "Apple Inc.", "category": "Stocks", "active": True, "est_spread_pct": 0.015},
        {"symbol": "AMZN", "name": "Amazon.com", "category": "Stocks", "active": True, "est_spread_pct": 0.015},
        {"symbol": "GOOG", "name": "Alphabet Inc.", "category": "Stocks", "active": True, "est_spread_pct": 0.015},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "category": "Stocks", "active": True, "est_spread_pct": 0.015},
        {"symbol": "NVDA", "name": "NVIDIA Corp.", "category": "Stocks", "active": True, "est_spread_pct": 0.018},
        {"symbol": "TSLA", "name": "Tesla Inc.", "category": "Stocks", "active": True, "est_spread_pct": 0.020},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "category": "Stocks", "active": True, "est_spread_pct": 0.020},
        {"symbol": "META", "name": "Meta Platforms", "category": "Stocks", "active": True, "est_spread_pct": 0.018},
        {"symbol": "BABA", "name": "Alibaba Group", "category": "Stocks", "active": True, "est_spread_pct": 0.025},
        {"symbol": "NFLX", "name": "Netflix Inc.", "category": "Stocks", "active": True, "est_spread_pct": 0.020},
        {"symbol": "INTC", "name": "Intel Corp.", "category": "Stocks", "active": True, "est_spread_pct": 0.020},
        {"symbol": "NKE", "name": "Nike Inc.", "category": "Stocks", "active": True, "est_spread_pct": 0.020},
        {"symbol": "KO", "name": "Coca-Cola Co.", "category": "Stocks", "active": True, "est_spread_pct": 0.015},
        {"symbol": "SPCX", "name": "SpaceX", "category": "Stocks", "active": False, "est_spread_pct": 0.040},
        {"symbol": "MBG", "name": "Mercedes-Benz Group", "category": "Stocks", "active": True, "est_spread_pct": 0.025},
        {"symbol": "BAYN", "name": "Bayer AG", "category": "Stocks", "active": True, "est_spread_pct": 0.025},
        {"symbol": "MC", "name": "LVMH", "category": "Stocks", "active": True, "est_spread_pct": 0.020},
        {"symbol": "VOW3", "name": "Volkswagen AG", "category": "Stocks", "active": True, "est_spread_pct": 0.025},
        {"symbol": "ADS", "name": "Adidas AG", "category": "Stocks", "active": True, "est_spread_pct": 0.025},
        {"symbol": "BMW", "name": "BMW AG", "category": "Stocks", "active": True, "est_spread_pct": 0.025}
    ]
}


class ConfigManager:
    """Handles loading, updating, and saving configuration to config.json."""
    
    def __init__(self, config_path: Path = CONFIG_FILE):
        self.config_path = config_path
        self._config: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            self._save(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge defaults for any missing keys
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                
                # Check for missing default watchlist assets (e.g. newly added Commodities & Metals)
                existing_symbols = {item.get("symbol", "").upper() for item in merged.get("watchlist", [])}
                missing_defaults = [item for item in DEFAULT_CONFIG["watchlist"] if item.get("symbol", "").upper() not in existing_symbols]
                needs_save = False
                if missing_defaults:
                    merged["watchlist"].extend(missing_defaults)
                    needs_save = True
                
                if "scan_timeframes" not in merged or not merged["scan_timeframes"]:
                    merged["scan_timeframes"] = DEFAULT_CONFIG["scan_timeframes"]
                    needs_save = True

                if "timesfm" not in merged or not isinstance(merged["timesfm"], dict):
                    merged["timesfm"] = DEFAULT_CONFIG["timesfm"].copy()
                    needs_save = True

                if needs_save:
                    self._save(merged)
                
                return merged
        except Exception as e:
            print(f"Warning: Error loading {self.config_path}, falling back to defaults: {e}")
            return DEFAULT_CONFIG.copy()

    def _save(self, data: Dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_all(self) -> Dict[str, Any]:
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        self._config.update(updates)
        self._save(self._config)
        return self._config

    def update_telegram(self, bot_token: str, chat_id: str, enabled: bool) -> Dict[str, Any]:
        self._config["telegram"]["bot_token"] = bot_token.strip()
        self._config["telegram"]["chat_id"] = chat_id.strip()
        self._config["telegram"]["enabled"] = enabled
        self._save(self._config)
        return self._config["telegram"]

    def update_timesfm(
        self,
        enabled: bool,
        min_candidate_conviction: float = 65.0,
        conviction_boost: float = 12.0,
        suppress_on_conflict: bool = False
    ) -> Dict[str, Any]:
        if "timesfm" not in self._config or not isinstance(self._config["timesfm"], dict):
            self._config["timesfm"] = DEFAULT_CONFIG["timesfm"].copy()
        self._config["timesfm"]["enabled"] = enabled
        self._config["timesfm"]["min_candidate_conviction"] = float(min_candidate_conviction)
        self._config["timesfm"]["conviction_boost"] = float(conviction_boost)
        self._config["timesfm"]["suppress_on_conflict"] = bool(suppress_on_conflict)
        self._save(self._config)
        return self._config["timesfm"]

    def get_watchlist(self) -> List[Dict[str, Any]]:
        return self._config.get("watchlist", [])

    def add_symbol(self, symbol: str, name: str, category: str, est_spread_pct: float = 0.02) -> List[Dict[str, Any]]:
        symbol = symbol.strip().upper()
        watchlist = self._config.get("watchlist", [])
        for item in watchlist:
            if item["symbol"] == symbol:
                item["name"] = name
                item["category"] = category
                item["active"] = True
                item["est_spread_pct"] = est_spread_pct
                self._save(self._config)
                return watchlist

        watchlist.append({
            "symbol": symbol,
            "name": name,
            "category": category,
            "active": True,
            "est_spread_pct": est_spread_pct
        })
        self._config["watchlist"] = watchlist
        self._save(self._config)
        return watchlist

    def toggle_symbol(self, symbol: str, active: bool) -> List[Dict[str, Any]]:
        watchlist = self._config.get("watchlist", [])
        for item in watchlist:
            if item["symbol"] == symbol:
                item["active"] = active
                break
        self._config["watchlist"] = watchlist
        self._save(self._config)
        return watchlist

    def remove_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        watchlist = self._config.get("watchlist", [])
        self._config["watchlist"] = [item for item in watchlist if item["symbol"] != symbol]
        self._save(self._config)
        return self._config["watchlist"]


# Global singleton instance
config_manager = ConfigManager()
