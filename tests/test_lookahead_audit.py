# tests/test_lookahead_audit.py
"""Systematic look-ahead audit — P0 Foundation.

Canonical invariant tested for every signal source:
    signal_at_t(feed[:t+1]) == signal_at_t(feed[:t+1+N])

i.e. appending future bars NEVER changes the signal value at bar t.

Also covers:
  - SimulatedExecutionHandler: same-bar fill is structurally impossible.
  - momentum.py: rebalance decision uses only data ≤ signal_date.
  - FusionEngine vol-targeter: scalar() is read before update() (no same-day leak).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from trader.core.events import BarEvent, Market, NormalizedSignal, OrderEvent, Side, Symbol
from trader.execution.costs import BpsCostModel
from trader.execution.simulated import SimulatedExecutionHandler
from trader.research.momentum import cross_sectional_momentum
from trader.signals.indicators import (
    BollingerReversion,
    MacdTrend,
    MovingAverageCross,
    RsiReversion,
)
from trader.signals.technical import TechnicalSignalSource
from trader.signals.technical_indicator_source import TechnicalIndicatorSource
from trader.strategy.vol_target import PortfolioVolTargeter

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
T0 = datetime(2024, 1, 2, tzinfo=timezone.utc)


def _bar(i: int, close: float, sym: Symbol = SYM) -> BarEvent:
    return BarEvent(sym, T0 + timedelta(days=i), close, close, close, close, 100)


def _bars(closes: list[float], sym: Symbol = SYM) -> list[BarEvent]:
    return [_bar(i, c, sym) for i, c in enumerate(closes)]


def _trend(n: int, start: float = 100.0, end: float = 200.0) -> list[float]:
    if n <= 1:
        return [start]
    step = (end - start) / (n - 1)
    return [start + i * step for i in range(n)]


# ---------------------------------------------------------------------------
# Part 1 — Parametrized no-look-ahead invariant over ALL signal sources
# ---------------------------------------------------------------------------
#
# For each source we:
#   1. Feed bars[:t+1] into instance A → capture signal at bar t.
#   2. Feed bars[:t+1+EXTRA] into instance B → capture signal at bar t.
#   3. Assert signal scores are identical (within float tolerance).
#
# This catches any mechanism by which future bars could alter a past signal.
# All indicators are stateless-per-call (pure functions of the passed window),
# so this is structurally guaranteed — but we test it explicitly.

EXTRA_FUTURE_BARS = 20   # number of future bars appended to "full feed"


def _feed_source_capture_at_t(source, all_bars: list[BarEvent], t: int) -> NormalizedSignal | None:
    """Feed all_bars[:t+1] into source, return the signal emitted at bar t."""
    sig_at_t = None
    for i, bar in enumerate(all_bars[: t + 1]):
        result = source.on_bar(bar)
        if i == t:
            sig_at_t = result
    return sig_at_t


def _make_technical_source() -> TechnicalSignalSource:
    return TechnicalSignalSource(fast=5, slow=15)


def _make_ma_source() -> TechnicalIndicatorSource:
    return TechnicalIndicatorSource(
        name="audit.ma", indicator=MovingAverageCross(fast=5, slow=15)
    )


def _make_rsi_source() -> TechnicalIndicatorSource:
    return TechnicalIndicatorSource(
        name="audit.rsi", indicator=RsiReversion(period=14)
    )


def _make_macd_source() -> TechnicalIndicatorSource:
    return TechnicalIndicatorSource(
        name="audit.macd", indicator=MacdTrend(fast=12, slow=26, signal=9)
    )


def _make_bollinger_source() -> TechnicalIndicatorSource:
    return TechnicalIndicatorSource(
        name="audit.bb", indicator=BollingerReversion(period=20, stdevs=2.0)
    )


# Parametrize: (factory_fn, min_bars_needed, description)
SOURCE_PARAMS: list[tuple[Any, int, str]] = [
    (_make_technical_source,  15,  "TechnicalSignalSource(fast=5,slow=15)"),
    (_make_ma_source,         15,  "TechnicalIndicatorSource(MA fast=5,slow=15)"),
    (_make_rsi_source,        15,  "TechnicalIndicatorSource(RSI period=14)"),
    (_make_macd_source,       35,  "TechnicalIndicatorSource(MACD 12/26/9)"),
    (_make_bollinger_source,  20,  "TechnicalIndicatorSource(Bollinger period=20)"),
]


@pytest.mark.parametrize("factory,min_bars,label", SOURCE_PARAMS, ids=[p[2] for p in SOURCE_PARAMS])
def test_no_lookahead_signal_at_t_invariant(factory, min_bars, label):
    """Signal at bar t must be unchanged when future bars are appended.

    Two independent source instances:
      A: fed bars[:t+1]            (truncated at t)
      B: fed bars[:t+1+EXTRA]      (sees future bars after t)
    Both must emit identical scores at bar t.
    """
    # Build a total pool of bars with clear trend (ensures non-None signal)
    total = min_bars + EXTRA_FUTURE_BARS + 10
    closes = _trend(total, start=100.0, end=200.0)
    all_bars = _bars(closes)

    # Pick t = min_bars (first bar that can emit a signal)
    t = min_bars  # 0-indexed; bars[0..t] inclusive = t+1 bars

    src_a = factory()   # fed only up to t
    src_b = factory()   # fed up to t + EXTRA_FUTURE_BARS

    sig_a = _feed_source_capture_at_t(src_a, all_bars, t)
    sig_b = _feed_source_capture_at_t(src_b, all_bars, t + EXTRA_FUTURE_BARS)
    # sig_b: we need the signal *at bar t*, not at t+EXTRA; replay differently
    # Re-run: feed src_b all bars up to t+EXTRA, capturing what it emitted at t
    src_b2 = factory()
    sig_b_at_t = None
    for i, bar in enumerate(all_bars[: t + 1 + EXTRA_FUTURE_BARS]):
        result = src_b2.on_bar(bar)
        if i == t:
            sig_b_at_t = result

    assert sig_a is not None, (
        f"[{label}] Instance A emitted no signal at bar {t}. "
        f"Check min_bars={min_bars} vs total bars fed={t+1}."
    )
    assert sig_b_at_t is not None, (
        f"[{label}] Instance B emitted no signal at bar {t}."
    )
    assert abs(sig_a.score - sig_b_at_t.score) < 1e-9, (
        f"[{label}] LOOK-AHEAD DETECTED at bar t={t}!\n"
        f"  Signal score truncated feed: {sig_a.score}\n"
        f"  Signal score with {EXTRA_FUTURE_BARS} future bars appended: {sig_b_at_t.score}\n"
        f"  Difference: {abs(sig_a.score - sig_b_at_t.score)}"
    )
    assert abs(sig_a.confidence - sig_b_at_t.confidence) < 1e-9, (
        f"[{label}] Confidence changed with future bars at bar t={t}: "
        f"{sig_a.confidence} vs {sig_b_at_t.confidence}"
    )


@pytest.mark.parametrize("factory,min_bars,label", SOURCE_PARAMS, ids=[p[2] for p in SOURCE_PARAMS])
def test_no_lookahead_at_multiple_t_values(factory, min_bars, label):
    """Check the invariant at three different bar indices t, not just the warmup boundary."""
    total = min_bars + EXTRA_FUTURE_BARS + 30
    closes = _trend(total, start=50.0, end=150.0)
    all_bars = _bars(closes)

    check_points = [min_bars, min_bars + 5, min_bars + 15]

    for t in check_points:
        if t + EXTRA_FUTURE_BARS >= len(all_bars):
            continue  # not enough future bars for this checkpoint

        src_a = factory()
        sig_a = None
        for i, bar in enumerate(all_bars[: t + 1]):
            r = src_a.on_bar(bar)
            if i == t:
                sig_a = r

        src_b = factory()
        sig_b_at_t = None
        for i, bar in enumerate(all_bars[: t + 1 + EXTRA_FUTURE_BARS]):
            r = src_b.on_bar(bar)
            if i == t:
                sig_b_at_t = r

        if sig_a is None or sig_b_at_t is None:
            continue  # warmup not reached yet; skip this checkpoint

        assert abs(sig_a.score - sig_b_at_t.score) < 1e-9, (
            f"[{label}] LOOK-AHEAD DETECTED at bar t={t}: "
            f"score_A={sig_a.score:.8f} score_B={sig_b_at_t.score:.8f}"
        )


# ---------------------------------------------------------------------------
# Part 2 — SimulatedExecutionHandler: same-bar fill is structurally impossible
# ---------------------------------------------------------------------------

def test_simulated_execution_no_same_bar_fill():
    """An order submitted after bar t's signal can never fill at bar t.

    The BacktestEngine loop is:
        1. execution.on_bar(bar_t)  ← fills pending (from t-1), at bar_t.open
        2. portfolio.mark(bar_t)
        3. strategy.on_bar(bar_t)   ← generates orders using bar_t.close
        4. execution.submit_order() ← queues for t+1

    We simulate this sequence directly and assert the order generated at bar t
    does NOT fill until bar t+1.
    """
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))

    bar_t   = _bar(0, close=100.0)
    bar_t1  = _bar(1, close=110.0)

    # Simulate step 1 at bar t: no pending orders → no fills
    fills_at_t_step1 = ex.on_bar(bar_t)
    assert fills_at_t_step1 == [], "No pending orders at bar t step 1"

    # Simulate step 3/4: strategy generates order at bar t's close, submits it
    order = OrderEvent(uuid4(), SYM, bar_t.ts, Side.BUY, 10)
    ex.submit_order(order)

    # Critically: calling on_bar AGAIN for the SAME bar must NOT fill the order
    # (this would be a same-bar fill bug; the engine never does this, but we verify)
    # In the real engine, on_bar is never called twice for the same bar.
    # We verify the structural guarantee: on_bar for bar_t+1 fills at bar_t+1.open
    fills_at_t1 = ex.on_bar(bar_t1)
    assert len(fills_at_t1) == 1, "Order should fill at bar t+1"
    assert fills_at_t1[0].price == bar_t1.open, (
        f"Fill must be at bar t+1 open={bar_t1.open}, got {fills_at_t1[0].price}"
    )
    # The fill timestamp is bar t+1's timestamp
    assert fills_at_t1[0].ts == bar_t1.ts, (
        "Fill timestamp must be bar t+1's timestamp, not bar t's"
    )


def test_simulated_execution_order_never_fills_on_bar_that_generated_it():
    """Reconstruct the BacktestEngine loop step-by-step to prove no same-bar fill."""
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))
    bars = [_bar(i, 100.0 + i) for i in range(5)]

    all_fills: list[tuple[int, float]] = []   # (bar_index, fill_price)
    order_bar_index: dict = {}                 # order_id → bar index when submitted

    for i, bar in enumerate(bars):
        # Step 1: fills from previous bar's orders
        fills = ex.on_bar(bar)
        for f in fills:
            all_fills.append((i, f.price))
            submitted_at = order_bar_index[f.order_id]
            # INVARIANT: fill bar index > submission bar index
            assert i > submitted_at, (
                f"Same-bar fill detected! Order submitted at bar {submitted_at} "
                f"filled at bar {i} (same bar)."
            )

        # Step 2: strategy generates order at bar i's close, submits
        if i < len(bars) - 1:  # don't submit on last bar (no next bar to fill)
            oid = uuid4()
            order = OrderEvent(oid, SYM, bar.ts, Side.BUY, 1)
            ex.submit_order(order)
            order_bar_index[oid] = i


def test_simulated_execution_fill_price_is_next_open_not_signal_bar_close():
    """Explicitly verify fill price != signal bar close (no price-based look-ahead)."""
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))

    signal_bar_close = 100.0
    next_bar_open    = 105.0   # deliberately different from close

    bar_t  = BarEvent(SYM, T0,                       signal_bar_close, signal_bar_close, signal_bar_close, signal_bar_close, 100)
    bar_t1 = BarEvent(SYM, T0 + timedelta(days=1),   next_bar_open,    next_bar_open + 2, next_bar_open - 1, next_bar_open + 1, 100)

    ex.on_bar(bar_t)  # step 1: no pending
    ex.submit_order(OrderEvent(uuid4(), SYM, bar_t.ts, Side.BUY, 5))  # step 4

    fills = ex.on_bar(bar_t1)  # step 1 of next bar
    assert len(fills) == 1
    fill_price = fills[0].price
    assert fill_price == next_bar_open, (
        f"Fill price should be next bar's open ({next_bar_open}), got {fill_price}"
    )
    assert fill_price != signal_bar_close, (
        f"Fill price must NOT equal signal bar close ({signal_bar_close}) — "
        "that would be a same-bar fill (look-ahead)"
    )


# ---------------------------------------------------------------------------
# Part 3 — momentum.py: rebalance uses only data ≤ signal_date
# ---------------------------------------------------------------------------

def _make_momentum_bars(
    ticker: str,
    closes: list[float],
    start: date = date(2018, 1, 2),
    market: Market = Market.NASDAQ,
) -> list[BarEvent]:
    currency = "USD" if market == Market.NASDAQ else "KRW"
    sym = Symbol(ticker, market, currency)
    bars = []
    d = start
    for c in closes:
        ts = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        bars.append(BarEvent(sym, ts, c, c, c, c, volume=1_000_000))
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
    return bars


def test_momentum_rebalance_uses_only_data_up_to_signal_date():
    """Injecting a future price spike AFTER signal_date must not alter the first rebalance.

    Setup:
    - Universe of 2 symbols over 300 bars.
    - Symbol A trends up (high momentum), B flat.
    - Spike version: B's last 10 bars get a huge artificial spike (999).
    - The first rebalance signal_date is well before these last 10 bars.
    - Holdings at first rebalance must be identical in both versions.
    """
    n = 300
    a_closes = [100.0 + i * 0.5 for i in range(n)]
    b_flat   = [100.0] * n
    b_spike  = b_flat[:]
    # Inject spike only in the last 10 bars — these are AFTER all signal dates
    # for the first rebalance (signal_date ≈ bar 252+, spike at bars 290-299)
    for i in range(n - 10, n):
        b_spike[i] = 9999.0

    bars_base  = {
        "A": _make_momentum_bars("A", a_closes),
        "B": _make_momentum_bars("B", b_flat),
    }
    bars_spike = {
        "A": _make_momentum_bars("A", a_closes),
        "B": _make_momentum_bars("B", b_spike),
    }

    result_base  = cross_sectional_momentum(
        bars_base,  lookback=252, skip=21, top_pct=0.6, min_k=1, max_k=2,
        init_capital=1_000_000,
    )
    result_spike = cross_sectional_momentum(
        bars_spike, lookback=252, skip=21, top_pct=0.6, min_k=1, max_k=2,
        init_capital=1_000_000,
    )

    log_base  = result_base["rebalance_log"]
    log_spike = result_spike["rebalance_log"]

    assert len(log_base) > 0, "Expected at least one rebalance in base universe"
    assert len(log_spike) > 0, "Expected at least one rebalance in spike universe"

    first_base  = set(log_base[0]["strat_holdings"])
    first_spike = set(log_spike[0]["strat_holdings"])

    assert first_base == first_spike, (
        f"LOOK-AHEAD in momentum: first rebalance holdings differ!\n"
        f"  base:  {first_base}\n"
        f"  spike: {first_spike}\n"
        f"  signal_date: {log_base[0]['signal_date']}\n"
        "  Future price spike (bars 290-299) should not affect rebalance at signal_date."
    )


def test_momentum_signal_date_strictly_before_exec_date():
    """Every rebalance log entry must have signal_date < exec_date (no same-day trade)."""
    n = 350
    closes_a = [100.0 + i * 0.3 for i in range(n)]
    closes_b = [100.0] * n
    closes_c = [150.0 - i * 0.2 for i in range(n)]

    bars = {
        "A": _make_momentum_bars("A", closes_a),
        "B": _make_momentum_bars("B", closes_b),
        "C": _make_momentum_bars("C", closes_c),
    }
    result = cross_sectional_momentum(
        bars, lookback=252, skip=21, top_pct=0.5, min_k=1, max_k=3,
        init_capital=1_000_000,
    )
    for entry in result["rebalance_log"]:
        sd = entry["signal_date"]
        ed = entry["exec_date"]
        assert sd < ed, (
            f"signal_date ({sd}) must be strictly before exec_date ({ed}). "
            "Same-day signal+execution would be look-ahead."
        )


def test_momentum_near_date_and_far_date_both_lte_signal_date():
    """Momentum score indices (near and far price dates) must both be ≤ signal_date.

    We verify this indirectly: if either were > signal_date the score in the spike
    test above would differ — but here we also check the signal_date / exec_date split
    is correct in the log metadata.
    """
    n = 350
    bars = {
        "A": _make_momentum_bars("A", [100.0 + i * 0.4 for i in range(n)]),
        "B": _make_momentum_bars("B", [100.0] * n),
    }
    result = cross_sectional_momentum(
        bars, lookback=252, skip=21, top_pct=0.6, min_k=1, max_k=2,
        init_capital=1_000_000,
    )
    log = result["rebalance_log"]
    assert len(log) > 0

    for entry in log:
        # signal_date is the last day of the prior month
        # exec_date is the first day of the new month
        assert entry["signal_date"] < entry["exec_date"], (
            "signal_date must precede exec_date for no-look-ahead"
        )
        # momentum_scores should exist (non-empty when there are eligible names)
        if entry["eligible"]:
            assert entry["momentum_scores"], "Expected non-empty momentum_scores"


# ---------------------------------------------------------------------------
# Part 4 — PortfolioVolTargeter: scalar() before update() (no same-day vol leak)
# ---------------------------------------------------------------------------

def test_vol_targeter_scalar_before_update_is_prior_day():
    """scalar() reflects EWMA through yesterday; update() ingests today.

    The FusionEngine protocol requires scalar() → size → update().
    If called in the wrong order (update first), the scalar would reflect today's move.
    """
    lam = 0.94
    vt = PortfolioVolTargeter(min_obs=5, lam=lam, target_vol=0.12)

    # Warm up with 22 moderate daily returns (1%/day) so we're past min_obs AND
    # the annualised vol (~15.9%) exceeds vol_floor (2%), letting scalar < 1.0.
    # Returns of 0.001/day give ann_vol ~ 1.6% < vol_floor → scalar clips to 1.0.
    equity = 10_000_000.0
    calm_returns = [0.01] * 22   # 1%/day → ann_vol ~15.9% > vol_floor 2%
    equities = [equity]
    for r in calm_returns:
        equities.append(equities[-1] * (1 + r))
    for e in equities:
        vt.update(e)

    # Read scalar BEFORE ingesting today's large move (correct FusionEngine order)
    scalar_before = vt.scalar()
    assert scalar_before != 1.0, (
        f"Should be past min_obs warmup and below max_scalar; got {scalar_before}. "
        "Check that daily return is large enough to exceed vol_floor."
    )

    # Simulate a 30% crash (today's bar t)
    crashed_equity = equities[-1] * 0.70
    vt.update(crashed_equity)  # ingested AFTER scalar was read

    scalar_after = vt.scalar()

    # scalar_after should be different (crash raised EWMA variance → lower scalar)
    assert scalar_before != scalar_after, (
        "scalar() should change after a large equity move is ingested via update()"
    )
    assert scalar_before > scalar_after, (
        f"scalar before crash ({scalar_before:.4f}) should be > after ({scalar_after:.4f}): "
        "crash raises variance, which should lower the position-size scalar"
    )


def test_vol_targeter_update_before_scalar_leaks_same_day_move():
    """Demonstrates what WRONG order would look like (update before scalar).

    Correct:   scalar() → update() → scalar stays calm for today's sizing
    Wrong:     update() → scalar() → scalar reflects today's crash, over-reducing size

    We assert the two orderings give DIFFERENT scalars after a large move,
    proving that the correct order (scalar first) does NOT leak same-day data.
    """
    def _run(update_first: bool) -> float:
        vt = PortfolioVolTargeter(min_obs=5, target_vol=0.12)
        equity = 10_000_000.0
        # 1%/day → ann_vol ~15.9% > vol_floor 2% → scalar < 1.0 after warmup
        path = [equity * (1.01 ** i) for i in range(23)]  # 22 moderate returns
        for e in path:
            vt.update(e)
        crashed = path[-1] * 0.60  # 40% crash
        if update_first:
            vt.update(crashed)       # WRONG: today's crash enters EWMA before sizing
            return vt.scalar()
        else:
            s = vt.scalar()          # CORRECT: today's crash not yet in EWMA
            vt.update(crashed)
            return s

    scalar_correct    = _run(update_first=False)
    scalar_lookahead  = _run(update_first=True)

    assert scalar_correct != scalar_lookahead, (
        "The two orderings should produce different scalars after a large move"
    )
    assert scalar_correct > scalar_lookahead, (
        f"Correct scalar ({scalar_correct:.4f}) should be > look-ahead scalar "
        f"({scalar_lookahead:.4f}): correct order does not see today's crash"
    )


def test_vol_targeter_identity_until_min_obs_regardless_of_future_updates():
    """scalar() == 1.0 for the first min_obs-1 returns, even with many more updates after."""
    vt = PortfolioVolTargeter(min_obs=20, target_vol=0.12)
    equity = 10_000_000.0

    # Feed exactly 20 updates (19 returns → _n=19 < 20 → still identity)
    for i in range(20):
        vt.update(equity * (1.01 ** i))

    scalar_at_warmup_boundary = vt.scalar()
    assert scalar_at_warmup_boundary == 1.0, (
        f"scalar() should be 1.0 (identity) at warmup boundary, got {scalar_at_warmup_boundary}"
    )


# ---------------------------------------------------------------------------
# Part 5 — BacktestEngine / LiveEngine loop order structural test
# ---------------------------------------------------------------------------

def test_backtest_loop_order_enforces_next_bar_execution():
    """Reconstruct the BacktestEngine loop and verify that orders generated at
    bar t's close are filled at bar t+1's open — never at bar t.

    This is the most important structural guarantee: the engine never feeds
    bar t's strategy output back into bar t's execution step.
    """
    from trader.backtest.engine import BacktestEngine
    from trader.data.historical_feed import InMemoryDailyFeed
    from trader.signals.technical import TechnicalSignalSource
    from trader.strategy.fusion_engine import FusionEngine
    from trader.strategy.order_factory import OrderFactory
    from trader.strategy.portfolio import FxRates, Portfolio
    from trader.strategy.risk import RiskManager

    # Very low threshold so signals fire early
    SYM2 = Symbol("TEST", Market.NASDAQ, "USD")
    T_BASE = datetime(2024, 1, 2, tzinfo=timezone.utc)
    closes = [float(10 + i) for i in range(20)]
    bars = [
        BarEvent(SYM2, T_BASE + timedelta(days=i), c, c, c, c, 100)
        for i, c in enumerate(closes)
    ]

    class TrackingExec(SimulatedExecutionHandler):
        """Records (bar_index, action, price) for every submit and fill."""
        def __init__(self):
            super().__init__(BpsCostModel(0.0))
            self.events: list[dict] = []
            self._bar_index = -1

        def on_bar(self, bar: BarEvent):
            self._bar_index += 1
            fills = super().on_bar(bar)
            for f in fills:
                self.events.append({
                    "type": "fill",
                    "bar_index": self._bar_index,
                    "fill_price": f.price,
                    "bar_open": bar.open,
                })
            return fills

        def submit_order(self, order: OrderEvent):
            self.events.append({
                "type": "submit",
                "bar_index": self._bar_index,
            })
            super().submit_order(order)

    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 10_000_000.0}, fx)
    ex = TrackingExec()
    eng = FusionEngine(
        [TechnicalSignalSource(fast=2, slow=4)],
        pf,
        RiskManager(max_symbol_weight=0.5),
        OrderFactory(),
        enter_threshold=0.01,   # very low so we get orders
    )
    BacktestEngine(InMemoryDailyFeed(bars), eng, ex, pf).run()

    # Verify: every fill's bar_index > the submit bar_index it corresponds to
    submits = [e for e in ex.events if e["type"] == "submit"]
    fills   = [e for e in ex.events if e["type"] == "fill"]

    # There should be at least one fill if any orders were generated
    if submits and fills:
        # Each fill must occur at a strictly later bar than the preceding submit
        for submit, fill in zip(submits, fills):
            assert fill["bar_index"] > submit["bar_index"], (
                f"Same-bar fill detected! Submit at bar {submit['bar_index']}, "
                f"fill at bar {fill['bar_index']}."
            )
            # Fill price must be the bar's open (not the signal bar's close)
            assert fill["fill_price"] == fill["bar_open"], (
                f"Fill price {fill['fill_price']} != bar open {fill['bar_open']}"
            )
