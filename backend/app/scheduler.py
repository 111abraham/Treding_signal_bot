import asyncio
import datetime
import logging
from typing import Dict, Any, List, Optional
from app.config import config_manager
from app.data_fetcher import MarketDataFetcher, get_current_session_info
from app.forecasting.chronos_engine import ai_engine
from app.forecasting.signal_generator import signal_generator
from app.telegram_bot import telegram_notifier
from app.forecasting.outcome_tracker import outcome_tracker
from app.forecasting.timesfm_arbiter import timesfm_arbiter
from app.market_liveness import market_liveness

logger = logging.getLogger(__name__)


class ScanEngine:
    """Orchestrates asset scanning, AI multi-step forecasting, and signal dispatching."""

    def __init__(self):
        self.is_scanning = False
        self.is_initial_boot = True  # Guards against blasting 20+ alerts on startup
        self.last_scan_time: Optional[str] = None
        self.signal_history: List[Dict[str, Any]] = []
        self.latest_forecasts: Dict[str, Dict[str, Any]] = {}
        self.alerted_cooldown: Dict[str, datetime.datetime] = {}
        self.current_status: str = "Idle"

    async def scan_all_assets(self, force_notify: bool = False) -> Dict[str, Any]:
        """Runs a multi-timeframe scan cycle across all active watchlist assets concurrently."""
        if self.is_scanning:
            return {"status": "already_scanning", "message": "A scan is already in progress."}

        # 20:00 - 23:00 UTC Rollover Guard: Suppress signals during daily broker spread expansion
        session_info = get_current_session_info()
        if session_info.get("is_rollover", False) and not force_notify:
            self.current_status = "Signals suppressed: 20:00 - 23:00 UTC Rollover window (Spread risk protection active)."
            logger.info("Scan cycle: 20:00 - 23:00 UTC market rollover window active. Automated alerts suppressed.")
            return {
                "status": "suppressed",
                "message": "Market rollover window active (20:00-23:00 UTC). Signals suppressed to protect against broker spread expansion.",
                "actionable_signals": []
            }

        self.is_scanning = True
        self.current_status = "Initializing multi-timeframe scan..."
        results = []
        new_signals = []

        cfg = config_manager.get_all()
        watchlist = cfg.get("watchlist", [])
        active_assets = [item for item in watchlist if item.get("active", True)]
        # Multi-timeframe list: e.g. ["5m", "15m", "1h", "4h"]
        scan_timeframes = cfg.get("scan_timeframes") or ["5m", "15m", "1h", "4h"]
        if isinstance(scan_timeframes, str):
            scan_timeframes = [scan_timeframes]

        telegram_cfg = cfg.get("telegram", {})
        telegram_enabled = telegram_cfg.get("enabled", False)
        strat_cfg = cfg.get("strategy", {})
        timesfm_cfg = cfg.get("timesfm", {})

        scan_cats = strat_cfg.get("scan_categories")
        if scan_cats and len(scan_cats) > 0:
            scan_cats_lower = [c.lower() for c in scan_cats]
            def _cat_allowed(c: str) -> bool:
                c_low = c.lower()
                if c_low in scan_cats_lower:
                    return True
                if c_low in ("commodities", "metals") and ("commodities" in scan_cats_lower or "metals" in scan_cats_lower):
                    return True
                return False
            active_assets = [item for item in active_assets if _cat_allowed(item.get("category", ""))]

        # Sync telegram credentials
        telegram_notifier.update_credentials(
            telegram_cfg.get("bot_token", ""),
            telegram_cfg.get("chat_id", "")
        )

        try:
            total_combinations = len(active_assets) * len(scan_timeframes)
            completed_count = 0
            sem = asyncio.Semaphore(5)  # 5 concurrent workers for fast, rate-limit-safe downloads

            async def scan_asset_timeframe(asset: Dict[str, Any], tf: str):
                nonlocal completed_count
                sym = asset["symbol"]
                name = asset.get("name", sym)

                async with sem:
                    try:
                        # 1. Fetch 500 candles in thread pool
                        df, err = await asyncio.to_thread(MarketDataFetcher.fetch_candles, sym, tf, 500)
                        if err or df.empty:
                            return None
                        
                        df.attrs["symbol"] = sym

                        # 1b. Check Market & Broker Liveness (Suppress closed / stagnant markets)
                        liveness = market_liveness.check_liveness(sym, tf, df)
                        if not liveness.get("is_open", True):
                            logger.info(f"Skipping {sym} ({tf}): Market closed on active broker ({liveness.get('reason')})")
                            results.append({
                                "symbol": sym,
                                "timeframe": tf,
                                "is_actionable": False,
                                "direction": "NEUTRAL",
                                "market_closed": True,
                                "suppression_reason": liveness.get("reason", "Market is closed on broker")
                            })
                            return None

                        # 2. Run AI multi-step forecast
                        forecast_len = int(cfg.get("forecast_candles", 5))
                        forecast = ai_engine.forecast_next_5(df, interval=tf, prediction_length=forecast_len)
                        self.latest_forecasts[f"{sym}_{tf}"] = forecast

                        # 3. Evaluate trading setup & spread filters
                        signal = signal_generator.evaluate_signal(forecast, df, asset, strat_cfg)
                        if signal:
                            signal["timeframe"] = tf
                            results.append(signal)

                            if signal.get("is_actionable"):
                                # 4. Candidate Arbiter (Google TimesFM 2.5 Cross-Validation)
                                if timesfm_cfg.get("enabled", True):
                                    signal = await asyncio.to_thread(
                                        timesfm_arbiter.evaluate_candidate,
                                        df["Close"].values,
                                        signal,
                                        timesfm_cfg
                                    )

                                if signal.get("is_actionable"):
                                    # 4b. MetaTrader 5 Auto-Execution Engine
                                    auto_trade_enabled = bool(strat_cfg.get("auto_trade_enabled", False))
                                    auto_trade_min_conv = float(strat_cfg.get("auto_trade_min_conviction", 80.0))
                                    auto_trade_dual_ai_only = bool(strat_cfg.get("auto_trade_dual_ai_only", True))
                                    auto_trade_tfs = [t.lower() for t in strat_cfg.get("auto_trade_timeframes", ["1h", "4h"])]
                                    tf_allowed = (tf or "1h").lower() in auto_trade_tfs

                                    auto_trade_sessions = [s.lower() for s in strat_cfg.get("auto_trade_sessions", ["overlap", "london", "new york"])]
                                    curr_session = (signal.get("session_name") or "").lower()
                                    session_allowed = True
                                    if auto_trade_sessions:
                                        session_allowed = any(
                                            (s == "overlap" and "overlap" in curr_session) or
                                            (s == "london" and "london" in curr_session and "overlap" not in curr_session) or
                                            (s in ("ny", "new york") and ("new york" in curr_session or "ny" in curr_session) and "overlap" not in curr_session) or
                                            (s == "asian" and "asian" in curr_session) or
                                            (s in ("off-hours", "offhours") and ("off-hours" in curr_session or "rollover" in curr_session))
                                            for s in auto_trade_sessions
                                        )

                                    auto_trade_cats = [c.lower() for c in strat_cfg.get("auto_trade_categories", [])]
                                    cat_allowed = True
                                    if auto_trade_cats:
                                        asset_cat = (asset.get("category") or "").lower()
                                        cat_allowed = asset_cat in auto_trade_cats or (asset_cat in ("commodities", "metals") and ("commodities" in auto_trade_cats or "metals" in auto_trade_cats))

                                    if auto_trade_enabled and tf_allowed and session_allowed and cat_allowed and signal.get("conviction", 0) >= auto_trade_min_conv:
                                        dual_ai_ok = True
                                        if auto_trade_dual_ai_only:
                                            dual_ai_ok = (signal.get("timesfm_status") == "ready" and signal.get("timesfm_consensus") == "AGREEMENT")

                                        if dual_ai_ok:
                                            try:
                                                from app.mt5_bridge import mt5_bridge
                                                risk_amt = float(strat_cfg.get("default_dollar_risk", 50.0))
                                                is_split = bool(strat_cfg.get("split_tp_mode", False))
                                                logger.info(f"⚡ Auto-executing MT5 trade for {sym} ({tf}) - Conviction: {signal.get('conviction')}% | Risk: ${risk_amt} | Split: {is_split}")
                                                exec_res = await asyncio.to_thread(
                                                    mt5_bridge.execute_order,
                                                    symbol=sym,
                                                    direction=signal["direction"],
                                                    dollar_risk=risk_amt,
                                                    sl=signal["stop_loss"],
                                                    tp=signal["take_profit_1"],
                                                    tp2=signal.get("take_profit_2"),
                                                    split_tp=is_split,
                                                    comment=f"Auto AI {signal.get('conviction'):.0f}%"
                                                )
                                                if exec_res.get("success"):
                                                    tickets = exec_res.get("tickets") or ([exec_res["ticket"]] if "ticket" in exec_res else [])
                                                    signal["mt5_tickets"] = tickets
                                                    signal["auto_traded"] = True
                                                    logger.info(f"✅ Auto-execution successful on MT5 for {sym}: Tickets {tickets}")
                                                elif exec_res.get("guardrail_blocked"):
                                                    signal["guardrail_blocked"] = True
                                                    signal["guardrail_reason"] = exec_res.get("error")
                                                    logger.warning(f"🛡️ Auto-execution paused by Prop Firm Guardrail for {sym}: {exec_res.get('error')}")
                                                else:
                                                    logger.warning(f"⚠️ Auto-execution rejected by MT5 broker for {sym}: {exec_res.get('error')}")
                                            except Exception as e_auto:
                                                logger.error(f"Error during auto-execution on MT5 for {sym}: {e_auto}")

                                    new_signals.append(signal)
                                    self._add_to_history(signal)
                                    outcome_tracker.register_signal(signal)
                                    await self._dispatch_telegram(signal, force_notify, telegram_enabled)
                                    return signal
                    except Exception as ex:
                        logger.error(f"Error scanning {sym} on {tf}: {ex}")
                    finally:
                        completed_count += 1
                        pct = int((completed_count / max(1, total_combinations)) * 100)
                        self.current_status = f"Scanning multi-timeframes: {pct}% ({completed_count}/{total_combinations} tasks)..."
                return None

            # Execute all asset-timeframe tasks concurrently
            tasks = [scan_asset_timeframe(asset, tf) for asset in active_assets for tf in scan_timeframes]
            await asyncio.gather(*tasks)

            self.last_scan_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            self.current_status = f"Completed at {self.last_scan_time}. Scanned {len(scan_timeframes)} TFs across {len(active_assets)} assets. Found {len(new_signals)} actionable signals."

            return {
                "status": "success",
                "scanned_count": len(active_assets),
                "timeframes": scan_timeframes,
                "actionable_signals": new_signals,
                "all_evaluations": results,
                "timestamp": self.last_scan_time
            }

        finally:
            self.is_scanning = False

    def _add_to_history(self, signal: Dict[str, Any]):
        # Prepend to history, retain up to 1000 entries
        self.signal_history.insert(0, signal)
        if len(self.signal_history) > 1000:
            self.signal_history = self.signal_history[:1000]

    def get_history(self) -> List[Dict[str, Any]]:
        return self.signal_history

    async def _dispatch_telegram(self, signal: Dict[str, Any], force_notify: bool, telegram_enabled: bool):
        if not telegram_enabled:
            return
        sym = signal["symbol"]
        tf = signal.get("timeframe", "1h")
        cooldown_key = f"{sym}_{signal['direction']}_{tf}"
        last_alert = self.alerted_cooldown.get(cooldown_key)
        now = datetime.datetime.now(datetime.timezone.utc)

        # Dynamic cooldown based on timeframe:
        # 5m: 20 min | 15m: 40 min | 1h: 90 min | 4h: 4 hr | 1d: 12 hr
        cooldown_secs = {
            "5m": 1200,
            "15m": 2400,
            "1h": 5400,
            "4h": 14400,
            "1d": 43200
        }.get(tf, 3600)

        # Guard against blasting 20+ alerts simultaneously upon terminal boot
        if self.is_initial_boot and not force_notify:
            self.alerted_cooldown[cooldown_key] = now
            logger.info(f"Startup scan: primed alert cooldown for {sym} ({tf}) without blasting telegram.")
            return

        should_send = force_notify or (
            last_alert is None or (now - last_alert).total_seconds() > cooldown_secs
        )

        if should_send:
            success, alert_msg = await telegram_notifier.send_trade_signal(signal)
            if success:
                self.alerted_cooldown[cooldown_key] = now
                logger.info(f"Telegram alert dispatched for {sym} ({tf})")
            else:
                logger.warning(f"Telegram alert failed for {sym}: {alert_msg}")

    def get_latest_forecast(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self.latest_forecasts.get(symbol)


scan_engine = ScanEngine()


async def background_scheduler_loop():
    """Background task running scan_all_assets and tracking active trade outcomes."""
    # Start TimesFM background weight loading if enabled
    if config_manager.get("timesfm", {}).get("enabled", True):
        timesfm_arbiter.start_background_load()

    # Grace delay on boot: lets uvicorn bind socket and open dashboard instantaneously
    await asyncio.sleep(8)

    while True:
        try:
            cfg = config_manager.get_all()
            
            # 1. Evaluate any open/active trades for TP1/SL/Expiration
            try:
                telegram_enabled = cfg.get("telegram", {}).get("enabled", False)
                await outcome_tracker.evaluate_active_trades(notify_telegram=telegram_enabled)
            except Exception as e_out:
                logger.error(f"Error evaluating active trade outcomes: {e_out}")

            # 2. Run automated scan if enabled
            if cfg.get("auto_scan_enabled", True):
                interval_min = max(2, cfg.get("scan_interval_minutes", 5))
                await scan_engine.scan_all_assets()
                # Initial boot is complete after first cycle
                scan_engine.is_initial_boot = False
                await asyncio.sleep(interval_min * 60)
            else:
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}", exc_info=True)
            await asyncio.sleep(60)
