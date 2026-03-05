#!/usr/bin/env python3
"""
Live data fetcher for BTC Econometric Model v7.2.

Fetches real-time market data from free public APIs:
- CoinGecko: price, ATH, market cap, MAs, derivatives, BTC dominance
- Alternative.me: Fear & Greed Index
- FRED (St. Louis Fed): Fed balance sheet, M2, DXY, RRP, TGA

Set FRED_API_KEY environment variable for macro data.

Usage:
    from fetch_live_data import fetch_live_market_data
    data = fetch_live_market_data()

    # With manual overrides for paid-API fields:
    data = fetch_live_market_data(overrides={"mvrv_z_score": 1.5, "etf_flow_7d": 0.3})
"""

import os
import requests
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from btc_model_v72 import MarketDataV72

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")


def _get_json(url: str, timeout: int = 15) -> Optional[dict]:
    """Fetch JSON from URL, return None on failure."""
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return None


def _compute_rsi(closes: list, period: int = 14) -> float:
    """Compute RSI from a list of closing prices."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-(period):]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0.001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_weekly_rsi(daily_closes: list) -> float:
    """Compute weekly RSI from daily closing prices."""
    # Resample to weekly (take every 7th close)
    weekly = daily_closes[::7]
    if len(weekly) < 15:
        weekly = daily_closes[::5]  # fallback to ~5-day windows
    return _compute_rsi(weekly, period=14)


def _count_days_below_ma(daily_closes: list, ma_value: float) -> int:
    """Count consecutive recent days below a moving average."""
    count = 0
    for price in reversed(daily_closes):
        if price < ma_value:
            count += 1
        else:
            break
    return count


def _fetch_coingecko_coin_data() -> Optional[dict]:
    """Fetch BTC coin detail (ATH, current price, market cap)."""
    return _get_json(
        "https://api.coingecko.com/api/v3/coins/bitcoin"
        "?localization=false&tickers=false&market_data=true"
        "&community_data=false&developer_data=false"
    )


def _fetch_price_history(days: int = 365) -> Optional[list]:
    """Fetch daily price history from CoinGecko."""
    data = _get_json(
        f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        f"?vs_currency=usd&days={days}&interval=daily"
    )
    if data and "prices" in data:
        return [p[1] for p in data["prices"]]
    return None


def _fetch_fear_greed() -> Optional[int]:
    """Fetch current Fear & Greed Index from Alternative.me."""
    data = _get_json("https://api.alternative.me/fng/?limit=1")
    if data and "data" in data and len(data["data"]) > 0:
        return int(data["data"][0]["value"])
    return None


def _fetch_global_data() -> Optional[dict]:
    """Fetch global crypto market data (BTC dominance)."""
    data = _get_json("https://api.coingecko.com/api/v3/global")
    if data and "data" in data:
        return data["data"]
    return None


def _fetch_derivatives_data() -> dict:
    """Fetch BTC perpetual derivatives data from CoinGecko."""
    data = _get_json("https://api.coingecko.com/api/v3/derivatives")
    if not data:
        return {}

    # Filter for BTC perpetual contracts on major exchanges
    major_exchanges = {"Binance (Futures)", "OKX (Futures)", "Bybit (Futures)", "dYdX (Futures)"}
    btc_perps = [
        d for d in data
        if d.get("index_id") == "BTC"
        and d.get("contract_type") == "perpetual"
        and d.get("market") in major_exchanges
        and d.get("funding_rate") is not None
        and d.get("open_interest") is not None
    ]

    if not btc_perps:
        return {}

    # Average funding rate across major exchanges
    funding_rates = [float(d["funding_rate"]) for d in btc_perps if d["funding_rate"]]
    avg_funding = sum(funding_rates) / len(funding_rates) if funding_rates else 0

    # Total open interest across exchanges
    total_oi = sum(float(d["open_interest"]) for d in btc_perps if d["open_interest"])

    return {
        "funding_rate": round(avg_funding * 100, 4),  # Convert to percentage
        "oi_total_usd": total_oi,
        "num_exchanges": len(btc_perps),
    }


def _fred_latest(series_id: str) -> Optional[float]:
    """Fetch the latest value for a FRED series."""
    if not FRED_API_KEY:
        return None
    data = _get_json(
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&sort_order=desc&limit=1"
        f"&api_key={FRED_API_KEY}&file_type=json"
    )
    if data and "observations" in data and data["observations"]:
        val = data["observations"][0].get("value", ".")
        if val != ".":
            return float(val)
    return None


def _fred_value_n_months_ago(series_id: str, months: int) -> Optional[float]:
    """Fetch the value from approximately N months ago for a FRED series."""
    if not FRED_API_KEY:
        return None
    target = datetime.now(timezone.utc) - timedelta(days=months * 30)
    start = (target - timedelta(days=15)).strftime("%Y-%m-%d")
    end = (target + timedelta(days=15)).strftime("%Y-%m-%d")
    data = _get_json(
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&observation_start={start}&observation_end={end}"
        f"&sort_order=desc&limit=1"
        f"&api_key={FRED_API_KEY}&file_type=json"
    )
    if data and "observations" in data and data["observations"]:
        val = data["observations"][0].get("value", ".")
        if val != ".":
            return float(val)
    return None


def _fetch_fred_macro() -> dict:
    """Fetch macro data from FRED: Fed BS, RRP, TGA, M2, DXY."""
    if not FRED_API_KEY:
        return {}

    result = {}

    # WALCL = Fed total assets (weekly, in millions)
    fed_bs = _fred_latest("WALCL")
    if fed_bs is not None:
        result["fed_bs"] = fed_bs / 1000  # Convert millions to billions
    fed_bs_3m = _fred_value_n_months_ago("WALCL", 3)
    if fed_bs_3m is not None:
        result["fed_bs_3m_ago"] = fed_bs_3m / 1000

    # RRPONTSYD = Overnight Reverse Repo (daily, in billions)
    rrp = _fred_latest("RRPONTSYD")
    if rrp is not None:
        result["rrp"] = rrp

    # WTREGEN = Treasury General Account (weekly, in millions)
    tga = _fred_latest("WTREGEN")
    if tga is not None:
        result["tga"] = tga / 1000  # Convert millions to billions

    # WM2NS = M2 Money Stock (monthly, in billions)
    m2_now = _fred_latest("WM2NS")
    m2_1y = _fred_value_n_months_ago("WM2NS", 12)
    if m2_now is not None and m2_1y is not None and m2_1y > 0:
        result["m2_yoy"] = round((m2_now - m2_1y) / m2_1y * 100, 2)

    # Note: FRED's DTWEXBGS (Trade Weighted Dollar Index) uses a different
    # scale (~115-120) than ICE DXY (~95-110) that the model is calibrated for.
    # DXY should be provided via overrides or defaults to 100 (neutral).

    return result


def fetch_live_market_data(overrides: Optional[Dict[str, Any]] = None) -> MarketDataV72:
    """
    Fetch live market data and construct a MarketDataV72 instance.

    Args:
        overrides: Dict of field names to override with manual values.
                   Useful for fields requiring paid APIs (MVRV, ETF flows, etc.)

    Returns:
        MarketDataV72 with live data where available, defaults elsewhere.
    """
    overrides = overrides or {}
    quality_deductions = 0
    print("Fetching live market data...")

    # --- Price & Market Data ---
    coin_data = _fetch_coingecko_coin_data()
    if coin_data and "market_data" in coin_data:
        md = coin_data["market_data"]
        btc_price = md["current_price"]["usd"]
        btc_ath = md["ath"]["usd"]
        market_cap = md["market_cap"]["usd"]
    else:
        print("  [ERROR] Could not fetch BTC price data")
        quality_deductions += 30
        btc_price = overrides.get("btc_price", 0)
        btc_ath = overrides.get("btc_ath", 0)

    # --- Price History & Moving Averages ---
    daily_closes = _fetch_price_history(365)
    if daily_closes and len(daily_closes) >= 50:
        ma_50 = sum(daily_closes[-50:]) / 50
        ma_200 = sum(daily_closes[-200:]) / min(200, len(daily_closes)) if len(daily_closes) >= 200 else sum(daily_closes) / len(daily_closes)
        ma_365 = sum(daily_closes) / len(daily_closes)
        btc_7d_ago = daily_closes[-8] if len(daily_closes) >= 8 else daily_closes[0]
        btc_30d_ago = daily_closes[-31] if len(daily_closes) >= 31 else daily_closes[0]
        btc_90d_ago = daily_closes[-91] if len(daily_closes) >= 91 else daily_closes[0]
        weekly_rsi = _compute_weekly_rsi(daily_closes)
        days_below_200 = _count_days_below_ma(daily_closes, ma_200)
        days_below_365 = _count_days_below_ma(daily_closes, ma_365)
        recent_support_break = btc_price < ma_200 and days_below_200 <= 14
    else:
        print("  [ERROR] Could not fetch price history")
        quality_deductions += 20
        ma_50 = btc_price
        ma_200 = btc_price
        ma_365 = btc_price
        btc_7d_ago = btc_price
        btc_30d_ago = btc_price
        btc_90d_ago = btc_price
        weekly_rsi = 50
        days_below_200 = 0
        days_below_365 = 0
        recent_support_break = False

    # --- Fear & Greed ---
    fear_greed = _fetch_fear_greed()
    if fear_greed is None:
        print("  [WARN] Could not fetch Fear & Greed index")
        quality_deductions += 5
        fear_greed = 50

    # --- Global Data (BTC Dominance) ---
    global_data = _fetch_global_data()
    btc_dominance = 50.0
    if global_data:
        btc_dominance = global_data.get("market_cap_percentage", {}).get("btc", 50.0)
    else:
        quality_deductions += 3

    # --- Derivatives ---
    deriv = _fetch_derivatives_data()
    if deriv:
        funding_rate = deriv["funding_rate"]
        oi_total_b = deriv["oi_total_usd"] / 1e9
        mcap_b = btc_price * 19.8e6 / 1e9
        oi_pct_mcap = (oi_total_b / mcap_b * 100) if mcap_b > 0 else 0
    else:
        quality_deductions += 10
        funding_rate = 0
        oi_total_b = 0
        oi_pct_mcap = 0

    # --- Fields requiring paid APIs (use overrides or defaults) ---
    # On-chain: MVRV, NUPL, SOPR need Glassnode/CryptoQuant
    mvrv = overrides.get("mvrv_z_score", 1.0)
    nupl = overrides.get("nupl", 0.3)
    sopr = overrides.get("sopr", 1.0)
    if "mvrv_z_score" not in overrides:
        quality_deductions += 15
        print("  [INFO] MVRV using default (1.0). Pass overrides={'mvrv_z_score': X} for accuracy.")

    # ETF flows: need SoSoValue/Bloomberg
    etf_flow_1d = overrides.get("etf_flow_1d", 0)
    etf_flow_7d = overrides.get("etf_flow_7d", 0)
    etf_flow_30d = overrides.get("etf_flow_30d", 0)
    etf_flow_90d = overrides.get("etf_flow_90d", 0)
    etf_cumulative = overrides.get("etf_cumulative", 55.0)
    etf_aum_pct = overrides.get("etf_aum_pct_mcap", 5.0)
    max_single_day = overrides.get("max_single_day_flow_7d", 0)
    if "etf_flow_7d" not in overrides:
        quality_deductions += 10
        print("  [INFO] ETF flows using default (0). Pass overrides={'etf_flow_7d': X, ...} for accuracy.")

    # Macro: Fed BS, RRP, TGA, M2, DXY from FRED API
    fred = _fetch_fred_macro()
    if fred:
        print(f"  [FRED] Fetched {len(fred)} macro data points")
    elif FRED_API_KEY:
        print("  [WARN] FRED API returned no data")
    else:
        print("  [INFO] Set FRED_API_KEY env var for live macro data")

    fed_bs = overrides.get("fed_bs", fred.get("fed_bs", 6500))
    fed_bs_3m = overrides.get("fed_bs_3m_ago", fred.get("fed_bs_3m_ago", 6520))
    rrp = overrides.get("rrp", fred.get("rrp", 200))
    tga = overrides.get("tga", fred.get("tga", 750))
    m2_yoy = overrides.get("m2_yoy", fred.get("m2_yoy", 3.0))
    dxy = overrides.get("dxy", fred.get("dxy", 100))
    if not fred and "fed_bs" not in overrides:
        quality_deductions += 5

    # Derivatives fields not from CoinGecko
    funding_7d_avg = overrides.get("funding_rate_7d_avg", funding_rate)
    oi_change_7d = overrides.get("oi_change_7d", 0)
    ls_ratio = overrides.get("long_short_ratio", 1.0)
    liqs_24h = overrides.get("liquidations_24h", 0)
    liq_distance = overrides.get("price_to_liq_cluster_pct", 10)
    supply_profit = overrides.get("supply_in_profit_pct", 60)

    # Apply overrides for any remaining fields
    data_quality = max(0, 100 - quality_deductions)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"  Data quality: {data_quality}/100")
    print(f"  BTC: ${btc_price:,.0f} | ATH: ${btc_ath:,.0f} | F&G: {fear_greed}")
    print(f"  MA50: ${ma_50:,.0f} | MA200: ${ma_200:,.0f} | MA365: ${ma_365:,.0f}")
    if deriv:
        print(f"  Funding: {funding_rate:.4f}% | OI: ${oi_total_b:.1f}B ({oi_pct_mcap:.1f}% mcap)")
    if fred:
        print(f"  Fed BS: ${fed_bs:,.0f}B | RRP: ${rrp:,.0f}B | TGA: ${tga:,.0f}B")
        print(f"  M2 YoY: {m2_yoy:.1f}% | DXY: {dxy:.1f}")
    print()

    return MarketDataV72(
        btc_price=overrides.get("btc_price", btc_price),
        btc_ath=overrides.get("btc_ath", btc_ath),
        btc_7d_ago=overrides.get("btc_7d_ago", btc_7d_ago),
        btc_30d_ago=overrides.get("btc_30d_ago", btc_30d_ago),
        btc_90d_ago=overrides.get("btc_90d_ago", btc_90d_ago),
        ma_50=overrides.get("ma_50", ma_50),
        ma_200=overrides.get("ma_200", ma_200),
        ma_365=overrides.get("ma_365", ma_365),
        mvrv_z_score=mvrv,
        nupl=nupl,
        sopr=sopr,
        supply_in_profit_pct=supply_profit,
        etf_flow_1d=etf_flow_1d,
        etf_flow_7d=etf_flow_7d,
        etf_flow_30d=etf_flow_30d,
        etf_flow_90d=etf_flow_90d,
        etf_cumulative=etf_cumulative,
        etf_aum_pct_mcap=etf_aum_pct,
        max_single_day_flow_7d=max_single_day,
        funding_rate=overrides.get("funding_rate", funding_rate),
        funding_rate_7d_avg=funding_7d_avg,
        oi_total=overrides.get("oi_total", oi_total_b),
        oi_change_7d=oi_change_7d,
        oi_pct_mcap=overrides.get("oi_pct_mcap", oi_pct_mcap),
        long_short_ratio=ls_ratio,
        liquidations_24h=liqs_24h,
        price_to_liq_cluster_pct=liq_distance,
        fear_greed=overrides.get("fear_greed", fear_greed),
        weekly_rsi=overrides.get("weekly_rsi", weekly_rsi),
        fed_bs=fed_bs,
        fed_bs_3m_ago=fed_bs_3m,
        rrp=rrp,
        tga=tga,
        m2_yoy=m2_yoy,
        dxy=dxy,
        days_below_200ma=overrides.get("days_below_200ma", days_below_200),
        days_below_365ma=overrides.get("days_below_365ma", days_below_365),
        recent_support_break=overrides.get("recent_support_break", recent_support_break),
        btc_dominance=overrides.get("btc_dominance", btc_dominance),
        date=today,
        data_quality_score=data_quality,
    )


if __name__ == "__main__":
    from btc_model_v72 import BTCModelV72, CalibratedThresholds

    data = fetch_live_market_data()
    model = BTCModelV72(data, CalibratedThresholds())
    result = model.run_full_analysis()

    print(f"Health: {result['health']}")
    print(f"Signal: {result['signal']}")
    print(f"Allocation: {result['final_allocation']}%")
    print(f"Phase: {result['phase']}")
    print(f"Data Quality: {data.data_quality_score}/100")
    print()
    print("Layer Scores:")
    for layer, score in result["layer_scores"].items():
        src = "LIVE" if layer in ("momentum", "sentiment", "support_integrity", "derivatives") else "DEFAULT"
        print(f"  {layer:>22}: {score:6.1f}  [{src}]")
    if result["warnings"]:
        print(f"\nWarnings: {result['warnings']}")
