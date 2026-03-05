#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
BTC ECONOMETRIC MODEL v7.2 - CALIBRATED POST-CRASH FRAMEWORK
═══════════════════════════════════════════════════════════════════════════════

Version: 7.2.0
Date: February 7, 2026
Author: Calibrated from Oct 2025 - Feb 2026 crash post-mortem

MAJOR CHANGES FROM v7.1:
────────────────────────
1. NEW: Flow Velocity Layer (10%) - Rate of change of institutional flows
2. NEW: Leverage Fragility Index (8%) - Detect buildup before cascades
3. NEW: Support Integrity Score (7%) - MA breaks are structural signals
4. UPDATED: Regime-adjusted MVRV thresholds for ETF era
5. UPDATED: Institutional weight 8% → 15% (ETF flows critical)
6. UPDATED: On-Chain weight 28% → 20% (MVRV less reliable in ETF era)
7. NEW: Asymmetric Response Rules (faster exits, slower entries)
8. NEW: Emergency Override System for extreme conditions

LAYER WEIGHTS v7.2:
───────────────────
├─ On-Chain (MVRV):      20%  (down from 28%)
├─ Institutional:        15%  (up from 8%)
├─ Flow Velocity:        10%  (NEW)
├─ Momentum:             12%  (down from 20%)
├─ Derivatives:          10%  (down from 18%)
├─ Leverage Fragility:    8%  (NEW)
├─ Support Integrity:     7%  (NEW)
├─ Liquidity:             8%  (down from 12%)
├─ Global M2:             5%  (down from 8%)
└─ Sentiment:             5%  (NEW - Fear/Greed explicit)
   TOTAL:               100%

CALIBRATION SOURCES:
────────────────────
- October 2025 - February 2026 crash data
- ETF flow patterns (SoSoValue, Farside)
- Leverage cascade analysis (Coinglass)
- Historical MVRV regime analysis
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum
from datetime import datetime
import math

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def clamp(value: float, min_val: float = 0, max_val: float = 100) -> float:
    """Clamp value to range [min_val, max_val]"""
    return max(min_val, min(max_val, value))

def linear_score(value: float, low: float, high: float,
                 low_score: float = 0, high_score: float = 100) -> float:
    """Linear interpolation for scoring"""
    if value <= low:
        return low_score
    elif value >= high:
        return high_score
    else:
        return low_score + (value - low) / (high - low) * (high_score - low_score)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS AND CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

class CyclePhase(Enum):
    """Market cycle phases"""
    CAPITULATION = "CAPITULATION"
    DEEP_ACCUMULATION = "DEEP_ACCUMULATION"
    ACCUMULATION = "ACCUMULATION"
    EARLY_BULL = "EARLY_BULL"
    MID_BULL = "MID_BULL"
    LATE_BULL = "LATE_BULL"
    DISTRIBUTION = "DISTRIBUTION"
    EARLY_BEAR = "EARLY_BEAR"
    BEAR = "BEAR"

class Signal(Enum):
    """Trading signals"""
    EMERGENCY_SELL = "EMERGENCY_SELL"
    STRONG_SELL = "STRONG_SELL"
    SELL = "SELL"
    REDUCE = "REDUCE"
    HOLD = "HOLD"
    ACCUMULATE = "ACCUMULATE"
    BUY = "BUY"
    STRONG_BUY = "STRONG_BUY"
    AGGRESSIVE_BUY = "AGGRESSIVE_BUY"


# ═══════════════════════════════════════════════════════════════════════════════
# CALIBRATED THRESHOLDS (from post-mortem analysis)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CalibratedThresholds:
    """
    Thresholds calibrated from October 2025 - February 2026 crash analysis.

    Key insight: ETF era requires regime-adjusted thresholds.
    Old thresholds (MVRV >4 = top) failed at $126K where MVRV was only ~2.8
    """

    # MVRV Z-SCORE THRESHOLDS (Regime-Adjusted for ETF Era)
    mvrv_extreme_overvalued_base: float = 4.0
    mvrv_overvalued_base: float = 3.0
    mvrv_fair_high_base: float = 2.0
    mvrv_fair_low: float = 1.0
    mvrv_undervalued: float = 0.75
    mvrv_deep_value: float = 0.5
    mvrv_capitulation: float = 0.0
    etf_compression_factor: float = 0.75

    # FLOW VELOCITY THRESHOLDS (NEW in v7.2)
    flow_spike_multiplier: float = 3.0
    flow_crisis_pct: float = -0.5
    flow_warning_pct: float = -0.2
    flow_healthy_pct: float = 0.1
    flow_strong_pct: float = 0.3

    # LEVERAGE FRAGILITY THRESHOLDS (NEW in v7.2)
    oi_dangerous_pct: float = 6.0
    oi_elevated_pct: float = 4.5
    oi_normal_pct: float = 3.0
    oi_low_pct: float = 2.0

    funding_extreme_positive: float = 0.05
    funding_elevated_positive: float = 0.03
    funding_neutral_low: float = -0.01
    funding_extreme_negative: float = -0.03

    ls_ratio_long_heavy: float = 1.5
    ls_ratio_balanced_high: float = 1.2
    ls_ratio_balanced_low: float = 0.8
    ls_ratio_short_heavy: float = 0.7

    liquidation_cascade: float = 500
    liquidation_elevated: float = 200
    liquidation_cluster_danger: float = 3
    liquidation_cluster_warning: float = 5

    # SUPPORT INTEGRITY THRESHOLDS (NEW in v7.2)
    support_strong_above_all: float = 90
    support_uptrend: float = 75
    support_pullback: float = 60
    support_warning: float = 45
    support_broken: float = 25

    days_below_200ma_concern: int = 7
    days_below_200ma_critical: int = 21

    # ASYMMETRIC RESPONSE THRESHOLDS
    bearish_flow_crisis: float = 30
    bearish_flow_warning: float = 45
    bearish_fragility_cascade: float = 30
    bearish_fragility_elevated: float = 45
    bearish_support_broken: float = 35
    bearish_support_warning: float = 50
    bearish_multi_layer_count: int = 4

    bullish_confirm_layers: int = 5
    bullish_max_increase: float = 10
    bullish_confirm_weeks: int = 2

    # ALLOCATION THRESHOLDS
    alloc_aggressive_health: float = 75
    alloc_moderate_health: float = 55
    alloc_cautious_health: float = 40
    alloc_defensive_health: float = 25

    alloc_max_accumulation: float = 100
    alloc_max_normal: float = 85
    alloc_min_hold: float = 10
    alloc_emergency_max: float = 5


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET DATA STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketDataV72:
    """
    Complete market data structure for v7.2 model.
    Includes new fields required for Flow Velocity, Leverage Fragility,
    and Support Integrity layers.
    """

    # PRICE DATA
    btc_price: float
    btc_ath: float
    btc_7d_ago: float
    btc_30d_ago: float
    btc_90d_ago: float

    # Moving Averages
    ma_50: float
    ma_200: float
    ma_365: float

    # ON-CHAIN DATA
    mvrv_z_score: float
    nupl: Optional[float] = None
    sopr: Optional[float] = None
    supply_in_profit_pct: Optional[float] = None

    # INSTITUTIONAL / ETF DATA
    etf_flow_1d: float = 0
    etf_flow_7d: float = 0
    etf_flow_30d: float = 0
    etf_flow_90d: float = 0
    etf_cumulative: float = 0
    etf_aum_pct_mcap: float = 5.0
    max_single_day_flow_7d: float = 0

    # DERIVATIVES DATA
    funding_rate: float = 0
    funding_rate_7d_avg: float = 0
    oi_total: float = 0
    oi_change_7d: float = 0
    oi_pct_mcap: float = 0
    long_short_ratio: float = 1.0
    liquidations_24h: float = 0
    price_to_liq_cluster_pct: float = 10

    # SENTIMENT DATA
    fear_greed: float = 50
    weekly_rsi: float = 50

    # MACRO / LIQUIDITY DATA
    fed_bs: float = 0
    fed_bs_3m_ago: float = 0
    rrp: float = 0
    tga: float = 0
    m2_yoy: float = 0
    dxy: float = 100

    # SUPPORT INTEGRITY DATA (NEW for v7.2)
    days_below_200ma: int = 0
    days_below_365ma: int = 0
    recent_support_break: bool = False

    # ROTATION DATA
    btc_dominance: float = 50

    # META
    date: str = ""
    data_quality_score: float = 100

    @property
    def market_cap(self) -> float:
        """Estimated BTC market cap in $B"""
        circulating_supply = 19.8
        return (self.btc_price * circulating_supply * 1_000_000) / 1_000_000_000

    @property
    def net_liquidity(self) -> float:
        """Net Liquidity = Fed BS - RRP - TGA (in $B)"""
        return self.fed_bs - self.rrp - self.tga

    @property
    def drawdown_from_ath(self) -> float:
        """Current drawdown from ATH as %"""
        if self.btc_ath <= 0:
            return 0
        return ((self.btc_ath - self.btc_price) / self.btc_ath) * 100

    @property
    def roc_7d(self) -> float:
        """7-day rate of change %"""
        if self.btc_7d_ago <= 0:
            return 0
        return ((self.btc_price - self.btc_7d_ago) / self.btc_7d_ago) * 100

    @property
    def roc_30d(self) -> float:
        """30-day rate of change %"""
        if self.btc_30d_ago <= 0:
            return 0
        return ((self.btc_price - self.btc_30d_ago) / self.btc_30d_ago) * 100

    @property
    def pct_vs_200ma(self) -> float:
        """% above/below 200 MA"""
        if self.ma_200 <= 0:
            return 0
        return ((self.btc_price - self.ma_200) / self.ma_200) * 100

    @property
    def pct_vs_365ma(self) -> float:
        """% above/below 365 MA"""
        if self.ma_365 <= 0:
            return 0
        return ((self.btc_price - self.ma_365) / self.ma_365) * 100

    @property
    def etf_flow_7d_pct_mcap(self) -> float:
        """7d ETF flows as % of market cap"""
        if self.market_cap <= 0:
            return 0
        return (self.etf_flow_7d * 1000 / self.market_cap) * 100


# ═══════════════════════════════════════════════════════════════════════════════
# BTC MODEL v7.2 - MAIN CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class BTCModelV72:
    """
    BTC Econometric Model v7.2 - Calibrated Post-Crash Framework
    """

    LAYER_WEIGHTS = {
        'onchain':           0.20,
        'institutional':     0.15,
        'flow_velocity':     0.10,
        'momentum':          0.12,
        'derivatives':       0.10,
        'leverage_fragility': 0.08,
        'support_integrity': 0.07,
        'liquidity':         0.08,
        'global_m2':         0.05,
        'sentiment':         0.05,
    }

    def __init__(self, data: MarketDataV72, thresholds: CalibratedThresholds = None):
        self.data = data
        self.thresholds = thresholds or CalibratedThresholds()
        self.layer_scores: Dict[str, float] = {}
        self.layer_details: Dict[str, Dict] = {}
        self.warnings: List[str] = []
        self.asymmetric_adjustments: List[str] = []

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 1: ON-CHAIN (20%) - MVRV with Regime Adjustment
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_onchain(self) -> float:
        mvrv = self.data.mvrv_z_score
        t = self.thresholds

        etf_aum = self.data.etf_aum_pct_mcap
        if etf_aum >= 5:
            compression = t.etf_compression_factor
        elif etf_aum >= 3:
            compression = 0.85
        elif etf_aum >= 1:
            compression = 0.92
        else:
            compression = 1.0

        adj_extreme = t.mvrv_extreme_overvalued_base * compression
        adj_overvalued = t.mvrv_overvalued_base * compression
        adj_fair_high = t.mvrv_fair_high_base * compression

        if mvrv <= t.mvrv_capitulation:
            score = 98
        elif mvrv <= t.mvrv_deep_value:
            score = 92
        elif mvrv <= t.mvrv_undervalued:
            score = 85
        elif mvrv <= t.mvrv_fair_low:
            score = 75
        elif mvrv <= adj_fair_high:
            score = 60
        elif mvrv <= adj_overvalued:
            score = 45
        elif mvrv <= adj_extreme:
            score = 30
        else:
            score = 15

        if self.data.nupl is not None:
            nupl = self.data.nupl
            if nupl > 0.75:
                score -= 12
            elif nupl > 0.5:
                score -= 5
            elif nupl < 0:
                score += 8
            elif nupl < 0.25:
                score += 4

        if self.data.sopr is not None:
            sopr = self.data.sopr
            if sopr < 0.95:
                score += 5
            elif sopr > 1.1:
                score -= 8

        score = clamp(score)

        if mvrv <= t.mvrv_deep_value:
            zone = "DEEP_VALUE"
        elif mvrv <= t.mvrv_undervalued:
            zone = "UNDERVALUED"
        elif mvrv <= t.mvrv_fair_low:
            zone = "FAIR_LOW"
        elif mvrv <= adj_fair_high:
            zone = "FAIR"
        elif mvrv <= adj_overvalued:
            zone = "WARM"
        elif mvrv <= adj_extreme:
            zone = "OVERVALUED"
        else:
            zone = "EXTREME"

        self.layer_details['onchain'] = {
            'mvrv_z': mvrv,
            'nupl': self.data.nupl,
            'sopr': self.data.sopr,
            'etf_compression': compression,
            'adj_overvalued_threshold': round(adj_overvalued, 2),
            'adj_extreme_threshold': round(adj_extreme, 2),
            'zone': zone,
            'score': score
        }

        return score

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 2: INSTITUTIONAL (15%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_institutional(self) -> float:
        flow_7d = self.data.etf_flow_7d
        flow_30d = self.data.etf_flow_30d

        if flow_7d >= 2.0:
            score_7d = 95
        elif flow_7d >= 1.0:
            score_7d = 85
        elif flow_7d >= 0.5:
            score_7d = 75
        elif flow_7d >= 0:
            score_7d = 60
        elif flow_7d >= -0.5:
            score_7d = 45
        elif flow_7d >= -1.0:
            score_7d = 30
        elif flow_7d >= -2.0:
            score_7d = 18
        else:
            score_7d = 8

        if flow_30d >= 5.0:
            score_30d = 90
        elif flow_30d >= 2.0:
            score_30d = 75
        elif flow_30d >= 0:
            score_30d = 55
        elif flow_30d >= -2.0:
            score_30d = 35
        elif flow_30d >= -5.0:
            score_30d = 20
        else:
            score_30d = 10

        score = score_7d * 0.60 + score_30d * 0.40

        if score >= 70:
            signal = "ACCUMULATING"
        elif score >= 50:
            signal = "NEUTRAL"
        elif score >= 30:
            signal = "DISTRIBUTING"
        else:
            signal = "HEAVY_DISTRIBUTION"

        self.layer_details['institutional'] = {
            'etf_flow_7d': flow_7d,
            'etf_flow_30d': flow_30d,
            'score_7d': score_7d,
            'score_30d': score_30d,
            'signal': signal
        }

        return clamp(score)

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 3: FLOW VELOCITY (10%) - NEW in v7.2
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_flow_velocity(self) -> float:
        t = self.thresholds

        flow_7d = self.data.etf_flow_7d
        flow_30d = self.data.etf_flow_30d
        flow_90d = self.data.etf_flow_90d
        single_day_max = self.data.max_single_day_flow_7d
        mcap = self.data.market_cap

        # Flows and mcap are both in $B — divide directly for percentage
        flow_7d_pct = (flow_7d / mcap * 100) if mcap > 0 else 0
        flow_30d_pct = (flow_30d / mcap * 100) if mcap > 0 else 0
        flow_90d_pct = (flow_90d / mcap * 100) if mcap > 0 else 0

        weekly_rate = flow_7d_pct * 52
        monthly_rate = flow_30d_pct * 12
        velocity_short = weekly_rate - monthly_rate

        quarterly_rate = flow_90d_pct * 4 if flow_90d_pct != 0 else monthly_rate
        velocity_medium = monthly_rate - quarterly_rate

        avg_daily = abs(flow_7d / 7) if flow_7d != 0 else 0.1
        spike_ratio = abs(single_day_max) / (avg_daily + 0.01)
        spike_detected = spike_ratio > t.flow_spike_multiplier and single_day_max < 0

        if flow_7d_pct >= t.flow_strong_pct:
            base_score = 85
        elif flow_7d_pct >= t.flow_healthy_pct:
            base_score = 70
        elif flow_7d_pct >= 0:
            base_score = 55
        elif flow_7d_pct >= t.flow_warning_pct:
            base_score = 40
        elif flow_7d_pct >= t.flow_crisis_pct:
            base_score = 25
        else:
            base_score = 10

        velocity_adj = (velocity_short * 2 + velocity_medium) * 3
        velocity_adj = max(-25, min(25, velocity_adj))

        spike_penalty = -25 if spike_detected else 0

        score = clamp(base_score + velocity_adj + spike_penalty)

        if score >= 70:
            interpretation = "ACCELERATING_INFLOWS"
        elif score >= 55:
            interpretation = "STABLE_POSITIVE"
        elif score >= 40:
            interpretation = "DECELERATING_WARNING"
        elif score >= 25:
            interpretation = "ACCELERATING_OUTFLOWS"
        else:
            interpretation = "PANIC_DISTRIBUTION"

        self.layer_details['flow_velocity'] = {
            'flow_7d_pct': round(flow_7d_pct, 4),
            'flow_30d_pct': round(flow_30d_pct, 4),
            'velocity_short': round(velocity_short, 4),
            'velocity_medium': round(velocity_medium, 4),
            'spike_ratio': round(spike_ratio, 2),
            'spike_detected': spike_detected,
            'interpretation': interpretation
        }

        if spike_detected:
            self.warnings.append(
                f"PANIC SPIKE: Single-day flow {single_day_max:.0f}M is {spike_ratio:.1f}x average"
            )

        return score

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 4: MOMENTUM (12%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_momentum(self) -> float:
        price = self.data.btc_price
        ma50 = self.data.ma_50
        ma200 = self.data.ma_200
        rsi = self.data.weekly_rsi
        roc_30d = self.data.roc_30d

        if price > ma50 > ma200:
            ma_score = 85
        elif price > ma200 and ma50 > ma200:
            ma_score = 75
        elif price > ma200:
            ma_score = 60
        elif price > ma50:
            ma_score = 45
        else:
            ma_score = 30

        ma_spread = ((ma50 - ma200) / ma200) * 100 if ma200 > 0 else 0
        if ma_spread < -5:
            ma_score -= 10
        elif ma_spread > 10:
            ma_score += 5

        if rsi < 25:
            rsi_score = 92
        elif rsi < 30:
            rsi_score = 85
        elif rsi < 40:
            rsi_score = 70
        elif rsi < 60:
            rsi_score = 55
        elif rsi < 70:
            rsi_score = 40
        elif rsi < 80:
            rsi_score = 25
        else:
            rsi_score = 12

        if roc_30d < -30:
            roc_score = 80
        elif roc_30d < -20:
            roc_score = 70
        elif roc_30d < -10:
            roc_score = 55
        elif roc_30d < 10:
            roc_score = 50
        elif roc_30d < 30:
            roc_score = 60
        elif roc_30d < 50:
            roc_score = 45
        else:
            roc_score = 30

        score = ma_score * 0.35 + rsi_score * 0.35 + roc_score * 0.30

        if price > ma50 > ma200:
            structure = "BULLISH"
        elif price > ma200:
            structure = "NEUTRAL_BULLISH"
        elif price > ma50:
            structure = "RECOVERY"
        else:
            structure = "BEARISH"

        self.layer_details['momentum'] = {
            'price': price,
            'ma_50': ma50,
            'ma_200': ma200,
            'ma_spread': round(ma_spread, 2),
            'rsi': rsi,
            'roc_30d': round(roc_30d, 2),
            'ma_score': round(ma_score, 1),
            'rsi_score': round(rsi_score, 1),
            'roc_score': round(roc_score, 1),
            'structure': structure
        }

        return clamp(score)

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 5: DERIVATIVES (10%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_derivatives(self) -> float:
        funding = self.data.funding_rate
        oi_change = self.data.oi_change_7d
        ls_ratio = self.data.long_short_ratio
        t = self.thresholds

        if funding < t.funding_extreme_negative:
            funding_score = 90
        elif funding < t.funding_neutral_low:
            funding_score = 75
        elif funding < t.funding_elevated_positive:
            funding_score = 55
        elif funding < t.funding_extreme_positive:
            funding_score = 35
        else:
            funding_score = 20

        if oi_change < -25:
            oi_score = 85
        elif oi_change < -10:
            oi_score = 70
        elif oi_change < 10:
            oi_score = 55
        elif oi_change < 25:
            oi_score = 40
        else:
            oi_score = 25

        if ls_ratio < t.ls_ratio_short_heavy:
            ls_score = 80
        elif ls_ratio < t.ls_ratio_balanced_low:
            ls_score = 65
        elif ls_ratio < t.ls_ratio_balanced_high:
            ls_score = 55
        elif ls_ratio < t.ls_ratio_long_heavy:
            ls_score = 40
        else:
            ls_score = 25

        score = funding_score * 0.50 + oi_score * 0.30 + ls_score * 0.20

        if score >= 70:
            signal = "BULLISH_RESET"
        elif score >= 50:
            signal = "NEUTRAL"
        elif score >= 35:
            signal = "BUILDING_RISK"
        else:
            signal = "OVERCROWDED"

        self.layer_details['derivatives'] = {
            'funding_rate': funding,
            'funding_score': round(funding_score, 1),
            'oi_change_7d': oi_change,
            'oi_score': round(oi_score, 1),
            'long_short_ratio': ls_ratio,
            'ls_score': round(ls_score, 1),
            'signal': signal
        }

        return clamp(score)

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 6: LEVERAGE FRAGILITY (8%) - NEW in v7.2
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_leverage_fragility(self) -> float:
        t = self.thresholds

        oi_pct = self.data.oi_pct_mcap
        funding = self.data.funding_rate
        funding_avg = self.data.funding_rate_7d_avg
        ls_ratio = self.data.long_short_ratio
        liq_24h = self.data.liquidations_24h
        liq_distance = self.data.price_to_liq_cluster_pct

        if oi_pct < t.oi_low_pct:
            oi_score = 90
        elif oi_pct < t.oi_normal_pct:
            oi_score = 70
        elif oi_pct < t.oi_elevated_pct:
            oi_score = 50
        elif oi_pct < t.oi_dangerous_pct:
            oi_score = 30
        else:
            oi_score = 15

        if funding > t.funding_extreme_positive:
            fund_score = 20
        elif funding > t.funding_elevated_positive:
            fund_score = 40
        elif funding < t.funding_extreme_negative:
            fund_score = 85
        elif funding < t.funding_neutral_low:
            fund_score = 70
        else:
            fund_score = 55

        if ls_ratio > t.ls_ratio_long_heavy:
            ls_score = 25
        elif ls_ratio > t.ls_ratio_balanced_high:
            ls_score = 45
        elif ls_ratio < t.ls_ratio_short_heavy:
            ls_score = 80
        elif ls_ratio < t.ls_ratio_balanced_low:
            ls_score = 65
        else:
            ls_score = 55

        if liq_distance < t.liquidation_cluster_danger:
            prox_score = 20
        elif liq_distance < t.liquidation_cluster_warning:
            prox_score = 40
        elif liq_distance < 10:
            prox_score = 60
        else:
            prox_score = 85

        score = (oi_score * 0.30 + fund_score * 0.25 +
                 ls_score * 0.20 + prox_score * 0.25)

        if liq_24h > t.liquidation_cascade:
            score = max(10, score - 25)
            self.warnings.append(
                f"CASCADE IN PROGRESS: ${liq_24h:.0f}M liquidated in 24h"
            )
        elif liq_24h > t.liquidation_elevated:
            score = max(20, score - 12)

        if score >= 75:
            interpretation = "LOW_FRAGILITY"
        elif score >= 55:
            interpretation = "MODERATE_FRAGILITY"
        elif score >= 40:
            interpretation = "ELEVATED_FRAGILITY"
        elif score >= 25:
            interpretation = "HIGH_FRAGILITY"
        else:
            interpretation = "CASCADE_RISK"

        self.layer_details['leverage_fragility'] = {
            'oi_pct_mcap': round(oi_pct, 2),
            'oi_score': round(oi_score, 1),
            'funding_rate': funding,
            'funding_score': round(fund_score, 1),
            'ls_ratio': ls_ratio,
            'ls_score': round(ls_score, 1),
            'liq_distance_pct': liq_distance,
            'prox_score': round(prox_score, 1),
            'liquidations_24h': liq_24h,
            'interpretation': interpretation
        }

        return clamp(score)

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 7: SUPPORT INTEGRITY (7%) - NEW in v7.2
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_support_integrity(self) -> float:
        t = self.thresholds

        price = self.data.btc_price
        ma50 = self.data.ma_50
        ma200 = self.data.ma_200
        ma365 = self.data.ma_365
        days_below_200 = self.data.days_below_200ma
        recent_break = self.data.recent_support_break

        pct_vs_50 = ((price - ma50) / ma50) * 100 if ma50 > 0 else 0
        pct_vs_200 = ((price - ma200) / ma200) * 100 if ma200 > 0 else 0
        pct_vs_365 = ((price - ma365) / ma365) * 100 if ma365 > 0 else 0

        if price > ma50 and price > ma200 and price > ma365:
            structure_score = t.support_strong_above_all
            structure = "STRONG_UPTREND"
        elif price > ma200 and price > ma365:
            structure_score = t.support_uptrend
            structure = "UPTREND"
        elif price > ma365:
            structure_score = t.support_pullback
            structure = "PULLBACK"
        elif price > ma200:
            structure_score = t.support_warning
            structure = "TREND_WARNING"
        else:
            structure_score = t.support_broken
            structure = "STRUCTURAL_BREAK"

        if days_below_200 >= t.days_below_200ma_critical:
            time_penalty = 20
        elif days_below_200 >= t.days_below_200ma_concern:
            time_penalty = 10
        else:
            time_penalty = 0

        break_penalty = 15 if recent_break else 0

        score = structure_score - time_penalty - break_penalty

        if pct_vs_365 < 0:
            score = min(40, score)
            if pct_vs_365 < -5:
                self.warnings.append(
                    f"STRUCTURAL DAMAGE: Price {pct_vs_365:.1f}% below 365-day MA"
                )

        score = clamp(score)

        self.layer_details['support_integrity'] = {
            'price': price,
            'ma_50': ma50,
            'ma_200': ma200,
            'ma_365': ma365,
            'pct_vs_50': round(pct_vs_50, 2),
            'pct_vs_200': round(pct_vs_200, 2),
            'pct_vs_365': round(pct_vs_365, 2),
            'days_below_200ma': days_below_200,
            'recent_break': recent_break,
            'structure': structure
        }

        return score

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 8: LIQUIDITY (8%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_liquidity(self) -> float:
        net_liq = self.data.net_liquidity
        fed_bs = self.data.fed_bs
        fed_bs_3m = self.data.fed_bs_3m_ago

        if net_liq > 6000:
            level_score = 85
        elif net_liq > 5500:
            level_score = 70
        elif net_liq > 5000:
            level_score = 55
        elif net_liq > 4500:
            level_score = 40
        else:
            level_score = 25

        fed_change = ((fed_bs - fed_bs_3m) / fed_bs_3m) * 100 if fed_bs_3m > 0 else 0

        if fed_change > 3:
            direction_score = 90
        elif fed_change > 1:
            direction_score = 75
        elif fed_change > -1:
            direction_score = 55
        elif fed_change > -3:
            direction_score = 35
        else:
            direction_score = 20

        score = level_score * 0.40 + direction_score * 0.60

        if fed_change > 1:
            regime = "EXPANSION"
        elif fed_change > -1:
            regime = "STABLE"
        else:
            regime = "CONTRACTION"

        self.layer_details['liquidity'] = {
            'net_liquidity_T': round(net_liq / 1000, 2),
            'fed_bs': fed_bs,
            'fed_change_3m': round(fed_change, 2),
            'level_score': round(level_score, 1),
            'direction_score': round(direction_score, 1),
            'regime': regime
        }

        return clamp(score)

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 9: GLOBAL M2 (5%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_global_m2(self) -> float:
        m2_yoy = self.data.m2_yoy
        dxy = self.data.dxy

        if m2_yoy > 8:
            m2_score = 90
        elif m2_yoy > 5:
            m2_score = 75
        elif m2_yoy > 2:
            m2_score = 55
        elif m2_yoy > 0:
            m2_score = 40
        else:
            m2_score = 25

        if dxy < 95:
            dxy_score = 85
        elif dxy < 100:
            dxy_score = 70
        elif dxy < 105:
            dxy_score = 50
        elif dxy < 110:
            dxy_score = 35
        else:
            dxy_score = 20

        score = m2_score * 0.60 + dxy_score * 0.40

        if dxy < 98:
            dollar_impact = "TAILWIND"
        elif dxy < 103:
            dollar_impact = "NEUTRAL"
        else:
            dollar_impact = "HEADWIND"

        self.layer_details['global_m2'] = {
            'm2_yoy': m2_yoy,
            'm2_score': round(m2_score, 1),
            'dxy': dxy,
            'dxy_score': round(dxy_score, 1),
            'dollar_impact': dollar_impact
        }

        return clamp(score)

    # ═══════════════════════════════════════════════════════════════════════
    # LAYER 10: SENTIMENT (5%)
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_sentiment(self) -> float:
        fear_greed = self.data.fear_greed

        if fear_greed < 10:
            score = 95
        elif fear_greed < 20:
            score = 85
        elif fear_greed < 35:
            score = 70
        elif fear_greed < 50:
            score = 55
        elif fear_greed < 65:
            score = 45
        elif fear_greed < 80:
            score = 30
        elif fear_greed < 90:
            score = 18
        else:
            score = 8

        if fear_greed < 25:
            zone = "EXTREME_FEAR"
        elif fear_greed < 45:
            zone = "FEAR"
        elif fear_greed < 55:
            zone = "NEUTRAL"
        elif fear_greed < 75:
            zone = "GREED"
        else:
            zone = "EXTREME_GREED"

        self.layer_details['sentiment'] = {
            'fear_greed': fear_greed,
            'zone': zone
        }

        return clamp(score)

    # ═══════════════════════════════════════════════════════════════════════
    # MASTER CALCULATIONS
    # ═══════════════════════════════════════════════════════════════════════

    def calculate_all_layers(self) -> Dict[str, float]:
        self.layer_scores = {
            'onchain': self.calculate_onchain(),
            'institutional': self.calculate_institutional(),
            'flow_velocity': self.calculate_flow_velocity(),
            'momentum': self.calculate_momentum(),
            'derivatives': self.calculate_derivatives(),
            'leverage_fragility': self.calculate_leverage_fragility(),
            'support_integrity': self.calculate_support_integrity(),
            'liquidity': self.calculate_liquidity(),
            'global_m2': self.calculate_global_m2(),
            'sentiment': self.calculate_sentiment()
        }
        return self.layer_scores

    def calculate_master_health(self) -> float:
        if not self.layer_scores:
            self.calculate_all_layers()

        health = sum(
            self.layer_scores[layer] * weight
            for layer, weight in self.LAYER_WEIGHTS.items()
        )
        return round(health, 1)

    # ═══════════════════════════════════════════════════════════════════════
    # ASYMMETRIC RESPONSE SYSTEM
    # ═══════════════════════════════════════════════════════════════════════

    def apply_asymmetric_rules(self, base_allocation: float) -> Tuple[float, List[str]]:
        t = self.thresholds
        adjustments = []
        total_adjustment = 0

        if not self.layer_scores:
            self.calculate_all_layers()

        # CAPITULATION OVERRIDE CHECK
        mvrv = self.data.mvrv_z_score
        fear = self.data.fear_greed
        leverage_flushed = self.layer_scores.get('leverage_fragility', 50) >= 65
        onchain_screaming_buy = self.layer_scores.get('onchain', 50) >= 85

        capitulation_conditions = (
            mvrv < 0.6 and
            fear < 15 and
            leverage_flushed and
            onchain_screaming_buy
        )

        if capitulation_conditions:
            adjustments.append("CAPITULATION OVERRIDE: Extreme value + flushed leverage")
            adjustments.append("Bearish signals are LAGGING (crash already happened)")
            adjustments.append("Switching to ACCUMULATION mode")

            if mvrv < 0.5:
                total_adjustment += 35
                adjustments.append(f"MVRV {mvrv:.2f} = GENERATIONAL VALUE -> +35%")
            else:
                total_adjustment += 20
                adjustments.append(f"MVRV {mvrv:.2f} = DEEP VALUE -> +20%")

            if fear < 10:
                total_adjustment += 15
                adjustments.append(f"Fear {fear:.0f} = EXTREME CAPITULATION -> +15%")
            else:
                total_adjustment += 8
                adjustments.append(f"Fear {fear:.0f} = HIGH FEAR -> +8%")

            final_allocation = clamp(base_allocation + total_adjustment, 0, 100)
            self.asymmetric_adjustments = adjustments
            return final_allocation, adjustments

        # BEARISH TRIGGERS
        flow_vel = self.layer_scores.get('flow_velocity', 50)
        if flow_vel < t.bearish_flow_crisis:
            adjustments.append(f"FLOW CRISIS ({flow_vel:.0f}) -> -30%")
            total_adjustment -= 30
        elif flow_vel < t.bearish_flow_warning:
            adjustments.append(f"FLOW WARNING ({flow_vel:.0f}) -> -15%")
            total_adjustment -= 15

        lev_frag = self.layer_scores.get('leverage_fragility', 50)
        if lev_frag < t.bearish_fragility_cascade:
            adjustments.append(f"CASCADE RISK ({lev_frag:.0f}) -> -25%")
            total_adjustment -= 25
        elif lev_frag < t.bearish_fragility_elevated:
            adjustments.append(f"ELEVATED FRAGILITY ({lev_frag:.0f}) -> -12%")
            total_adjustment -= 12

        support = self.layer_scores.get('support_integrity', 50)
        if support < t.bearish_support_broken:
            adjustments.append(f"SUPPORT BROKEN ({support:.0f}) -> -25%")
            total_adjustment -= 25
        elif support < t.bearish_support_warning:
            adjustments.append(f"SUPPORT WARNING ({support:.0f}) -> -10%")
            total_adjustment -= 10

        bearish_count = sum(1 for v in self.layer_scores.values() if v < 40)
        if bearish_count >= t.bearish_multi_layer_count:
            adjustments.append(f"MULTIPLE BEARISH ({bearish_count} layers) -> -20%")
            total_adjustment -= 20

        inst = self.layer_scores.get('institutional', 50)
        if inst < 25:
            adjustments.append(f"INSTITUTIONAL EXODUS ({inst:.0f}) -> -15%")
            total_adjustment -= 15

        # BULLISH TRIGGERS
        if total_adjustment >= 0:
            bullish_count = sum(1 for v in self.layer_scores.values() if v > 70)
            if bullish_count >= t.bullish_confirm_layers:
                adjustments.append(
                    f"BULLISH CONFIRMATION ({bullish_count} layers) -> +{t.bullish_max_increase:.0f}%"
                )
                total_adjustment += t.bullish_max_increase

        final_allocation = clamp(base_allocation + total_adjustment, 0, 100)

        if total_adjustment <= -50:
            final_allocation = min(final_allocation, t.alloc_emergency_max)
            adjustments.append(f"EMERGENCY DEFENSIVE -> Max {t.alloc_emergency_max:.0f}%")

        self.asymmetric_adjustments = adjustments

        return final_allocation, adjustments

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL GENERATION
    # ═══════════════════════════════════════════════════════════════════════

    def get_base_allocation(self, health: float) -> float:
        t = self.thresholds

        if health >= t.alloc_aggressive_health:
            return 95
        elif health >= 70:
            return 85
        elif health >= 60:
            return 70
        elif health >= t.alloc_moderate_health:
            return 55
        elif health >= t.alloc_cautious_health:
            return 40
        elif health >= t.alloc_defensive_health:
            return 25
        else:
            return 10

    def get_cycle_phase(self, health: float) -> CyclePhase:
        mvrv = self.data.mvrv_z_score
        fear = self.data.fear_greed

        if mvrv < 0.5 and fear < 20:
            return CyclePhase.CAPITULATION
        elif mvrv < 0.75:
            return CyclePhase.DEEP_ACCUMULATION
        elif mvrv < 1.0 and health < 60:
            return CyclePhase.ACCUMULATION
        elif health >= 75 and mvrv < 2.0:
            return CyclePhase.EARLY_BULL
        elif health >= 65 and mvrv < 2.5:
            return CyclePhase.MID_BULL
        elif mvrv >= 2.5:
            return CyclePhase.LATE_BULL
        elif health < 45 and mvrv > 2.0:
            return CyclePhase.DISTRIBUTION
        elif health < 40:
            return CyclePhase.EARLY_BEAR
        else:
            return CyclePhase.BEAR

    def get_signal(self, final_allocation: float, health: float) -> Signal:
        if final_allocation <= 5:
            return Signal.EMERGENCY_SELL
        elif final_allocation <= 15:
            return Signal.STRONG_SELL
        elif final_allocation <= 30:
            return Signal.SELL
        elif final_allocation <= 45:
            return Signal.REDUCE
        elif final_allocation <= 55:
            return Signal.HOLD
        elif final_allocation <= 70:
            return Signal.ACCUMULATE
        elif final_allocation <= 85:
            return Signal.BUY
        elif final_allocation <= 95:
            return Signal.STRONG_BUY
        else:
            return Signal.AGGRESSIVE_BUY

    def get_allocation_breakdown(self, total_alloc: float) -> Dict[str, int]:
        btc_dom = self.data.btc_dominance

        if btc_dom >= 60:
            btc_pct = 75
            eth_pct = 18
            alt_pct = 7
        elif btc_dom >= 55:
            btc_pct = 70
            eth_pct = 20
            alt_pct = 10
        elif btc_dom >= 50:
            btc_pct = 60
            eth_pct = 25
            alt_pct = 15
        else:
            btc_pct = 50
            eth_pct = 30
            alt_pct = 20

        return {
            'total_allocation': int(total_alloc),
            'btc_pct': btc_pct,
            'eth_pct': eth_pct,
            'alt_pct': alt_pct
        }

    # ═══════════════════════════════════════════════════════════════════════
    # FULL ANALYSIS (for dashboard use)
    # ═══════════════════════════════════════════════════════════════════════

    def run_full_analysis(self) -> Dict:
        """Run full analysis and return all results as a dict."""
        self.calculate_all_layers()
        health = self.calculate_master_health()
        base_alloc = self.get_base_allocation(health)
        final_alloc, asymmetric_adj = self.apply_asymmetric_rules(base_alloc)
        phase = self.get_cycle_phase(health)
        signal = self.get_signal(final_alloc, health)
        alloc = self.get_allocation_breakdown(final_alloc)

        return {
            'layer_scores': dict(self.layer_scores),
            'layer_details': {k: dict(v) for k, v in self.layer_details.items()},
            'layer_weights': dict(self.LAYER_WEIGHTS),
            'health': health,
            'base_allocation': base_alloc,
            'final_allocation': final_alloc,
            'asymmetric_adjustments': list(asymmetric_adj),
            'phase': phase.value,
            'signal': signal.value,
            'allocation_breakdown': alloc,
            'warnings': list(self.warnings),
            'market_data': {
                'btc_price': self.data.btc_price,
                'btc_ath': self.data.btc_ath,
                'drawdown_from_ath': round(self.data.drawdown_from_ath, 1),
                'mvrv_z_score': self.data.mvrv_z_score,
                'fear_greed': self.data.fear_greed,
                'weekly_rsi': self.data.weekly_rsi,
                'ma_50': self.data.ma_50,
                'ma_200': self.data.ma_200,
                'ma_365': self.data.ma_365,
                'pct_vs_200ma': round(self.data.pct_vs_200ma, 1),
                'pct_vs_365ma': round(self.data.pct_vs_365ma, 1),
                'roc_30d': round(self.data.roc_30d, 1),
                'etf_flow_1d': self.data.etf_flow_1d,
                'etf_flow_7d': self.data.etf_flow_7d,
                'etf_flow_30d': self.data.etf_flow_30d,
                'etf_flow_90d': self.data.etf_flow_90d,
                'etf_aum_pct_mcap': self.data.etf_aum_pct_mcap,
                'funding_rate': self.data.funding_rate,
                'oi_pct_mcap': self.data.oi_pct_mcap,
                'oi_change_7d': self.data.oi_change_7d,
                'long_short_ratio': self.data.long_short_ratio,
                'liquidations_24h': self.data.liquidations_24h,
                'net_liquidity': round(self.data.net_liquidity, 1),
                'dxy': self.data.dxy,
                'm2_yoy': self.data.m2_yoy,
                'btc_dominance': self.data.btc_dominance,
                'date': self.data.date,
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET DATA SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════

def get_current_market_data() -> MarketDataV72:
    """Return verified market data for February 7, 2026."""
    return MarketDataV72(
        btc_price=68500,
        btc_ath=126000,
        btc_7d_ago=78000,
        btc_30d_ago=95000,
        btc_90d_ago=115000,
        ma_50=85000,
        ma_200=78000,
        ma_365=72000,
        mvrv_z_score=0.52,
        nupl=0.15,
        sopr=0.97,
        supply_in_profit_pct=56,
        etf_flow_1d=-0.2,
        etf_flow_7d=-1.7,
        etf_flow_30d=-3.0,
        etf_flow_90d=-12.0,
        etf_cumulative=54.75,
        etf_aum_pct_mcap=5.2,
        max_single_day_flow_7d=-0.544,
        funding_rate=-0.02,
        funding_rate_7d_avg=-0.01,
        oi_total=25,
        oi_change_7d=-25,
        oi_pct_mcap=1.8,
        long_short_ratio=0.85,
        liquidations_24h=150,
        price_to_liq_cluster_pct=8,
        fear_greed=7,
        weekly_rsi=28,
        fed_bs=6450,
        fed_bs_3m_ago=6520,
        rrp=150,
        tga=800,
        m2_yoy=3.5,
        dxy=97.68,
        days_below_200ma=5,
        days_below_365ma=2,
        recent_support_break=True,
        btc_dominance=58.5,
        date="2026-02-07",
        data_quality_score=85
    )


def backtest_october_2025_ath() -> MarketDataV72:
    """October 2025 ATH scenario - $126K"""
    return MarketDataV72(
        btc_price=126000,
        btc_ath=126000,
        btc_7d_ago=118000,
        btc_30d_ago=100000,
        btc_90d_ago=75000,
        ma_50=115000,
        ma_200=90000,
        ma_365=75000,
        mvrv_z_score=2.8,
        nupl=0.65,
        sopr=1.08,
        etf_flow_1d=0.1,
        etf_flow_7d=0.5,
        etf_flow_30d=3.0,
        etf_flow_90d=15.0,
        etf_cumulative=62.9,
        etf_aum_pct_mcap=5.5,
        max_single_day_flow_7d=0.2,
        funding_rate=0.08,
        funding_rate_7d_avg=0.05,
        oi_total=45,
        oi_change_7d=15,
        oi_pct_mcap=5.5,
        long_short_ratio=1.6,
        liquidations_24h=50,
        price_to_liq_cluster_pct=8,
        fear_greed=75,
        weekly_rsi=72,
        fed_bs=6500,
        fed_bs_3m_ago=6550,
        rrp=200,
        tga=750,
        m2_yoy=4.0,
        dxy=102,
        days_below_200ma=0,
        days_below_365ma=0,
        recent_support_break=False,
        btc_dominance=55,
        date="2025-10-15"
    )


def backtest_january_2026_breakdown() -> MarketDataV72:
    """January 29, 2026 - $85K breakdown"""
    return MarketDataV72(
        btc_price=85000,
        btc_ath=126000,
        btc_7d_ago=95000,
        btc_30d_ago=105000,
        btc_90d_ago=126000,
        ma_50=95000,
        ma_200=88000,
        ma_365=87000,
        mvrv_z_score=1.2,
        nupl=0.35,
        sopr=0.98,
        etf_flow_1d=-0.817,
        etf_flow_7d=-1.7,
        etf_flow_30d=-3.0,
        etf_flow_90d=-12.0,
        etf_cumulative=56.0,
        etf_aum_pct_mcap=5.0,
        max_single_day_flow_7d=-0.817,
        funding_rate=0.02,
        funding_rate_7d_avg=0.04,
        oi_total=35,
        oi_change_7d=-10,
        oi_pct_mcap=4.5,
        long_short_ratio=1.3,
        liquidations_24h=400,
        price_to_liq_cluster_pct=2,
        fear_greed=22,
        weekly_rsi=38,
        fed_bs=6450,
        fed_bs_3m_ago=6520,
        rrp=180,
        tga=800,
        m2_yoy=3.5,
        dxy=99,
        days_below_200ma=0,
        days_below_365ma=0,
        recent_support_break=True,
        btc_dominance=57,
        date="2026-01-29"
    )


if __name__ == "__main__":
    try:
        from fetch_live_data import fetch_live_market_data
        data = fetch_live_market_data()
        print("(Using live data)")
    except (ImportError, Exception):
        data = get_current_market_data()
        print("(Using static snapshot)")

    thresholds = CalibratedThresholds()
    model = BTCModelV72(data, thresholds)
    result = model.run_full_analysis()

    print(f"Health: {result['health']}")
    print(f"Signal: {result['signal']}")
    print(f"Allocation: {result['final_allocation']}%")
    print(f"Phase: {result['phase']}")
