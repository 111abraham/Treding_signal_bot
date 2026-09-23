/**
 * AI Quant Trading Forecast Terminal - Frontend Controller
 * TradingView Lightweight Charts integration with 500 historical + 5 predicted candles,
 * Spread-to-SL filter visualization, session overlap tracker, and Telegram dispatch.
 */

// Global State
let chart = null;
let historicalSeries = null;
let predictedSeries = null;
let upperBandSeries = null;
let lowerBandSeries = null;
let priceLines = [];

let currentSymbol = "EURUSD";
let currentTimeframe = "1h";
let currentCategory = "ALL";
let watchlistData = [];
let scanPollInterval = null;
let activeTradesData = [];
let showCountdownTimers = true;
let currentForecastCandles = 5;
let currentActiveSignal = null;
let currentSignalTfFilter = "ALL";
let selectedTfs = new Set(["ALL"]);

function isTfSelected(tf) {
  if (!tf) return false;
  if (selectedTfs.has("ALL")) return true;
  return selectedTfs.has(tf.toLowerCase());
}

function getSelectedTfsString() {
  if (selectedTfs.has("ALL")) return "ALL";
  return Array.from(selectedTfs).join(",");
}

function getSelectedTfsDisplay() {
  if (selectedTfs.has("ALL")) return "ALL";
  return Array.from(selectedTfs).map((t) => (t.toUpperCase() === "1D" ? "1D" : t)).join(" + ");
}
let showChartTradeMarkers = true;
let autoCloseOnExpiryEnabled = true;
let pinnedActiveSignal = null;
let signalsData = [];
let closedTradesData = [];
let currentHistoricalCandles = [];

// DOM Elements
const signalsTfFilterBar = document.getElementById("signalsTfFilterBar");
const chartContainer = document.getElementById("tradingviewChart");
const chartOverlay = document.getElementById("chartLoadingOverlay");
const currentPriceDisplay = document.getElementById("currentPriceDisplay");
const activeSymbolElem = document.getElementById("activeSymbol");
const activeNameElem = document.getElementById("activeName");
const activeCategoryElem = document.getElementById("activeCategory");
const activeMarketLiveness = document.getElementById("activeMarketLiveness");
const directionValue = document.getElementById("directionValue");
const expectedReturnValue = document.getElementById("expectedReturnValue");
const convictionValue = document.getElementById("convictionValue");
const timeframeSelect = document.getElementById("timeframeSelect");
const btnScanNow = document.getElementById("btnScanNow");
const scanStatusText = document.getElementById("scanStatusText");
const progressBarContainer = document.getElementById("progressBarContainer");
const sessionText = document.getElementById("sessionText");
const sessionBadge = document.getElementById("sessionBadge");
const deviceText = document.getElementById("deviceText");
const watchlistContainer = document.getElementById("watchlistContainer");
const signalHistoryList = document.getElementById("signalHistoryList");
const signalCountBadge = document.getElementById("signalCountBadge");

// Candle Countdown & Lifespan Elements
const candleTimerBadge = document.getElementById("candleTimerBadge");
const candleTimerText = document.getElementById("candleTimerText");
const lifespanPill = document.getElementById("lifespanPill");
const lifespanPillLabel = document.getElementById("lifespanPillLabel");
const lifespanPillValue = document.getElementById("lifespanPillValue");
const rowSignalLifespan = document.getElementById("rowSignalLifespan");
const lvlSignalRemaining = document.getElementById("lvlSignalRemaining");
const lifespanSegments = document.getElementById("lifespanSegments");

// Guardrail DOM Elements
const currentSpreadRatio = document.getElementById("currentSpreadRatio");
const spreadMeterFill = document.getElementById("spreadMeterFill");
const spreadStatusPill = document.getElementById("spreadStatusPill");
const lvlEntry = document.getElementById("lvlEntry");
const lvlSL = document.getElementById("lvlSL");
const lvlTP1 = document.getElementById("lvlTP1");
const lvlTP2 = document.getElementById("lvlTP2");
const lvlRR = document.getElementById("lvlRR");
const rowDualAi = document.getElementById("rowDualAi");
const lvlDualAi = document.getElementById("lvlDualAi");
const timesfmPill = document.getElementById("timesfmPill");
const timesfmValue = document.getElementById("timesfmValue");

// 1-Click MT5 Execution Elements
const mt5ExecutionBox = document.getElementById("mt5ExecutionBox");
const tradeRiskAmount = document.getElementById("tradeRiskAmount");
const tradeCalculatedLots = document.getElementById("tradeCalculatedLots");
const tradeProjectedLoss = document.getElementById("tradeProjectedLoss");
const tradeProjectedReward = document.getElementById("tradeProjectedReward");
const tradeProjectedRR = document.getElementById("tradeProjectedRR");
const btnExecuteMt5Trade = document.getElementById("btnExecuteMt5Trade");
const btnExecuteMt5Text = document.getElementById("btnExecuteMt5Text");
const mt5TradeFeedback = document.getElementById("mt5TradeFeedback");
const mt5ExecBrokerTag = document.getElementById("mt5ExecBrokerTag");
const btnTpModeSingle = document.getElementById("btnTpModeSingle");
const btnTpModeSplit = document.getElementById("btnTpModeSplit");
let currentTpMode = "single";
let currentActiveSetupSignal = null;

// Performance & Outcome DOM Elements
const statWinRate = document.getElementById("statWinRate");
const statProfitFactor = document.getElementById("statProfitFactor");
const statRecord = document.getElementById("statRecord");
const statTotalR = document.getElementById("statTotalR");
const perfActiveCount = document.getElementById("perfActiveCount");
const perfConvictionFilter = document.getElementById("perfConvictionFilter");
const perfConvictionLabel = document.getElementById("perfConvictionLabel");
const perfDualAiOnly = document.getElementById("perfDualAiOnly");
const btnExportHistory = document.getElementById("btnExportHistory");
const btnImportHistory = document.getElementById("btnImportHistory");
const btnClearHistory = document.getElementById("btnClearHistory");
const historyFileInput = document.getElementById("historyFileInput");
const exportModal = document.getElementById("exportModal");
const btnCloseExportModal = document.getElementById("btnCloseExportModal");
const btnExportCsvAll = document.getElementById("btnExportCsvAll");
const btnExportCsvFiltered = document.getElementById("btnExportCsvFiltered");
const btnExportJsonAll = document.getElementById("btnExportJsonAll");
const btnExportJsonFiltered = document.getElementById("btnExportJsonFiltered");
const tabRecentSignals = document.getElementById("tabRecentSignals");
const tabResolvedTrades = document.getElementById("tabResolvedTrades");
const resolvedTradesList = document.getElementById("resolvedTradesList");
const resolvedCountBadge = document.getElementById("resolvedCountBadge");
let currentMinConviction = 65;

// HTF Radar Elements
const chip5m = document.getElementById("chip5m");
const chip15m = document.getElementById("chip15m");
const chip1h = document.getElementById("chip1h");
const chip4h = document.getElementById("chip4h");
const htfAlignmentSummary = document.getElementById("htfAlignmentSummary");
const htfOpportunityAlert = document.getElementById("htfOpportunityAlert");
const htfAlertText = document.getElementById("htfAlertText");
const btnViewHtfSetup = document.getElementById("btnViewHtfSetup");
let activeHtfSetup = null;

// Modals
const settingsModal = document.getElementById("settingsModal");
const btnSettings = document.getElementById("btnSettings");
const btnCloseSettings = document.getElementById("btnCloseSettings");
const btnCancelSettings = document.getElementById("btnCancelSettings");
const settingsForm = document.getElementById("settingsForm");
const btnTestTelegram = document.getElementById("btnTestTelegram");
const tgTestStatus = document.getElementById("tgTestStatus");

const addAssetModal = document.getElementById("addAssetModal");
const btnAddAsset = document.getElementById("btnAddAsset");
const btnCloseAddAsset = document.getElementById("btnCloseAddAsset");
const btnCancelAddAsset = document.getElementById("btnCancelAddAsset");
const addAssetForm = document.getElementById("addAssetForm");


// Utility: Format Seconds into Human-Readable Countdown
function formatRemainingDuration(seconds) {
  if (seconds <= 0) return "0s";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s < 10 ? "0" : ""}${s}s`;
  return `${s}s`;
}

// Utility: Timeframe Duration in Seconds
function getTimeframeSeconds(tf) {
  const map = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
  };
  return map[(tf || "").toLowerCase()] || 3600;
}

// Live Countdown Engine for Active Chart Signal Lifespan
function updateActiveSignalLifespanClock(nowSec) {
  if (!showCountdownTimers) {
    if (lifespanPill) lifespanPill.style.display = "none";
    if (rowSignalLifespan) rowSignalLifespan.style.display = "none";
    return;
  }

  if (lifespanPill) lifespanPill.style.display = "flex";
  if (rowSignalLifespan) rowSignalLifespan.style.display = currentActiveSignal ? "flex" : "none";

  if (!currentActiveSignal) return;

  nowSec = nowSec || Math.floor(Date.now() / 1000);

  // CRITICAL: Signal lifespan is strictly anchored to the signal's native timeframe, NEVER the chart's current viewing timeframe
  const sigTf = currentActiveSignal.timeframe || currentTimeframe;
  const sigTfSec = getTimeframeSeconds(sigTf);

  const activeTrade = activeTradesData.find(
    (t) => (currentActiveSignal.id && t.id === currentActiveSignal.id) ||
           (t.symbol.toUpperCase() === (currentActiveSignal.symbol || currentSymbol).toUpperCase() && t.timeframe === sigTf)
  );

  let maxBars = currentActiveSignal.max_candles || currentForecastCandles || 5;
  let elapsedBars = 0;
  let secLeft = maxBars * sigTfSec;

  if (activeTrade) {
    maxBars = activeTrade.max_candles || maxBars;
    const entryUnix = activeTrade.entry_candle_unix || activeTrade.opened_unix || nowSec;
    const expUnix = activeTrade.expires_at_unix || (entryUnix + (maxBars * sigTfSec));
    secLeft = Math.max(0, expUnix - nowSec);

    if (activeTrade.candles_monitored !== undefined && activeTrade.candles_monitored !== null) {
      elapsedBars = activeTrade.candles_monitored;
    } else {
      elapsedBars = Math.floor(Math.max(0, nowSec - entryUnix) / sigTfSec);
    }
    elapsedBars = Math.min(maxBars, elapsedBars);
  } else if (currentActiveSignal.candle_unix || currentActiveSignal.entry_candle_unix || currentActiveSignal.timestamp) {
    const entryUnix = currentActiveSignal.candle_unix || currentActiveSignal.entry_candle_unix || Math.floor(new Date(currentActiveSignal.timestamp).getTime() / 1000) || nowSec;
    const expUnix = currentActiveSignal.expires_at_unix || (entryUnix + (maxBars * sigTfSec));
    secLeft = Math.max(0, expUnix - nowSec);
    elapsedBars = Math.min(maxBars, Math.max(0, Math.floor((nowSec - entryUnix) / sigTfSec)));
  } else {
    const nextBoundary = Math.ceil(nowSec / sigTfSec) * sigTfSec;
    const curCandleRemaining = Math.max(0, nextBoundary - nowSec);
    secLeft = curCandleRemaining + Math.max(0, maxBars - 1) * sigTfSec;
    elapsedBars = 0;
  }

  const isFinished = secLeft <= 0 || elapsedBars >= maxBars;
  const currentBar = isFinished ? maxBars : Math.min(maxBars, elapsedBars + 1);

  // Render Lifespan Segments (Elapsed, Current Active, Pending)
  if (lifespanSegments) {
    lifespanSegments.innerHTML = "";
    for (let i = 0; i < maxBars; i++) {
      const seg = document.createElement("span");
      seg.className = "lifespan-segment";
      if (isFinished) {
        seg.classList.add("elapsed");
        seg.title = `Bar ${i + 1} of ${maxBars} [${sigTf}] (Completed)`;
      } else if (i < elapsedBars) {
        seg.classList.add("elapsed");
        seg.title = `Bar ${i + 1} of ${maxBars} [${sigTf}] (Completed)`;
      } else if (i === elapsedBars) {
        seg.classList.add("current");
        if (currentBar === maxBars) seg.classList.add("danger");
        seg.title = `Bar ${i + 1} of ${maxBars} [${sigTf}] (Active Now)`;
      } else {
        seg.classList.add("pending");
        seg.title = `Bar ${i + 1} of ${maxBars} [${sigTf}] (Upcoming)`;
      }
      lifespanSegments.appendChild(seg);
    }
  }

  const isMarketPaused = (activeTrade && (activeTrade.is_market_paused || activeTrade.is_market_open === false)) ||
                         (currentActiveSignal && (currentActiveSignal.is_market_paused || currentActiveSignal.is_market_open === false));

  const durStr = formatRemainingDuration(secLeft);
  if (lvlSignalRemaining) {
    if (isMarketPaused) {
      lvlSignalRemaining.textContent = `⏸️ Paused (Market Closed) - Bar ${currentBar} of ${maxBars} [${sigTf}]`;
    } else if (isFinished) {
      lvlSignalRemaining.textContent = `⏱️ Finished (${maxBars}/${maxBars} [${sigTf}])`;
    } else {
      lvlSignalRemaining.textContent = `⏳ Bar ${currentBar} of ${maxBars} [${sigTf}] (~${durStr} left)`;
    }
  }

  if (lifespanPillValue) {
    if (isMarketPaused) {
      lifespanPillValue.textContent = `⏸️ Paused (Market Closed)`;
    } else if (isFinished) {
      lifespanPillValue.textContent = `⏱️ Finished (${maxBars}/${maxBars} [${sigTf}])`;
    } else {
      lifespanPillValue.textContent = `⏳ Bar ${currentBar}/${maxBars} [${sigTf}] (${durStr} left)`;
    }
  }
}

// 1-Second Live Countdown Engine (Client-Side, 0 Server Overhead)
function startLiveCountdownEngine() {
  setInterval(() => {
    if (!showCountdownTimers) {
      if (candleTimerBadge) candleTimerBadge.style.display = "none";
      if (lifespanPill) lifespanPill.style.display = "none";
      if (rowSignalLifespan) rowSignalLifespan.style.display = "none";
      document.querySelectorAll(".sig-countdown").forEach((el) => (el.style.display = "none"));
      return;
    } else {
      if (candleTimerBadge) candleTimerBadge.style.display = "flex";
      document.querySelectorAll(".sig-countdown").forEach((el) => (el.style.display = "inline-block"));
    }

    const nowSec = Math.floor(Date.now() / 1000);
    const tfSec = getTimeframeSeconds(currentTimeframe);

    // 1. Current Candle Close Timer
    const nextCandleBoundary = Math.ceil(nowSec / tfSec) * tfSec;
    const candleSecLeft = Math.max(0, nextCandleBoundary - nowSec);
    if (candleTimerText) {
      const cm = Math.floor(candleSecLeft / 60);
      const cs = candleSecLeft % 60;
      if (candleSecLeft >= 3600) {
        const ch = Math.floor(candleSecLeft / 3600);
        candleTimerText.textContent = `${ch}h ${cm % 60}m`;
      } else {
        candleTimerText.textContent = `${cm < 10 ? "0" : ""}${cm}:${cs < 10 ? "0" : ""}${cs}`;
      }
      if (candleTimerBadge) {
        if (candleSecLeft < 60 && tfSec <= 900) {
          candleTimerBadge.classList.add("closing-soon");
        } else {
          candleTimerBadge.classList.remove("closing-soon");
        }
      }
    }

    // 2. Active Chart Signal Lifespan (anchored strictly to signal native timeframe)
    updateActiveSignalLifespanClock(nowSec);

    // 3. Signal list cards countdown
    document.querySelectorAll(".sig-countdown").forEach((el) => {
      const entryUnix = parseInt(el.dataset.entry, 10);
      const tf = el.dataset.tf || "1h";
      const maxC = parseInt(el.dataset.max, 10) || currentForecastCandles || 5;
      const step = getTimeframeSeconds(tf);
      if (!entryUnix) return;
      if (el.dataset.paused === "true" || el.classList.contains("paused")) return;

      const expUnix = entryUnix + maxC * step;
      const secLeft = expUnix - nowSec;
      if (secLeft <= 0) {
        el.textContent = `⏱️ Finished (${maxC}/${maxC})`;
        el.className = "sig-countdown completed";
      } else {
        const elapsedBars = Math.min(maxC, Math.max(0, Math.floor((nowSec - entryUnix) / step)));
        const currentBar = Math.min(maxC, elapsedBars + 1);
        el.textContent = `⏳ Bar ${currentBar}/${maxC} (${formatRemainingDuration(secLeft)} left)`;
        el.className = "sig-countdown";
      }
    });
  }, 1000);
}

async function loadPropGuardStatus() {
  try {
    const res = await fetch("/api/mt5/prop-guard-status");
    if (!res.ok) return;
    const data = await res.json();
    const rules = data.rules || {};
    const telem = data.telemetry || {};

    const elNotice = document.getElementById("mt5PropGuardNotice");
    const elState = document.getElementById("mt5PropGuardState");
    const elTrades = document.getElementById("mt5PropGuardTradesBadge");
    const elMargin = document.getElementById("mt5PropGuardMargin");
    const elDD = document.getElementById("mt5PropGuardDD");

    if (!elNotice || !elState) return;

    if (!rules.enabled) {
      elState.textContent = "DISABLED";
      elState.style.color = "var(--text-muted)";
      elNotice.style.borderColor = "rgba(255, 255, 255, 0.1)";
      if (elTrades) elTrades.textContent = "Disabled in Settings";
      if (elMargin) elMargin.textContent = "--";
      if (elDD) elDD.textContent = "--";
      return;
    }

    if (!telem.mt5_connected) {
      elState.textContent = "MT5 OFFLINE";
      elState.style.color = "var(--accent-red)";
      elNotice.style.borderColor = "rgba(255, 77, 77, 0.2)";
      if (elTrades) elTrades.textContent = "Disconnected";
      if (elMargin) elMargin.textContent = "--";
      if (elDD) elDD.textContent = "--";
      return;
    }

    const openCount = telem.open_trades_count || 0;
    const maxTrades = rules.max_simultaneous_trades || 3;
    const isAtCap = openCount >= maxTrades;

    const freeMarginPct = telem.free_margin_pct !== undefined ? telem.free_margin_pct : 100.0;
    const minMargin = rules.min_free_margin_pct || 50.0;
    const isMarginLow = freeMarginPct < minMargin;

    const dailyDD = telem.daily_drawdown_pct || 0.0;
    const maxDD = rules.max_daily_drawdown_pct || 3.5;
    const isDDHigh = dailyDD >= maxDD;

    if (isAtCap || isMarginLow || isDDHigh) {
      elState.textContent = "PAUSED";
      elState.style.color = "var(--accent-red)";
      elNotice.style.borderColor = "rgba(255, 77, 77, 0.4)";
      elNotice.style.background = "rgba(255, 77, 77, 0.08)";
    } else {
      elState.textContent = "ACTIVE";
      elState.style.color = "var(--accent-green)";
      elNotice.style.borderColor = "rgba(16, 185, 129, 0.2)";
      elNotice.style.background = "rgba(16, 185, 129, 0.05)";
    }

    if (elTrades) {
      elTrades.textContent = `Trades: ${openCount} / ${maxTrades}`;
      elTrades.style.color = isAtCap ? "var(--accent-red)" : "var(--text-primary)";
    }

    if (elMargin) {
      elMargin.textContent = `${freeMarginPct.toFixed(0)}%`;
      elMargin.style.color = isMarginLow ? "var(--accent-red)" : "var(--accent-cyan)";
    }

    if (elDD) {
      elDD.textContent = `${dailyDD.toFixed(1)}% / ${maxDD.toFixed(1)}%`;
      elDD.style.color = isDDHigh ? "var(--accent-red)" : (dailyDD > 2.0 ? "var(--accent-yellow, #f59e0b)" : "var(--accent-green)");
    }
  } catch (e) {
    console.debug("Failed loading prop guard status:", e);
  }
}

async function loadInitialSettings() {
  try {
    const res = await fetch("/api/settings");
    if (res.ok) {
      const cfg = await res.json();
      showCountdownTimers = cfg.strategy?.show_countdown_timers !== false;
      showChartTradeMarkers = cfg.strategy?.show_chart_trade_markers !== false;
      currentForecastCandles = cfg.forecast_candles || 5;

      const defaultRisk = cfg.strategy?.default_dollar_risk || 50;
      if (tradeRiskAmount) {
        tradeRiskAmount.value = defaultRisk;
        document.querySelectorAll(".risk-pill-btn").forEach((p) => {
          p.classList.toggle("active", parseFloat(p.dataset.risk) === defaultRisk);
        });
      }

      currentTpMode = cfg.strategy?.split_tp_mode ? "split" : "single";
      if (btnTpModeSingle && btnTpModeSplit) {
        btnTpModeSingle.classList.toggle("active", currentTpMode === "single");
        btnTpModeSplit.classList.toggle("active", currentTpMode === "split");
      }

      autoCloseOnExpiryEnabled = cfg.strategy?.auto_close_on_expiry !== false;
      const elGuardStatus = document.getElementById("mt5LifespanGuardStatus");
      if (elGuardStatus) {
        elGuardStatus.textContent = autoCloseOnExpiryEnabled ? `Active (Auto-closes at Bar ${currentForecastCandles})` : "Disabled in Settings";
        elGuardStatus.style.color = autoCloseOnExpiryEnabled ? "var(--accent-cyan)" : "var(--text-muted)";
      }
    }
  } catch (e) {
    console.debug("Failed loading initial settings:", e);
  }
}

// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
  initChart();
  setupEventListeners();
  startLiveCountdownEngine();
  await loadInitialSettings();
  await loadStatus();
  await loadPropGuardStatus();
  await loadWatchlist();
  await loadSignals();
  await loadPerformance();
  await pollHtfRadar();
  await loadChartData(currentSymbol, currentTimeframe);

  // Status and scanner polling
  setInterval(loadStatus, 15000);
  setInterval(loadPropGuardStatus, 15000);
  setInterval(loadSignals, 30000);
  setInterval(loadPerformance, 20000);
  setInterval(pollHtfRadar, 20000);
});


// 1. CHART INITIALIZATION
function initChart() {
  if (!window.LightweightCharts) {
    console.error("TradingView Lightweight Charts library failed to load.");
    return;
  }

  chart = LightweightCharts.createChart(chartContainer, {
    layout: {
      background: { color: "#0b0e14" },
      textColor: "#9ca3af",
      fontSize: 12,
      fontFamily: "'JetBrains Mono', monospace",
    },
    grid: {
      vertLines: { color: "rgba(35, 45, 66, 0.4)" },
      horzLines: { color: "rgba(35, 45, 66, 0.4)" },
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
    },
    rightPriceScale: {
      borderColor: "#232d42",
      scaleMargins: { top: 0.15, bottom: 0.15 },
    },
    timeScale: {
      borderColor: "#232d42",
      timeVisible: true,
      secondsVisible: false,
    },
  });

  // Series 1: Historical 500 Candlesticks
  historicalSeries = chart.addCandlestickSeries({
    upColor: "#10b981",
    downColor: "#ef4444",
    borderVisible: false,
    wickUpColor: "#10b981",
    wickDownColor: "#ef4444",
  });

  // Series 2: Predicted Future Candlesticks (Glowing Neon Cyan)
  predictedSeries = chart.addCandlestickSeries({
    upColor: "#00f2fe",
    downColor: "#0284c7",
    borderVisible: true,
    borderColor: "#38bdf8",
    wickUpColor: "#00f2fe",
    wickDownColor: "#38bdf8",
  });

  // Series 3 & 4: Upper (90%) and Lower (10%) Quantile Confidence Bounds
  upperBandSeries = chart.addLineSeries({
    color: "rgba(56, 189, 248, 0.6)",
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    title: "90% Bound",
  });

  lowerBandSeries = chart.addLineSeries({
    color: "rgba(56, 189, 248, 0.6)",
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    title: "10% Bound",
  });

  window.addEventListener("resize", () => {
    chart.applyOptions({
      width: chartContainer.clientWidth,
      height: chartContainer.clientHeight,
    });
  });

  // Subscribe to chart clicks for bidirectional navigation to signals/outcomes
  chart.subscribeClick((param) => {
    if (!param || !param.time) return;
    handleChartClick(param.time);
  });
}

function findNearestCandleTime(targetUnix, maxDiffSec = 3600) {
  if (!currentHistoricalCandles || currentHistoricalCandles.length === 0) return null;
  let bestTime = null;
  let minDiff = Infinity;
  for (let i = 0; i < currentHistoricalCandles.length; i++) {
    const cTime = currentHistoricalCandles[i].time;
    const diff = Math.abs(cTime - targetUnix);
    if (diff < minDiff) {
      minDiff = diff;
      bestTime = cTime;
    }
  }
  if (minDiff <= (maxDiffSec * 2.5)) {
    return bestTime;
  }
  return null;
}

function frameChartToCandle(targetUnix, tf = "1h") {
  if (!chart || !currentHistoricalCandles || currentHistoricalCandles.length === 0) return;
  let targetIdx = -1;
  if (targetUnix) {
    let minDiff = Infinity;
    for (let i = 0; i < currentHistoricalCandles.length; i++) {
      const diff = Math.abs(currentHistoricalCandles[i].time - targetUnix);
      if (diff < minDiff) {
        minDiff = diff;
        targetIdx = i;
      }
    }
  } else {
    targetIdx = currentHistoricalCandles.length - 1;
  }

  if (targetIdx !== -1) {
    const fromIdx = Math.max(0, targetIdx - 35);
    const toIdx = Math.min(currentHistoricalCandles.length + 15, targetIdx + 20);
    try {
      chart.timeScale().setVisibleLogicalRange({ from: fromIdx, to: toIdx });
    } catch (e) {
      console.warn("Could not set visible logical range:", e);
    }
  }
}

function renderChartTradeMarkers() {
  if (!historicalSeries) return;
  if (!showChartTradeMarkers) {
    try { historicalSeries.setMarkers([]); } catch (e) {}
    return;
  }

  const symbolUpper = (currentSymbol || "").toUpperCase();
  const currentTrades = [];

  // Active trades matching symbol
  activeTradesData.forEach((t) => {
    if ((t.symbol || "").toUpperCase() === symbolUpper) {
      currentTrades.push({ ...t, isActive: true });
    }
  });

  // Closed trades matching symbol
  closedTradesData.forEach((t) => {
    if ((t.symbol || "").toUpperCase() === symbolUpper) {
      currentTrades.push({ ...t, isActive: false });
    }
  });

  // Include pinned active signal if not already present
  if (pinnedActiveSignal && (pinnedActiveSignal.symbol || "").toUpperCase() === symbolUpper) {
    const exists = currentTrades.some(
      (t) => (t.id && t.id === pinnedActiveSignal.id) ||
             (t.entry_price === pinnedActiveSignal.entry_price && t.timeframe === pinnedActiveSignal.timeframe)
    );
    if (!exists) {
      currentTrades.push({ ...pinnedActiveSignal, isActive: true });
    }
  }

  const markers = [];
  const tfSec = getTimeframeSeconds(currentTimeframe);

  currentTrades.forEach((tr) => {
    const entryUnix = tr.entry_candle_unix || tr.opened_unix || tr.candle_unix;
    if (!entryUnix) return;

    const matchedTime = findNearestCandleTime(entryUnix, tr.step_seconds || getTimeframeSeconds(tr.timeframe) || tfSec);
    if (!matchedTime) return;

    const isBull = tr.direction === "BULLISH";
    // Entry marker (arrow up for buy, arrow down for sell)
    markers.push({
      time: matchedTime,
      position: isBull ? "belowBar" : "aboveBar",
      color: isBull ? "#10b981" : "#ef4444",
      shape: isBull ? "arrowUp" : "arrowDown",
      text: `${isBull ? "BUY" : "SELL"} @ ${formatPrice(tr.entry_price)}`,
      id: `entry_${tr.id || entryUnix}`,
    });

    // Exit marker for closed trades
    if (!tr.isActive && tr.status === "CLOSED") {
      const exitUnix = tr.exit_candle_unix || tr.closed_unix;
      if (exitUnix) {
        const matchedExitTime = findNearestCandleTime(exitUnix, tr.step_seconds || getTimeframeSeconds(tr.timeframe) || tfSec);
        if (matchedExitTime) {
          const isWin = tr.outcome === "WIN" || tr.outcome === "EXPIRED_PROFIT";
          const outcomeColor = isWin ? "#10b981" : (tr.outcome === "LOSS" || tr.outcome === "EXPIRED_LOSS" ? "#ef4444" : "#f59e0b");
          const rStr = tr.realized_r !== undefined ? `${tr.realized_r >= 0 ? "+" : ""}${tr.realized_r}R` : "";
          markers.push({
            time: matchedExitTime,
            position: isBull ? "aboveBar" : "belowBar",
            color: outcomeColor,
            shape: isWin ? "circle" : "square",
            text: `${tr.outcome || "EXIT"} ${rStr}`,
            id: `exit_${tr.id || exitUnix}`,
          });
        }
      }
    }
  });

  // Sort strictly ascending by time for Lightweight Charts
  markers.sort((a, b) => a.time - b.time);
  try {
    historicalSeries.setMarkers(markers);
  } catch (err) {
    console.debug("Failed setting chart markers:", err);
  }
}

function handleChartClick(clickTime) {
  const symbolUpper = (currentSymbol || "").toUpperCase();
  const tfSec = getTimeframeSeconds(currentTimeframe);
  const toleranceSec = tfSec * 2.5;

  let found = null;
  let isOutcome = false;

  // 1. Search in signalsData
  for (const sig of signalsData) {
    if ((sig.symbol || "").toUpperCase() !== symbolUpper) continue;
    const entryUnix = sig.candle_unix || Math.floor(new Date(sig.timestamp).getTime() / 1000);
    if (entryUnix && Math.abs(entryUnix - clickTime) <= toleranceSec) {
      found = sig;
      isOutcome = false;
      break;
    }
  }

  // 2. If not found in signals, search in activeTradesData
  if (!found) {
    for (const t of activeTradesData) {
      if ((t.symbol || "").toUpperCase() !== symbolUpper) continue;
      const entryUnix = t.entry_candle_unix || t.opened_unix;
      if (entryUnix && Math.abs(entryUnix - clickTime) <= toleranceSec) {
        found = t;
        isOutcome = false;
        break;
      }
    }
  }

  // 3. If not found, search in closedTradesData
  if (!found) {
    for (const tr of closedTradesData) {
      if ((tr.symbol || "").toUpperCase() !== symbolUpper) continue;
      const entryUnix = tr.entry_candle_unix || tr.opened_unix;
      const exitUnix = tr.exit_candle_unix || tr.closed_unix;
      if ((entryUnix && Math.abs(entryUnix - clickTime) <= toleranceSec) ||
          (exitUnix && Math.abs(exitUnix - clickTime) <= toleranceSec)) {
        found = tr;
        isOutcome = true;
        break;
      }
    }
  }

  if (!found) return;

  // Switch tabs if necessary
  if (isOutcome) {
    if (tabResolvedTrades) tabResolvedTrades.click();
  } else {
    if (tabRecentSignals) tabRecentSignals.click();
  }

  // Locate the card
  const container = isOutcome ? resolvedTradesList : signalHistoryList;
  if (!container) return;

  const tradeId = found.id || `${found.symbol}_${found.timeframe}_${found.entry_candle_unix || found.candle_unix || ""}`;
  const cards = container.querySelectorAll(".signal-card-mini");
  let matchedCard = null;

  cards.forEach((c) => {
    c.classList.remove("active-signal-card");
    if (c.dataset.tradeId === tradeId || c.textContent.includes(found.symbol)) {
      if (!matchedCard) matchedCard = c;
    }
  });

  if (matchedCard) {
    matchedCard.classList.add("active-signal-card");
    matchedCard.classList.add("pulse-highlight");
    matchedCard.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => matchedCard.classList.remove("pulse-highlight"), 1500);
  }

  // Update levels and pinned signal
  pinnedActiveSignal = found;
  currentActiveSignal = found;
  const lastHistorical = currentHistoricalCandles[currentHistoricalCandles.length - 1];
  updateGuardrailsAndLevels(found, lastHistorical?.close);
  updateActiveSignalLifespanClock();
}


// 2. DATA LOADING & CHART RENDERING
async function loadChartData(symbol, timeframe, pinnedSignal = null) {
  chartOverlay.style.display = "flex";
  clearPriceLines();

  if (pinnedSignal) {
    pinnedActiveSignal = pinnedSignal;
  } else if (!timeframe || (pinnedActiveSignal && pinnedActiveSignal.symbol.toUpperCase() !== symbol.toUpperCase())) {
    pinnedActiveSignal = null;
  }

  if (timeframe) {
    currentTimeframe = timeframe;
    if (timeframeSelect && timeframeSelect.value !== timeframe) {
      timeframeSelect.value = timeframe;
    }
  }

  try {
    const res = await fetch(`/api/chart/${encodeURIComponent(symbol)}?timeframe=${currentTimeframe}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to load chart data");
    }

    const data = await res.json();
    currentSymbol = data.symbol;
    currentTimeframe = data.timeframe || timeframe || currentTimeframe;
    if (timeframeSelect && timeframeSelect.value !== currentTimeframe) {
      timeframeSelect.value = currentTimeframe;
    }

    // Update Header
    activeSymbolElem.textContent = data.symbol;
    activeNameElem.textContent = data.name;
    activeCategoryElem.textContent = data.category;

    // Check & Update Live Broker Market Status
    if (activeMarketLiveness) {
      try {
        fetch(`/api/market/liveness?symbol=${encodeURIComponent(data.symbol)}&timeframe=${encodeURIComponent(currentTimeframe)}`)
          .then((r) => r.json())
          .then((lData) => {
            if (lData && lData.is_open) {
              activeMarketLiveness.className = "badge market-liveness-pill live";
              activeMarketLiveness.textContent = "🟢 Live";
              activeMarketLiveness.title = lData.reason || "Market is open and quoting live";
            } else {
              activeMarketLiveness.className = "badge market-liveness-pill closed";
              activeMarketLiveness.textContent = "🔴 Market Closed";
              activeMarketLiveness.title = (lData && lData.reason) ? lData.reason : "Market is closed or broker feed is frozen";
            }
          })
          .catch(() => {});
      } catch (errLive) {}
    }
    
    currentHistoricalCandles = data.candles || [];
    const lastHistorical = currentHistoricalCandles[currentHistoricalCandles.length - 1];
    if (lastHistorical) {
      currentPriceDisplay.textContent = formatPrice(lastHistorical.close);
    }

    // Set Historical Candles (500)
    historicalSeries.setData(currentHistoricalCandles);

    // Render Predicted Future Candles
    const predCandles = data.forecast.predicted_candles || [];
    if (predCandles.length > 0) {
      predictedSeries.setData(predCandles);

      // Quantile ribbon lines
      const upperData = predCandles.map((c) => ({ time: c.time, value: c.p90 }));
      const lowerData = predCandles.map((c) => ({ time: c.time, value: c.p10 }));
      upperBandSeries.setData(upperData);
      lowerBandSeries.setData(lowerData);

      // Fit content or frame to pinned signal
      if (pinnedActiveSignal) {
        const targetUnix = pinnedActiveSignal.entry_candle_unix || pinnedActiveSignal.candle_unix || pinnedActiveSignal.opened_unix;
        frameChartToCandle(targetUnix, currentTimeframe);
      } else {
        chart.timeScale().fitContent();
      }
    }

    // Prioritize pinned signal (clicked card), then active trade, then fresh live signal
    if (pinnedActiveSignal && pinnedActiveSignal.symbol.toUpperCase() === data.symbol.toUpperCase()) {
      currentActiveSignal = pinnedActiveSignal;
    } else {
      currentActiveSignal = data.active_trade || data.signal;
    }

    // Update Direction Pill Dynamic Horizon Label (e.g. 5-Candle Direction)
    const maxBars = currentActiveSignal?.max_candles || data.forecast?.predicted_candles?.length || currentForecastCandles || 5;
    const dirPillLabel = document.querySelector("#directionPill .pill-label");
    if (dirPillLabel) dirPillLabel.textContent = `${maxBars}-Candle Direction`;

    // Update Forecast Pills
    updateForecastPills(data.forecast, currentActiveSignal);

    // Update Guardrails & Levels Card
    updateGuardrailsAndLevels(currentActiveSignal, lastHistorical?.close);

    // Render Chart Trade Markers (entry arrows & exit circles)
    renderChartTradeMarkers();

    // Update Higher Timeframe Radar & Confluence
    updateHtfConfluence(data.htf_confluence);

  } catch (error) {
    console.error("Error loading chart:", error);
    alert(`Could not load forecast for ${symbol}: ${error.message}`);
  } finally {
    chartOverlay.style.display = "none";
  }
}


function updateHtfConfluence(htf) {
  if (!htf || !htf.matrix) return;
  const chipMap = {
    "5m": chip5m,
    "15m": chip15m,
    "1h": chip1h,
    "4h": chip4h
  };

  for (const [tf, el] of Object.entries(chipMap)) {
    if (!el) continue;
    const info = htf.matrix[tf];
    if (!info) continue;
    const bias = info.bias || "UNKNOWN";
    el.className = "htf-chip";
    if (bias === "BULLISH") {
      el.classList.add("chip-bull");
      el.textContent = `${tf}: 🟢 BULL`;
    } else if (bias === "BEARISH") {
      el.classList.add("chip-bear");
      el.textContent = `${tf}: 🔴 BEAR`;
    } else {
      el.classList.add("chip-neutral");
      el.textContent = `${tf}: ⚪ RANGE`;
    }
  }

  if (htfAlignmentSummary) {
    htfAlignmentSummary.textContent = htf.alignment_text || "HTF Analyzed";
  }
}


async function pollHtfRadar() {
  try {
    const res = await fetch("/api/htf-radar");
    const data = await res.json();
    if (data.opportunities && data.opportunities.length > 0) {
      const topOpp = data.opportunities[0];
      activeHtfSetup = topOpp;
      const dirText = topOpp.direction === "BULLISH" ? "🟢 BUY" : "🔴 SELL";
      htfAlertText.textContent = `HTF ${topOpp.timeframe.toUpperCase()}: ${topOpp.symbol} ${dirText} (${topOpp.conviction}% Conviction)`;
      htfOpportunityAlert.style.display = "flex";
    } else {
      htfOpportunityAlert.style.display = "none";
    }
  } catch (e) {
    console.debug("HTF radar poll:", e);
  }
}


function clearPriceLines() {
  priceLines.forEach((pl) => historicalSeries.removePriceLine(pl));
  priceLines = [];
}

function updateForecastPills(forecast, signal) {
  const dir = forecast.direction || "NEUTRAL";
  directionValue.textContent = dir;
  directionValue.className = "pill-val";
  if (dir === "BULLISH") directionValue.classList.add("direction-bullish");
  else if (dir === "BEARISH") directionValue.classList.add("direction-bearish");
  else directionValue.classList.add("direction-neutral");

  const ret = forecast.expected_return_pct;
  expectedReturnValue.textContent = (ret > 0 ? "+" : "") + ret + "%";
  expectedReturnValue.className = "pill-val " + (ret >= 0 ? "direction-bullish" : "direction-bearish");

  const conv = signal?.conviction ?? 50.0;
  convictionValue.textContent = conv + "%";

  // TimesFM Arbiter Pill
  if (timesfmPill && timesfmValue) {
    if (signal && signal.timesfm_status === "ready") {
      timesfmPill.style.display = "flex";
      const tfmRet = signal.timesfm_return_pct ?? 0;
      const tfmRetStr = (tfmRet >= 0 ? "+" : "") + tfmRet + "%";
      if (signal.timesfm_consensus === "AGREEMENT") {
        timesfmValue.innerHTML = `<span class="timesfm-consensus-agree">🤖 ${tfmRetStr} (Agree)</span>`;
      } else if (signal.timesfm_consensus === "CONFLICT") {
        timesfmValue.innerHTML = `<span class="timesfm-consensus-conflict">⚠️ ${signal.timesfm_direction} (${tfmRetStr})</span>`;
      } else {
        timesfmValue.innerHTML = `<span class="timesfm-consensus-neutral">⏸️ ${tfmRetStr}</span>`;
      }
    } else {
      timesfmPill.style.display = "none";
    }
  }

  // Update Lifespan Clock and Segments
  updateActiveSignalLifespanClock();
}

function updateGuardrailsAndLevels(signal, currentClose) {
  if (!signal) {
    lvlEntry.textContent = "--";
    lvlSL.textContent = "--";
    lvlTP1.textContent = "--";
    lvlTP2.textContent = "--";
    lvlRR.textContent = "--";
    if (rowDualAi) rowDualAi.style.display = "none";
    if (rowSignalLifespan) rowSignalLifespan.style.display = "none";
    currentSpreadRatio.textContent = "--";
    spreadMeterFill.style.width = "0%";
    spreadStatusPill.className = "guardrail-status-pill";
    spreadStatusPill.textContent = "No active trade setup";
    updateMt5ExecutionControls(null);
    return;
  }

  // Levels
  lvlEntry.textContent = formatPrice(signal.entry_price);
  lvlSL.textContent = formatPrice(signal.stop_loss);
  lvlTP1.textContent = formatPrice(signal.take_profit_1);
  lvlTP2.textContent = formatPrice(signal.take_profit_2);
  lvlRR.textContent = `1 : ${signal.risk_reward_ratio}`;
  updateMt5ExecutionControls(signal);

  if (rowDualAi) {
    if (signal.dual_ai_confluence) {
      rowDualAi.style.display = "flex";
      const retStr = signal.timesfm_return_pct >= 0 ? `+${signal.timesfm_return_pct}%` : `${signal.timesfm_return_pct}%`;
      if (lvlDualAi) lvlDualAi.innerHTML = `🤖 Confirmed (${retStr})`;
    } else {
      rowDualAi.style.display = "none";
    }
  }

  // Lifespan row display
  if (rowSignalLifespan) {
    rowSignalLifespan.style.display = showCountdownTimers ? "flex" : "none";
  }
  updateActiveSignalLifespanClock();

  // Draw Price Lines on Chart
  clearPriceLines();
  priceLines.push(
    historicalSeries.createPriceLine({
      price: signal.entry_price,
      color: "#3b82f6",
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      title: "ENTRY",
    }),
    historicalSeries.createPriceLine({
      price: signal.stop_loss,
      color: "#ef4444",
      lineWidth: 2,
      lineStyle: LightweightCharts.LineStyle.Solid,
      title: "STOP-LOSS",
    }),
    historicalSeries.createPriceLine({
      price: signal.take_profit_1,
      color: "#10b981",
      lineWidth: 2,
      lineStyle: LightweightCharts.LineStyle.Solid,
      title: "TAKE-PROFIT 1",
    })
  );

  // Spread vs Stop Loss Guardrail (< 5% Rule)
  let ratioPct = signal.spread_to_sl_ratio_pct;
  if (ratioPct === undefined || ratioPct === null || isNaN(ratioPct)) {
    if (signal.sl_distance && signal.sl_distance > 0 && signal.estimated_spread) {
      ratioPct = (signal.estimated_spread / signal.sl_distance) * 100.0;
    } else if (signal.spread_to_sl_ratio !== undefined && signal.spread_to_sl_ratio !== null && !isNaN(signal.spread_to_sl_ratio)) {
      ratioPct = signal.spread_to_sl_ratio * 100.0;
    } else if (signal.sl_distance && signal.sl_distance > 0 && signal.entry_price) {
      ratioPct = ((signal.entry_price * 0.0002) / signal.sl_distance) * 100.0;
    } else {
      ratioPct = 1.5;
    }
  }
  ratioPct = Number(Number(ratioPct).toFixed(2));
  currentSpreadRatio.textContent = `${ratioPct}% of SL`;
  
  // Meter visualization: 5% is midpoint (50% bar width)
  const meterWidth = Math.max(0, Math.min(100, (ratioPct / 10.0) * 100));
  spreadMeterFill.style.width = `${meterWidth}%`;

  const passesSpread = (signal.passes_spread_filter !== undefined && signal.passes_spread_filter !== null)
    ? Boolean(signal.passes_spread_filter)
    : (ratioPct <= 5.0);

  if (passesSpread) {
    spreadMeterFill.classList.remove("warning");
    spreadStatusPill.className = "guardrail-status-pill";
    spreadStatusPill.innerHTML = `✅ <b>PASS:</b> Spread is ${ratioPct}% (&lt; 5% Target Met)`;
  } else {
    spreadMeterFill.classList.add("warning");
    spreadStatusPill.className = "guardrail-status-pill danger";
    spreadStatusPill.innerHTML = `⚠️ <b>FILTERED:</b> Spread is ${ratioPct}% (&gt; 5% SL distance)`;
  }
}

async function updateMt5ExecutionControls(signal) {
  currentActiveSetupSignal = signal;
  if (!btnExecuteMt5Trade) return;

  if (!signal || !signal.entry_price || !signal.stop_loss) {
    if (tradeCalculatedLots) tradeCalculatedLots.textContent = "-- Lots";
    if (tradeProjectedLoss) tradeProjectedLoss.textContent = "--";
    if (tradeProjectedReward) tradeProjectedReward.textContent = "--";
    if (tradeProjectedRR) tradeProjectedRR.textContent = "--";
    btnExecuteMt5Trade.disabled = true;
    btnExecuteMt5Trade.className = "btn-execute-mt5";
    if (btnExecuteMt5Text) btnExecuteMt5Text.textContent = "No Active Setup Selected";
    return;
  }

  const risk = parseFloat(tradeRiskAmount ? tradeRiskAmount.value : 50) || 50;
  const isBuy = signal.direction === "BULLISH";
  const isSplit = currentTpMode === "split";

  try {
    if (isSplit && signal.take_profit_2) {
      const halfRisk = risk / 2.0;
      const [res1, res2] = await Promise.all([
        fetch("/api/mt5/calculate-lots", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            symbol: signal.symbol,
            entry_price: signal.entry_price,
            stop_loss: signal.stop_loss,
            dollar_risk: halfRisk,
            take_profit: signal.take_profit_1
          })
        }),
        fetch("/api/mt5/calculate-lots", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            symbol: signal.symbol,
            entry_price: signal.entry_price,
            stop_loss: signal.stop_loss,
            dollar_risk: halfRisk,
            take_profit: signal.take_profit_2
          })
        })
      ]);

      if (res1.ok && res2.ok) {
        const data1 = await res1.json();
        const data2 = await res2.json();
        const totLoss = ((data1.actual_loss_at_sl || halfRisk) + (data2.actual_loss_at_sl || halfRisk)).toFixed(2);
        const rew1 = data1.actual_reward_at_tp || 0;
        const rew2 = data2.actual_reward_at_tp || 0;
        const totRew = (rew1 + rew2).toFixed(2);

        if (tradeCalculatedLots) tradeCalculatedLots.textContent = `${data1.lots} + ${data2.lots} (50/50)`;
        if (tradeProjectedLoss) tradeProjectedLoss.textContent = `-$${totLoss} (Capped)`;
        if (tradeProjectedReward) tradeProjectedReward.textContent = `+$${totRew} (TP1+TP2)`;
        const combRR = (Number(totRew) / Math.max(1, Number(totLoss))).toFixed(2);
        if (tradeProjectedRR) tradeProjectedRR.textContent = `1 : ${combRR} (Avg)`;
        if (mt5ExecBrokerTag && data1.broker_symbol) {
          mt5ExecBrokerTag.textContent = `${data1.broker_symbol} (FundedNext)`;
        }
      }
    } else {
      const res = await fetch("/api/mt5/calculate-lots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: signal.symbol,
          entry_price: signal.entry_price,
          stop_loss: signal.stop_loss,
          dollar_risk: risk,
          take_profit: signal.take_profit_1
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (tradeCalculatedLots) tradeCalculatedLots.textContent = `${data.lots} Lots`;
        if (tradeProjectedLoss) tradeProjectedLoss.textContent = `-$${(data.actual_loss_at_sl || risk).toFixed(2)}`;
        if (tradeProjectedReward) tradeProjectedReward.textContent = `+$${(data.actual_reward_at_tp || 0).toFixed(2)}`;
        if (tradeProjectedRR) tradeProjectedRR.textContent = `1 : ${data.rr_ratio || signal.risk_reward_ratio || "--"}`;
        if (mt5ExecBrokerTag && data.broker_symbol) {
          mt5ExecBrokerTag.textContent = `${data.broker_symbol} (FundedNext)`;
        }
      }
    }
  } catch (e) {
    console.debug("Error calculating lots:", e);
  }

  btnExecuteMt5Trade.disabled = false;
  btnExecuteMt5Trade.className = isBuy ? "btn-execute-mt5 buy" : "btn-execute-mt5 sell";
  const dirText = isBuy ? "BUY" : "SELL";
  const modeTag = isSplit ? " [Split 50/50]" : "";
  if (btnExecuteMt5Text) {
    btnExecuteMt5Text.textContent = `⚡ Place ${dirText}${modeTag} on MT5 (${signal.symbol})`;
  }
}

async function executeActiveSignalOnMt5() {
  if (!currentActiveSetupSignal || !btnExecuteMt5Trade) return;

  const sig = currentActiveSetupSignal;
  const risk = parseFloat(tradeRiskAmount ? tradeRiskAmount.value : 50) || 50;
  const isBuy = sig.direction === "BULLISH";
  const dirText = isBuy ? "BUY" : "SELL";
  const isSplit = currentTpMode === "split";

  btnExecuteMt5Trade.disabled = true;
  if (btnExecuteMt5Text) btnExecuteMt5Text.textContent = `⏳ Placing ${dirText}${isSplit ? " (Split 50/50)" : ""} on MT5...`;
  if (mt5TradeFeedback) mt5TradeFeedback.style.display = "none";

  try {
    const res = await fetch("/api/mt5/execute-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: sig.symbol,
        direction: dirText,
        timeframe: sig.timeframe || currentTimeframe || "1h",
        entry_price: sig.entry_price,
        dollar_risk: risk,
        sl: sig.stop_loss,
        tp: sig.take_profit_1,
        tp2: sig.take_profit_2,
        split_tp: isSplit,
        comment: `AI ${sig.timeframe || currentTimeframe || "1h"}`
      })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      if (mt5TradeFeedback) {
        mt5TradeFeedback.className = "mt5-feedback-success";
        if (data.split) {
          mt5TradeFeedback.innerHTML = `🎉 <b>Split Orders Executed!</b> Tickets <b>#${data.tickets.join(", #")}</b><br/>Order 1: ${data.orders[0]?.volume || ""} Lots to TP1 | Order 2: ${data.orders[1]?.volume || ""} Lots to TP2<br/><small style="color:var(--text-muted)">Total Max Risk Capped at $${risk.toFixed(2)}</small>`;
        } else {
          mt5TradeFeedback.innerHTML = `🎉 <b>Order Executed!</b> Ticket <b>#${data.ticket}</b><br/>${data.volume} Lots of ${data.symbol} @ ${formatPrice(data.price)}<br/><small style="color:var(--text-muted)">SL: ${formatPrice(data.sl)} | TP: ${formatPrice(data.tp)}</small>`;
        }
        mt5TradeFeedback.style.display = "block";
      }
      const ticketStr = data.split ? data.tickets.join(", #") : data.ticket;
      if (btnExecuteMt5Text) btnExecuteMt5Text.textContent = `✅ Order #${ticketStr} Placed!`;
      setTimeout(() => {
        btnExecuteMt5Trade.disabled = false;
        if (btnExecuteMt5Text) btnExecuteMt5Text.textContent = `⚡ Place ${dirText} on FundedNext MT5 (${sig.symbol})`;
      }, 5000);
      loadPerformance();
      loadPropGuardStatus();
    } else {
      const errMsg = data.detail || data.error || data.comment || "Order execution rejected by broker";
      if (mt5TradeFeedback) {
        mt5TradeFeedback.className = "mt5-feedback-error";
        mt5TradeFeedback.textContent = `❌ ${errMsg}`;
        mt5TradeFeedback.style.display = "block";
      }
      btnExecuteMt5Trade.disabled = false;
      if (btnExecuteMt5Text) btnExecuteMt5Text.textContent = `⚡ Place ${dirText} on FundedNext MT5 (${sig.symbol})`;
      loadPropGuardStatus();
    }
  } catch (err) {
    if (mt5TradeFeedback) {
      mt5TradeFeedback.className = "mt5-feedback-error";
      mt5TradeFeedback.textContent = `❌ Execution Error: ${err.message}`;
      mt5TradeFeedback.style.display = "block";
    }
    btnExecuteMt5Trade.disabled = false;
    if (btnExecuteMt5Text) btnExecuteMt5Text.textContent = `⚡ Place ${dirText} on FundedNext MT5 (${sig.symbol})`;
  }
}

function formatPrice(val) {
  if (val === undefined || val === null || isNaN(val)) return "--";
  if (val >= 1000) return val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (val >= 1) return val.toFixed(4);
  return val.toFixed(6);
}


// 3. WATCHLIST & ASSET SELECTION
async function loadWatchlist() {
  try {
    const res = await fetch("/api/watchlist");
    const data = await res.json();
    watchlistData = data.watchlist || [];
    renderWatchlist();
  } catch (e) {
    console.error("Error loading watchlist:", e);
  }
}

function renderWatchlist() {
  const filtered = watchlistData.filter((item) => {
    if (currentCategory === "ALL") return true;
    return item.category.toLowerCase() === currentCategory.toLowerCase();
  });

  watchlistContainer.innerHTML = "";

  if (filtered.length === 0) {
    watchlistContainer.innerHTML = `<div class="empty-history">No assets found for category "${currentCategory}".</div>`;
    return;
  }

  filtered.forEach((asset) => {
    const el = document.createElement("div");
    el.className = "watchlist-item" + (asset.symbol === currentSymbol ? " active-asset" : "");
    el.innerHTML = `
      <div class="asset-meta">
        <span class="sym">${asset.symbol}</span>
        <span class="nm">${asset.name}</span>
      </div>
      <div class="asset-right">
        <span class="asset-badge">${asset.category}</span>
        <input type="checkbox" title="Include in automated scans" ${asset.active ? "checked" : ""} class="asset-toggle" data-symbol="${asset.symbol}" />
        <button class="item-delete-btn" data-symbol="${asset.symbol}" title="Remove asset">&times;</button>
      </div>
    `;

    // Click item to load chart
    el.addEventListener("click", (e) => {
      if (e.target.classList.contains("asset-toggle") || e.target.classList.contains("item-delete-btn")) return;
      document.querySelectorAll(".watchlist-item").forEach((x) => x.classList.remove("active-asset"));
      el.classList.add("active-asset");
      loadChartData(asset.symbol, currentTimeframe);
    });

    // Toggle active state
    const toggle = el.querySelector(".asset-toggle");
    toggle.addEventListener("change", async (e) => {
      await fetch("/api/watchlist/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: asset.symbol, active: e.target.checked }),
      });
      asset.active = e.target.checked;
    });

    // Delete asset
    const delBtn = el.querySelector(".item-delete-btn");
    delBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (confirm(`Remove ${asset.symbol} from watchlist?`)) {
        await fetch(`/api/watchlist/${encodeURIComponent(asset.symbol)}`, { method: "DELETE" });
        await loadWatchlist();
      }
    });

    watchlistContainer.appendChild(el);
  });
}


// 4. SIGNALS & SYSTEM STATUS
async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    // Session badge
    sessionText.textContent = data.active_session;
    if (data.is_london_ny_overlap) {
      sessionBadge.className = "metric-badge session-badge overlap";
    } else {
      sessionBadge.className = "metric-badge session-badge";
    }

    // Device badge
    deviceText.textContent = data.device.includes("cuda") ? "⚡ RTX 5080 (CUDA)" : "💻 24-Core CPU";

    // MT5 status badge
    if (data.mt5) {
      const mt5Badge = document.getElementById("mt5Badge");
      const mt5Text = document.getElementById("mt5Text");
      if (mt5Badge && mt5Text) {
        if (data.mt5.is_connected) {
          mt5Badge.className = "metric-badge mt5-badge connected";
          const srv = data.mt5.account?.server || "Live";
          mt5Text.textContent = `🟢 MT5: ${srv}`;
        } else {
          mt5Badge.className = "metric-badge mt5-badge";
          mt5Text.textContent = "⚪ MT5: Offline";
        }
      }
    }

    // Scan progress
    scanStatusText.textContent = `Status: ${data.scan_status_text}`;
    if (data.is_scanning) {
      progressBarContainer.style.display = "block";
      btnScanNow.disabled = true;
    } else {
      progressBarContainer.style.display = "none";
      btnScanNow.disabled = false;
    }
  } catch (e) {
    console.error("Error loading status:", e);
  }
}

function renderSignalsList() {
  if (!signalsData || signalsData.length === 0) {
    signalHistoryList.innerHTML = `<div class="empty-history">No signals recorded yet. Click "Run Scan Now" to scan active watchlist.</div>`;
    signalCountBadge.textContent = "0";
    return;
  }

  // 1. Sort signals by most recent first (newest timestamp / candle_unix at the top)
  const sorted = [...signalsData].sort((a, b) => {
    const timeA = a.candle_unix || (a.timestamp ? (typeof a.timestamp === "number" ? a.timestamp : new Date(a.timestamp).getTime() / 1000) : 0);
    const timeB = b.candle_unix || (b.timestamp ? (typeof b.timestamp === "number" ? b.timestamp : new Date(b.timestamp).getTime() / 1000) : 0);
    return timeB - timeA;
  });

  // 2. Filter by selected timeframe(s)
  let filtered = selectedTfs.has("ALL")
    ? sorted
    : sorted.filter((s) => isTfSelected(s.timeframe));

  if (perfDualAiOnly && perfDualAiOnly.checked) {
    filtered = filtered.filter((s) => s.dual_ai_confluence === true);
  }

  signalCountBadge.textContent = filtered.length;

  if (filtered.length === 0) {
    signalHistoryList.innerHTML = `<div class="empty-history">No ${getSelectedTfsDisplay()} signals recorded yet.</div>`;
    return;
  }

  signalHistoryList.innerHTML = "";
  filtered.forEach((sig) => {
    const card = document.createElement("div");
    card.className = "signal-card-mini";
    const tradeId = sig.id || `${sig.symbol}_${sig.timeframe}_${sig.candle_unix || ""}`;
    card.dataset.tradeId = tradeId;
    if (pinnedActiveSignal && (pinnedActiveSignal.id === tradeId || (pinnedActiveSignal.symbol === sig.symbol && pinnedActiveSignal.timeframe === sig.timeframe && pinnedActiveSignal.entry_price === sig.entry_price))) {
      card.classList.add("active-signal-card");
    }

    const badgeClass = sig.direction === "BULLISH" ? "sig-badge-long" : "sig-badge-short";
    const dirText = sig.direction === "BULLISH" ? "LONG" : "SHORT";
    const dualBadge = sig.dual_ai_confluence ? `<span class="sig-badge-dual">🤖 DUAL AI</span>` : "";

    const maxC = sig.max_candles || currentForecastCandles || 5;
    const step = getTimeframeSeconds(sig.timeframe);
    const nowSec = Math.floor(Date.now() / 1000);
    const entryUnix = sig.candle_unix || Math.floor(new Date(sig.timestamp).getTime() / 1000) || nowSec;
    const expUnix = sig.expires_at_unix || (entryUnix + maxC * step);
    const secLeft = Math.max(0, expUnix - nowSec);
    const elapsedBars = Math.min(maxC, Math.max(0, Math.floor((nowSec - entryUnix) / step)));
    const currentBar = Math.min(maxC, elapsedBars + 1);

    const isPaused = sig.is_market_paused || sig.is_market_open === false;
    let countdownHtml = "";
    if (showCountdownTimers) {
      if (isPaused) {
        countdownHtml = `<span class="sig-countdown paused" data-paused="true" title="${sig.market_reason || 'Market is closed on broker'}">⏸️ Paused (Market Closed)</span>`;
      } else if (secLeft <= 0) {
        countdownHtml = `<span class="sig-countdown completed" data-entry="${entryUnix}" data-tf="${sig.timeframe}" data-max="${maxC}">⏱️ Finished (${maxC}/${maxC} [${sig.timeframe}])</span>`;
      } else {
        countdownHtml = `<span class="sig-countdown" data-entry="${entryUnix}" data-tf="${sig.timeframe}" data-max="${maxC}">⏳ Bar ${currentBar}/${maxC} [${sig.timeframe}] (${formatRemainingDuration(secLeft)} left)</span>`;
      }
    }

    card.innerHTML = `
      <div class="sig-header">
        <span class="sig-sym">${sig.symbol} <small style="color:var(--text-muted);font-weight:normal">${sig.timeframe}</small></span>
        <div>
          <span class="${badgeClass}">${dirText} ${sig.conviction}%</span>
          ${dualBadge}
        </div>
      </div>
      <div class="sig-body">
        <span>Entry: ${formatPrice(sig.entry_price)}</span>
        <span>R:R ${sig.risk_reward_ratio}</span>
      </div>
      <div class="sig-footer" style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
        <div class="sig-time">${sig.timestamp ? sig.timestamp.split(" ")[1] : ""} UTC | ${sig.session_name ? sig.session_name.split(" ")[0] : ""}</div>
        ${countdownHtml}
      </div>
    `;

    card.addEventListener("click", async () => {
      document.querySelectorAll(".signal-card-mini").forEach((c) => c.classList.remove("active-signal-card"));
      card.classList.add("active-signal-card");
      currentTimeframe = sig.timeframe;
      if (timeframeSelect) {
        timeframeSelect.value = sig.timeframe;
      }
      await loadChartData(sig.symbol, sig.timeframe, sig);
      const targetUnix = sig.candle_unix || (sig.timestamp ? Math.floor(new Date(sig.timestamp).getTime() / 1000) : null);
      frameChartToCandle(targetUnix, sig.timeframe);
    });

    signalHistoryList.appendChild(card);
  });
}

async function loadSignals() {
  try {
    const res = await fetch("/api/signals");
    const data = await res.json();
    signalsData = data.signals || [];
    renderSignalsList();
  } catch (e) {
    console.error("Error loading signals:", e);
  }
}

function formatUtcTimestamp(strOrUnix) {
  if (!strOrUnix) return "--";
  if (typeof strOrUnix === "number") {
    const d = new Date(strOrUnix * 1000);
    return d.toISOString().replace("T", " ").slice(5, 16) + " UTC";
  }
  const clean = String(strOrUnix).replace(" UTC", "");
  return clean.length >= 16 ? clean.slice(5, 16) + " UTC" : clean;
}

function updatePerformanceDisplay() {
  let filtered = closedTradesData || [];
  if (currentMinConviction !== null && currentMinConviction !== undefined) {
    filtered = filtered.filter((t) => (t.conviction ?? 0) >= currentMinConviction);
  }
  let activeFiltered = activeTradesData || [];
  if (perfDualAiOnly && perfDualAiOnly.checked) {
    filtered = filtered.filter((t) => t.dual_ai_confluence === true);
    activeFiltered = activeFiltered.filter((t) => t.dual_ai_confluence === true);
  }
  if (!selectedTfs.has("ALL")) {
    filtered = filtered.filter((t) => isTfSelected(t.timeframe));
    activeFiltered = activeFiltered.filter((t) => isTfSelected(t.timeframe));
  }

  const total = filtered.length;
  let wins = 0;
  let losses = 0;
  let tpWins = 0;
  let slLosses = 0;
  let expWins = 0;
  let expLosses = 0;
  let grossProfit = 0;
  let grossLoss = 0;
  let totalR = 0;

  filtered.forEach((t) => {
    const outcome = t.outcome || "";
    const r = Number(t.realized_r) || 0;
    totalR += r;
    if (r > 0) grossProfit += r;
    if (r < 0) grossLoss += Math.abs(r);

    if (outcome === "WIN" || outcome === "EXPIRED_PROFIT") {
      wins++;
    } else if (outcome === "LOSS" || outcome === "EXPIRED_LOSS") {
      losses++;
    }

    if (outcome === "WIN") tpWins++;
    else if (outcome === "LOSS") slLosses++;
    else if (outcome === "EXPIRED_PROFIT") expWins++;
    else if (outcome === "EXPIRED_LOSS") expLosses++;
  });

  const winRate = total > 0 ? ((wins / total) * 100).toFixed(1) : "0.0";
  let profitFactor = "1.0";
  if (grossLoss > 0) {
    profitFactor = (grossProfit / grossLoss).toFixed(2);
  } else if (grossProfit > 0) {
    profitFactor = grossProfit.toFixed(2);
  }

  if (statWinRate) {
    statWinRate.textContent = `${winRate}%`;
    const wrNum = parseFloat(winRate);
    if (wrNum >= 60) {
      statWinRate.style.color = "var(--accent-green)";
    } else if (wrNum < 45 && total > 0) {
      statWinRate.style.color = "var(--accent-red)";
    } else {
      statWinRate.style.color = "var(--accent-cyan)";
    }
  }

  if (statProfitFactor) {
    statProfitFactor.textContent = profitFactor;
  }

  if (statRecord) {
    statRecord.textContent = `${wins}W - ${losses}L`;
  }

  if (statTotalR) {
    const roundedR = totalR.toFixed(2);
    statTotalR.textContent = (totalR >= 0 ? "+" : "") + roundedR + "R";
    statTotalR.style.color = totalR >= 0 ? "var(--accent-green)" : "var(--accent-red)";
  }

  if (perfActiveCount) {
    perfActiveCount.textContent = `${activeFiltered.length} Active`;
  }

  if (resolvedCountBadge) {
    resolvedCountBadge.textContent = filtered.length;
  }

  const elTpWins = document.getElementById("breakdownTpWins");
  const elExpWins = document.getElementById("breakdownExpWins");
  const elSlLosses = document.getElementById("breakdownSlLosses");
  const elExpLosses = document.getElementById("breakdownExpLosses");
  if (elTpWins) elTpWins.textContent = `🎯 ${tpWins} TP`;
  if (elExpWins) elExpWins.textContent = `⏱️ +${expWins} Exp`;
  if (elSlLosses) elSlLosses.textContent = `🛑 ${slLosses} SL`;
  if (elExpLosses) elExpLosses.textContent = `⏱️ -${expLosses} Exp`;
}

function renderOutcomesList() {
  if (!resolvedTradesList) return;

  const list = (closedTradesData || []).filter((tr) => {
    if (!isTfSelected(tr.timeframe)) {
      return false;
    }
    if (currentMinConviction !== null && (tr.conviction ?? 0) < currentMinConviction) {
      return false;
    }
    if (perfDualAiOnly && perfDualAiOnly.checked && !tr.dual_ai_confluence) {
      return false;
    }
    return true;
  });

  if (resolvedCountBadge) {
    resolvedCountBadge.textContent = list.length;
  }

  if (list.length === 0) {
    resolvedTradesList.innerHTML = `<div class="empty-history">No ${!selectedTfs.has("ALL") ? getSelectedTfsDisplay() : ""} closed trades found.</div>`;
    return;
  }

  resolvedTradesList.innerHTML = "";
  list.forEach((tr) => {
    const card = document.createElement("div");
    card.className = "signal-card-mini";
    const tradeId = tr.id || `${tr.symbol}_${tr.timeframe}_${tr.entry_candle_unix || tr.opened_unix || ""}`;
    card.dataset.tradeId = tradeId;
    if (pinnedActiveSignal && (pinnedActiveSignal.id === tradeId || (pinnedActiveSignal.symbol === tr.symbol && pinnedActiveSignal.timeframe === tr.timeframe && pinnedActiveSignal.entry_price === tr.entry_price))) {
      card.classList.add("active-signal-card");
    }

    let badgeClass = "sig-badge-expired";
    let outcomeLabel = tr.outcome || "EXPIRED";
    let pnlClass = (tr.realized_r >= 0) ? "sig-pnl-win" : "sig-pnl-loss";

    if (tr.outcome === "WIN") {
      badgeClass = "sig-badge-win";
      if (tr.runner_outcome === "TP2_HIT") {
        outcomeLabel = "WIN (TP1+TP2)";
      } else if (tr.runner_outcome === "BREAKEVEN_HIT") {
        outcomeLabel = "WIN (TP1+BE)";
      } else if (tr.runner_outcome === "EXPIRED_BAR5") {
        outcomeLabel = "WIN (TP1+Exp)";
      } else {
        outcomeLabel = "WIN";
      }
    } else if (tr.outcome === "LOSS") {
      badgeClass = "sig-badge-loss";
      outcomeLabel = "LOSS (SL)";
    } else if (tr.outcome === "EXPIRED_PROFIT") {
      badgeClass = "sig-badge-win";
      outcomeLabel = "EXP +PNL";
    } else if (tr.outcome === "EXPIRED_LOSS") {
      badgeClass = "sig-badge-loss";
      outcomeLabel = "EXP -PNL";
    } else if (tr.outcome === "EXPIRED_BREAKEVEN") {
      badgeClass = "sig-badge-expired";
      outcomeLabel = "EXP BE";
    }

    const pnlSign = (tr.realized_pnl_pct >= 0 ? "+" : "");
    const rSign = (tr.realized_r >= 0 ? "+" : "");
    const pnlStr = `${pnlSign}${tr.realized_pnl_pct ?? 0}% (${rSign}${tr.realized_r ?? 0}R)`;
    const maxC = tr.max_candles || currentForecastCandles || 5;
    const hitBar = tr.hit_on_candle || tr.candles_monitored || maxC;
    const candleDuration = `Bar ${hitBar}/${maxC} [${tr.timeframe || "1h"}]`;

    const isBull = tr.direction === "BULLISH";
    const dirBadge = isBull
      ? `<span class="dir-badge bullish" style="font-size:9px;padding:1px 4px;margin-left:4px;">🟢 BUY</span>`
      : `<span class="dir-badge bearish" style="font-size:9px;padding:1px 4px;margin-left:4px;">🔴 SELL</span>`;
    const dualBadge = tr.dual_ai_confluence
      ? `<span class="sig-badge-dual" style="font-size:9px;padding:1px 4px;margin-left:4px;">🤖 DUAL</span>`
      : "";

    const openedStr = formatUtcTimestamp(tr.opened_at || tr.opened_unix);
    const closedStr = formatUtcTimestamp(tr.closed_at || tr.closed_unix);
    const sessionStr = tr.session_name ? tr.session_name.split(" ")[0] : "Market";

    card.innerHTML = `
      <div class="sig-header">
        <span class="sig-sym">
          ${tr.symbol} <small style="color:var(--text-muted);font-weight:600">${tr.timeframe}</small>
          ${dirBadge}
          ${dualBadge}
        </span>
        <span class="${badgeClass}">${outcomeLabel}</span>
      </div>

      <div class="outcome-meta-grid">
        <div class="outcome-meta-item">
          <span class="meta-label">Entry &rarr; Exit</span>
          <span class="meta-val">${formatPrice(tr.entry_price)} &rarr; ${formatPrice(tr.exit_price || tr.entry_price)}</span>
        </div>
        <div class="outcome-meta-item">
          <span class="meta-label">PnL / Return</span>
          <span class="meta-val ${pnlClass}">${pnlStr}</span>
        </div>
        <div class="outcome-meta-item">
          <span class="meta-label">SL / TP</span>
          <span class="meta-val">${formatPrice(tr.sl)} / ${formatPrice(tr.tp)}</span>
        </div>
        <div class="outcome-meta-item">
          <span class="meta-label">Duration</span>
          <span class="meta-val">${candleDuration}</span>
        </div>
      </div>

      <div class="outcome-timestamps">
        <div class="outcome-time-row">
          <span>In: ${openedStr}</span>
          <span>Out: ${closedStr}</span>
        </div>
        <div class="outcome-time-row" style="color: var(--text-secondary); margin-top: 2px;">
          <span>${sessionStr} | Conv: ${tr.conviction || 0}%</span>
          <span title="${tr.exit_reason || ''}" style="max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            ${tr.exit_reason || outcomeLabel}
          </span>
        </div>
      </div>
    `;

    card.addEventListener("click", async () => {
      document.querySelectorAll(".signal-card-mini").forEach((c) => c.classList.remove("active-signal-card"));
      card.classList.add("active-signal-card");
      currentTimeframe = tr.timeframe || "1h";
      if (timeframeSelect) {
        timeframeSelect.value = currentTimeframe;
      }
      await loadChartData(tr.symbol, currentTimeframe, tr);
      const targetUnix = tr.entry_candle_unix || tr.opened_unix;
      frameChartToCandle(targetUnix, currentTimeframe);
    });

    resolvedTradesList.appendChild(card);
  });
}

async function loadPerformance() {
  try {
    const res = await fetch(`/api/performance?limit=200`);
    if (!res.ok) return;
    const data = await res.json();
    const closedTrades = data.closed_trades || [];
    const activeTrades = data.active_trades || [];
    activeTradesData = activeTrades;
    closedTradesData = closedTrades;
    updateActiveSignalLifespanClock();
    renderChartTradeMarkers();

    updatePerformanceDisplay();
    renderOutcomesList();
  } catch (e) {
    console.error("Error loading performance:", e);
  }
}


// 5. EVENT LISTENERS & MODALS
function setupEventListeners() {
  const btnToggleWatchlist = document.getElementById("btnToggleWatchlist");
  const btnExpandWatchlist = document.getElementById("btnExpandWatchlist");
  const terminalBody = document.getElementById("terminalBody");

  function setWatchlistCollapsed(collapsed) {
    if (!terminalBody) return;
    if (collapsed) {
      terminalBody.classList.add("watchlist-collapsed");
      if (btnExpandWatchlist) btnExpandWatchlist.style.display = "inline-flex";
    } else {
      terminalBody.classList.remove("watchlist-collapsed");
      if (btnExpandWatchlist) btnExpandWatchlist.style.display = "none";
    }
    setTimeout(() => {
      if (chart && chartContainer) {
        chart.applyOptions({
          width: chartContainer.clientWidth,
          height: chartContainer.clientHeight,
        });
      }
    }, 60);
  }

  if (btnToggleWatchlist) {
    btnToggleWatchlist.addEventListener("click", () => setWatchlistCollapsed(true));
  }
  if (btnExpandWatchlist) {
    btnExpandWatchlist.addEventListener("click", () => setWatchlistCollapsed(false));
  }

  // On smaller screens <= 1080px, auto-collapse watchlist so chart & right sidebar have ample room
  if (window.innerWidth <= 1080) {
    setWatchlistCollapsed(true);
  }

  // -------------------------------------------------------------
  // Draggable Splitter: Drag from Right to Left to Expand Sidebar
  // -------------------------------------------------------------
  function initSidebarResizer() {
    const resizer = document.getElementById("rightSidebarResizer");
    if (!resizer || !terminalBody) return;

    // Restore saved width from localStorage if present
    const savedWidth = localStorage.getItem("signalSidebarWidth");
    if (savedWidth) {
      const parsed = parseInt(savedWidth, 10);
      if (!isNaN(parsed) && parsed >= 260 && parsed <= window.innerWidth * 0.7) {
        document.documentElement.style.setProperty("--signal-sidebar-width", `${parsed}px`);
      }
    }

    let isDragging = false;
    let startX = 0;
    let startWidth = 310;

    resizer.addEventListener("pointerdown", (e) => {
      isDragging = true;
      startX = e.clientX;
      resizer.setPointerCapture(e.pointerId);

      const currentWidthStr = getComputedStyle(document.documentElement).getPropertyValue("--signal-sidebar-width").trim();
      startWidth = parseInt(currentWidthStr, 10) || 310;

      resizer.classList.add("resizing");
      document.body.classList.add("col-resizing");
      e.preventDefault();
    });

    resizer.addEventListener("pointermove", (e) => {
      if (!isDragging) return;

      // Dragging right-to-left (startX - e.clientX) increases width
      const deltaX = startX - e.clientX;
      const minW = 260;
      const maxW = Math.max(minW, Math.floor(window.innerWidth * 0.65));
      const newWidth = Math.min(maxW, Math.max(minW, startWidth + deltaX));

      document.documentElement.style.setProperty("--signal-sidebar-width", `${newWidth}px`);

      if (chart && chartContainer) {
        requestAnimationFrame(() => {
          chart.applyOptions({
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight,
          });
        });
      }
    });

    function stopDrag(e) {
      if (!isDragging) return;
      isDragging = false;
      try {
        resizer.releasePointerCapture(e.pointerId);
      } catch (_) {}

      resizer.classList.remove("resizing");
      document.body.classList.remove("col-resizing");

      const finalWidthStr = getComputedStyle(document.documentElement).getPropertyValue("--signal-sidebar-width").trim();
      localStorage.setItem("signalSidebarWidth", finalWidthStr);

      if (chart && chartContainer) {
        chart.applyOptions({
          width: chartContainer.clientWidth,
          height: chartContainer.clientHeight,
        });
      }
    }

    resizer.addEventListener("pointerup", stopDrag);
    resizer.addEventListener("pointercancel", stopDrag);

    // Double-click to toggle between standard width (310px) and wide view (460px)
    resizer.addEventListener("dblclick", () => {
      const currentWidthStr = getComputedStyle(document.documentElement).getPropertyValue("--signal-sidebar-width").trim();
      const currW = parseInt(currentWidthStr, 10) || 310;
      const targetW = currW > 360 ? 310 : 460;
      document.documentElement.style.setProperty("--signal-sidebar-width", `${targetW}px`);
      localStorage.setItem("signalSidebarWidth", `${targetW}px`);
      if (chart && chartContainer) {
        setTimeout(() => {
          chart.applyOptions({
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight,
          });
        }, 60);
      }
    });
  }

  initSidebarResizer();

  // Download helper for CSV / JSON export
  async function downloadExportFile(format, tf = null) {
    try {
      const tfParam = tf && tf.toUpperCase() !== "ALL" ? `&timeframe=${encodeURIComponent(tf)}` : "";
      const isDualAi = perfDualAiOnly && perfDualAiOnly.checked;
      const dualParam = isDualAi ? "&dual_ai_only=true" : "";
      const convParam = currentMinConviction && currentMinConviction > 0 ? `&min_conviction=${currentMinConviction}` : "";
      const res = await fetch(`/api/performance/export?format=${format}${tfParam}${dualParam}${convParam}`);
      if (!res.ok) throw new Error("Failed to export history");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
      const ext = format === "csv" ? "csv" : "json";
      const tfSuffix = tf && tf.toUpperCase() !== "ALL" ? `_${tf}` : "";
      const dualSuffix = isDualAi ? "_dual_ai" : "";
      a.href = url;
      a.download = `trade_history${tfSuffix}${dualSuffix}_${ts}.${ext}`;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        try {
          document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
        } catch (err) {}
      }, 250);
      if (exportModal) exportModal.style.display = "none";
    } catch (e) {
      console.error("Export error:", e);
      alert(`Failed to export trade history: ${e.message}`);
    }
  }

  // History Export Modal & Actions
  if (btnExportHistory) {
    btnExportHistory.addEventListener("click", () => {
      if (exportModal) {
        document.querySelectorAll(".export-current-tf-label").forEach((el) => {
          el.textContent = getSelectedTfsDisplay();
        });
        const elNotice = document.getElementById("exportFilterNotice");
        if (elNotice) {
          elNotice.style.display = (perfDualAiOnly && perfDualAiOnly.checked) ? "block" : "none";
        }
        exportModal.style.display = "flex";
      } else {
        downloadExportFile("json", null);
      }
    });

    if (exportModal) {
      exportModal.addEventListener("click", (e) => {
        if (e.target === exportModal) {
          exportModal.style.display = "none";
        }
      });
    }

    if (btnCloseExportModal && exportModal) {
      btnCloseExportModal.addEventListener("click", () => {
        exportModal.style.display = "none";
      });
    }

    if (btnExportCsvAll) {
      btnExportCsvAll.addEventListener("click", () => downloadExportFile("csv", null));
    }
    if (btnExportCsvFiltered) {
      btnExportCsvFiltered.addEventListener("click", () => downloadExportFile("csv", currentSignalTfFilter));
    }
    if (btnExportJsonAll) {
      btnExportJsonAll.addEventListener("click", () => downloadExportFile("json", null));
    }
    if (btnExportJsonFiltered) {
      btnExportJsonFiltered.addEventListener("click", () => downloadExportFile("json", currentSignalTfFilter));
    }
  }

  // Clear / Reset Trade History
  if (btnClearHistory) {
    btnClearHistory.addEventListener("click", async () => {
      const ok = confirm(
        "⚠️ CLEAR TRADE HISTORY & START FROM SCRATCH?\n\n" +
        "This will reset all active and closed trade records in memory and on disk.\n" +
        "An automatic safety backup copy will be saved before clearing.\n\n" +
        "Click OK to clear history."
      );
      if (!ok) return;

      try {
        const res = await fetch("/api/performance/clear", { method: "POST" });
        const data = await res.json();
        if (data.status === "success") {
          alert(`🧹 Trade history cleared successfully!\n${data.message}`);
          await loadPerformance();
          await loadSignals();
        } else {
          alert(`Failed to clear: ${data.message || "Unknown error"}`);
        }
      } catch (e) {
        console.error("Clear error:", e);
        alert(`Error clearing history: ${e.message}`);
      }
    });
  }

  if (btnImportHistory && historyFileInput) {
    btnImportHistory.addEventListener("click", () => {
      historyFileInput.value = "";
      historyFileInput.click();
    });

    historyFileInput.addEventListener("change", async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = async (event) => {
        try {
          const payload = JSON.parse(event.target.result);
          if (!payload || (!payload.closed_trades && !payload.trades)) {
            alert("Invalid trade history JSON file format. Expected 'closed_trades' list.");
            return;
          }

          const shouldMerge = confirm(
            `Importing trade history file: "${file.name}"\n\n` +
            `• Click OK to MERGE with existing history (combines without losing records)\n` +
            `• Click Cancel to REPLACE current history completely`
          );

          const res = await fetch("/api/performance/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              active_trades: payload.active_trades || [],
              closed_trades: payload.closed_trades || payload.trades || [],
              merge: shouldMerge
            })
          });

          const data = await res.json();
          if (data.status === "ok") {
            alert(`✅ Trade history imported successfully!\n${data.message}`);
            await loadPerformance();
          } else {
            alert(`Failed to import: ${data.message || "Unknown error"}`);
          }
        } catch (err) {
          console.error("Import parse error:", err);
          alert(`Error reading JSON file: ${err.message}`);
        }
      };
      reader.readAsText(file);
    });
  }

  // MT5 Badge Click to connect/refresh
  const mt5Badge = document.getElementById("mt5Badge");
  if (mt5Badge) {
    mt5Badge.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/mt5/connect", { method: "POST" });
        const resData = await res.json();
        if (resData.success) {
          alert(`✅ Successfully connected to MetaTrader 5 (${resData.status.account?.server || "Server"})!\nAccount: ${resData.status.account?.login || "N/A"}`);
        } else {
          alert(`ℹ️ MetaTrader 5 status: ${resData.status.last_error || "Not connected"}.\n\nEnsure MetaTrader 5 is launched on your PC!`);
        }
        await loadStatus();
      } catch (e) {
        console.error("MT5 connect error:", e);
      }
    });
  }

  // Timeframe selector
  timeframeSelect.addEventListener("change", (e) => {
    currentTimeframe = e.target.value;
    loadChartData(currentSymbol, currentTimeframe);
  });

  // History tab toggles (Recent Signals vs Resolved Outcomes)
  if (tabRecentSignals && tabResolvedTrades) {
    tabRecentSignals.addEventListener("click", () => {
      tabRecentSignals.classList.add("active");
      tabResolvedTrades.classList.remove("active");
      signalHistoryList.style.display = "block";
      resolvedTradesList.style.display = "none";
      if (signalsTfFilterBar) signalsTfFilterBar.style.display = "flex";
    });

    tabResolvedTrades.addEventListener("click", () => {
      tabResolvedTrades.classList.add("active");
      tabRecentSignals.classList.remove("active");
      signalHistoryList.style.display = "none";
      resolvedTradesList.style.display = "block";
      if (signalsTfFilterBar) signalsTfFilterBar.style.display = "flex";
      renderOutcomesList();
    });
  }

  // Timeframe sub-filter buttons for Signals & Outcomes tabs with Shift / Ctrl multi-select
  document.querySelectorAll(".sig-tf-tab").forEach((tab) => {
    tab.addEventListener("click", (e) => {
      const tf = (tab.dataset.tf || "ALL").toLowerCase();
      const isMultiKey = e.shiftKey || e.ctrlKey || e.metaKey;

      if (tf === "all") {
        selectedTfs = new Set(["ALL"]);
      } else if (isMultiKey) {
        // Multi-select toggle mode (Shift, Ctrl, or Cmd held)
        if (selectedTfs.has("ALL")) {
          selectedTfs.clear();
        }
        if (selectedTfs.has(tf)) {
          selectedTfs.delete(tf);
          if (selectedTfs.size === 0) {
            selectedTfs.add("ALL");
          }
        } else {
          selectedTfs.add(tf);
        }
      } else {
        // Normal click: if multiple are already selected and user clicks one of them, toggle it off
        if (selectedTfs.size > 1 && selectedTfs.has(tf)) {
          selectedTfs.delete(tf);
        } else {
          // Standard single-select switch
          selectedTfs = new Set([tf]);
        }
      }

      // If user ended up selecting all 5 timeframes, simplify to ALL
      const ALL_TFS = ["5m", "15m", "1h", "4h", "1d"];
      if (ALL_TFS.every((t) => selectedTfs.has(t))) {
        selectedTfs = new Set(["ALL"]);
      }

      // Update active CSS classes on all tabs
      document.querySelectorAll(".sig-tf-tab").forEach((t) => {
        const tabTf = (t.dataset.tf || "ALL").toLowerCase();
        if (selectedTfs.has("ALL")) {
          t.classList.toggle("active", tabTf === "all");
        } else {
          t.classList.toggle("active", selectedTfs.has(tabTf));
        }
      });

      currentSignalTfFilter = getSelectedTfsString();
      renderSignalsList();
      renderOutcomesList();
      updatePerformanceDisplay();
    });
  });

  // Conviction filter slider
  if (perfConvictionFilter) {
    perfConvictionFilter.addEventListener("input", (e) => {
      currentMinConviction = parseInt(e.target.value);
      if (perfConvictionLabel) {
        perfConvictionLabel.innerHTML = `&ge; ${currentMinConviction}%`;
      }
      updatePerformanceDisplay();
      renderOutcomesList();
    });
  }

  // Dual AI Confluence filter checkbox
  if (perfDualAiOnly) {
    perfDualAiOnly.addEventListener("change", () => {
      updatePerformanceDisplay();
      renderSignalsList();
      renderOutcomesList();
    });
  }

  // 1-Click MT5 Execution: Risk quick pills ($25, $50, $100, $250)
  let riskDebounceTimer = null;
  function saveRiskPreference(riskVal) {
    clearTimeout(riskDebounceTimer);
    riskDebounceTimer = setTimeout(async () => {
      try {
        await fetch("/api/settings/strategy", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ default_dollar_risk: parseFloat(riskVal) || 50 })
        });
      } catch (e) {
        console.debug("Failed saving risk preference:", e);
      }
    }, 800);
  }

  document.querySelectorAll(".risk-pill-btn").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".risk-pill-btn").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      const r = pill.dataset.risk;
      if (tradeRiskAmount) {
        tradeRiskAmount.value = r;
        saveRiskPreference(r);
        if (currentActiveSetupSignal) {
          updateMt5ExecutionControls(currentActiveSetupSignal);
        }
      }
    });
  });

  if (tradeRiskAmount) {
    tradeRiskAmount.addEventListener("input", () => {
      document.querySelectorAll(".risk-pill-btn").forEach((p) => {
        p.classList.toggle("active", p.dataset.risk === tradeRiskAmount.value);
      });
      saveRiskPreference(tradeRiskAmount.value);
      if (currentActiveSetupSignal) {
        updateMt5ExecutionControls(currentActiveSetupSignal);
      }
    });
  }

  // TP Mode Selector pills (Single TP1 vs Split 50/50 TP1 & TP2)
  if (btnTpModeSingle && btnTpModeSplit) {
    btnTpModeSingle.addEventListener("click", () => {
      btnTpModeSingle.classList.add("active");
      btnTpModeSplit.classList.remove("active");
      currentTpMode = "single";
      if (currentActiveSetupSignal) {
        updateMt5ExecutionControls(currentActiveSetupSignal);
      }
    });

    btnTpModeSplit.addEventListener("click", () => {
      btnTpModeSplit.classList.add("active");
      btnTpModeSingle.classList.remove("active");
      currentTpMode = "split";
      if (currentActiveSetupSignal) {
        updateMt5ExecutionControls(currentActiveSetupSignal);
      }
    });
  }

  if (btnExecuteMt5Trade) {
    btnExecuteMt5Trade.addEventListener("click", executeActiveSignalOnMt5);
  }

  // HTF Radar View Setup button
  if (btnViewHtfSetup) {
    btnViewHtfSetup.addEventListener("click", () => {
      if (activeHtfSetup) {
        currentTimeframe = activeHtfSetup.timeframe || "1h";
        timeframeSelect.value = currentTimeframe;
        loadChartData(activeHtfSetup.symbol, currentTimeframe);
      }
    });
  }

  // Watchlist category tabs
  document.querySelectorAll(".cat-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".cat-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      currentCategory = tab.dataset.category;
      renderWatchlist();
    });
  });

  // Run Scan Button
  btnScanNow.addEventListener("click", async () => {
    btnScanNow.disabled = true;
    scanStatusText.textContent = "Initiating scan...";
    progressBarContainer.style.display = "block";

    try {
      await fetch("/api/scan", { method: "POST" });
      setTimeout(loadStatus, 1000);
      setTimeout(loadSignals, 3000);
    } catch (e) {
      alert(`Error starting scan: ${e.message}`);
      btnScanNow.disabled = false;
    }
  });

  // Settings Modal open/close
  btnSettings.addEventListener("click", async () => {
    settingsModal.style.display = "flex";
    tgTestStatus.textContent = "";
    // Load current settings into form
    try {
      const res = await fetch("/api/settings");
      const cfg = await res.json();
      document.getElementById("tgEnabled").checked = cfg.telegram?.enabled || false;
      document.getElementById("tgBotToken").value = cfg.telegram?.bot_token || "";
      document.getElementById("tgChatId").value = cfg.telegram?.chat_id || "";
      document.getElementById("maxSpreadRatio").value = cfg.strategy?.max_spread_to_sl_ratio || 0.05;
      document.getElementById("minConviction").value = cfg.strategy?.min_conviction || 65;
      document.getElementById("scanInterval").value = cfg.scan_interval_minutes || 15;
      document.getElementById("autoScanEnabled").checked = cfg.auto_scan_enabled !== false;
      document.getElementById("forecastCandles").value = cfg.forecast_candles || 5;
      document.getElementById("showCountdownTimers").checked = cfg.strategy?.show_countdown_timers !== false;
      const elMarkers = document.getElementById("showChartTradeMarkers");
      if (elMarkers) elMarkers.checked = cfg.strategy?.show_chart_trade_markers !== false;
      const elFilterLowLiq = document.getElementById("filterLowLiquiditySessions");
      if (elFilterLowLiq) elFilterLowLiq.checked = cfg.strategy?.filter_low_liquidity_sessions !== false;
      const elReqOverlap = document.getElementById("requireLondonNyOverlap");
      if (elReqOverlap) elReqOverlap.checked = cfg.strategy?.require_london_ny_overlap === true;

      // Populate multi-timeframe checkboxes
      const savedTfs = cfg.scan_timeframes || ["5m", "15m", "1h", "4h"];
      document.querySelectorAll(".scan-tf-check").forEach((cb) => {
        cb.checked = savedTfs.includes(cb.value);
      });

      // Populate TimesFM controls
      const tfm = cfg.timesfm || {};
      const elTfmEnabled = document.getElementById("timesfmEnabled");
      const elTfmSuppress = document.getElementById("timesfmSuppressConflict");
      const elTfmBoost = document.getElementById("timesfmBoost");
      if (elTfmEnabled) elTfmEnabled.checked = tfm.enabled !== false;
      if (elTfmSuppress) elTfmSuppress.checked = tfm.suppress_on_conflict === true;
      if (elTfmBoost) elTfmBoost.value = tfm.conviction_boost ?? 12;

      // Populate MT5 Auto-Execution & Risk Management
      const strat = cfg.strategy || {};
      const elAutoTrade = document.getElementById("autoTradeEnabled");
      const elAutoConv = document.getElementById("autoTradeMinConviction");
      const elAutoDualAi = document.getElementById("autoTradeDualAiOnly");
      const elDefRisk = document.getElementById("defaultDollarRisk");
      const elTpMode = document.getElementById("tpExecutionMode");
      const elAutoClose = document.getElementById("autoCloseOnExpiry");

      if (elAutoTrade) elAutoTrade.checked = strat.auto_trade_enabled === true;
      if (elAutoConv) elAutoConv.value = strat.auto_trade_min_conviction ?? 80;
      if (elAutoDualAi) elAutoDualAi.checked = strat.auto_trade_dual_ai_only !== false;
      if (elDefRisk) elDefRisk.value = strat.default_dollar_risk ?? 50;
      if (elTpMode) elTpMode.value = strat.split_tp_mode ? "split" : "single";
      if (elAutoClose) elAutoClose.checked = strat.auto_close_on_expiry !== false;

      // Populate FundedNext Prop Firm Guardrails
      const propRules = strat.prop_firm_guardrails || {};
      const elPropEnabled = document.getElementById("propGuardEnabled");
      const elPropMaxTrades = document.getElementById("propMaxTrades");
      const elPropMaxPerSym = document.getElementById("propMaxPerSymbol");
      const elPropMinMargin = document.getElementById("propMinFreeMargin");
      const elPropMaxDD = document.getElementById("propMaxDailyDrawdown");
      const elPropPreventCorrelated = document.getElementById("propPreventCorrelated");

      if (elPropEnabled) elPropEnabled.checked = propRules.enabled !== false;
      if (elPropMaxTrades) elPropMaxTrades.value = propRules.max_simultaneous_trades ?? 3;
      if (elPropMaxPerSym) elPropMaxPerSym.value = propRules.max_trades_per_symbol ?? 1;
      if (elPropMinMargin) elPropMinMargin.value = propRules.min_free_margin_pct ?? 50;
      if (elPropMaxDD) elPropMaxDD.value = propRules.max_daily_drawdown_pct ?? 3.5;
      if (elPropPreventCorrelated) elPropPreventCorrelated.checked = propRules.prevent_correlated_exposure !== false;

      // Populate auto-execution timeframe checkboxes
      const savedAutoTfs = strat.auto_trade_timeframes || ["1h", "4h"];
      document.querySelectorAll(".auto-trade-tf-check").forEach((cb) => {
        cb.checked = savedAutoTfs.includes(cb.value);
      });
    } catch (e) {
      console.error("Error loading settings:", e);
    }
  });

  const closeSettings = () => (settingsModal.style.display = "none");
  btnCloseSettings.addEventListener("click", closeSettings);
  btnCancelSettings.addEventListener("click", closeSettings);

  // Settings Save Form
  settingsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const tgData = {
      bot_token: document.getElementById("tgBotToken").value,
      chat_id: document.getElementById("tgChatId").value,
      enabled: document.getElementById("tgEnabled").checked,
    };

    // Collect selected multi-timeframe targets
    const selectedTfs = Array.from(document.querySelectorAll(".scan-tf-check:checked")).map((cb) => cb.value);
    const selectedAutoTfs = Array.from(document.querySelectorAll(".auto-trade-tf-check:checked")).map((cb) => cb.value);

    const stratData = {
      max_spread_to_sl_ratio: parseFloat(document.getElementById("maxSpreadRatio").value),
      min_conviction: parseFloat(document.getElementById("minConviction").value),
      scan_interval_minutes: parseInt(document.getElementById("scanInterval").value),
      auto_scan_enabled: document.getElementById("autoScanEnabled").checked,
      filter_low_liquidity_sessions: document.getElementById("filterLowLiquiditySessions")?.checked !== false,
      require_london_ny_overlap: document.getElementById("requireLondonNyOverlap")?.checked === true,
      scan_timeframes: selectedTfs.length > 0 ? selectedTfs : ["1h"],
      forecast_candles: parseInt(document.getElementById("forecastCandles").value) || 5,
      show_countdown_timers: document.getElementById("showCountdownTimers").checked,
      show_chart_trade_markers: document.getElementById("showChartTradeMarkers")?.checked !== false,
      timesfm_enabled: document.getElementById("timesfmEnabled")?.checked !== false,
      timesfm_suppress_on_conflict: document.getElementById("timesfmSuppressConflict")?.checked === true,
      timesfm_conviction_boost: parseFloat(document.getElementById("timesfmBoost")?.value || 12),
      auto_trade_enabled: document.getElementById("autoTradeEnabled")?.checked === true,
      auto_trade_min_conviction: parseFloat(document.getElementById("autoTradeMinConviction")?.value || 80),
      auto_trade_dual_ai_only: document.getElementById("autoTradeDualAiOnly")?.checked !== false,
      auto_trade_timeframes: selectedAutoTfs.length > 0 ? selectedAutoTfs : ["1h", "4h"],
      default_dollar_risk: parseFloat(document.getElementById("defaultDollarRisk")?.value || 50),
      split_tp_mode: document.getElementById("tpExecutionMode")?.value === "split",
      auto_close_on_expiry: document.getElementById("autoCloseOnExpiry")?.checked !== false,
      prop_guard_enabled: document.getElementById("propGuardEnabled")?.checked !== false,
      prop_max_trades: parseInt(document.getElementById("propMaxTrades")?.value || 3),
      prop_max_per_symbol: parseInt(document.getElementById("propMaxPerSymbol")?.value || 1),
      prop_min_free_margin: parseFloat(document.getElementById("propMinFreeMargin")?.value || 50),
      prop_max_daily_drawdown: parseFloat(document.getElementById("propMaxDailyDrawdown")?.value || 3.5),
      prop_prevent_correlated: document.getElementById("propPreventCorrelated")?.checked !== false,
    };

    currentForecastCandles = stratData.forecast_candles;
    showCountdownTimers = stratData.show_countdown_timers;
    showChartTradeMarkers = stratData.show_chart_trade_markers;

    await fetch("/api/settings/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(tgData),
    });

    await fetch("/api/settings/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(stratData),
    });

    // Sync UI with saved settings
    if (tradeRiskAmount && stratData.default_dollar_risk) {
      tradeRiskAmount.value = stratData.default_dollar_risk;
      document.querySelectorAll(".risk-pill-btn").forEach((p) => {
        p.classList.toggle("active", parseFloat(p.dataset.risk) === stratData.default_dollar_risk);
      });
    }

    currentTpMode = stratData.split_tp_mode ? "split" : "single";
    if (btnTpModeSingle && btnTpModeSplit) {
      btnTpModeSingle.classList.toggle("active", currentTpMode === "single");
      btnTpModeSplit.classList.toggle("active", currentTpMode === "split");
    }

    if (currentActiveSetupSignal) {
      updateMt5ExecutionControls(currentActiveSetupSignal);
    }

    autoCloseOnExpiryEnabled = stratData.auto_close_on_expiry !== false;
    const elGuardStatus = document.getElementById("mt5LifespanGuardStatus");
    if (elGuardStatus) {
      elGuardStatus.textContent = autoCloseOnExpiryEnabled ? `Active (Auto-closes at Bar ${currentForecastCandles})` : "Disabled in Settings";
      elGuardStatus.style.color = autoCloseOnExpiryEnabled ? "var(--accent-cyan)" : "var(--text-muted)";
    }

    await loadPropGuardStatus();
    closeSettings();
    renderChartTradeMarkers();
    loadChartData(currentSymbol, currentTimeframe);
    alert("Settings saved successfully!");
  });

  // Test Telegram Button
  btnTestTelegram.addEventListener("click", async () => {
    tgTestStatus.textContent = "Sending test message to Telegram...";
    tgTestStatus.className = "status-msg";

    // Save credentials first
    await fetch("/api/settings/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bot_token: document.getElementById("tgBotToken").value,
        chat_id: document.getElementById("tgChatId").value,
        enabled: document.getElementById("tgEnabled").checked,
      }),
    });

    const res = await fetch("/api/telegram/test", { method: "POST" });
    const result = await res.json();
    if (result.success) {
      tgTestStatus.textContent = "✅ Test message received on Telegram!";
      tgTestStatus.className = "status-msg success";
    } else {
      tgTestStatus.textContent = `❌ ${result.message}`;
      tgTestStatus.className = "status-msg error";
    }
  });

  // Add Asset Modal open/close
  btnAddAsset.addEventListener("click", () => {
    addAssetModal.style.display = "flex";
  });

  const closeAddAsset = () => (addAssetModal.style.display = "none");
  btnCloseAddAsset.addEventListener("click", closeAddAsset);
  btnCancelAddAsset.addEventListener("click", closeAddAsset);

  addAssetForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const symbol = document.getElementById("assetSymbol").value.trim().toUpperCase();
    const name = document.getElementById("assetName").value.trim();
    const category = document.getElementById("assetCategory").value;
    const est_spread_pct = parseFloat(document.getElementById("assetSpread").value) || 0.02;

    const res = await fetch("/api/watchlist/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, name, category, est_spread_pct }),
    });

    if (res.ok) {
      await loadWatchlist();
      closeAddAsset();
      loadChartData(symbol, currentTimeframe);
    } else {
      alert("Failed to add asset.");
    }
  });

  // Sync MT5 Universe
  const btnSyncMt5 = document.getElementById("btnSyncMt5");
  if (btnSyncMt5) {
    btnSyncMt5.addEventListener("click", async () => {
      const originalText = btnSyncMt5.textContent;
      btnSyncMt5.disabled = true;
      btnSyncMt5.textContent = "Syncing...";
      try {
        const res = await fetch("/api/mt5/sync-universe", { method: "POST" });
        const data = await res.json();
        if (res.ok) {
          alert(`✅ Successfully synced ${data.synced_count} FundedNext symbols from MT5!`);
          await loadWatchlist();
        } else {
          alert(`❌ Failed to sync: ${data.detail || "MT5 error"}`);
        }
      } catch (e) {
        alert(`Error syncing MT5 universe: ${e.message}`);
      } finally {
        btnSyncMt5.disabled = false;
        btnSyncMt5.textContent = originalText;
      }
    });
  }
}
