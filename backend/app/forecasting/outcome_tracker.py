import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

from app.data_fetcher import MarketDataFetcher
from app.telegram_bot import telegram_notifier
from app.market_liveness import market_liveness

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
            "mt5_tickets": signal.get("mt5_tickets", []),
            "auto_traded": bool(signal.get("auto_traded", False)),
            "manual_executed": bool(signal.get("manual_executed", False)),
            "status": "ACTIVE"
        }

        self.active_trades.append(trade_entry)
        self._save()
        logger.info(f"Registered trade for tracking: {trade_id}")
        return True

    def attach_mt5_tickets(
        self,
        symbol: str,
        timeframe: Optional[str],
        tickets: List[int],
        manual: bool = False,
        signal_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Associates MT5 order tickets (from manual 1-click or automated executions)
        with an active trade so they are monitored and auto-closed upon lifespan expiration.
        """
        if not tickets:
            return False
        sym_clean = symbol.strip().upper()
        tf_clean = (timeframe or "1h").lower()

        # 1. Search existing active trades
        found = False
        for trade in self.active_trades:
            t_sym = trade.get("symbol", "").upper()
            t_tf = trade.get("timeframe", "1h").lower()
            if t_sym == sym_clean and (timeframe is None or t_tf == tf_clean):
                if "mt5_tickets" not in trade or not isinstance(trade["mt5_tickets"], list):
                    trade["mt5_tickets"] = []
                for tk in tickets:
                    if tk not in trade["mt5_tickets"]:
                        trade["mt5_tickets"].append(tk)
                if manual:
                    trade["manual_executed"] = True
                found = True
                break

        # 2. If no active trade exists yet for this symbol & timeframe, register it
        if not found and signal_data:
            sig = dict(signal_data)
            sig["symbol"] = sym_clean
            sig["timeframe"] = tf_clean
            sig["mt5_tickets"] = tickets
            sig["manual_executed"] = manual
            sig.setdefault("timestamp", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
            self.register_signal(sig)
            found = True

        if found:
            self._save()
            logger.info(f"Attached MT5 tickets {tickets} to active trade {sym_clean} ({tf_clean}) (manual={manual})")
            return True
        return False

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

                # Pause evaluation if market is closed or stagnant on active broker
                liveness = market_liveness.check_liveness(sym, tf, df)
                if not liveness.get("is_open", True):
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

                    # Auto-close associated MT5 positions upon lifespan expiration
                    if outcome.startswith("EXPIRED") and trade.get("mt5_tickets"):
                        try:
                            from app.config import config_manager
                            from app.mt5_bridge import mt5_bridge
                            strat_cfg = config_manager.get("strategy", {})
                            if strat_cfg.get("auto_close_on_expiry", True):
                                for ticket in trade["mt5_tickets"]:
                                    logger.info(f"Liquidating MT5 ticket #{ticket} on signal lifespan expiration for trade {trade.get('id')}...")
                                    res_close = mt5_bridge.close_position(ticket, comment=f"AI Expiry ({trade.get('timeframe')})")
                                    logger.info(f"MT5 ticket #{ticket} close result: {res_close}")
                                trade["mt5_closed"] = True
                        except Exception as e_close:
                            logger.error(f"Failed auto-closing MT5 positions for expired trade {trade.get('id')}: {e_close}")

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

    def get_statistics(
        self,
        min_conviction: Optional[float] = None,
        timeframe: Optional[str] = None,
        dual_ai_only: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Calculates win rate, profit factor, R-multiples, and conviction breakdown with optional timeframe and Dual AI filters."""
        filtered = self.closed_trades
        active = self.active_trades

        if min_conviction is not None:
            filtered = [t for t in filtered if t.get("conviction", 0) >= min_conviction]

        if dual_ai_only:
            filtered = [t for t in filtered if t.get("dual_ai_confluence") is True]
            active = [t for t in active if t.get("dual_ai_confluence") is True]

        if timeframe and timeframe.upper() != "ALL":
            tf_set = {x.strip().lower() for x in timeframe.split(",") if x.strip()}
            filtered = [t for t in filtered if (t.get("timeframe") or "").lower() in tf_set]
            active_cnt = len([t for t in active if (t.get("timeframe") or "").lower() in tf_set])
        else:
            active_cnt = len(active)

        total = len(filtered)
        if total == 0:
            return {
                "total_closed": 0,
                "active_count": active_cnt,
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
            "active_count": active_cnt,
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

    def get_trades_log(
        self,
        limit: Optional[int] = 50,
        timeframe: Optional[str] = None,
        dual_ai_only: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Returns active and closed trades enriched with dynamic countdown metrics with optional timeframe and Dual AI filters."""
        now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        step_map = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}
        
        raw_active = self.active_trades
        raw_closed = self.closed_trades

        if dual_ai_only:
            raw_active = [t for t in raw_active if t.get("dual_ai_confluence") is True]
            raw_closed = [t for t in raw_closed if t.get("dual_ai_confluence") is True]

        if timeframe and timeframe.upper() != "ALL":
            tf_set = {x.strip().lower() for x in timeframe.split(",") if x.strip()}
            raw_active = [t for t in raw_active if (t.get("timeframe") or "").lower() in tf_set]
            raw_closed = [t for t in raw_closed if (t.get("timeframe") or "").lower() in tf_set]

        enriched_active = []
        for t in raw_active:
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

            # Check market liveness for active trade
            liveness = market_liveness.check_liveness(t_copy.get("symbol", ""), tf)
            is_open = liveness.get("is_open", True)
            t_copy["is_market_open"] = is_open
            t_copy["market_reason"] = liveness.get("reason", "")
            t_copy["is_market_paused"] = not is_open

            enriched_active.append(t_copy)

        closed_slice = raw_closed[:limit] if (limit is not None and limit > 0) else raw_closed

        return {
            "active": enriched_active,
            "closed": closed_slice,
            "total_closed_count": len(raw_closed),
            "stats": self.get_statistics(timeframe=timeframe)
        }

    def export_history(
        self,
        timeframe: Optional[str] = None,
        min_conviction: Optional[float] = None,
        dual_ai_only: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Exports trade history database, with optional timeframe, conviction, and Dual AI filtering."""
        closed = self.closed_trades
        active = self.active_trades

        if dual_ai_only:
            closed = [t for t in closed if t.get("dual_ai_confluence") is True]
            active = [t for t in active if t.get("dual_ai_confluence") is True]

        if min_conviction is not None and min_conviction > 0:
            closed = [t for t in closed if float(t.get("conviction", 0)) >= min_conviction]
            active = [t for t in active if float(t.get("conviction", 0)) >= min_conviction]

        if timeframe and timeframe.upper() != "ALL":
            tf_set = {x.strip().lower() for x in timeframe.split(",") if x.strip()}
            closed = [t for t in closed if (t.get("timeframe") or "").lower() in tf_set]
            active = [t for t in active if (t.get("timeframe") or "").lower() in tf_set]

        return {
            "version": "1.0",
            "exported_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "filter_timeframe": timeframe or "ALL",
            "filter_min_conviction": min_conviction,
            "filter_dual_ai_only": bool(dual_ai_only),
            "total_closed": len(closed),
            "total_active": len(active),
            "statistics": self.get_statistics(timeframe=timeframe, min_conviction=min_conviction, dual_ai_only=dual_ai_only),
            "active_trades": active,
            "closed_trades": closed
        }

    def export_csv(
        self,
        timeframe: Optional[str] = None,
        min_conviction: Optional[float] = None,
        dual_ai_only: Optional[bool] = None
    ) -> str:
        """Exports closed and active trades as a CSV string formatted for Excel / Sheets with optional filters."""
        import io
        import csv

        closed = self.closed_trades
        if dual_ai_only:
            closed = [t for t in closed if t.get("dual_ai_confluence") is True]

        if min_conviction is not None and min_conviction > 0:
            closed = [t for t in closed if float(t.get("conviction", 0)) >= min_conviction]

        if timeframe and timeframe.upper() != "ALL":
            tf_set = {x.strip().lower() for x in timeframe.split(",") if x.strip()}
            closed = [t for t in closed if (t.get("timeframe") or "").lower() in tf_set]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Symbol", "Timeframe", "Direction", "Conviction (%)",
            "Entry Price", "Exit Price", "Stop Loss", "Take Profit 1", "Take Profit 2",
            "Outcome", "Realized PnL (%)", "Realized R", "Duration (Bars)", "Max Candles",
            "Opened At (UTC)", "Closed At (UTC)", "Session", "Exit Reason", "Dual AI Confluence"
        ])

        for t in closed:
            writer.writerow([
                t.get("id", ""),
                t.get("symbol", ""),
                t.get("timeframe", ""),
                t.get("direction", ""),
                t.get("conviction", ""),
                t.get("entry_price", ""),
                t.get("exit_price", ""),
                t.get("stop_loss") or t.get("sl", ""),
                t.get("take_profit_1") or t.get("tp", ""),
                t.get("take_profit_2") or t.get("tp2", ""),
                t.get("outcome", ""),
                t.get("realized_pnl_pct", ""),
                t.get("realized_r", ""),
                t.get("hit_on_candle", t.get("candles_monitored", "")),
                t.get("max_candles", 5),
                t.get("opened_at", ""),
                t.get("closed_at", ""),
                t.get("session_name", ""),
                t.get("exit_reason", ""),
                t.get("dual_ai_confluence", False)
            ])
        return output.getvalue()

    def import_history(self, payload: Dict[str, Any], merge: bool = True) -> Dict[str, Any]:
        """Imports trade history, sanitizes entries, deduplicates, and saves."""
        imported_active = payload.get("active_trades", [])
        imported_closed = payload.get("closed_trades", [])

        if not isinstance(imported_active, list) or not isinstance(imported_closed, list):
            raise ValueError("Invalid import format: active_trades and closed_trades must be arrays")

        sanitized_active = [self._sanitize_trade(t) for t in imported_active]
        sanitized_closed = [self._sanitize_trade(t) for t in imported_closed]

        if merge:
            existing_active_ids = {t["id"] for t in self.active_trades if "id" in t}
            existing_closed_ids = {t["id"] for t in self.closed_trades if "id" in t}

            new_active_count = 0
            for t in sanitized_active:
                if t.get("id") not in existing_active_ids:
                    self.active_trades.append(t)
                    if t.get("id"):
                        existing_active_ids.add(t["id"])
                    new_active_count += 1

            new_closed_count = 0
            for t in sanitized_closed:
                if t.get("id") not in existing_closed_ids:
                    self.closed_trades.append(t)
                    if t.get("id"):
                        existing_closed_ids.add(t["id"])
                    new_closed_count += 1
        else:
            self.active_trades = sanitized_active
            self.closed_trades = sanitized_closed
            new_active_count = len(sanitized_active)
            new_closed_count = len(sanitized_closed)

        self._save()
        logger.info(f"Imported trade history: {new_active_count} active, {new_closed_count} closed.")
        return {
            "status": "success",
            "new_active_count": new_active_count,
            "new_closed_count": new_closed_count,
            "total_active": len(self.active_trades),
            "total_closed": len(self.closed_trades)
        }

    def clear_history(self, backup: bool = True) -> Dict[str, Any]:
        """Clears active and closed trades ledger with automatic backup preservation."""
        backup_file = None
        if backup and self.storage_path.exists() and (self.active_trades or self.closed_trades):
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_file = self.storage_path.parent / f"trade_outcomes_backup_{ts}.json"
            try:
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "active_trades": self.active_trades,
                        "closed_trades": self.closed_trades,
                        "backed_up_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    }, f, indent=2)
                logger.info(f"Created trade history backup: {backup_file}")
            except Exception as e:
                logger.warning(f"Failed to create backup before clear: {e}")

        prev_closed = len(self.closed_trades)
        prev_active = len(self.active_trades)
        self.active_trades = []
        self.closed_trades = []
        self._save()
        logger.info(f"Cleared {prev_closed} closed and {prev_active} active trades.")
        return {
            "status": "success",
            "cleared_closed": prev_closed,
            "cleared_active": prev_active,
            "backup_saved": backup_file.name if backup_file else None,
            "message": f"Successfully cleared {prev_closed} closed trades from memory & disk." + (f" Backup saved to {backup_file.name}" if backup_file else "")
        }


# Global singleton
outcome_tracker = OutcomeTracker()
