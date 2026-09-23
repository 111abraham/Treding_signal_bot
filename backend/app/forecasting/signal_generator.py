import datetime
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from app.data_fetcher import get_current_session_info
from app.market_liveness import market_liveness


class SignalGenerator:
    """
    Translates AI 5-candle forecasts and market data into quantitative signals
    enforcing user risk guardrails (Spread < 5% of SL, London-NY session priority).
    """

    @staticmethod
    def evaluate_signal(
        forecast_result: Dict[str, Any],
        df: pd.DataFrame,
        asset_info: Dict[str, Any],
        strategy_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates whether the 5-candle forecast qualifies as a valid trading setup.
        Returns signal dictionary if valid, or a structured report explaining the filters.
        """
        symbol = asset_info.get("symbol", "UNKNOWN")
        name = asset_info.get("name", symbol)
        category = asset_info.get("category", "General")
        est_spread_pct = float(asset_info.get("est_spread_pct", 0.02))

        current_price = forecast_result["current_price"]
        current_atr = forecast_result["current_atr"]
        direction = forecast_result["direction"]
        expected_return_pct = forecast_result["expected_return_pct"]
        pred_candles = forecast_result["predicted_candles"]
        
        # Market liveness & session check
        liveness = market_liveness.check_liveness(symbol, df=df)
        if not liveness.get("is_open", True):
            return None

        session_info = get_current_session_info()
        is_overlap = session_info["is_london_ny_overlap"]
        
        # If neutral direction or minimal ATR, no setup
        if direction == "NEUTRAL" or current_atr <= 0:
            return None

        # Calculate Dynamic Stop-Loss and Take-Profit based on ATR and forecast quantiles
        atr_sl_mult = strategy_config.get("atr_sl_multiplier", 1.5)
        atr_tp_mult = strategy_config.get("atr_tp_multiplier", 2.5)

        entry_price = current_price

        if direction == "BULLISH":
            stop_loss = round(entry_price - (current_atr * atr_sl_mult), 4)
            # Take profit aligned with 5th predicted candle median or ATR multiple
            predicted_target = pred_candles[-1]["close"]
            tp_atr = round(entry_price + (current_atr * atr_tp_mult), 4)
            take_profit_1 = round(max(predicted_target, tp_atr), 4)
            take_profit_2 = round(pred_candles[-1]["p90"], 4)
            
            sl_distance = entry_price - stop_loss
            tp_distance = take_profit_1 - entry_price

        else:  # BEARISH
            stop_loss = round(entry_price + (current_atr * atr_sl_mult), 4)
            predicted_target = pred_candles[-1]["close"]
            tp_atr = round(entry_price - (current_atr * atr_tp_mult), 4)
            take_profit_1 = round(min(predicted_target, tp_atr), 4)
            take_profit_2 = round(pred_candles[-1]["p10"], 4)
            
            sl_distance = stop_loss - entry_price
            tp_distance = entry_price - take_profit_1

        if sl_distance <= 0:
            return None

        # Risk-to-Reward Ratio
        rr_ratio = round(tp_distance / sl_distance, 2) if sl_distance > 0 else 0.0

        # Spread Guardrail: Live FundedNext MT5 spread or calibrated fallback must be < 5% of Stop-Loss distance
        live_tick = None
        try:
            from app.mt5_bridge import mt5_bridge
            if mt5_bridge.is_connected:
                live_tick = mt5_bridge.get_live_spread(symbol)
        except Exception:
            live_tick = None

        if live_tick:
            actual_spread_value = live_tick["spread_value"]
            actual_spread_pct = live_tick["spread_pct"]
            spread_source = "FundedNext MT5 (Live)"
            spread_points = live_tick["spread_points"]
        else:
            actual_spread_value = current_price * (est_spread_pct / 100.0)
            actual_spread_pct = est_spread_pct
            spread_source = "Calibrated Model"
            spread_points = None

        spread_to_sl_ratio = round((actual_spread_value / sl_distance), 4)
        max_allowed_ratio = strategy_config.get("max_spread_to_sl_ratio", 0.05)
        passes_spread_filter = spread_to_sl_ratio <= max_allowed_ratio

        # Conviction Scoring (0 to 100)
        conviction = 50.0  # Base

        # 1. Return strength vs ATR
        return_vs_atr = abs(expected_return_pct) / ((current_atr / current_price) * 100 + 1e-6)
        conviction += min(20.0, return_vs_atr * 10.0)

        # 2. Risk-Reward bonus
        if rr_ratio >= 2.0:
            conviction += 10.0
        elif rr_ratio >= 1.5:
            conviction += 5.0

        # 3. Session confluence bonus: London & New York overlap
        if is_overlap:
            conviction += 12.0
        elif session_info["is_high_liquidity"]:
            conviction += 5.0

        # 4. Spread friction penalty
        if not passes_spread_filter:
            conviction -= 25.0  # Major penalty if spread eats too much SL
        else:
            conviction += 8.0   # Reward for very low spread-to-SL

        # 5. Technical indicator alignment (EMA & RSI)
        if len(df) > 50 and 'RSI' in df.columns:
            rsi = df['RSI'].iloc[-1]
            ema20 = df['EMA20'].iloc[-1] if 'EMA20' in df.columns else current_price
            ema50 = df['EMA50'].iloc[-1] if 'EMA50' in df.columns else current_price

            if direction == "BULLISH":
                if current_price > ema20 > ema50:
                    conviction += 5.0
                if 45 <= rsi <= 68:  # Healthy bullish momentum, not overbought
                    conviction += 5.0
            elif direction == "BEARISH":
                if current_price < ema20 < ema50:
                    conviction += 5.0
                if 32 <= rsi <= 55:  # Healthy bearish momentum, not oversold
                    conviction += 5.0

        conviction = round(min(98.0, max(15.0, conviction)), 1)
        min_required_conviction = strategy_config.get("min_conviction", 65.0)
        is_rollover = session_info.get("is_rollover", False)

        # Institutional Session Filter: Restrict signal generation to user-configured sessions (Crypto runs 24/7)
        passes_session_filter = True
        scan_sessions = [s.lower() for s in strategy_config.get("scan_sessions", [])]
        if scan_sessions and len(scan_sessions) < 5 and category != "Crypto":
            active_sess_str = (session_info.get("active_session") or "").lower()
            is_asian = session_info.get("is_asian", False)
            sess_matched = any(
                (s == "overlap" and is_overlap) or
                (s == "london" and "london" in active_sess_str and not is_overlap) or
                (s in ("ny", "new york") and ("new york" in active_sess_str or "ny" in active_sess_str) and not is_overlap) or
                (s == "asian" and is_asian) or
                (s in ("off-hours", "offhours") and ("off-hours" in active_sess_str or is_rollover))
                for s in scan_sessions
            )
            if not sess_matched:
                passes_session_filter = False

        is_actionable = (
            passes_spread_filter and
            passes_session_filter and
            not is_rollover and  # Suppress all signals during 20:00 - 23:00 UTC rollover spread expansion
            conviction >= min_required_conviction and
            rr_ratio >= strategy_config.get("min_risk_reward", 1.5)
        )

        candle_time_str = str(df["Time"].iloc[-1])
        try:
            candle_unix = int(pd.to_datetime(df["Time"].iloc[-1]).timestamp())
        except Exception:
            candle_unix = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

        tf = forecast_result.get("timeframe", "1h")
        step_seconds_map = {
            "1m": 60,
            "5m": 5 * 60,
            "15m": 15 * 60,
            "30m": 30 * 60,
            "1h": 60 * 60,
            "4h": 4 * 60 * 60,
            "1d": 24 * 60 * 60
        }
        step_seconds = step_seconds_map.get(tf.lower(), 3600)
        max_candles = len(pred_candles) if pred_candles else strategy_config.get("forecast_candles", 5)
        expires_at_unix = candle_unix + (max_candles * step_seconds)

        return {
            "symbol": symbol,
            "name": name,
            "category": category,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "candle_time": candle_time_str,
            "candle_unix": candle_unix,
            "timeframe": tf,
            "max_candles": max_candles,
            "step_seconds": step_seconds,
            "expires_at_unix": expires_at_unix,
            "direction": direction,
            "current_price": current_price,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit_1": take_profit_1,
            "take_profit_2": take_profit_2,
            "sl_distance": round(sl_distance, 4),
            "tp_distance": round(tp_distance, 4),
            "risk_reward_ratio": rr_ratio,
            "estimated_spread": round(actual_spread_value, 4),
            "spread_to_sl_ratio_pct": round(spread_to_sl_ratio * 100, 2),
            "passes_spread_filter": passes_spread_filter,
            "passes_session_filter": passes_session_filter,
            "spread_source": spread_source,
            "live_spread_points": spread_points,
            "conviction": conviction,
            "is_actionable": is_actionable,
            "session_name": session_info["active_session"],
            "is_london_ny_overlap": is_overlap,
            "is_rollover": is_rollover,
            "expected_return_pct": expected_return_pct,
            "model_used": forecast_result.get("model_used", "AI Model")
        }


# Global signal generator singleton
signal_generator = SignalGenerator()
