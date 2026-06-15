from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from trader.core.events import Market, Side


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class CostModel(Protocol):
    def commission(
        self,
        price: float,
        quantity: int,
        market: Optional[Market] = None,
        side: Optional[Side] = None,
    ) -> float: ...


# ---------------------------------------------------------------------------
# BpsCostModel — flat basis-point model (BACKWARD-COMPATIBLE)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BpsCostModel:
    """명목가 * bps. market/side are accepted but ignored (flat rate)."""
    bps: float = 0.0

    def commission(
        self,
        price: float,
        quantity: int,
        market: Optional[Market] = None,
        side: Optional[Side] = None,
    ) -> float:
        return price * quantity * (self.bps / 10_000.0)


# ---------------------------------------------------------------------------
# MarketCostConfig — per-market rate configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MarketCostConfig:
    """Per-market transaction cost parameters.

    Rates:
        commission_bps   : broker commission in bps (both sides)
        buy_tax_bps      : government buy-side tax in bps (rare; default 0)
        sell_tax_bps     : government sell-side tax in bps
                           KOSPI: 20.0 bps (0.20%) — NOTE: KR securities transaction
                           tax is being reduced in stages; treat as APPROXIMATE/verify.
        sec_sell_bps     : US SEC Section 31 fee on sells (bps of notional).
                           NASDAQ/KIS 2026: ~0.206 bps — APPROXIMATE, changes annually.
        finra_taf_per_share : FINRA Trading Activity Fee per share (USD), sell only.
                           Default: $0.000195/share.
        finra_taf_cap    : Cap per trade for FINRA TAF (USD). None = no cap.
                           Default: $9.79.
        fx_bps_per_conversion : FX spread cost in bps per currency conversion.
                           KRW-auto-FX via KIS: ~40 bps is an ESTIMATE — default 0,
                           configurable.
    """
    commission_bps: float = 0.0
    buy_tax_bps: float = 0.0
    sell_tax_bps: float = 0.0
    sec_sell_bps: float = 0.0
    finra_taf_per_share: float = 0.0
    finra_taf_cap: Optional[float] = None
    fx_bps_per_conversion: float = 0.0


# ---------------------------------------------------------------------------
# DEFAULT_COSTS — 2026 rates (cited; approximate items flagged)
# ---------------------------------------------------------------------------

DEFAULT_COSTS: dict[Market, MarketCostConfig] = {
    # KOSPI via KIS domestic account
    # commission: ~1.40527 bps (both sides) — KIS retail schedule 2026
    # sell tax: 0.20% = 20.0 bps — APPROXIMATE; KR securities transaction tax
    #   is being phased down; verify current rate before production use.
    Market.KOSPI: MarketCostConfig(
        commission_bps=1.40527,
        sell_tax_bps=20.0,       # APPROX — verify KR STT phase-down schedule
    ),

    # NASDAQ via KIS overseas account (USD)
    # commission: 25.0 bps (both sides) — KIS US stock commission schedule 2026
    # SEC fee: 0.206 bps on sells — APPROXIMATE; Section 31 rate changes annually
    # FINRA TAF: $0.000195/share on sells, capped $9.79/trade — 2026 schedule
    # fx_bps_per_conversion: KRW↔USD auto-FX spread ~40 bps is an ESTIMATE;
    #   default 0 so callers opt-in explicitly.
    Market.NASDAQ: MarketCostConfig(
        commission_bps=25.0,
        sec_sell_bps=0.206,      # APPROX — SEC Section 31, changes annually
        finra_taf_per_share=0.000195,
        finra_taf_cap=9.79,
        fx_bps_per_conversion=0.0,   # set to ~40 to model KRW-auto-FX spread
    ),
}


# ---------------------------------------------------------------------------
# MarketCostModel — market-specific, side-aware cost model
# ---------------------------------------------------------------------------

class MarketCostModel:
    """Market-specific, side-aware transaction cost model.

    Uses DEFAULT_COSTS by default; pass a custom configs dict to override.
    If market is not in configs, raises KeyError with a clear message.
    """

    def __init__(self, configs: dict[Market, MarketCostConfig] | None = None) -> None:
        self._configs: dict[Market, MarketCostConfig] = configs if configs is not None else DEFAULT_COSTS

    def commission(
        self,
        price: float,
        quantity: int,
        market: Optional[Market] = None,
        side: Optional[Side] = None,
    ) -> float:
        if market not in self._configs:
            raise KeyError(
                f"MarketCostModel: no config for market {market!r}. "
                f"Known markets: {list(self._configs.keys())}"
            )

        cfg = self._configs[market]
        notional = price * quantity

        # Basis-point component: commission + applicable taxes/fees
        bps = cfg.commission_bps
        if side == Side.SELL:
            bps += cfg.sell_tax_bps + cfg.sec_sell_bps
        else:
            bps += cfg.buy_tax_bps

        cost = notional * bps / 10_000.0

        # FX spread (if configured)
        cost += notional * cfg.fx_bps_per_conversion / 10_000.0

        # FINRA TAF: per-share on sells, capped per trade
        if side == Side.SELL and cfg.finra_taf_per_share > 0:
            taf = cfg.finra_taf_per_share * quantity
            if cfg.finra_taf_cap is not None:
                taf = min(taf, cfg.finra_taf_cap)
            cost += taf

        return cost
