# ⚡ AI Quant Trading Forecast Terminal

An institutional-grade trading forecasting system and web dashboard that consumes **500 historical candles** and generates **5-candle multi-horizon probabilistic forecasts** across Commodities, Cryptocurrencies, Global Indices, and Gold.

---

## Key Features

1. **500 $\to$ 5 Candle Multi-Horizon AI Forecasting**:
   * Analyzes 500 OHLCV historical candles.
   * Generates next 5 candles with median trajectory ($p50$) and 10% / 90% quantile confidence bounds ($p10, p90$).
   * Uses GPU acceleration (NVIDIA RTX 5080 with CUDA) and multi-core CPU fallback.

2. **Custom Risk Guardrail (< 5% Spread-to-SL Ratio)**:
   * Evaluates the asset's estimated bid-ask spread against the (Entry - StopLoss) distance.
   * Only triggers actionable setups where:
     $$\text{Estimated Spread} < 5\% \times |\text{Entry} - \text{StopLoss}|$$
   * Prevents trading setups where friction/spread erodes profitability.

3. **London & New York Session Overlap Confluence**:
   * Live session monitor automatically flags the **13:00 - 16:30 UTC** window.
   * Boosts signal conviction score when institutional liquidity is peak and spreads are narrowest.

4. **Multi-Asset Watchlist**:
   * **Gold & Metals**: `GC=F` (Gold Futures), `SI=F` (Silver Futures), `XAUUSD=X`
   * **Crypto**: `BTC-USD`, `ETH-USD`, `SOL-USD`
   * **Indices**: `^GSPC` (S&P 500), `^IXIC` (Nasdaq), `^DJI` (Dow Jones)
   * **Commodities**: `CL=F` (Crude Oil), `NG=F` (Natural Gas)
   * Add, remove, or toggle any ticker anytime via the UI.

5. **Direct Telegram Signal Dispatch**:
   * Dispatches rich HTML cards with:
     * Asset name & ticker
     * Direction (🟢 LONG / 🔴 SHORT)
     * Entry, Dynamic ATR Stop Loss, Take Profit 1 & 2
     * Risk : Reward ratio
     * Spread-to-SL ratio verification
     * AI Conviction Score & Expected 5-candle return %
   * Includes in-dashboard **"Send Test Alert"** button to verify setup instantly.

6. **Interactive Financial Web Terminal**:
   * **TradingView Lightweight Charts**: Crisp candlestick charts with historical bars, neon predicted candles, and quantile uncertainty envelopes.
   * Real-time scan progress bar.
   * Signal history feed with one-click chart inspection.

---

## Quick Start

### 1. Launch Terminal
Double-click `start_terminal.bat` or run:
```bash
python run.py
```

### 2. Access Web Dashboard
Open your browser at:
```
http://localhost:8000
```

---

## Configuring Telegram Alerts

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` to create your bot and copy the **HTTP API Token**.
3. To find your Chat ID, message `@userinfobot` or add your bot to your trading channel.
4. In the Web Dashboard, click **⚙️ Settings & Telegram**.
5. Paste your **Bot Token** and **Chat ID**, toggle **Enable Telegram Signal Dispatch**, and click **✉️ Send Test Alert to Telegram**.
6. Save Settings!

---

## Architecture

```
trading/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI server & REST routes
│   │   ├── config.py                # JSON-persisted configuration & watchlists
│   │   ├── data_fetcher.py          # yfinance OHLCV fetcher & session detector
│   │   ├── forecasting/
│   │   │   ├── chronos_engine.py    # Time-series AI forecasting engine
│   │   │   └── signal_generator.py  # Spread guardrail & signal evaluator
│   │   ├── telegram_bot.py          # Telegram async alert dispatcher
│   │   └── scheduler.py             # Background scanning worker
│   └── test_pipeline.py             # Automated pipeline verification script
├── frontend/
│   ├── index.html                   # Dashboard UI
│   └── static/
│       ├── css/style.css            # Dark financial terminal styling
│       └── js/app.js                # TradingView charts & UI controller
├── run.py                           # Python launcher
├── start_terminal.bat               # Windows double-click runner
└── requirements.txt                 # Dependencies
```
