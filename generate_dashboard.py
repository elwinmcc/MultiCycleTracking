#!/usr/bin/env python3
"""
Dashboard generator for BTC Econometric Model v7.2.

Runs the model against current + backtest scenarios and produces
a self-contained HTML dashboard with Chart.js visualizations.

Usage:
    python generate_dashboard.py          # writes index.html
    python generate_dashboard.py --open   # writes and opens in browser
"""

import json
import sys
from btc_model_v72 import (
    BTCModelV72,
    CalibratedThresholds,
    get_current_market_data,
    backtest_october_2025_ath,
    backtest_january_2026_breakdown,
)

# ─────────────────────────────────────────────────────────────────────────────
# Collect model results for all scenarios
# ─────────────────────────────────────────────────────────────────────────────

def collect_dashboard_data() -> dict:
    scenarios = [
        ("Oct 2025 ATH ($126K)", backtest_october_2025_ath()),
        ("Jan 2026 Crash ($85K)", backtest_january_2026_breakdown()),
        ("Feb 2026 Now ($68.5K)", get_current_market_data()),
    ]

    results = []
    for label, market_data in scenarios:
        model = BTCModelV72(market_data, CalibratedThresholds())
        analysis = model.run_full_analysis()
        analysis["scenario_label"] = label
        results.append(analysis)

    return {
        "current": results[-1],
        "scenarios": results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTML template
# ─────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BTC Model v7.2 Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js"></script>
<style>
/* ── Reset & Base ────────────────────────────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0f172a;--card:#1e293b;--card-border:#334155;
  --text:#e2e8f0;--muted:#94a3b8;--accent:#38bdf8;
  --green:#22c55e;--yellow:#eab308;--red:#ef4444;--orange:#f97316;
  --blue:#3b82f6;--purple:#a855f7;--cyan:#06b6d4;--pink:#ec4899;
}
html{font-size:14px}
body{background:var(--bg);color:var(--text);font-family:'SF Mono',SFMono-Regular,ui-monospace,Menlo,Consolas,monospace;line-height:1.5;padding:1rem}

/* ── Layout ──────────────────────────────────────────────────────────── */
.header{text-align:center;padding:1.5rem 0 1rem;border-bottom:1px solid var(--card-border);margin-bottom:1.5rem}
.header h1{font-size:1.6rem;letter-spacing:.05em;color:var(--accent)}
.header .subtitle{color:var(--muted);font-size:.85rem;margin-top:.3rem}

.grid{display:grid;gap:1rem}
.g1{grid-template-columns:1fr}
.g2{grid-template-columns:repeat(2,1fr)}
.g3{grid-template-columns:repeat(3,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:1100px){.g3,.g4{grid-template-columns:repeat(2,1fr)}}
@media(max-width:700px){.g2,.g3,.g4{grid-template-columns:1fr}}

.card{background:var(--card);border:1px solid var(--card-border);border-radius:.5rem;padding:1.2rem;position:relative;overflow:hidden}
.card h2{font-size:.85rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:.8rem;display:flex;align-items:center;gap:.4rem}
.card h2 .dot{width:8px;height:8px;border-radius:50%;display:inline-block}

/* ── KPI Cards ───────────────────────────────────────────────────────── */
.kpi{text-align:center;padding:1.5rem 1rem}
.kpi .value{font-size:2.4rem;font-weight:700;line-height:1.1}
.kpi .label{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-top:.3rem}
.kpi .sub{font-size:.8rem;margin-top:.5rem;color:var(--muted)}

/* ── Signal badge ────────────────────────────────────────────────────── */
.signal-badge{display:inline-block;padding:.35rem 1rem;border-radius:4px;font-weight:700;font-size:.95rem;letter-spacing:.06em}
.sig-green{background:rgba(34,197,94,.15);color:var(--green);border:1px solid rgba(34,197,94,.3)}
.sig-yellow{background:rgba(234,179,8,.12);color:var(--yellow);border:1px solid rgba(234,179,8,.25)}
.sig-red{background:rgba(239,68,68,.12);color:var(--red);border:1px solid rgba(239,68,68,.25)}
.sig-blue{background:rgba(56,189,248,.12);color:var(--accent);border:1px solid rgba(56,189,248,.25)}

/* ── Warnings ────────────────────────────────────────────────────────── */
.warn-list{list-style:none;font-size:.82rem}
.warn-list li{padding:.45rem .6rem;border-left:3px solid var(--orange);margin-bottom:.4rem;background:rgba(249,115,22,.06);border-radius:0 4px 4px 0}

/* ── Adjustments ─────────────────────────────────────────────────────── */
.adj-list{list-style:none;font-size:.82rem}
.adj-list li{padding:.4rem .6rem;margin-bottom:.3rem;border-radius:4px}
.adj-list li.pos{background:rgba(34,197,94,.08);border-left:3px solid var(--green)}
.adj-list li.neg{background:rgba(239,68,68,.08);border-left:3px solid var(--red)}
.adj-list li.info{background:rgba(56,189,248,.08);border-left:3px solid var(--accent)}

/* ── Chart wrappers ──────────────────────────────────────────────────── */
.chart-wrap{position:relative;width:100%}
.chart-wrap.sq{aspect-ratio:1/1;max-height:320px;margin:0 auto}
.chart-wrap.wide{height:340px}
.chart-wrap.tall{height:400px}

/* ── Market data table ───────────────────────────────────────────────── */
.data-grid{display:grid;grid-template-columns:1fr 1fr;gap:0}
.data-item{display:flex;justify-content:space-between;padding:.35rem .5rem;border-bottom:1px solid rgba(51,65,85,.4);font-size:.8rem}
.data-item .k{color:var(--muted)}
.data-item .v{font-weight:600;text-align:right}

/* ── Section dividers ────────────────────────────────────────────────── */
.section-title{font-size:1rem;color:var(--accent);margin:1.8rem 0 .8rem;padding-bottom:.4rem;border-bottom:1px solid var(--card-border);letter-spacing:.06em}

/* ── Score bar ───────────────────────────────────────────────────────── */
.score-bar-row{display:flex;align-items:center;gap:.5rem;margin-bottom:.5rem;font-size:.78rem}
.score-bar-row .lbl{width:140px;text-align:right;color:var(--muted);flex-shrink:0}
.score-bar-track{flex:1;height:18px;background:rgba(51,65,85,.5);border-radius:3px;overflow:hidden;position:relative}
.score-bar-fill{height:100%;border-radius:3px;transition:width .6s}
.score-bar-row .val{width:42px;text-align:right;font-weight:600;flex-shrink:0}
</style>
</head>
<body>

<div class="header">
  <h1>BTC ECONOMETRIC MODEL v7.2</h1>
  <div class="subtitle">Calibrated Post-Crash Framework &mdash; <span id="run-date"></span></div>
</div>

<!-- ═══ KPI ROW ═══════════════════════════════════════════════════════ -->
<div class="grid g4" id="kpi-row"></div>

<!-- ═══ LAYER SCORES ══════════════════════════════════════════════════ -->
<div class="section-title">Layer Scores &amp; Weights</div>
<div class="grid g2">
  <div class="card">
    <h2><span class="dot" style="background:var(--accent)"></span> Layer Health Scores</h2>
    <div id="layer-bars"></div>
  </div>
  <div class="card">
    <h2><span class="dot" style="background:var(--purple)"></span> Radar Profile</h2>
    <div class="chart-wrap sq"><canvas id="radarChart"></canvas></div>
  </div>
</div>

<!-- ═══ CONTRIBUTIONS & WEIGHTS ═══════════════════════════════════════ -->
<div class="grid g2" style="margin-top:1rem">
  <div class="card">
    <h2><span class="dot" style="background:var(--cyan)"></span> Weighted Contributions</h2>
    <div class="chart-wrap wide"><canvas id="contribChart"></canvas></div>
  </div>
  <div class="card">
    <h2><span class="dot" style="background:var(--pink)"></span> Layer Weight Distribution</h2>
    <div class="chart-wrap sq"><canvas id="weightsDonut"></canvas></div>
  </div>
</div>

<!-- ═══ BACKTEST COMPARISON ═══════════════════════════════════════════ -->
<div class="section-title">Scenario Backtest Comparison</div>
<div class="grid g1">
  <div class="card">
    <h2><span class="dot" style="background:var(--yellow)"></span> Health &amp; Allocation Across Scenarios</h2>
    <div class="chart-wrap wide"><canvas id="backtestHealth"></canvas></div>
  </div>
</div>
<div class="grid g1" style="margin-top:1rem">
  <div class="card">
    <h2><span class="dot" style="background:var(--orange)"></span> Layer Scores by Scenario</h2>
    <div class="chart-wrap tall"><canvas id="backtestLayers"></canvas></div>
  </div>
</div>

<!-- ═══ ALLOCATION ════════════════════════════════════════════════════ -->
<div class="section-title">Allocation &amp; Signals</div>
<div class="grid g3">
  <div class="card">
    <h2><span class="dot" style="background:var(--green)"></span> Portfolio Allocation</h2>
    <div class="chart-wrap sq"><canvas id="allocDonut"></canvas></div>
  </div>
  <div class="card">
    <h2><span class="dot" style="background:var(--orange)"></span> Asymmetric Adjustments</h2>
    <ul class="adj-list" id="adj-list"></ul>
  </div>
  <div class="card">
    <h2><span class="dot" style="background:var(--red)"></span> Warnings &amp; Alerts</h2>
    <ul class="warn-list" id="warn-list"></ul>
  </div>
</div>

<!-- ═══ NEW v7.2 LAYERS DETAIL ════════════════════════════════════════ -->
<div class="section-title">New v7.2 Layer Details</div>
<div class="grid g3">
  <div class="card" id="detail-flow"></div>
  <div class="card" id="detail-fragility"></div>
  <div class="card" id="detail-support"></div>
</div>

<!-- ═══ MARKET DATA ═══════════════════════════════════════════════════ -->
<div class="section-title">Verified Market Data</div>
<div class="grid g3">
  <div class="card"><h2>Price &amp; Valuation</h2><div class="data-grid" id="md-price"></div></div>
  <div class="card"><h2>Institutional / ETF</h2><div class="data-grid" id="md-etf"></div></div>
  <div class="card"><h2>Derivatives &amp; Macro</h2><div class="data-grid" id="md-deriv"></div></div>
</div>

<!-- ═══ MVRV REGIME CHART ═════════════════════════════════════════════ -->
<div class="section-title">MVRV Regime Zones (ETF-Era Adjusted)</div>
<div class="grid g1">
  <div class="card">
    <div class="chart-wrap wide"><canvas id="mvrvZones"></canvas></div>
  </div>
</div>

<div style="text-align:center;padding:2rem 0 1rem;color:var(--muted);font-size:.75rem">
  BTC Model v7.2 &mdash; Calibrated from Oct 2025 &ndash; Feb 2026 crash post-mortem
</div>

<!-- ═══ DATA & CHART LOGIC ════════════════════════════════════════════ -->
<script>
// Injected by generate_dashboard.py
const D = __DASHBOARD_JSON__;

const cur = D.current;
const scenarios = D.scenarios;

// ── Helpers ─────────────────────────────────────────────────────────
function scoreColor(v){return v>=65?'#22c55e':v>=35?'#eab308':'#ef4444'}
function scoreBg(v){return v>=65?'rgba(34,197,94,.18)':v>=35?'rgba(234,179,8,.12)':'rgba(239,68,68,.12)'}
function fmt(v,d=1){return typeof v==='number'?v.toFixed(d):v}
function pct(v){return typeof v==='number'?(v>=0?'+':'')+v.toFixed(1)+'%':'--'}
function usd(v){return '$'+Number(v).toLocaleString()}

const LAYER_LABELS = {
  onchain:'On-Chain (MVRV)',institutional:'Institutional',
  flow_velocity:'Flow Velocity',momentum:'Momentum',
  derivatives:'Derivatives',leverage_fragility:'Leverage Fragility',
  support_integrity:'Support Integrity',liquidity:'Liquidity',
  global_m2:'Global M2',sentiment:'Sentiment'
};
const LAYER_ORDER = Object.keys(LAYER_LABELS);
const NEW_LAYERS = new Set(['flow_velocity','leverage_fragility','support_integrity']);

// ── Chart.js defaults ───────────────────────────────────────────────
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = 'rgba(51,65,85,.4)';
Chart.defaults.font.family = "'SF Mono',SFMono-Regular,ui-monospace,Menlo,Consolas,monospace";
Chart.defaults.font.size = 11;

// ── Run date ────────────────────────────────────────────────────────
document.getElementById('run-date').textContent = cur.market_data.date;

// ═══════════════════════════════════════════════════════════════════
// KPI CARDS
// ═══════════════════════════════════════════════════════════════════
(function(){
  const row = document.getElementById('kpi-row');
  const h = cur.health;
  const sigText = cur.signal.replace(/_/g,' ');
  const sigClass = cur.final_allocation>=60?'sig-green':cur.final_allocation>=40?'sig-yellow':'sig-red';
  // Special case: capitulation override means model is actually bullish
  const isCapitulation = cur.phase === 'CAPITULATION' || cur.phase === 'DEEP_ACCUMULATION';
  const effectiveSigClass = isCapitulation && cur.final_allocation >= 60 ? 'sig-blue' : sigClass;

  const cards = [
    {label:'Master Health',value:fmt(h)+'/100',color:scoreColor(h),sub:cur.phase.replace(/_/g,' ')},
    {label:'Signal',value:`<span class="signal-badge ${effectiveSigClass}">${sigText}</span>`,sub:'Asymmetric-adjusted'},
    {label:'Allocation',value:cur.final_allocation+'%',color:scoreColor(cur.final_allocation),sub:`Base ${cur.base_allocation}% → Final ${cur.final_allocation}%`},
    {label:'BTC Price',value:usd(cur.market_data.btc_price),color:'var(--accent)',sub:`-${fmt(cur.market_data.drawdown_from_ath)}% from ATH`},
  ];

  row.innerHTML = cards.map(c=>`
    <div class="card kpi">
      <div class="value" style="color:${c.color||'var(--text)'}">${c.value}</div>
      <div class="label">${c.label}</div>
      <div class="sub">${c.sub}</div>
    </div>`).join('');
})();

// ═══════════════════════════════════════════════════════════════════
// LAYER SCORE BARS
// ═══════════════════════════════════════════════════════════════════
(function(){
  const el = document.getElementById('layer-bars');
  el.innerHTML = LAYER_ORDER.map(k=>{
    const s = cur.layer_scores[k];
    const w = cur.layer_weights[k]*100;
    const star = NEW_LAYERS.has(k) ? ' <span style="color:var(--accent)">*</span>' : '';
    return `<div class="score-bar-row">
      <span class="lbl">${LAYER_LABELS[k]}${star}</span>
      <div class="score-bar-track">
        <div class="score-bar-fill" style="width:${s}%;background:${scoreColor(s)}"></div>
      </div>
      <span class="val" style="color:${scoreColor(s)}">${fmt(s,0)}</span>
    </div>`;
  }).join('') + '<div style="font-size:.7rem;color:var(--muted);margin-top:.5rem">* New in v7.2</div>';
})();

// ═══════════════════════════════════════════════════════════════════
// RADAR CHART
// ═══════════════════════════════════════════════════════════════════
(function(){
  const ctx = document.getElementById('radarChart').getContext('2d');
  new Chart(ctx,{
    type:'radar',
    data:{
      labels:LAYER_ORDER.map(k=>LAYER_LABELS[k]),
      datasets:[{
        label:'Current',
        data:LAYER_ORDER.map(k=>cur.layer_scores[k]),
        backgroundColor:'rgba(56,189,248,.15)',
        borderColor:'#38bdf8',
        borderWidth:2,
        pointBackgroundColor:'#38bdf8',
        pointRadius:3
      }]
    },
    options:{
      scales:{r:{min:0,max:100,ticks:{stepSize:25,backdropColor:'transparent'},grid:{color:'rgba(51,65,85,.4)'},pointLabels:{font:{size:10}}}},
      plugins:{legend:{display:false}}
    }
  });
})();

// ═══════════════════════════════════════════════════════════════════
// WEIGHTED CONTRIBUTIONS BAR
// ═══════════════════════════════════════════════════════════════════
(function(){
  const ctx = document.getElementById('contribChart').getContext('2d');
  const contribs = LAYER_ORDER.map(k=>+(cur.layer_scores[k]*cur.layer_weights[k]).toFixed(1));
  const colors = LAYER_ORDER.map(k=>scoreColor(cur.layer_scores[k]));
  new Chart(ctx,{
    type:'bar',
    data:{
      labels:LAYER_ORDER.map(k=>LAYER_LABELS[k]),
      datasets:[{data:contribs,backgroundColor:colors,borderRadius:3}]
    },
    options:{
      indexAxis:'y',
      plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.raw+' pts ('+LAYER_ORDER[c.dataIndex]+': '+fmt(cur.layer_scores[LAYER_ORDER[c.dataIndex]],0)+' x '+fmt(cur.layer_weights[LAYER_ORDER[c.dataIndex]]*100,0)+'%)'}}},
      scales:{x:{title:{display:true,text:'Contribution to Health Score'},grid:{color:'rgba(51,65,85,.3)'}},y:{grid:{display:false}}}
    }
  });
})();

// ═══════════════════════════════════════════════════════════════════
// WEIGHTS DONUT
// ═══════════════════════════════════════════════════════════════════
(function(){
  const ctx = document.getElementById('weightsDonut').getContext('2d');
  const palette = ['#38bdf8','#22c55e','#a855f7','#eab308','#f97316','#ec4899','#06b6d4','#3b82f6','#64748b','#f43f5e'];
  new Chart(ctx,{
    type:'doughnut',
    data:{
      labels:LAYER_ORDER.map(k=>LAYER_LABELS[k]),
      datasets:[{data:LAYER_ORDER.map(k=>cur.layer_weights[k]*100),backgroundColor:palette,borderWidth:0}]
    },
    options:{
      cutout:'55%',
      plugins:{legend:{position:'right',labels:{boxWidth:10,padding:6,font:{size:10}}},
        tooltip:{callbacks:{label:c=>c.label+': '+c.raw+'%'}}}
    }
  });
})();

// ═══════════════════════════════════════════════════════════════════
// BACKTEST: HEALTH & ALLOCATION
// ═══════════════════════════════════════════════════════════════════
(function(){
  const ctx = document.getElementById('backtestHealth').getContext('2d');
  const labels = scenarios.map(s=>s.scenario_label);
  new Chart(ctx,{
    type:'bar',
    data:{
      labels,
      datasets:[
        {label:'Health Score',data:scenarios.map(s=>s.health),backgroundColor:'rgba(56,189,248,.6)',borderRadius:3},
        {label:'Base Alloc %',data:scenarios.map(s=>s.base_allocation),backgroundColor:'rgba(234,179,8,.5)',borderRadius:3},
        {label:'Final Alloc %',data:scenarios.map(s=>s.final_allocation),backgroundColor:'rgba(34,197,94,.6)',borderRadius:3},
      ]
    },
    options:{
      plugins:{legend:{labels:{boxWidth:12,padding:12}}},
      scales:{y:{max:100,grid:{color:'rgba(51,65,85,.3)'}},x:{grid:{display:false}}}
    }
  });
})();

// ═══════════════════════════════════════════════════════════════════
// BACKTEST: LAYER SCORES GROUPED
// ═══════════════════════════════════════════════════════════════════
(function(){
  const ctx = document.getElementById('backtestLayers').getContext('2d');
  const palette = ['#ef4444','#eab308','#22c55e'];
  new Chart(ctx,{
    type:'bar',
    data:{
      labels:LAYER_ORDER.map(k=>LAYER_LABELS[k]),
      datasets:scenarios.map((s,i)=>({
        label:s.scenario_label,
        data:LAYER_ORDER.map(k=>s.layer_scores[k]),
        backgroundColor:palette[i]+'99',
        borderRadius:2
      }))
    },
    options:{
      plugins:{legend:{labels:{boxWidth:12,padding:12}}},
      scales:{y:{max:100,grid:{color:'rgba(51,65,85,.3)'}},x:{grid:{display:false},ticks:{maxRotation:45,minRotation:25}}}
    }
  });
})();

// ═══════════════════════════════════════════════════════════════════
// ALLOCATION DONUT
// ═══════════════════════════════════════════════════════════════════
(function(){
  const a = cur.allocation_breakdown;
  const ctx = document.getElementById('allocDonut').getContext('2d');
  const cashPct = 100 - a.total_allocation;
  new Chart(ctx,{
    type:'doughnut',
    data:{
      labels:['BTC ('+a.btc_pct+'%)','ETH ('+a.eth_pct+'%)','ALTs ('+a.alt_pct+'%)','Cash ('+(cashPct)+'%)'],
      datasets:[{
        data:[
          +(a.total_allocation*a.btc_pct/100).toFixed(1),
          +(a.total_allocation*a.eth_pct/100).toFixed(1),
          +(a.total_allocation*a.alt_pct/100).toFixed(1),
          cashPct
        ],
        backgroundColor:['#f7931a','#627eea','#a855f7','#334155'],
        borderWidth:0
      }]
    },
    options:{
      cutout:'50%',
      plugins:{legend:{position:'bottom',labels:{boxWidth:12,padding:8,font:{size:11}}},
        tooltip:{callbacks:{label:c=>c.label+': '+c.raw+'% of portfolio'}}}
    }
  });
})();

// ═══════════════════════════════════════════════════════════════════
// ADJUSTMENTS LIST
// ═══════════════════════════════════════════════════════════════════
(function(){
  const el = document.getElementById('adj-list');
  const items = cur.asymmetric_adjustments;
  if(!items.length){el.innerHTML='<li class="info">No asymmetric adjustments triggered.</li>';return}
  el.innerHTML = items.map(a=>{
    const cls = a.includes('+') ? 'pos' : a.includes('-') ? 'neg' : 'info';
    return `<li class="${cls}">${a}</li>`;
  }).join('');
})();

// ═══════════════════════════════════════════════════════════════════
// WARNINGS LIST
// ═══════════════════════════════════════════════════════════════════
(function(){
  const el = document.getElementById('warn-list');
  const w = cur.warnings;
  if(!w.length){el.innerHTML='<li>No active warnings.</li>';return}
  el.innerHTML = w.map(x=>`<li>${x}</li>`).join('');
})();

// ═══════════════════════════════════════════════════════════════════
// NEW v7.2 LAYER DETAIL CARDS
// ═══════════════════════════════════════════════════════════════════
(function(){
  const fv = cur.layer_details.flow_velocity;
  document.getElementById('detail-flow').innerHTML = `
    <h2><span class="dot" style="background:var(--purple)"></span> Flow Velocity (10%)</h2>
    <div style="text-align:center;margin:.8rem 0">
      <span style="font-size:2rem;font-weight:700;color:${scoreColor(cur.layer_scores.flow_velocity)}">${fmt(cur.layer_scores.flow_velocity,0)}</span>
      <span style="color:var(--muted);font-size:.8rem">/100</span>
    </div>
    <div class="data-grid">
      <div class="data-item"><span class="k">7d Flow % Mcap</span><span class="v">${fmt(fv.flow_7d_pct,4)}%</span></div>
      <div class="data-item"><span class="k">Velocity (Short)</span><span class="v">${pct(fv.velocity_short)}</span></div>
      <div class="data-item"><span class="k">Velocity (Medium)</span><span class="v">${pct(fv.velocity_medium)}</span></div>
      <div class="data-item"><span class="k">Spike Ratio</span><span class="v">${fmt(fv.spike_ratio,1)}x</span></div>
      <div class="data-item"><span class="k">Spike Detected</span><span class="v" style="color:${fv.spike_detected?'var(--red)':'var(--green)'}">${fv.spike_detected?'YES':'No'}</span></div>
      <div class="data-item"><span class="k">Interpretation</span><span class="v">${fv.interpretation.replace(/_/g,' ')}</span></div>
    </div>`;

  const lf = cur.layer_details.leverage_fragility;
  document.getElementById('detail-fragility').innerHTML = `
    <h2><span class="dot" style="background:var(--orange)"></span> Leverage Fragility (8%)</h2>
    <div style="text-align:center;margin:.8rem 0">
      <span style="font-size:2rem;font-weight:700;color:${scoreColor(cur.layer_scores.leverage_fragility)}">${fmt(cur.layer_scores.leverage_fragility,0)}</span>
      <span style="color:var(--muted);font-size:.8rem">/100</span>
    </div>
    <div class="data-grid">
      <div class="data-item"><span class="k">OI % of Mcap</span><span class="v">${fmt(lf.oi_pct_mcap,1)}%</span></div>
      <div class="data-item"><span class="k">OI Score</span><span class="v">${fmt(lf.oi_score,0)}</span></div>
      <div class="data-item"><span class="k">Funding Score</span><span class="v">${fmt(lf.funding_score,0)}</span></div>
      <div class="data-item"><span class="k">L/S Score</span><span class="v">${fmt(lf.ls_score,0)}</span></div>
      <div class="data-item"><span class="k">Proximity Score</span><span class="v">${fmt(lf.prox_score,0)}</span></div>
      <div class="data-item"><span class="k">24h Liquidations</span><span class="v">$${fmt(lf.liquidations_24h,0)}M</span></div>
      <div class="data-item"><span class="k">Interpretation</span><span class="v">${lf.interpretation.replace(/_/g,' ')}</span></div>
    </div>`;

  const si = cur.layer_details.support_integrity;
  document.getElementById('detail-support').innerHTML = `
    <h2><span class="dot" style="background:var(--cyan)"></span> Support Integrity (7%)</h2>
    <div style="text-align:center;margin:.8rem 0">
      <span style="font-size:2rem;font-weight:700;color:${scoreColor(cur.layer_scores.support_integrity)}">${fmt(cur.layer_scores.support_integrity,0)}</span>
      <span style="color:var(--muted);font-size:.8rem">/100</span>
    </div>
    <div class="data-grid">
      <div class="data-item"><span class="k">vs 50-day MA</span><span class="v">${pct(si.pct_vs_50)}</span></div>
      <div class="data-item"><span class="k">vs 200-day MA</span><span class="v">${pct(si.pct_vs_200)}</span></div>
      <div class="data-item"><span class="k">vs 365-day MA</span><span class="v" style="color:${si.pct_vs_365<0?'var(--red)':'var(--green)'}">${pct(si.pct_vs_365)}</span></div>
      <div class="data-item"><span class="k">Days Below 200MA</span><span class="v">${si.days_below_200ma}</span></div>
      <div class="data-item"><span class="k">Recent Break</span><span class="v" style="color:${si.recent_break?'var(--red)':'var(--green)'}">${si.recent_break?'YES':'No'}</span></div>
      <div class="data-item"><span class="k">Structure</span><span class="v">${si.structure.replace(/_/g,' ')}</span></div>
    </div>`;
})();

// ═══════════════════════════════════════════════════════════════════
// MARKET DATA PANELS
// ═══════════════════════════════════════════════════════════════════
(function(){
  const md = cur.market_data;
  function rows(pairs){return pairs.map(([k,v])=>`<div class="data-item"><span class="k">${k}</span><span class="v">${v}</span></div>`).join('')}

  document.getElementById('md-price').innerHTML = rows([
    ['BTC Price', usd(md.btc_price)],
    ['ATH', usd(md.btc_ath)],
    ['Drawdown', '-'+fmt(md.drawdown_from_ath)+'%'],
    ['MVRV Z-Score', fmt(md.mvrv_z_score,2)],
    ['Fear & Greed', fmt(md.fear_greed,0)],
    ['Weekly RSI', fmt(md.weekly_rsi,0)],
    ['50-day MA', usd(md.ma_50)],
    ['200-day MA', usd(md.ma_200)],
    ['365-day MA', usd(md.ma_365)],
    ['vs 200MA', pct(md.pct_vs_200ma)],
    ['vs 365MA', pct(md.pct_vs_365ma)],
    ['30d ROC', pct(md.roc_30d)],
  ]);

  document.getElementById('md-etf').innerHTML = rows([
    ['1d Flow', '$'+fmt(md.etf_flow_1d,2)+'B'],
    ['7d Flow', '$'+fmt(md.etf_flow_7d,2)+'B'],
    ['30d Flow', '$'+fmt(md.etf_flow_30d,2)+'B'],
    ['90d Flow', '$'+fmt(md.etf_flow_90d,2)+'B'],
    ['ETF AUM % Mcap', fmt(md.etf_aum_pct_mcap,1)+'%'],
    ['BTC Dominance', fmt(md.btc_dominance,1)+'%'],
  ]);

  document.getElementById('md-deriv').innerHTML = rows([
    ['Funding Rate', (md.funding_rate*100).toFixed(3)+'%'],
    ['OI % Mcap', fmt(md.oi_pct_mcap,1)+'%'],
    ['OI Change 7d', pct(md.oi_change_7d)],
    ['Long/Short', fmt(md.long_short_ratio,2)],
    ['24h Liqs', '$'+fmt(md.liquidations_24h,0)+'M'],
    ['Net Liquidity', '$'+fmt(md.net_liquidity/1000,2)+'T'],
    ['DXY', fmt(md.dxy,2)],
    ['M2 YoY', pct(md.m2_yoy)],
  ]);
})();

// ═══════════════════════════════════════════════════════════════════
// MVRV REGIME ZONE CHART
// ═══════════════════════════════════════════════════════════════════
(function(){
  const ctx = document.getElementById('mvrvZones').getContext('2d');
  const oc = cur.layer_details.onchain;
  const mvrv = oc.mvrv_z;
  const adjOV = oc.adj_overvalued_threshold;
  const adjEX = oc.adj_extreme_threshold;

  // Zone boundaries for the horizontal stacked bar
  const zones = [
    {label:'Capitulation',max:0,color:'#166534'},
    {label:'Deep Value',max:0.5,color:'#22c55e'},
    {label:'Undervalued',max:0.75,color:'#4ade80'},
    {label:'Fair Low',max:1.0,color:'#86efac'},
    {label:'Fair',max:adjOV,color:'#fde047'},
    {label:'Overvalued',max:adjEX,color:'#f97316'},
    {label:'Extreme',max:5.0,color:'#ef4444'},
  ];

  // Build stacked segments
  let prev = -0.5;
  const segments = zones.map(z => {
    const width = z.max - prev;
    prev = z.max;
    return {label: z.label, width, color: z.color};
  });

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['MVRV Zone'],
      datasets: segments.map(s => ({
        label: s.label,
        data: [s.width],
        backgroundColor: s.color,
        borderWidth: 0
      }))
    },
    options: {
      indexAxis: 'y',
      scales: {
        x: {
          stacked: true,
          min: -0.5,
          max: 5,
          title: {display: true, text: 'MVRV Z-Score'},
          grid: {color: 'rgba(51,65,85,.3)'}
        },
        y: {stacked: true, display: false}
      },
      plugins: {
        legend: {position: 'bottom', labels: {boxWidth: 12, padding: 8, font: {size: 10}}},
        tooltip: {enabled: true},
        annotation: undefined
      },
      animation: {
        onComplete: function() {
          // Draw the current MVRV marker
          const chart = this;
          const xScale = chart.scales.x;
          const yScale = chart.scales.y;
          const xPx = xScale.getPixelForValue(mvrv);
          const yCenter = (yScale.top + yScale.bottom) / 2;

          const dctx = chart.ctx;
          dctx.save();
          // Vertical line
          dctx.strokeStyle = '#ffffff';
          dctx.lineWidth = 2;
          dctx.setLineDash([4, 3]);
          dctx.beginPath();
          dctx.moveTo(xPx, yScale.top - 10);
          dctx.lineTo(xPx, yScale.bottom + 10);
          dctx.stroke();
          // Triangle marker
          dctx.setLineDash([]);
          dctx.fillStyle = '#ffffff';
          dctx.beginPath();
          dctx.moveTo(xPx, yScale.top - 14);
          dctx.lineTo(xPx - 6, yScale.top - 24);
          dctx.lineTo(xPx + 6, yScale.top - 24);
          dctx.closePath();
          dctx.fill();
          // Label
          dctx.fillStyle = '#ffffff';
          dctx.font = 'bold 11px monospace';
          dctx.textAlign = 'center';
          dctx.fillText('Current: ' + mvrv.toFixed(2), xPx, yScale.top - 28);
          dctx.restore();
        }
      }
    }
  });
})();

</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Build and write
# ─────────────────────────────────────────────────────────────────────────────

def main():
    data = collect_dashboard_data()
    json_blob = json.dumps(data, default=str)
    html = HTML_TEMPLATE.replace("__DASHBOARD_JSON__", json_blob)

    out_path = "index.html"
    with open(out_path, "w") as f:
        f.write(html)

    print(f"Dashboard written to {out_path}")

    if "--open" in sys.argv:
        import webbrowser
        webbrowser.open(out_path)


if __name__ == "__main__":
    main()
