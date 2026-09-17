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


// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
  initChart();
  setupEventListeners();
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
}

function updateGuardrailsAndLevels(signal, currentClose) {
  if (!signal) {
    lvlEntry.textContent = "--";
    lvlSL.textContent = "--";
    lvlTP1.textContent = "--";
    lvlTP2.textContent = "--";
    lvlRR.textContent = "--";
    if (rowDualAi) rowDualAi.style.display = "none";
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
        <div class="sig-time">${sig.timestamp.split(" ")[1]} UTC | ${sig.session_name.split(" ")[0]}</div>
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
      timesfm_enabled: document.getElementById("timesfmEnabled")?.checked !== false,
      timesfm_suppress_on_conflict: document.getElementById("timesfmSuppressConflict")?.checked === true,
      timesfm_conviction_boost: parseFloat(document.getElementById("timesfmBoost")?.value || 12),
    };

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
}
