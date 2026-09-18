import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

from app.data_fetcher import MarketDataFetcher
from app.telegram_bot import telegram_notifier

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTCOMES_FILE = BASE_DIR / "trade_outcomes.json"


class OutcomeTracker:
    """
    Monitors active trade signals across each candle up to 5 candles.
    Tracks whether price hits Take-Profit 1 (WIN), Stop-Loss (LOSS), or expires (EXPIRED).
    Maintains statistics on win-rates, profit factors, and conviction calibration.
    """

    def __init__(self, storage_path: Path = OUTCOMES_FILE):
        self.storage_path = storage_path
        self.active_trades: List[Dict[str, Any]] = []
        self.closed_trades: List[Dict[str, Any]] = []
        self._load()

    def _sanitize_trade(self, t: Dict[str, Any]) -> Dict[str, Any]:
        sl_dist = float(t.get("sl_distance", 0.0))
        entry = float(t.get("entry_price", 1.0))
        if "estimated_spread" not in t or t.get("estimated_spread") is None:
            t["estimated_spread"] = round(entry * 0.0002, 4)
        if "spread_to_sl_ratio_pct" not in t or t.get("spread_to_sl_ratio_pct") is None:
            if sl_dist > 0 and t["estimated_spread"] > 0:
                t["spread_to_sl_ratio_pct"] = round((t["estimated_spread"] / sl_dist) * 100.0, 2)
            else:
                t["spread_to_sl_ratio_pct"] = 1.5
        if "passes_spread_filter" not in t or t.get("passes_spread_filter") is None:
            t["passes_spread_filter"] = t["spread_to_sl_ratio_pct"] <= 5.0
        if "entry_candle_unix" not in t:
            t["entry_candle_unix"] = t.get("opened_unix", int(datetime.datetime.now(datetime.timezone.utc).timestamp()))
        return t

    def _load(self):
        if not self.storage_path.exists():
            self._save()
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_active = data.get("active_trades", [])
                raw_closed = data.get("closed_trades", [])
                self.active_trades = [self._sanitize_trade(t) for t in raw_active]
                self.closed_trades = [self._sanitize_trade(t) for t in raw_closed]
        except Exception as e:
            logger.warning(f"Error loading {self.storage_path}: {e}")
            self.active_trades = []
            self.closed_trades = []

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump({
                "active_trades": self.active_trades,
                "closed_trades": self.closed_trades,
                "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            }, f, indent=2)

    def register_signal(self, signal: Dict[str, Any]) -> bool:
        """Adds a newly dispatched actionable signal to active tracking ledger."""
        tf = signal.get("timeframe", "1h")
        sym = signal["symbol"]

        # Prevent duplicate active trade on the same symbol and timeframe
        for t in self.active_trades:
            if t["symbol"] == sym and t["timeframe"] == tf:
                return False

        candle_time = signal.get("candle_time") or signal["timestamp"]
        candle_unix = signal.get("candle_unix") or int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        trade_id = f"{sym}_{tf}_{signal['direction']}_{candle_time}"

        # Check if already tracked
        for t in self.active_trades:
            if t["id"] == trade_id:
                return False

        max_candles = int(signal.get("max_candles", 5))
        step_sec = int(signal.get("step_seconds", 3600))
        expires_at_unix = int(signal.get("expires_at_unix") or (candle_unix + (max_candles * step_sec)))

        sl_dist = float(signal.get("sl_distance", 0.0))
        entry_p = float(signal["entry_price"])
        est_spread = float(signal.get("estimated_spread", 0.0))
        if est_spread <= 0.0 and sl_dist > 0:
            est_spread = round(entry_p * 0.0002, 4)

        spread_ratio_pct = signal.get("spread_to_sl_ratio_pct")
        if spread_ratio_pct is None:
            spread_ratio_pct = round((est_spread / sl_dist) * 100.0, 2) if sl_dist > 0 else 1.5
        else:
            spread_ratio_pct = float(spread_ratio_pct)

        passes_spread = signal.get("passes_spread_filter")
        if passes_spread is None:
            passes_spread = spread_ratio_pct <= 5.0
        else:
            passes_spread = bool(passes_spread)

        trade_entry = {
            "id": trade_id,
            "symbol": sym,
            "name": signal.get("name", sym),
            "category": signal.get("category", "General"),
            "timeframe": tf,
            "direction": signal["direction"],
            "entry_price": entry_p,
            "stop_loss": float(signal["stop_loss"]),
            "take_profit_1": float(signal["take_profit_1"]),
            "take_profit_2": float(signal.get("take_profit_2", signal["take_profit_1"])),
            "risk_reward_ratio": float(signal.get("risk_reward_ratio", 1.5)),
            "conviction": float(signal.get("conviction", 70.0)),
            "sl_distance": sl_dist,
            "tp_distance": float(signal.get("tp_distance", 0.0)),
            "estimated_spread": est_spread,
            "spread_to_sl_ratio_pct": spread_ratio_pct,
            "passes_spread_filter": passes_spread,
            "spread_source": signal.get("spread_source", "Calibrated Model"),
            "dual_ai_confluence": bool(signal.get("dual_ai_confluence", False)),
            "timesfm_return_pct": float(signal["timesfm_return_pct"]) if signal.get("timesfm_return_pct") is not None else None,
            "timesfm_status": signal.get("timesfm_status"),
            "timesfm_consensus": signal.get("timesfm_consensus"),
            "timesfm_direction": signal.get("timesfm_direction"),
            "session_name": signal.get("session_name", "Market Session"),
            "opened_at": signal["timestamp"],
            "opened_candle_time": candle_time,
            "entry_candle_unix": candle_unix,
            "opened_unix": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            "candles_monitored": 0,
            "max_candles": max_candles,
            "step_seconds": step_sec,
            "expires_at_unix": expires_at_unix,
            "max_favorable_price": entry_p,
            "max_adverse_price": entry_p,
            "status": "ACTIVE"
        }

        self.active_trades.append(trade_entry)
        self._save()
        logger.info(f"Registered trade for tracking: {trade_id}")
        return True

    async def evaluate_active_trades(self, notify_telegram: bool = True) -> List[Dict[str, Any]]:
        """
        Polls market data for each active trade and checks whether TP1 or SL was touched,
        or if 5 candles have passed (time expiration).
        Evaluates ONLY candles formed strictly after trade entry candle.
        """
        if not self.active_trades:
            return []

        resolved_this_cycle = []
        remaining_active = []

        for trade in self.active_trades:
            sym = trade["symbol"]
            tf = trade["timeframe"]
            direction = trade["direction"]
            entry = trade["entry_price"]
            sl = trade["stop_loss"]
            tp1 = trade["take_profit_1"]
            entry_unix = trade.get("entry_candle_unix") or trade.get("opened_unix", 0)

            try:
                # Fetch recent candles to evaluate price progression since trade opening
                df, err = MarketDataFetcher.fetch_candles(sym, interval=tf, target_count=30)
                if err or df.empty:
                    remaining_active.append(trade)
                    continue

                # Filter candles that occurred STRICTLY AFTER trade entry candle
                df["unix"] = pd.to_datetime(df["Time"]).apply(lambda x: int(x.timestamp()))
                sub_df = df[df["unix"] > entry_unix].copy().reset_index(drop=True)

                if sub_df.empty:
                    # Still waiting for the first new candle to close after entry
                    remaining_active.append(trade)
                    continue

                # Count candles elapsed since trade start
                candles_elapsed = len(sub_df)
                trade["candles_monitored"] = candles_elapsed

                outcome = None
                resolved_price = None
                exit_reason = None
                hit_candle_idx = 0
                exit_candle_unix = None

                # Check each subsequent candle for TP or SL hit
                for idx, row in sub_df.iterrows():
                    high = float(row["High"])
                    low = float(row["Low"])
                    c = float(row["Close"])
                    bar_num = idx + 1
                    candle_ts = int(row["unix"])

                    if direction == "BULLISH":
                        # Track best and worst prices
                        trade["max_favorable_price"] = max(trade["max_favorable_price"], high)
                        trade["max_adverse_price"] = min(trade["max_adverse_price"], low)

                        # Did it hit Take-Profit 1?
                        if high >= tp1:
                            outcome = "WIN"
                            resolved_price = tp1
                            exit_reason = f"Take-Profit 1 hit at {tp1:.4f}"
                            hit_candle_idx = bar_num
                            exit_candle_unix = candle_ts
                            break
                        # Did it hit Stop-Loss?
                        elif low <= sl:
                            outcome = "LOSS"
                            resolved_price = sl
                            exit_reason = f"Stop-Loss hit at {sl:.4f}"
                            hit_candle_idx = bar_num
                            exit_candle_unix = candle_ts
                            break

                    else:  # BEARISH
                        trade["max_favorable_price"] = min(trade["max_favorable_price"], low)
                        trade["max_adverse_price"] = max(trade["max_adverse_price"], high)

                        if low <= tp1:
                            outcome = "WIN"
                            resolved_price = tp1
                            exit_reason = f"Take-Profit 1 hit at {tp1:.4f}"
                            hit_candle_idx = bar_num
                            exit_candle_unix = candle_ts
                            break
                        elif high >= sl:
                            outcome = "LOSS"
                            resolved_price = sl
                            exit_reason = f"Stop-Loss hit at {sl:.4f}"
                            hit_candle_idx = bar_num
                            exit_candle_unix = candle_ts
                            break

                # If neither TP nor SL touched, check if max_candles have passed (Time Expiration)
                max_candles = int(trade.get("max_candles", 5))
                if outcome is None and candles_elapsed >= max_candles:
                    idx_close = max_candles - 1 if len(sub_df) >= max_candles else -1
                    last_close = float(sub_df["Close"].iloc[idx_close])
                    resolved_price = last_close
                    hit_candle_idx = max_candles
                    exit_candle_unix = int(sub_df["unix"].iloc[idx_close])

                    if direction == "BULLISH":
                        pnl = last_close - entry
                    else:
                        pnl = entry - last_close

                    if pnl > 0.0001:
                        outcome = "EXPIRED_PROFIT"
                        exit_reason = f"{max_candles}-Candle Time Expiration (Closed in Profit at {last_close:.4f})"
                    elif pnl < -0.0001:
                        outcome = "EXPIRED_LOSS"
                        exit_reason = f"{max_candles}-Candle Time Expiration (Closed in Drawdown at {last_close:.4f})"
                    else:
                        outcome = "EXPIRED_BREAKEVEN"
                        exit_reason = f"{max_candles}-Candle Time Expiration (Closed at Breakeven at {last_close:.4f})"

                if outcome:
                    # Finalize resolved trade
                    closed_at_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    now_closed_unix = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
                    
                    # Calculate realized return % and R-multiple
                    if direction == "BULLISH":
                        realized_pnl_pct = ((resolved_price - entry) / entry) * 100.0
                    else:
                        realized_pnl_pct = ((entry - resolved_price) / entry) * 100.0

                    r_multiple = (realized_pnl_pct / ((trade["sl_distance"] / entry) * 100.0)) if trade["sl_distance"] > 0 else 0.0

                    trade["status"] = "CLOSED"
                    trade["outcome"] = outcome
                    trade["closed_at"] = closed_at_str
                    trade["closed_unix"] = now_closed_unix
                    trade["exit_candle_unix"] = exit_candle_unix or now_closed_unix
                    trade["exit_price"] = round(resolved_price, 4)
                    trade["exit_reason"] = exit_reason
                    trade["hit_on_candle"] = hit_candle_idx
                    trade["realized_pnl_pct"] = round(realized_pnl_pct, 2)
                    trade["realized_r"] = round(r_multiple, 2)

                    self.closed_trades.insert(0, trade)
                    resolved_this_cycle.append(trade)

                    # Send Telegram resolution notification
                    if notify_telegram:
                        await self._send_resolution_telegram(trade)
                else:
                    remaining_active.append(trade)

            except Exception as e:
                logger.error(f"Error evaluating active trade {trade.get('id')}: {e}", exc_info=True)
                remaining_active.append(trade)

        self.active_trades = remaining_active
        if resolved_this_cycle:
            self._save()

        return resolved_this_cycle

    async def _send_resolution_telegram(self, trade: Dict[str, Any]):
        """Dispatches an outcome card to Telegram when a trade concludes."""
        outcome = trade["outcome"]
        if outcome == "WIN":
            header = "🎯 <b>TRADE RESOLUTION: TAKE-PROFIT HIT!</b>"
            badge = "✅ <b>WIN</b>"
        elif outcome == "LOSS":
            header = "🛑 <b>TRADE RESOLUTION: STOP-LOSS HIT</b>"
            badge = "❌ <b>LOSS</b>"
        else:
            header = "⏱️ <b>TRADE RESOLUTION: TIME BARRIER EXPIRED (5 BARS)</b>"
            badge = f"⚖️ <b>{outcome.replace('_', ' ')}</b>"

        pnl_str = f"{trade['realized_pnl_pct']:+0.2f}% ({trade['realized_r']:+0.2f}R)"
        max_c = int(trade.get("max_candles", 5))
        duration_str = f"Candle {trade['hit_on_candle']} of {max_c}"

        stats = self.get_statistics()
        win_rate = stats.get("win_rate_pct", 0.0)
        total_closed = stats.get("total_closed", 0)

        msg = (
            f"{header}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Asset:</b> {trade['name']} (<code>{trade['symbol']}</code>)\n"
            f"<b>Timeframe:</b> {trade['timeframe']} | <b>Direction:</b> {trade['direction']}\n"
            f"<b>Result:</b> {badge} | <b>Return:</b> <code>{pnl_str}</code>\n\n"
            f"📊 <b>Execution Summary:</b>\n"
            f"• <b>Entry:</b> <code>{trade['entry_price']}</code>\n"
            f"• <b>Exit:</b> <code>{trade['exit_price']}</code>\n"
            f"• <b>Reason:</b> <i>{trade['exit_reason']}</i>\n"
            f"• <b>Duration:</b> {duration_str}\n"
            f"• <b>Initial Conviction:</b> <b>{trade['conviction']}%</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Overall System Accuracy:</b> <b>{win_rate}%</b> ({stats.get('wins', 0)}W - {stats.get('losses', 0)}L out of {total_closed} trades)\n"
            f"⏰ <i>{trade['closed_at']}</i>"
        )
        try:
            await telegram_notifier.send_message(msg)
        except Exception as e:
            logger.warning(f"Could not send resolution telegram: {e}")

    def get_statistics(self, min_conviction: Optional[float] = None) -> Dict[str, Any]:
        """Calculates win rate, profit factor, R-multiples, and conviction breakdown."""
        filtered = self.closed_trades
        if min_conviction is not None:
            filtered = [t for t in filtered if t.get("conviction", 0) >= min_conviction]

        total = len(filtered)
        if total == 0:
            return {
                "total_closed": 0,
                "active_count": len(self.active_trades),
                "wins": 0,
                "losses": 0,
                "expired": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "avg_r": 0.0,
                "total_realized_r": 0.0
            }

        wins = sum(1 for t in filtered if t.get("outcome") in ["WIN", "EXPIRED_PROFIT"])
        losses = sum(1 for t in filtered if t.get("outcome") in ["LOSS", "EXPIRED_LOSS"])
        expired = sum(1 for t in filtered if "EXPIRED" in str(t.get("outcome")))

        tp_wins = sum(1 for t in filtered if t.get("outcome") == "WIN")
        sl_losses = sum(1 for t in filtered if t.get("outcome") == "LOSS")
        exp_wins = sum(1 for t in filtered if t.get("outcome") == "EXPIRED_PROFIT")
        exp_losses = sum(1 for t in filtered if t.get("outcome") == "EXPIRED_LOSS")
        exp_breakeven = sum(1 for t in filtered if t.get("outcome") == "EXPIRED_BREAKEVEN")
        exp_pnl_r = round(sum(t.get("realized_r", 0) for t in filtered if "EXPIRED" in str(t.get("outcome"))), 2)
        tp_pnl_r = round(sum(t.get("realized_r", 0) for t in filtered if t.get("outcome") == "WIN"), 2)
        sl_pnl_r = round(sum(t.get("realized_r", 0) for t in filtered if t.get("outcome") == "LOSS"), 2)

        gross_profit = sum(t.get("realized_r", 0) for t in filtered if t.get("realized_r", 0) > 0)
        gross_loss = abs(sum(t.get("realized_r", 0) for t in filtered if t.get("realized_r", 0) < 0))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (round(gross_profit, 2) if gross_profit > 0 else 1.0)

        total_r = sum(t.get("realized_r", 0) for t in filtered)
        avg_r = round(total_r / total, 2) if total > 0 else 0.0
        win_rate = round((wins / total) * 100.0, 1) if total > 0 else 0.0

        return {
            "total_closed": total,
            "active_count": len(self.active_trades),
            "wins": wins,
            "losses": losses,
            "expired": expired,
            "tp_wins": tp_wins,
            "sl_losses": sl_losses,
            "exp_wins": exp_wins,
            "exp_losses": exp_losses,
            "exp_breakeven": exp_breakeven,
            "exp_pnl_r": exp_pnl_r,
            "tp_pnl_r": tp_pnl_r,
            "sl_pnl_r": sl_pnl_r,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "avg_r": avg_r,
            "total_realized_r": round(total_r, 2)
        }

    def get_trades_log(self, limit: int = 50) -> Dict[str, Any]:
        """Returns recent active and closed trades enriched with dynamic countdown metrics."""
        now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        step_map = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}
        
        enriched_active = []
        for t in self.active_trades:
            t_copy = dict(t)
            max_c = int(t_copy.get("max_candles", 5))
            mon = int(t_copy.get("candles_monitored", 0))
            t_copy["candles_remaining"] = max(0, max_c - mon)
            
            tf = t_copy.get("timeframe", "1h").lower()
            step_sec = t_copy.get("step_seconds") or step_map.get(tf, 3600)
            entry_unix = t_copy.get("entry_candle_unix") or t_copy.get("opened_unix", now_ts)
            exp_unix = t_copy.get("expires_at_unix") or (entry_unix + (max_c * step_sec))
            t_copy["expires_at_unix"] = exp_unix
            t_copy["seconds_remaining"] = max(0, exp_unix - now_ts)
            enriched_active.append(t_copy)

        return {
            "active": enriched_active,
            "closed": self.closed_trades[:limit],
            "stats": self.get_statistics()
        }

    def clear_history(self):
        """Clears active and closed trades ledger."""
        self.active_trades = []
        self.closed_trades = []
        self._save()
        logger.info("Trade outcomes history cleared.")


# Global singleton
outcome_tracker = OutcomeTracker()
