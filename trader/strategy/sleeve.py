# trader/strategy/sleeve.py
"""Two-sleeve strategy architecture — independent sub-portfolios per regime.

Each StrategySleeve owns:
  - a FusionEngine configured with regime-compatible signal sources only
  - a dedicated Portfolio seeded with (capital_fraction × initial_equity)
  - a capital_fraction label (informational; capital is seeded at construction time)

MultiSleeveEngine coordinates N sleeves over a shared SimulatedExecutionHandler:
  - Per bar: execution.on_bar → fills → route each fill to the originating sleeve
    (via order_id→sleeve map) → sleeve.portfolio.mark → sleeve.on_bar → submit orders
  - Aggregate equity = Σ sleeve.portfolio.equity_krw()

Design notes
────────────
v1: NO cross-sleeve netting.  Each sleeve maintains its own independent book.
If both sleeves hold the same symbol they will hold it twice (two separate
position records in two separate Portfolio objects).  Cross-sleeve netting
(collapsing redundant positions into one broker leg) is a future cost
optimisation; it requires a netting layer that knows both books — out of scope
for this iteration.

The order_id→sleeve mapping is the routing key that keeps fills assigned to
the sleeve that generated the order.  Fills from orders not found in the map
(e.g. externally injected) are silently dropped.
"""
from __future__ import annotations

from typing import Sequence

from trader.core.events import BarEvent, FillEvent, OrderEvent
from trader.strategy.fusion_engine import FusionEngine


class StrategySleeve:
    """One strategy regime: a FusionEngine + its own Portfolio + a name.

    The Portfolio must already be seeded (cash set to capital_fraction × initial
    equity) before this object is created; StrategySleeve does not re-scale.

    Args:
        name: Human-readable label (e.g. "trend", "reversion").
        engine: A FusionEngine whose .portfolio attribute is the sleeve's book.
        capital_fraction: Informational — the fraction of total capital this
            sleeve was seeded with.  NOT enforced at runtime; it is a label
            for reporting and documentation.
    """

    def __init__(self, name: str, engine: FusionEngine, capital_fraction: float) -> None:
        self.name = name
        self.engine = engine
        self.capital_fraction = capital_fraction

    @property
    def portfolio(self):
        """Delegate to the engine's portfolio (single source of truth)."""
        return self.engine.portfolio

    def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
        """Delegate bar processing to the FusionEngine; returns list[OrderEvent]."""
        return self.engine.on_bar(bar)

    def apply_fill(self, fill: FillEvent) -> None:
        """Route a fill into this sleeve's portfolio (via FusionEngine.on_fill)."""
        self.engine.on_fill(fill)


class MultiSleeveEngine:
    """Coordinate multiple StrategySleeve instances over a shared execution handler.

    Usage (event loop)::

        engine = MultiSleeveEngine(sleeves, execution)
        for bar in sorted_bars:
            engine.on_bar(bar)   # drives fills → routing → mark → signals → submit

    Each sleeve trades its own independent book.  There is NO cross-sleeve
    position netting in v1 — document this clearly (see module docstring).

    Args:
        sleeves: Ordered list of StrategySleeve objects.
        execution: A SimulatedExecutionHandler (or compatible execution handler
            with submit_order / on_bar(bar) → list[FillEvent] interface).
    """

    def __init__(self, sleeves: Sequence[StrategySleeve], execution) -> None:
        self.sleeves = list(sleeves)
        self.execution = execution
        # order_id (UUID) → StrategySleeve: routing table populated when orders
        # are submitted, consumed when fills arrive.
        self._order_sleeve: dict = {}

    def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
        """Full per-bar event loop for all sleeves.

        Steps:
          1. execution.on_bar(bar) → fills
          2. route each fill to the originating sleeve; update that sleeve's portfolio
          3. mark each sleeve's portfolio at close
          4. each sleeve generates new orders
          5. submit all orders via execution; register routing entries

        Returns:
            All OrderEvents emitted this bar (across all sleeves).
        """
        # ── Phase 1: fill pending orders at bar open ─────────────────────────
        fills: list[FillEvent] = self.execution.on_bar(bar)
        for fill in fills:
            sleeve = self._order_sleeve.pop(fill.order_id, None)
            if sleeve is not None:
                sleeve.apply_fill(fill)

        # ── Phase 2: mark-to-market at close (each sleeve's own portfolio) ───
        for sleeve in self.sleeves:
            sleeve.portfolio.mark(bar)

        # ── Phase 3: each sleeve decides orders based on close signal ─────────
        all_orders: list[OrderEvent] = []
        for sleeve in self.sleeves:
            orders = sleeve.on_bar(bar)
            for order in orders:
                self._order_sleeve[order.order_id] = sleeve
                self.execution.submit_order(order)
                all_orders.append(order)

        return all_orders

    def equity_krw(self) -> float:
        """Aggregate equity across all sleeves (sum of each sleeve's portfolio)."""
        return sum(s.portfolio.equity_krw() for s in self.sleeves)
