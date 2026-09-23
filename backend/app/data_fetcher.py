import datetime
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
import yfinance as yf


def get_current_session_info() -> Dict[str, Any]:
    """
    Identifies the active global market session in UTC.
    London: 08:00 - 16:30 UTC
    New York: 13:00 - 21:00 UTC
    London-NY Overlap: 13:00 - 16:30 UTC (Prime Institutional Liquidity Window)
    Asian (Tokyo/Sydney): 00:00 - 09:00 UTC
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    hour = now_utc.hour + now_utc.minute / 60.0
    
    is_london = 8.0 <= hour < 16.5
    is_ny = 13.0 <= hour < 21.0
    is_overlap = is_london and is_ny
    is_asian = 0.0 <= hour < 9.0
    is_rollover = 20.0 <= hour < 23.0  # Daily Rollover Window: high spread & low liquidity
    
    session_names = []
    if is_rollover:
        session_names.append("Rollover Window (20:00-23:00 UTC - Spread Risk Suppressed)")
    elif is_overlap:
        session_names.append("London-NY Overlap (Prime Liquidity)")
    elif is_london:
        session_names.append("London Session")
    elif is_ny:
        session_names.append("New York Session")
    elif is_asian:
        session_names.append("Asian Session")
    else:
        session_names.append("Off-Hours / Late NY")

    return {
        "current_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "active_session": " & ".join(session_names),
        "is_london_ny_overlap": is_overlap,
        "is_london": is_london,
        "is_ny": is_ny,
        "is_asian": is_asian,
        "is_high_liquidity": is_overlap or (is_london and hour >= 8.5) or (is_ny and hour <= 18.0),
        "is_rollover": is_rollover
    }


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Computes ATR-14, RSI-14, EMA-20, EMA-50, EMA-200 and return features."""
    if len(df) < 20:
        return df

    # ATR 14
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14, min_periods=1).mean()

    # RSI 14
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14, min_periods=1).mean()
    avg_loss = loss.rolling(window=14, min_periods=1).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    # EMAs
    df['EMA20'] = close.ewm(span=20, adjust=False).mean()
    df['EMA50'] = close.ewm(span=50, adjust=False).mean()
    df['EMA200'] = close.ewm(span=200, adjust=False).mean()

    # Log Returns
    df['LogReturn'] = np.log(close / close.shift(1)).fillna(0.0)
    return df


class MarketDataFetcher:
    """Fetches and normalizes multi-asset OHLCV data using yfinance."""

    # Map intervals to appropriate yfinance periods (optimized for 500 candles + fast download)
    INTERVAL_PERIOD_MAP = {
        "5m": "5d",     # 5 days = ~1,300 5-min candles (well above 500 target, 6x faster)
        "15m": "14d",   # 14 days = ~1,300 15-min candles
        "30m": "25d",
        "1h": "60d",
        "4h": "120d",
        "1d": "2y"
    }

    FUNDED_NEXT_MAP = {
        # Indices
        "US30": "^DJI",
        "NDX100": "^NDX",
        "NAS100": "^NDX",
        "SPX500": "^GSPC",
        "US500": "^GSPC",
        "GER30": "^GDAXI",
        "GER40": "^GDAXI",
        "UK100": "^FTSE",
        "FRA40": "^FCHI",
        "EUSTX50": "^STOXX50E",
        "JP225": "^N225",
        "HK50": "^HSI",
        "AUS200": "^AXJO",
        "US2000": "^RUT",
        "SWI20": "^SSMI",
        "NTH25": "^AEX",
        "ESP35": "^IBEX",
        # Crypto
        "BTCUSD": "BTC-USD",
        "ETHUSD": "ETH-USD",
        "LTCUSD": "LTC-USD",
        "XRPUSD": "XRP-USD",
        "ADAUSD": "ADA-USD",
        "DOGUSD": "DOGE-USD",
        "XLMUSD": "XLM-USD",
        "LNKUSD": "LINK-USD",
        "XMRUSD": "XMR-USD",
        # Commodities & Metals (FundedNext)
        "XAUUSD": "GC=F",
        "GOLD": "GC=F",
        "XAGUSD": "SI=F",
        "SILVER": "SI=F",
        "XPTUSD": "PL=F",
        "PLATINUM": "PL=F",
        "USOUSD": "CL=F",
        "OIL": "CL=F",
        "WTI": "CL=F",
        "UKOUSD": "BZ=F",
        "BRENT": "BZ=F",
        # Stocks
        "MBG": "MBG.DE",
        "BAYN": "BAYN.DE",
        "MC": "MC.PA",
        "VOW3": "VOW3.DE",
        "ADS": "ADS.DE",
        "BMW": "BMW.DE",
    }

    @classmethod
    def resolve_symbol(cls, symbol: str) -> str:
        """Resolves FundedNext CFD symbols into market ticker format."""
        s = symbol.strip().upper()
        if s in cls.FUNDED_NEXT_MAP:
            return cls.FUNDED_NEXT_MAP[s]
        # Standard 6-letter currency pair (e.g. EURUSD, GBPJPY, AUDCAD)
        if len(s) == 6 and s.isalpha() and not s.endswith("=X"):
            return f"{s}=X"
        return s

    @staticmethod
    def fetch_candles(
        symbol: str,
        interval: str = "1h",
        target_count: int = 500
    ) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Fetches historical candles for `symbol` with the given interval,
        aiming for `target_count` candles (up to 500).
        Returns (DataFrame, error_message).
        """
        # 1. Primary Source: MetaTrader 5 live connection to FundedNext
        try:
            from app.mt5_bridge import mt5_bridge
            if mt5_bridge.is_connected:
                df_mt5 = mt5_bridge.get_candles_from_mt5(symbol, timeframe=interval, count=target_count)
                if df_mt5 is not None and len(df_mt5) >= 30:
                    df_mt5 = compute_indicators(df_mt5)
                    if len(df_mt5) > target_count:
                        df_mt5 = df_mt5.iloc[-target_count:].copy().reset_index(drop=True)
                    df_mt5.attrs["symbol"] = symbol
                    df_mt5.attrs["source"] = "FundedNext MT5"
                    return df_mt5, None
        except Exception as e_mt5:
            logger.debug(f"MT5 candle fetch failed for {symbol}, falling back to web feed: {e_mt5}")

        # 2. Fallback Source: yfinance web feed
        resolved_sym = MarketDataFetcher.resolve_symbol(symbol)
        period = MarketDataFetcher.INTERVAL_PERIOD_MAP.get(interval, "60d")
        
        # yfinance special case: 4h isn't natively supported by yfinance, so fetch 1h and resample to 4h
        fetch_interval = "1h" if interval == "4h" else interval

        try:
            ticker = yf.Ticker(resolved_sym)
            df = ticker.history(period=period, interval=fetch_interval, auto_adjust=False)
            
            if df.empty or len(df) < 30:
                # Fallback to wider period (never use 'max' for sub-hourly as Yahoo rejects it)
                fallback_period = "60d" if interval in ["5m", "15m", "30m"] else "max"
                df = ticker.history(period=fallback_period, interval=fetch_interval, auto_adjust=False)

            if df.empty:
                return pd.DataFrame(), f"No historical candle data returned for symbol '{symbol}'."

            # Reset index and clean column names
            df = df.reset_index()
            # Standardize timestamp column
            date_col = "Datetime" if "Datetime" in df.columns else "Date"
            if date_col not in df.columns:
                date_col = df.columns[0]

            df = df.rename(columns={date_col: "Time"})
            
            # If resampling to 4h
            if interval == "4h":
                df['Time'] = pd.to_datetime(df['Time'])
                df = df.set_index('Time')
                df = df.resample('4h').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna().reset_index()

            # Ensure numeric columns
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
            df = compute_indicators(df)

            # Keep the most recent target_count candles
            if len(df) > target_count:
                df = df.iloc[-target_count:].copy().reset_index(drop=True)

            return df, None

        except Exception as e:
            return pd.DataFrame(), f"Failed to fetch data for {symbol}: {str(e)}"

    @staticmethod
    def format_for_tradingview(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Converts DataFrame into TradingView Lightweight Charts format: [{time: unix_sec, open, high, low, close}]."""
        candles = []
        for _, row in df.iterrows():
            t = row['Time']
            if isinstance(t, str):
                t = pd.to_datetime(t)
            # Unix timestamp in seconds
            unix_ts = int(t.timestamp())
            candles.append({
                "time": unix_ts,
                "open": round(float(row['Open']), 4),
                "high": round(float(row['High']), 4),
                "low": round(float(row['Low']), 4),
                "close": round(float(row['Close']), 4),
                "volume": float(row.get('Volume', 0)),
                "atr": round(float(row.get('ATR', 0)), 4) if pd.notna(row.get('ATR')) else 0.0,
                "rsi": round(float(row.get('RSI', 50)), 2) if pd.notna(row.get('RSI')) else 50.0
            })
        return candles

    @staticmethod
    def compute_htf_alignment(symbol: str) -> Dict[str, Any]:
        """
        Scans Higher Timeframes (15m, 1h, 4h) for macro confluence
        so traders on the 5m timeframe never miss the big picture.
        """
        timeframes = ["5m", "15m", "1h", "4h"]
        tf_status = {}
        bull_count = 0
        bear_count = 0

        for tf in timeframes:
            try:
                df, err = MarketDataFetcher.fetch_candles(symbol, interval=tf, target_count=60)
                if not err and len(df) >= 20:
                    c = df['Close'].iloc[-1]
                    ema20 = df['EMA20'].iloc[-1] if 'EMA20' in df.columns else c
                    ema50 = df['EMA50'].iloc[-1] if 'EMA50' in df.columns else c
                    rsi = df['RSI'].iloc[-1] if 'RSI' in df.columns else 50.0

                    if c > ema20 > ema50:
                        bias = "BULLISH"
                        bull_count += 1
                    elif c < ema20 < ema50:
                        bias = "BEARISH"
                        bear_count += 1
                    else:
                        bias = "NEUTRAL"

                    tf_status[tf] = {
                        "bias": bias,
                        "rsi": round(float(rsi), 1),
                        "price": round(float(c), 4)
                    }
                else:
                    tf_status[tf] = {"bias": "UNKNOWN", "rsi": 50.0, "price": 0.0}
            except Exception:
                tf_status[tf] = {"bias": "UNKNOWN", "rsi": 50.0, "price": 0.0}

        # Confluence synthesis
        total_valid = len([v for v in tf_status.values() if v["bias"] != "UNKNOWN"])
        if bull_count >= 3:
            alignment = f"BULLISH CONFLUENCE: {bull_count}/{total_valid} Timeframes Aligned"
            htf_macro = "BULLISH"
        elif bear_count >= 3:
            alignment = f"BEARISH CONFLUENCE: {bear_count}/{total_valid} Timeframes Aligned"
            htf_macro = "BEARISH"
        else:
            alignment = f"MIXED TREND ({bull_count} Bull, {bear_count} Bear)"
            htf_macro = "MIXED"

        return {
            "symbol": symbol,
            "matrix": tf_status,
            "htf_macro": htf_macro,
            "alignment_text": alignment,
            "is_confluent": (bull_count >= 3 or bear_count >= 3)
        }

