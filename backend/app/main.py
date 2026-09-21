import os
import asyncio
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
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
from app.market_liveness import market_liveness

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TradingTerminal")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to spin up background scanner."""
    logger.info("Initializing AI Trading Forecast Terminal...")
    logger.info(f"Hardware Compute Device: {DEVICE}")

    # Auto-connect and sync from MT5 if available
    try:
        if mt5_bridge.initialize():
            logger.info("Auto-syncing universe from connected FundedNext MT5 terminal...")
            mt5_bridge.sync_watchlist_from_mt5()
    except Exception as e_sync:
        logger.debug(f"MT5 auto-sync on boot skipped: {e_sync}")

    # Pre-warm TimesFM 2.5 Arbiter in background thread
    try:
        cfg = config_manager.get_all()
        if cfg.get("timesfm", {}).get("enabled", True):
            logger.info("Pre-warming TimesFM 2.5 Foundation Model Arbiter...")
            timesfm_arbiter.start_background_load()
    except Exception as e_tfm:
        logger.debug(f"TimesFM pre-warm skipped: {e_tfm}")

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


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


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
    forecast_candles: Optional[int] = None
    show_countdown_timers: Optional[bool] = None
    show_chart_trade_markers: Optional[bool] = None
    timesfm_enabled: Optional[bool] = None
    timesfm_conviction_boost: Optional[float] = None
    timesfm_suppress_on_conflict: Optional[bool] = None
    default_dollar_risk: Optional[float] = None
    auto_trade_enabled: Optional[bool] = None
    auto_trade_min_conviction: Optional[float] = None
    auto_trade_dual_ai_only: Optional[bool] = None
    split_tp_mode: Optional[bool] = None
    auto_close_on_expiry: Optional[bool] = None
    auto_trade_timeframes: Optional[List[str]] = None


class CalculateLotsRequest(BaseModel):
    symbol: str
    entry_price: float
    stop_loss: float
    dollar_risk: float = 50.0
    take_profit: Optional[float] = None


class ExecuteOrderRequest(BaseModel):
    symbol: str
    direction: str
    timeframe: Optional[str] = "1h"
    entry_price: Optional[float] = None
    dollar_risk: Optional[float] = 50.0
    lots: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    tp2: Optional[float] = None
    split_tp: Optional[bool] = False
    comment: Optional[str] = "AI Quant Signal"


class ClosePositionRequest(BaseModel):
    ticket: int
    comment: Optional[str] = "Manual Close"


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


@app.get("/api/market/liveness")
async def get_market_liveness(symbol: str = Query("EURUSD"), timeframe: str = Query("1h")):
    """Evaluates broker liveness, tick freshness, and market open/close status for a symbol."""
    return market_liveness.check_liveness(symbol, timeframe)


@app.get("/api/mt5/status")
async def get_mt5_status():
    """Returns MT5 connection state, broker server, and account details."""
    return mt5_bridge.get_status()


@app.post("/api/mt5/connect")
async def connect_mt5():
    """Attempts to connect to the running MetaTrader 5 terminal."""
    success = mt5_bridge.initialize()
    return {"success": success, "status": mt5_bridge.get_status()}


@app.post("/api/mt5/sync-universe")
async def sync_mt5_universe():
    """Syncs the entire 96-asset universe directly from FundedNext MetaTrader 5."""
    watchlist = mt5_bridge.sync_watchlist_from_mt5()
    if not watchlist:
        raise HTTPException(
            status_code=400,
            detail=mt5_bridge.last_error or "MetaTrader 5 terminal not connected. Please ensure MT5 is running."
        )
    return {
        "status": "success",
        "synced_count": len(watchlist),
        "watchlist": watchlist
    }


@app.post("/api/mt5/calculate-lots")
async def calculate_lots(req: CalculateLotsRequest):
    """Calculates position size in lots based on dollar risk ($) and SL distance."""
    result = mt5_bridge.calculate_lot_size(
        symbol=req.symbol,
        entry_price=req.entry_price,
        stop_loss=req.stop_loss,
        dollar_risk=req.dollar_risk,
        take_profit=req.take_profit
    )
    return result


@app.post("/api/mt5/execute-order")
async def execute_mt5_order(req: ExecuteOrderRequest):
    """Executes a live market order directly on FundedNext MetaTrader 5."""
    result = mt5_bridge.execute_order(
        symbol=req.symbol,
        direction=req.direction,
        dollar_risk=req.dollar_risk,
        lots=req.lots,
        sl=req.sl,
        tp=req.tp,
        tp2=req.tp2,
        split_tp=req.split_tp or False,
        comment=req.comment or "AI Quant Terminal"
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Order execution failed"))

    # Link tickets to active outcome tracking so lifespan auto-close protects manual trades
    tickets = result.get("tickets") or ([result["ticket"]] if "ticket" in result else [])
    if tickets:
        sig_data = None
        if req.entry_price and req.sl and req.tp:
            sig_data = {
                "symbol": req.symbol,
                "direction": req.direction.upper(),
                "timeframe": req.timeframe or "1h",
                "entry_price": req.entry_price,
                "stop_loss": req.sl,
                "take_profit_1": req.tp,
                "take_profit_2": req.tp2 or req.tp,
                "sl_distance": abs(req.entry_price - req.sl),
                "tp_distance": abs(req.tp - req.entry_price),
                "conviction": 75.0,
                "is_actionable": True
            }
        outcome_tracker.attach_mt5_tickets(
            symbol=req.symbol,
            timeframe=req.timeframe or "1h",
            tickets=tickets,
            manual=True,
            signal_data=sig_data
        )

    return result


@app.post("/api/mt5/close-position")
async def close_mt5_position(req: ClosePositionRequest):
    """Closes an open position on MetaTrader 5 terminal at market price."""
    result = mt5_bridge.close_position(ticket=req.ticket, comment=req.comment or "Manual Close")
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to close position"))
    return result


@app.get("/api/mt5/positions")
async def get_mt5_positions():
    """Returns currently open positions on MetaTrader 5."""
    return {"positions": mt5_bridge.get_open_positions()}


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

    # 3. Generate AI forecast with configurable horizon length
    forecast_len = int(config_manager.get("forecast_candles", 5))
    forecast = ai_engine.forecast_next_5(df, interval=tf, prediction_length=forecast_len)

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

    # 6. Check for active trade tracking in outcome tracker
    active_trade = next(
        (t for t in outcome_tracker.active_trades if t["symbol"].upper() == symbol.upper() and t["timeframe"] == tf),
        None
    )
    if active_trade:
        active_trade = outcome_tracker._sanitize_trade(active_trade)

    return {
        "symbol": symbol,
        "name": asset_info.get("name", symbol),
        "category": asset_info.get("category", "General"),
        "timeframe": tf,
        "historical_count": len(historical_candles),
        "candles": historical_candles,
        "forecast": forecast,
        "signal": signal,
        "active_trade": active_trade,
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


class ImportHistoryRequest(BaseModel):
    active_trades: Optional[List[Dict[str, Any]]] = []
    closed_trades: Optional[List[Dict[str, Any]]] = []
    merge: Optional[bool] = True


@app.get("/api/performance")
async def get_performance(
    min_conviction: Optional[float] = Query(None),
    timeframe: Optional[str] = Query(None),
    dual_ai_only: Optional[bool] = Query(None),
    limit: int = Query(100)
):
    """
    Returns closed and active trade outcome metrics, win-rate, profit factor,
    and performance filtered by minimum conviction %, timeframe, and Dual AI status.
    """
    stats = outcome_tracker.get_statistics(min_conviction=min_conviction, timeframe=timeframe, dual_ai_only=dual_ai_only)
    trades = outcome_tracker.get_trades_log(limit=limit, timeframe=timeframe, dual_ai_only=dual_ai_only)
    return {
        "stats": stats,
        "active_trades": trades["active"],
        "closed_trades": trades["closed"],
        "total_closed_count": trades.get("total_closed_count", len(trades["closed"]))
    }


@app.get("/api/performance/export")
async def export_performance_history(
    format: str = Query("json", description="Export format: 'json' or 'csv'"),
    timeframe: Optional[str] = Query(None, description="Optional timeframe filter")
):
    """Exports full trade outcome ledger as a downloadable JSON or CSV file (ready for Excel)."""
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    tf_tag = f"_{timeframe}" if timeframe and timeframe.upper() != "ALL" else ""

    if format.lower() == "csv":
        csv_content = outcome_tracker.export_csv(timeframe=timeframe)
        headers = {
            "Content-Disposition": f'attachment; filename="trade_history{tf_tag}_{now_str}.csv"'
        }
        return Response(content=csv_content, media_type="text/csv", headers=headers)
    else:
        data = outcome_tracker.export_history(timeframe=timeframe)
        headers = {
            "Content-Disposition": f'attachment; filename="trade_history{tf_tag}_{now_str}.json"'
        }
        return JSONResponse(content=data, headers=headers)


@app.post("/api/performance/clear")
async def clear_performance_history(backup: bool = Query(True)):
    """Clears all active and closed trades from memory and storage, creating a safety backup first."""
    try:
        res = outcome_tracker.clear_history(backup=backup)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/performance/import")
async def import_performance_history(req: ImportHistoryRequest):
    """Imports or merges trade history ledger from JSON."""
    try:
        res = outcome_tracker.import_history({
            "active_trades": req.active_trades or [],
            "closed_trades": req.closed_trades or []
        }, merge=req.merge if req.merge is not None else True)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    if req.forecast_candles is not None:
        updates["forecast_candles"] = max(1, min(20, req.forecast_candles))
    if req.show_countdown_timers is not None:
        strat["show_countdown_timers"] = req.show_countdown_timers
    if req.show_chart_trade_markers is not None:
        strat["show_chart_trade_markers"] = req.show_chart_trade_markers
    if req.default_dollar_risk is not None:
        strat["default_dollar_risk"] = max(1.0, float(req.default_dollar_risk))
    if req.auto_trade_enabled is not None:
        strat["auto_trade_enabled"] = req.auto_trade_enabled
    if req.auto_trade_min_conviction is not None:
        strat["auto_trade_min_conviction"] = float(req.auto_trade_min_conviction)
    if req.auto_trade_dual_ai_only is not None:
        strat["auto_trade_dual_ai_only"] = req.auto_trade_dual_ai_only
    if req.split_tp_mode is not None:
        strat["split_tp_mode"] = req.split_tp_mode
    if req.auto_close_on_expiry is not None:
        strat["auto_close_on_expiry"] = req.auto_close_on_expiry
    if req.auto_trade_timeframes is not None:
        strat["auto_trade_timeframes"] = [t.lower() for t in req.auto_trade_timeframes]

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
