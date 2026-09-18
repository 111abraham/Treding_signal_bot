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

// DOM Elements
const chartContainer = document.getElementById("tradingviewChart");
const chartOverlay = document.getElementById("chartLoadingOverlay");
const currentPriceDisplay = document.getElementById("currentPriceDisplay");
const activeSymbolElem = document.getElementById("activeSymbol");
const activeNameElem = document.getElementById("activeName");
const activeCategoryElem = document.getElementById("activeCategory");
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

// Performance & Outcome DOM Elements
const statWinRate = document.getElementById("statWinRate");
const statProfitFactor = document.getElementById("statProfitFactor");
const statRecord = document.getElementById("statRecord");
const statTotalR = document.getElementById("statTotalR");
const perfActiveCount = document.getElementById("perfActiveCount");
const perfConvictionFilter = document.getElementById("perfConvictionFilter");
const perfConvictionLabel = document.getElementById("perfConvictionLabel");
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
function updateActiveSignalLifespanClock(nowSec, tfSec) {
  if (!showCountdownTimers) {
    if (lifespanPill) lifespanPill.style.display = "none";
    if (rowSignalLifespan) rowSignalLifespan.style.display = "none";
    return;
  }

  if (lifespanPill) lifespanPill.style.display = "flex";
  if (rowSignalLifespan) rowSignalLifespan.style.display = currentActiveSignal ? "flex" : "none";

  if (!currentActiveSignal) return;

  nowSec = nowSec || Math.floor(Date.now() / 1000);
  tfSec = tfSec || getTimeframeSeconds(currentTimeframe);

  const activeTrade = activeTradesData.find(
    (t) => t.symbol.toUpperCase() === currentSymbol.toUpperCase() && t.timeframe === currentTimeframe
  );

  let maxBars = currentActiveSignal.max_candles || currentForecastCandles || 5;
  let elapsedBars = 0;
  let remainingBars = maxBars;
  let secLeft = maxBars * tfSec;

  if (activeTrade) {
    maxBars = activeTrade.max_candles || maxBars;
    elapsedBars = activeTrade.candles_monitored || 0;
    remainingBars = Math.max(0, maxBars - elapsedBars);
    const expUnix = activeTrade.expires_at_unix || ((activeTrade.entry_candle_unix || activeTrade.opened_unix) + (maxBars * tfSec));
    secLeft = Math.max(0, expUnix - nowSec);
  } else {
    const nextBoundary = Math.ceil(nowSec / tfSec) * tfSec;
    const curCandleRemaining = Math.max(0, nextBoundary - nowSec);
    secLeft = curCandleRemaining + Math.max(0, maxBars - 1) * tfSec;
  }

  // Render Lifespan Segments
  if (lifespanSegments) {
    lifespanSegments.innerHTML = "";
    for (let i = 0; i < maxBars; i++) {
      const seg = document.createElement("span");
      seg.className = "lifespan-segment";
      if (i < elapsedBars) {
        seg.classList.add("elapsed");
        seg.title = `Bar ${i + 1} completed`;
      } else {
        seg.classList.add("active");
        if (remainingBars === 1) seg.classList.add("danger");
        seg.title = `Bar ${i + 1} remaining`;
      }
      lifespanSegments.appendChild(seg);
    }
  }

  const durStr = formatRemainingDuration(secLeft);
  if (lvlSignalRemaining) {
    if (activeTrade) {
      lvlSignalRemaining.textContent = `⏳ ${remainingBars} of ${maxBars} bars left (~${durStr})`;
    } else {
      lvlSignalRemaining.textContent = `⏳ ${maxBars} bars horizon (~${durStr})`;
    }
  }

  if (lifespanPillValue) {
    if (activeTrade) {
      lifespanPillValue.textContent = `⏳ ${remainingBars}/${maxBars} Bars (${durStr})`;
    } else {
      lifespanPillValue.textContent = `⏳ ${maxBars} Bars (~${durStr})`;
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

    // 2. Active Chart Signal Lifespan
    updateActiveSignalLifespanClock(nowSec, tfSec);

    // 3. Signal list cards countdown
    document.querySelectorAll(".sig-countdown").forEach((el) => {
      const entryUnix = parseInt(el.dataset.entry, 10);
      const tf = el.dataset.tf || "1h";
      const maxC = parseInt(el.dataset.max, 10) || currentForecastCandles || 5;
      const step = getTimeframeSeconds(tf);
      if (!entryUnix) return;

      const expUnix = entryUnix + maxC * step;
      const secLeft = expUnix - nowSec;
      if (secLeft <= 0) {
        el.textContent = `⏱️ Finished (${maxC} bars)`;
        el.className = "sig-countdown completed";
      } else {
        const elapsedBars = Math.min(maxC, Math.max(0, Math.floor((nowSec - entryUnix) / step)));
        const remBars = Math.max(0, maxC - elapsedBars);
        el.textContent = `⏳ ${remBars}/${maxC} bars (${formatRemainingDuration(secLeft)} left)`;
        el.className = "sig-countdown";
      }
    });
  }, 1000);
}

// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
  initChart();
  setupEventListeners();
  startLiveCountdownEngine();
  await loadStatus();
  await loadWatchlist();
  await loadSignals();
  await loadPerformance();
  await pollHtfRadar();
  await loadChartData(currentSymbol, currentTimeframe);

  // Status and scanner polling
  setInterval(loadStatus, 15000);
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
}


// 2. DATA LOADING & CHART RENDERING
async function loadChartData(symbol, timeframe) {
  chartOverlay.style.display = "flex";
  clearPriceLines();

  try {
    const res = await fetch(`/api/chart/${encodeURIComponent(symbol)}?timeframe=${timeframe}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to load chart data");
    }

    const data = await res.json();
    currentSymbol = data.symbol;

    // Update Header
    activeSymbolElem.textContent = data.symbol;
    activeNameElem.textContent = data.name;
    activeCategoryElem.textContent = data.category;
    
    const lastHistorical = data.candles[data.candles.length - 1];
    if (lastHistorical) {
      currentPriceDisplay.textContent = formatPrice(lastHistorical.close);
    }

    // Set Historical Candles (500)
    historicalSeries.setData(data.candles);

    // Render 5 Predicted Future Candles
    const predCandles = data.forecast.predicted_candles || [];
    if (predCandles.length > 0) {
      predictedSeries.setData(predCandles);

      // Quantile ribbon lines
      const upperData = predCandles.map((c) => ({ time: c.time, value: c.p90 }));
      const lowerData = predCandles.map((c) => ({ time: c.time, value: c.p10 }));
      upperBandSeries.setData(upperData);
      lowerBandSeries.setData(lowerData);

      // Fit content with padding
      chart.timeScale().fitContent();
    }

    currentActiveSignal = data.signal;

    // Update Direction Pill Dynamic Horizon Label (e.g. 5-Candle Direction)
    const maxBars = data.signal?.max_candles || data.forecast?.predicted_candles?.length || currentForecastCandles || 5;
    const dirPillLabel = document.querySelector("#directionPill .pill-label");
    if (dirPillLabel) dirPillLabel.textContent = `${maxBars}-Candle Direction`;

    // Update Forecast Pills
    updateForecastPills(data.forecast, data.signal);

    // Update Guardrails & Levels Card
    updateGuardrailsAndLevels(data.signal, lastHistorical?.close);

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
    return;
  }

  // Levels
  lvlEntry.textContent = formatPrice(signal.entry_price);
  lvlSL.textContent = formatPrice(signal.stop_loss);
  lvlTP1.textContent = formatPrice(signal.take_profit_1);
  lvlTP2.textContent = formatPrice(signal.take_profit_2);
  lvlRR.textContent = `1 : ${signal.risk_reward_ratio}`;

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
  const ratioPct = signal.spread_to_sl_ratio_pct;
  currentSpreadRatio.textContent = `${ratioPct}% of SL`;
  
  // Meter visualization: 5% is midpoint (50% bar width)
  const meterWidth = Math.min(100, (ratioPct / 10.0) * 100);
  spreadMeterFill.style.width = `${meterWidth}%`;

  if (signal.passes_spread_filter) {
    spreadMeterFill.classList.remove("warning");
    spreadStatusPill.className = "guardrail-status-pill";
    spreadStatusPill.innerHTML = `✅ <b>PASS:</b> Spread is ${ratioPct}% (&lt; 5% Target Met)`;
  } else {
    spreadMeterFill.classList.add("warning");
    spreadStatusPill.className = "guardrail-status-pill danger";
    spreadStatusPill.innerHTML = `⚠️ <b>FILTERED:</b> Spread is ${ratioPct}% (&gt; 5% SL distance)`;
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

async function loadSignals() {
  try {
    const res = await fetch("/api/signals");
    const data = await res.json();
    const signals = data.signals || [];
    signalCountBadge.textContent = signals.length;

    if (signals.length === 0) {
      signalHistoryList.innerHTML = `<div class="empty-history">No signals recorded yet. Click "Run Scan Now" to scan active watchlist.</div>`;
      return;
    }

    signalHistoryList.innerHTML = "";
    signals.forEach((sig) => {
      const card = document.createElement("div");
      card.className = "signal-card-mini";
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
      const remBars = Math.max(0, maxC - elapsedBars);

      const countdownHtml = showCountdownTimers
        ? (secLeft <= 0
            ? `<span class="sig-countdown completed" data-entry="${entryUnix}" data-tf="${sig.timeframe}" data-max="${maxC}">⏱️ Finished (${maxC} bars)</span>`
            : `<span class="sig-countdown" data-entry="${entryUnix}" data-tf="${sig.timeframe}" data-max="${maxC}">⏳ ${remBars}/${maxC} bars (${formatRemainingDuration(secLeft)} left)</span>`)
        : "";

      card.innerHTML = `
        <div class="sig-header">
          <span class="sig-sym">${sig.symbol} <small style="color:var(--text-muted);font-weight:normal">${sig.timeframe}</small></span>
          <div>
            <span class="${badgeClass}">${dirText} ${sig.conviction}%</span>
            ${dualBadge}
          </div>
        </div>
        <div class="sig-body">
          <span>Entry: ${sig.entry_price}</span>
          <span>R:R ${sig.risk_reward_ratio}</span>
        </div>
        <div class="sig-footer" style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
          <div class="sig-time">${sig.timestamp.split(" ")[1]} UTC | ${sig.session_name.split(" ")[0]}</div>
          ${countdownHtml}
        </div>
      `;

      card.addEventListener("click", () => {
        loadChartData(sig.symbol, sig.timeframe);
      });

      signalHistoryList.appendChild(card);
    });
  } catch (e) {
    console.error("Error loading signals:", e);
  }
}

async function loadPerformance() {
  try {
    const res = await fetch(`/api/performance?min_conviction=${currentMinConviction}`);
    if (!res.ok) return;
    const data = await res.json();
    const stats = data.stats || {};
    const closedTrades = data.closed_trades || [];
    const activeTrades = data.active_trades || [];
    activeTradesData = activeTrades;
    updateActiveSignalLifespanClock();

    // Update summary metrics
    if (statWinRate) {
      statWinRate.textContent = `${stats.win_rate_pct ?? 0}%`;
      statWinRate.className = "stat-val highlight";
      if (stats.win_rate_pct >= 60) {
        statWinRate.style.color = "var(--accent-green)";
      } else if (stats.win_rate_pct < 45 && stats.total_closed > 0) {
        statWinRate.style.color = "var(--accent-red)";
      } else {
        statWinRate.style.color = "var(--accent-cyan)";
      }
    }

    if (statProfitFactor) {
      statProfitFactor.textContent = stats.profit_factor ?? "1.0";
    }

    if (statRecord) {
      statRecord.textContent = `${stats.wins ?? 0}W - ${stats.losses ?? 0}L`;
    }

    if (statTotalR) {
      const tr = stats.total_realized_r ?? 0;
      statTotalR.textContent = (tr >= 0 ? "+" : "") + tr + "R";
      statTotalR.style.color = tr >= 0 ? "var(--accent-green)" : "var(--accent-red)";
    }

    if (perfActiveCount) {
      perfActiveCount.textContent = `${stats.active_count ?? activeTrades.length} Active`;
    }

    if (resolvedCountBadge) {
      resolvedCountBadge.textContent = closedTrades.length;
    }

    // Update breakdown pills
    const elTpWins = document.getElementById("breakdownTpWins");
    const elExpWins = document.getElementById("breakdownExpWins");
    const elSlLosses = document.getElementById("breakdownSlLosses");
    const elExpLosses = document.getElementById("breakdownExpLosses");
    if (elTpWins) elTpWins.textContent = `🎯 ${stats.tp_wins || 0} TP`;
    if (elExpWins) elExpWins.textContent = `⏱️ +${stats.exp_wins || 0} Exp`;
    if (elSlLosses) elSlLosses.textContent = `🛑 ${stats.sl_losses || 0} SL`;
    if (elExpLosses) elExpLosses.textContent = `⏱️ -${stats.exp_losses || 0} Exp`;

    // Render resolved trades list
    if (resolvedTradesList) {
      if (closedTrades.length === 0) {
        resolvedTradesList.innerHTML = `<div class="empty-history">No closed trades yet. Signals will be tracked across their 5-candle duration.</div>`;
        return;
      }

      resolvedTradesList.innerHTML = "";
      closedTrades.forEach((tr) => {
        const card = document.createElement("div");
        card.className = "signal-card-mini";

        let badgeClass = "sig-badge-expired";
        let outcomeLabel = tr.outcome || "EXPIRED";
        let pnlClass = (tr.realized_r >= 0) ? "sig-pnl-win" : "sig-pnl-loss";

        if (tr.outcome === "WIN") {
          badgeClass = "sig-badge-win";
          outcomeLabel = "WIN (TP1)";
        } else if (tr.outcome === "LOSS") {
          badgeClass = "sig-badge-loss";
          outcomeLabel = "LOSS (SL)";
        } else if (tr.outcome === "EXPIRED_PROFIT") {
          badgeClass = "sig-badge-win";
          outcomeLabel = "EXP +PNL";
        } else if (tr.outcome === "EXPIRED_LOSS") {
          badgeClass = "sig-badge-loss";
          outcomeLabel = "EXP -PNL";
        }

        const pnlStr = `${tr.realized_pnl_pct >= 0 ? "+" : ""}${tr.realized_pnl_pct}% (${tr.realized_r >= 0 ? "+" : ""}${tr.realized_r}R)`;
        const candleDuration = `Bar ${tr.hit_on_candle || tr.candles_monitored || 5}/5`;

        card.innerHTML = `
          <div class="sig-header">
            <span class="sig-sym">${tr.symbol} <small style="color:var(--text-muted);font-weight:normal">${tr.timeframe}</small></span>
            <span class="${badgeClass}">${outcomeLabel}</span>
          </div>
          <div class="sig-body">
            <span>Entry: ${tr.entry_price} &rarr; ${tr.exit_price}</span>
            <span class="${pnlClass}">${pnlStr}</span>
          </div>
          <div class="sig-time">${candleDuration} | Conv: ${tr.conviction}% | ${tr.exit_reason || tr.closed_at}</div>
        `;

        card.addEventListener("click", () => {
          currentTimeframe = tr.timeframe || "1h";
          timeframeSelect.value = currentTimeframe;
          loadChartData(tr.symbol, currentTimeframe);
        });

        resolvedTradesList.appendChild(card);
      });
    }
  } catch (e) {
    console.error("Error loading performance:", e);
  }
}


// 5. EVENT LISTENERS & MODALS
function setupEventListeners() {
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
    });

    tabResolvedTrades.addEventListener("click", () => {
      tabResolvedTrades.classList.add("active");
      tabRecentSignals.classList.remove("active");
      signalHistoryList.style.display = "none";
      resolvedTradesList.style.display = "block";
    });
  }

  // Conviction filter slider
  if (perfConvictionFilter) {
    perfConvictionFilter.addEventListener("input", (e) => {
      currentMinConviction = parseInt(e.target.value);
      if (perfConvictionLabel) {
        perfConvictionLabel.innerHTML = `&ge; ${currentMinConviction}%`;
      }
      loadPerformance();
    });
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

    const stratData = {
      max_spread_to_sl_ratio: parseFloat(document.getElementById("maxSpreadRatio").value),
      min_conviction: parseFloat(document.getElementById("minConviction").value),
      scan_interval_minutes: parseInt(document.getElementById("scanInterval").value),
      auto_scan_enabled: document.getElementById("autoScanEnabled").checked,
      scan_timeframes: selectedTfs.length > 0 ? selectedTfs : ["1h"],
      forecast_candles: parseInt(document.getElementById("forecastCandles").value) || 5,
      show_countdown_timers: document.getElementById("showCountdownTimers").checked,
      timesfm_enabled: document.getElementById("timesfmEnabled")?.checked !== false,
      timesfm_suppress_on_conflict: document.getElementById("timesfmSuppressConflict")?.checked === true,
      timesfm_conviction_boost: parseFloat(document.getElementById("timesfmBoost")?.value || 12),
    };

    currentForecastCandles = stratData.forecast_candles;
    showCountdownTimers = stratData.show_countdown_timers;

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

    closeSettings();
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
