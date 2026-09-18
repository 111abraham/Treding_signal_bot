import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import config_manager
from app.data_fetcher import MarketDataFetcher, get_current_session_info
from app.forecasting.chronos_engine import ai_engine, DEVICE
from app.forecasting.signal_generator import signal_generator
from app.forecasting.outcome_tracker import outcome_tracker
from app.telegram_bot import telegram_notifier
from app.scheduler import scan_engine, background_scheduler_loop
from app.forecasting.timesfm_arbiter import timesfm_arbiter
from app.mt5_bridge import mt5_bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TradingTerminal")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to spin up background scanner."""
    logger.info("Initializing AI Trading Forecast Terminal...")
    logger.info(f"Hardware Compute Device: {DEVICE}")
    scheduler_task = asyncio.create_task(background_scheduler_loop())
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    logger.info("Terminal shutdown complete.")


app = FastAPI(
    title="AI Quant Trading Forecast Terminal",
    description="Multi-horizon AI 5-step candlestick forecast with Telegram signals and spread/session guardrails",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving
if (FRONTEND_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


# Pydantic Schemas
class WatchlistAddRequest(BaseModel):
    symbol: str
    name: str
    category: str
    est_spread_pct: float = 0.02


class WatchlistToggleRequest(BaseModel):
    symbol: str
    active: bool


class TelegramSettingsRequest(BaseModel):
    bot_token: str
    chat_id: str
    enabled: bool


class StrategySettingsRequest(BaseModel):
    timeframe: Optional[str] = None
    scan_timeframes: Optional[List[str]] = None
    max_spread_to_sl_ratio: Optional[float] = None
    require_london_ny_overlap: Optional[bool] = None
    min_conviction: Optional[float] = None
    scan_interval_minutes: Optional[int] = None
    auto_scan_enabled: Optional[bool] = None
    timesfm_enabled: Optional[bool] = None
    timesfm_conviction_boost: Optional[float] = None
    timesfm_suppress_on_conflict: Optional[bool] = None


# Routes
@app.get("/")
async def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse({"message": "Frontend index.html not yet found. Backend API is active."})
    return FileResponse(str(index_path))


@app.get("/api/status")
async def get_system_status():
    session_info = get_current_session_info()
    return {
        "status": "online",
        "device": DEVICE,
        "active_session": session_info["active_session"],
        "is_london_ny_overlap": session_info["is_london_ny_overlap"],
        "is_scanning": scan_engine.is_scanning,
        "scan_status_text": scan_engine.current_status,
        "last_scan_time": scan_engine.last_scan_time,
        "timeframe": config_manager.get("timeframe", "1h"),
        "timesfm": timesfm_arbiter.get_status(),
        "mt5": mt5_bridge.get_status()
    }


@app.get("/api/mt5/status")
async def get_mt5_status():
    """Returns MT5 connection state, broker server, and account details."""
    return mt5_bridge.get_status()


@app.post("/api/mt5/connect")
async def connect_mt5():
    """Attempts to connect to the running MetaTrader 5 terminal."""
    success = mt5_bridge.initialize()
    return {"success": success, "status": mt5_bridge.get_status()}


@app.get("/api/watchlist")
async def get_watchlist():
    return {
        "watchlist": config_manager.get_watchlist(),
        "categories": ["Forex", "Indices", "Crypto", "Stocks"]
    }


@app.post("/api/watchlist/add")
async def add_to_watchlist(req: WatchlistAddRequest):
    updated = config_manager.add_symbol(req.symbol, req.name, req.category, req.est_spread_pct)
    return {"status": "success", "watchlist": updated}


@app.post("/api/watchlist/toggle")
async def toggle_in_watchlist(req: WatchlistToggleRequest):
    updated = config_manager.toggle_symbol(req.symbol, req.active)
    return {"status": "success", "watchlist": updated}


@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    updated = config_manager.remove_symbol(symbol)
    return {"status": "success", "watchlist": updated}


@app.get("/api/chart/{symbol}")
async def get_chart_and_forecast(symbol: str, timeframe: Optional[str] = None):
    """
    Returns 500 historical candles formatted for TradingView Lightweight Charts,
    plus 5 AI-predicted future candles with quantile confidence bounds and trade evaluation.
    """
    tf = timeframe or config_manager.get("timeframe", "1h")
    
    # 1. Fetch 500 historical candles
    df, err = MarketDataFetcher.fetch_candles(symbol, interval=tf, target_count=500)
    if err or df.empty:
        raise HTTPException(status_code=400, detail=err or "No data available for symbol")

    df.attrs["symbol"] = symbol

    # 2. Convert historical to TradingView format
    historical_candles = MarketDataFetcher.format_for_tradingview(df)

    # 3. Generate 5-step AI forecast
    forecast = ai_engine.forecast_next_5(df, interval=tf, prediction_length=5)

    # 4. Find asset config for spread & evaluation
    watchlist = config_manager.get_watchlist()
    asset_info = next((item for item in watchlist if item["symbol"].upper() == symbol.upper()), {
        "symbol": symbol,
        "name": symbol,
        "category": "Custom",
        "est_spread_pct": 0.02
    })

    strat_cfg = config_manager.get("strategy", {})
    signal = signal_generator.evaluate_signal(forecast, df, asset_info, strat_cfg)
    if signal and signal.get("is_actionable"):
        timesfm_cfg = config_manager.get("timesfm", {})
        if timesfm_cfg.get("enabled", True):
            signal = timesfm_arbiter.evaluate_candidate(df["Close"].values, signal, timesfm_cfg)

    # 5. Compute Higher-Timeframe Confluence (so 5m users never miss HTF picture)
    htf_confluence = MarketDataFetcher.compute_htf_alignment(symbol)

    return {
        "symbol": symbol,
        "name": asset_info.get("name", symbol),
        "category": asset_info.get("category", "General"),
        "timeframe": tf,
        "historical_count": len(historical_candles),
        "candles": historical_candles,
        "forecast": forecast,
        "signal": signal,
        "htf_confluence": htf_confluence,
        "session": get_current_session_info()
    }


@app.get("/api/htf-radar")
async def get_htf_radar():
    """
    Returns active Higher Timeframe (1h, 4h) opportunities across the watchlist
    so scalpers on 5m are alerted to institutional macro setups immediately.
    """
    signals = scan_engine.get_history()
    # Filter for HTF setups (1h or 4h) with high conviction
    htf_signals = [s for s in signals if s.get("timeframe") in ["1h", "4h", "1d"]]
    return {
        "count": len(htf_signals),
        "opportunities": htf_signals[:6]
    }


@app.get("/api/performance")
async def get_performance(min_conviction: Optional[float] = Query(None)):
    """
    Returns closed and active trade outcome metrics, win-rate, profit factor,
    and performance filtered by minimum conviction %.
    """
    stats = outcome_tracker.get_statistics(min_conviction=min_conviction)
    trades = outcome_tracker.get_trades_log(limit=50)
    return {
        "stats": stats,
        "active_trades": trades["active"],
        "closed_trades": trades["closed"]
    }


@app.post("/api/performance/evaluate")
async def trigger_performance_evaluation(background_tasks: BackgroundTasks):
    """Manually triggers evaluation of all active trades against recent candles."""
    cfg = config_manager.get_all()
    telegram_enabled = cfg.get("telegram", {}).get("enabled", False)
    background_tasks.add_task(outcome_tracker.evaluate_active_trades, telegram_enabled)
    return {"status": "started", "message": "Outcome evaluation running in background"}


@app.post("/api/performance/reset")
async def reset_performance():
    """Clears the trade outcome history and statistics ledger."""
    outcome_tracker.clear_history()
    return {"status": "success", "message": "Outcome tracking history reset successfully"}


@app.post("/api/scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    """Manually triggers an immediate scan of all active watchlist assets."""
    if scan_engine.is_scanning:
        return {"status": "in_progress", "message": "Scan already running"}
    
    background_tasks.add_task(scan_engine.scan_all_assets, True)
    return {"status": "started", "message": "Scan cycle initiated across active assets"}


@app.get("/api/signals")
async def get_signals():
    return {
        "signals": scan_engine.get_history(),
        "total": len(scan_engine.get_history())
    }


@app.get("/api/settings")
async def get_settings():
    return config_manager.get_all()


@app.post("/api/settings/strategy")
async def update_strategy_settings(req: StrategySettingsRequest):
    updates: Dict[str, Any] = {}
    if req.timeframe:
        updates["timeframe"] = req.timeframe
    if req.scan_timeframes is not None:
        updates["scan_timeframes"] = req.scan_timeframes
    if req.scan_interval_minutes is not None:
        updates["scan_interval_minutes"] = req.scan_interval_minutes
    if req.auto_scan_enabled is not None:
        updates["auto_scan_enabled"] = req.auto_scan_enabled

    strat = config_manager.get("strategy", {})
    if req.max_spread_to_sl_ratio is not None:
        strat["max_spread_to_sl_ratio"] = req.max_spread_to_sl_ratio
    if req.require_london_ny_overlap is not None:
        strat["require_london_ny_overlap"] = req.require_london_ny_overlap
    if req.min_conviction is not None:
        strat["min_conviction"] = req.min_conviction

    updates["strategy"] = strat
    config_manager.update(updates)

    if req.timesfm_enabled is not None or req.timesfm_conviction_boost is not None or req.timesfm_suppress_on_conflict is not None:
        curr_tfm = config_manager.get("timesfm", {})
        config_manager.update_timesfm(
            enabled=req.timesfm_enabled if req.timesfm_enabled is not None else curr_tfm.get("enabled", True),
            conviction_boost=req.timesfm_conviction_boost if req.timesfm_conviction_boost is not None else curr_tfm.get("conviction_boost", 12.0),
            suppress_on_conflict=req.timesfm_suppress_on_conflict if req.timesfm_suppress_on_conflict is not None else curr_tfm.get("suppress_on_conflict", False)
        )

    return {"status": "success", "config": config_manager.get_all()}


@app.post("/api/settings/telegram")
async def update_telegram_settings(req: TelegramSettingsRequest):
    updated = config_manager.update_telegram(req.bot_token, req.chat_id, req.enabled)
    telegram_notifier.update_credentials(req.bot_token, req.chat_id)
    return {"status": "success", "telegram": updated}


@app.post("/api/telegram/test")
async def test_telegram_connection():
    cfg = config_manager.get("telegram", {})
    telegram_notifier.update_credentials(cfg.get("bot_token", ""), cfg.get("chat_id", ""))
    success, msg = await telegram_notifier.send_test_alert()
    return {"success": success, "message": msg}
