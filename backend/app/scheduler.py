import asyncio
import datetime
import logging
from typing import Dict, Any, List, Optional
from app.config import config_manager
from app.data_fetcher import MarketDataFetcher
from app.forecasting.chronos_engine import ai_engine
from app.forecasting.signal_generator import signal_generator
from app.telegram_bot import telegram_notifier

logger = logging.getLogger(__name__)


class ScanEngine:
    """Orchestrates asset scanning, AI multi-step forecasting, and signal dispatching."""

    def __init__(self):
        self.is_scanning = False
        self.last_scan_time: Optional[str] = None
        self.signal_history: List[Dict[str, Any]] = []
        self.latest_forecasts: Dict[str, Dict[str, Any]] = {}
        self.alerted_cooldown: Dict[str, datetime.datetime] = {}
        self.current_status: str = "Idle"

    async def scan_all_assets(self, force_notify: bool = False) -> Dict[str, Any]:
        """Runs a complete scan cycle across all active watchlist assets."""
        if self.is_scanning:
            return {"status": "already_scanning", "message": "A scan is already in progress."}

        self.is_scanning = True
        self.current_status = "Scanning active assets..."
        results = []
        new_signals = []

        cfg = config_manager.get_all()
        watchlist = cfg.get("watchlist", [])
        active_assets = [item for item in watchlist if item.get("active", True)]
        timeframe = cfg.get("timeframe", "1h")
        telegram_cfg = cfg.get("telegram", {})
        telegram_enabled = telegram_cfg.get("enabled", False)
        strat_cfg = cfg.get("strategy", {})

        # Sync telegram credentials
        telegram_notifier.update_credentials(
            telegram_cfg.get("bot_token", ""),
            telegram_cfg.get("chat_id", "")
        )

        try:
            total = len(active_assets)
            for idx, asset in enumerate(active_assets):
                sym = asset["symbol"]
                name = asset.get("name", sym)
                self.current_status = f"Forecasting {sym} ({idx + 1}/{total})..."
                logger.info(f"Scanning asset {sym} ({name}) on {timeframe}...")

                try:
                    # 1. Fetch 500 candles
                    df, err = MarketDataFetcher.fetch_candles(sym, interval=timeframe, target_count=500)
                    if err or df.empty:
                        logger.warning(f"Could not fetch data for {sym}: {err}")
                        continue
                    
                    df.attrs["symbol"] = sym

                    # 2. Run AI 5-step forecast
                    forecast = ai_engine.forecast_next_5(df, interval=timeframe, prediction_length=5)
                    self.latest_forecasts[sym] = forecast

                    # 3. Evaluate trading setup & spread filters
                    signal = signal_generator.evaluate_signal(forecast, df, asset, strat_cfg)

                    if signal:
                        results.append(signal)

                        # If signal is actionable (passed spread < 5% SL and high conviction)
                        if signal.get("is_actionable"):
                            new_signals.append(signal)
                            self._add_to_history(signal)
                            await self._dispatch_telegram(signal, force_notify, telegram_enabled)

                    # 4. Multi-Timeframe Safety Net: If operating on low timeframe (5m or 15m),
                    # also inspect Higher Timeframe (1h) so the trader never misses macro moves!
                    if timeframe in ["5m", "15m"]:
                        try:
                            df_htf, err_htf = MarketDataFetcher.fetch_candles(sym, interval="1h", target_count=500)
                            if not err_htf and not df_htf.empty:
                                df_htf.attrs["symbol"] = sym
                                fc_htf = ai_engine.forecast_next_5(df_htf, interval="1h", prediction_length=5)
                                sig_htf = signal_generator.evaluate_signal(fc_htf, df_htf, asset, strat_cfg)
                                if sig_htf and sig_htf.get("is_actionable") and sig_htf.get("conviction", 0) >= 70:
                                    sig_htf["is_htf_opportunity"] = True
                                    sig_htf["note"] = "Macro 1h Opportunity detected while on lower timeframe"
                                    new_signals.append(sig_htf)
                                    self._add_to_history(sig_htf)
                                    await self._dispatch_telegram(sig_htf, force_notify, telegram_enabled)
                        except Exception as e_htf:
                            logger.debug(f"HTF check skipped for {sym}: {e_htf}")

                except Exception as e:
                    logger.error(f"Error during scan of {sym}: {e}", exc_info=True)

                # Minor delay to prevent aggressive rate limiting
                await asyncio.sleep(0.1)

            self.last_scan_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            self.current_status = f"Completed at {self.last_scan_time}. Found {len(new_signals)} actionable signals."

            return {
                "status": "success",
                "scanned_count": len(active_assets),
                "actionable_signals": new_signals,
                "all_evaluations": results,
                "timestamp": self.last_scan_time
            }

        finally:
            self.is_scanning = False

    def _add_to_history(self, signal: Dict[str, Any]):
        # Prepend to history, retain max 100 entries
        self.signal_history.insert(0, signal)
        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[:100]

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

        # Alert cooldown: 1.5 hours for same asset, direction, and timeframe
        should_send = force_notify or (
            last_alert is None or (now - last_alert).total_seconds() > 5400
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
    """Background task running scan_all_assets at configured intervals."""
    while True:
        try:
            cfg = config_manager.get_all()
            if cfg.get("auto_scan_enabled", True):
                interval_min = max(5, cfg.get("scan_interval_minutes", 15))
                await scan_engine.scan_all_assets()
                await asyncio.sleep(interval_min * 60)
            else:
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}", exc_info=True)
            await asyncio.sleep(60)
