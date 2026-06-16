from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from trader.core.events import BarEvent, Market, Side


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
    # sell tax: 0.20% = 20.0 bps — CONFIRMED 2026
    #   증권거래세 0.05% + 농어촌특별세 0.15% = 0.20% total; source MOFE 2026
    Market.KOSPI: MarketCostConfig(
        commission_bps=1.40527,
        sell_tax_bps=20.0,       # CONFIRMED 2026 (STT 0.05% + 농특세 0.15%); source MOFE 2026
    ),

    # NASDAQ via KIS overseas account (USD)
    # commission: 25.0 bps (both sides) — KIS US stock commission schedule 2026
    # SEC fee: 0.206 bps on sells — APPROXIMATE; Section 31 rate changes annually
    # FINRA TAF: $0.000195/share on sells, capped $9.79/trade — 2026 schedule
    # fx_bps_per_conversion: KRW-funded account auto-converts KRW→USD per fill
    #   via KIS auto-FX; honest cost includes this spread. Est. ~10 bps retail
    #   (range 5–40, account-specific). APPROX — verify with your KIS account terms.
    Market.NASDAQ: MarketCostConfig(
        commission_bps=25.0,
        sec_sell_bps=0.206,      # APPROX — SEC Section 31, changes annually
        finra_taf_per_share=0.000195,
        finra_taf_cap=9.79,
        fx_bps_per_conversion=10.0,  # APPROX — retail KIS auto-FX spread est. ~10bps (range 5-40, account-specific)
    ),

    # KOSDAQ: Market enum only has NASDAQ/KOSPI (adding KOSDAQ is out of scope).
    # For reference: KOSDAQ 2026 STT = 0.20% (증권거래세 0.20%, no 농특세) = 20.0 bps
    # sell_tax_bps — same total as KOSPI but different tax composition.
    # To add KOSDAQ support, extend the Market enum and add an entry here.
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


# ---------------------------------------------------------------------------
# DEFAULT_SLIPPAGE_BPS — conservative retail half-spread + market-impact est.
# APPROX: based on typical retail KIS order-book spreads + intraday impact.
#   KOSPI  8 bps : large-cap average quoted half-spread ~3–5 bps + ~2–3 bps
#                  impact for retail order sizes; 8 bps is deliberately
#                  conservative (small/mid caps will be wider). SOURCE: APPROX.
#   NASDAQ 3 bps : US large-cap half-spread ~1–2 bps at market open + small
#                  impact; 3 bps is conservative for retail sizes.
#                  SOURCE: APPROX — verify against your actual execution data.
# These are ESTIMATED FLOORS, not calibrated to any live execution data.
# Real results can be better or worse; treat as pessimistic baseline.
# ---------------------------------------------------------------------------

DEFAULT_SLIPPAGE_BPS: dict[Market, float] = {
    Market.KOSPI:  8.0,   # APPROX — conservative retail half-spread + impact
    Market.NASDAQ: 3.0,   # APPROX — conservative retail half-spread + impact
}


@dataclass(frozen=True)
class SlippageModel:
    """Conservative, OPT-IN slippage model.

    Models two adverse-fill components:
      1. spread_bps_by_market: per-market half-spread + market-impact estimate.
         Applied on every fill (cost of crossing the spread + small impact).
      2. open_close_extra_bps: additional cost at open or close bars, where
         order-book is thinner and fills are worse (default 5 bps).

    Design choices:
      - enabled=False by default → zero cost, parity tests are unaffected.
      - Cost is ALWAYS POSITIVE regardless of side (buying costs the ask,
        selling costs the bid — both are adverse to the trader).
      - Modelled as an addition to FillEvent.commission (not as fill-price
        adjustment) so portfolio accounting captures the cost without
        requiring a mutable FillEvent.  The fill price remains bar.open for
        auditability; the slippage is visible as a separate commission add-on.
      - Fills at bar.open → at_open_or_close=True should be passed by the
        execution handler (open is structurally thinner, especially KR).

    Args:
        spread_bps_by_market: Per-market half-spread + impact in bps.
                              Defaults to DEFAULT_SLIPPAGE_BPS if not supplied.
        open_close_extra_bps: Extra adverse-fill cost at open/close in bps
                              (default 5.0).  APPROX.
        enabled:              Master switch.  False (default) → always 0.0.
    """

    spread_bps_by_market: dict = field(default_factory=lambda: dict(DEFAULT_SLIPPAGE_BPS))
    open_close_extra_bps: float = 5.0   # APPROX
    enabled: bool = False

    def slippage(
        self,
        price: float,
        quantity: int,
        market: Market,
        side: Side,
        *,
        at_open_or_close: bool = True,
    ) -> float:
        """Compute adverse-fill slippage cost in the fill currency.

        Args:
            price:             Fill price (bar.open).
            quantity:          Number of shares/units.
            market:            Market enum (KOSPI / NASDAQ).
            side:              Side.BUY or Side.SELL (cost is positive for both).
            at_open_or_close:  True if this fill is at open or close bar
                               (adds open_close_extra_bps).

        Returns:
            Non-negative float cost in the fill currency.
            0.0 if not enabled or market not in spread_bps_by_market.
        """
        if not self.enabled:
            return 0.0

        spread_bps = self.spread_bps_by_market.get(market, 0.0)
        extra_bps = self.open_close_extra_bps if at_open_or_close else 0.0
        total_bps = spread_bps + extra_bps

        notional = price * quantity
        return notional * total_bps / 10_000.0


# ---------------------------------------------------------------------------
# tradable — pure liquidity/sanity filter for research/eval use
# ---------------------------------------------------------------------------

def tradable(bar: BarEvent, *, min_price: float = 1.0, min_volume: int = 0) -> bool:
    """Return True if the bar passes minimum liquidity/sanity thresholds.

    Use this in research and evaluation loops to skip names that are too
    illiquid or penny-stock-priced to trade at realistic costs.  NOT wired
    into the live engine — purely a helper for offline filtering.

    Args:
        bar:        BarEvent to test.
        min_price:  Minimum close price (default 1.0 — rejects penny stocks).
        min_volume: Minimum bar volume (default 0 — rejects zero-volume bars).

    Returns:
        True if bar.close >= min_price AND bar.volume >= min_volume.
    """
    return bar.close >= min_price and bar.volume >= min_volume
