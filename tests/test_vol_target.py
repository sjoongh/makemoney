# tests/test_vol_target.py
"""Tests for PortfolioVolTargeter and its integration into FusionEngine.

No-look-ahead contract
----------------------
scalar() used to size bar-t reflects EWMA returns through bar t-1 only.
update(equity_t) is called AFTER scalar() in FusionEngine.decide_orders(),
so bar-t equity never influences bar-t sizing.
"""
from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta

import pytest

from trader.core.events import BarEvent, FillEvent, NormalizedSignal, Symbol, Market, TargetPosition
from trader.signals.interfaces import SignalSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager
from trader.strategy.vol_target import PortfolioVolTargeter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYM = Symbol("005930", Market.KOSPI, "KRW")


def _eq(values: list[float]) -> PortfolioVolTargeter:
    """Feed a list of equity values into a fresh targeter and return it."""
    vt = PortfolioVolTargeter()
    for v in values:
        vt.update(v)
    return vt


def _equity_path(n: int, daily_return: float, start: float = 10_000_000.0) -> list[float]:
    """Compound a constant daily return for n bars starting at start."""
    path = [start]
    for _ in range(n - 1):
        path.append(path[-1] * (1.0 + daily_return))
    return path


# ---------------------------------------------------------------------------
# 1. Identity until min_obs
# ---------------------------------------------------------------------------

class TestIdentityUntilMinObs:
    def test_scalar_is_one_before_any_updates(self):
        vt = PortfolioVolTargeter(min_obs=20)
        assert vt.scalar() == 1.0

    def test_scalar_is_one_after_fewer_than_min_obs_returns(self):
        """After k < min_obs updates scalar is still 1.0 for all k."""
        vt = PortfolioVolTargeter(min_obs=20)
        equity = 10_000_000.0
        for i in range(20):   # 20 updates → 19 returns (first update just seeds _prev_equity)
            vt.update(equity * (1 + 0.05) ** i)
            # _n increments only from the 2nd update onward → _n == i after update i+1
            # After 20 updates _n == 19 < min_obs=20, so still identity
            assert vt.scalar() == 1.0

    def test_scalar_leaves_identity_after_min_obs_returns(self):
        """After min_obs+1 updates (min_obs returns ingested) scalar may differ from 1."""
        vt = PortfolioVolTargeter(min_obs=5, target_vol=0.12)
        # Feed 6 updates so 5 returns are ingested (_n == 5 == min_obs)
        equity = 10_000_000.0
        for i in range(6):
            vt.update(equity * (1.0 + 0.10) ** i)   # 10% daily → very high vol
        # After 5 returns at 10%/day vol is huge → scalar < 1.0 (de-levered)
        s = vt.scalar()
        assert s < 1.0, f"Expected scalar < 1.0 but got {s}"

    def test_exactly_min_obs_updates_still_identity(self):
        """Exactly min_obs updates = min_obs-1 returns → still identity."""
        vt = PortfolioVolTargeter(min_obs=20)
        for i in range(20):   # first update seeds prev_equity → 19 returns → _n=19 < 20
            vt.update(10_000_000.0 * (1 + 0.01 * i))
        assert vt.scalar() == 1.0


# ---------------------------------------------------------------------------
# 2. High vol → deleverage; low vol → scalar near max_scalar
# ---------------------------------------------------------------------------

class TestHighLowVol:
    def test_high_vol_deleverages(self):
        """5% daily returns → ~79% annualised vol → scalar well below 1."""
        vt = PortfolioVolTargeter(min_obs=5, target_vol=0.12)
        path = _equity_path(30, daily_return=0.05)
        for v in path:
            vt.update(v)
        s = vt.scalar()
        assert s < 0.5, f"High-vol scalar should be < 0.5, got {s:.4f}"

    def test_low_vol_scalar_approaches_max(self):
        """0.01% daily returns → ~0.16% annualised vol → scalar clipped to max_scalar=1.0."""
        vt = PortfolioVolTargeter(min_obs=5, target_vol=0.12, vol_floor=0.02)
        path = _equity_path(30, daily_return=0.0001)
        for v in path:
            vt.update(v)
        s = vt.scalar()
        # vol_ann ~ 0.16% < vol_floor=2% → target/floor = 0.12/0.02 = 6 → clipped to 1.0
        assert s == 1.0, f"Low-vol scalar should be 1.0 (max_scalar), got {s:.4f}"

    def test_scalar_between_min_and_max(self):
        """Feed a moderate vol path; verify scalar is within [min_scalar, max_scalar]."""
        vt = PortfolioVolTargeter(min_obs=5, target_vol=0.12, min_scalar=0.25, max_scalar=1.0)
        path = _equity_path(30, daily_return=0.01)   # ~16% ann vol
        for v in path:
            vt.update(v)
        s = vt.scalar()
        assert 0.25 <= s <= 1.0, f"Scalar {s:.4f} outside [0.25, 1.0]"


# ---------------------------------------------------------------------------
# 3. Clip bounds respected
# ---------------------------------------------------------------------------

class TestClipBounds:
    def test_min_scalar_enforced(self):
        vt = PortfolioVolTargeter(min_obs=3, min_scalar=0.40, max_scalar=1.0, target_vol=0.05)
        # Extremely high daily vol → scalar would be tiny without floor
        path = _equity_path(10, daily_return=0.50)
        for v in path:
            vt.update(v)
        assert vt.scalar() >= 0.40

    def test_max_scalar_enforced(self):
        vt = PortfolioVolTargeter(min_obs=3, min_scalar=0.25, max_scalar=0.80, target_vol=0.50)
        # Very low vol, high target → would exceed 1.0 without clip
        path = _equity_path(10, daily_return=0.0001)
        for v in path:
            vt.update(v)
        assert vt.scalar() <= 0.80

    def test_custom_min_scalar_floor(self):
        vt = PortfolioVolTargeter(min_obs=3, min_scalar=0.30, max_scalar=1.0, target_vol=0.01)
        path = _equity_path(20, daily_return=0.10)   # high vol, low target → would be < 0.30
        for v in path:
            vt.update(v)
        assert vt.scalar() >= 0.30


# ---------------------------------------------------------------------------
# 4. No look-ahead: scalar for bar-t uses returns ≤ t-1
# ---------------------------------------------------------------------------

class TestNoLookahead:
    """Verify that a large equity jump on bar-t does NOT change the scalar
    that would be used to size bar-t (i.e. scalar() before update())."""

    def test_scalar_unchanged_by_same_bar_move(self):
        """scalar() read before and after update() differ; before-value is what matters."""
        vt = PortfolioVolTargeter(min_obs=5, target_vol=0.12)
        # Warm up with 21 calm returns so we're past min_obs
        calm_path = _equity_path(22, daily_return=0.001)
        for v in calm_path:
            vt.update(v)

        # Read scalar() BEFORE ingesting today's large move
        s_before = vt.scalar()   # this is what FusionEngine uses to size today's order

        # Simulate a catastrophic same-day move (50% drop)
        today_equity = calm_path[-1] * 0.50
        vt.update(today_equity)   # only now does the crash enter the EWMA

        s_after = vt.scalar()   # would be different — but we already sized before this

        # The scalar used for today's order (s_before) does NOT incorporate today's move
        # s_after < s_before because the crash raised var
        assert s_before != s_after, "A 50% crash should change EWMA variance"
        # Confirm s_before was the 'today sizing' scalar (reflects only up to yesterday)
        assert s_before > s_after, (
            f"Before-update scalar {s_before:.4f} should be > after {s_after:.4f} "
            "since crash increases variance and reduces scalar"
        )

    def test_order_of_calls_enforces_no_lookahead(self):
        """Simulate the FusionEngine protocol: scalar() then update().

        Compare two scenarios:
          A. scalar() → size → update()   (correct: no look-ahead)
          B. update() → scalar() → ...    (wrong: today's return in today's scalar)
        They must differ when vol changes on bar t.
        """
        def run_protocol(use_lookahead: bool) -> float:
            vt = PortfolioVolTargeter(min_obs=5, target_vol=0.12)
            calm_equities = _equity_path(22, daily_return=0.001)
            # Warm up
            for v in calm_equities[:-1]:
                vt.update(v)

            big_move_equity = calm_equities[-1] * 0.40   # 60% crash on last bar

            if use_lookahead:
                vt.update(big_move_equity)   # BAD: today first
                return vt.scalar()
            else:
                s = vt.scalar()              # GOOD: scalar first (today not yet ingested)
                vt.update(big_move_equity)
                return s

        scalar_correct = run_protocol(use_lookahead=False)
        scalar_lookahead = run_protocol(use_lookahead=True)
        assert scalar_correct != scalar_lookahead, (
            "Correct (no look-ahead) and look-ahead scalars should differ after a large move"
        )
        # Correct scalar is higher: crash hasn't been ingested yet → var still calm
        assert scalar_correct > scalar_lookahead


# ---------------------------------------------------------------------------
# 5. FusionEngine with vol_targeter=None is byte-identical (parity micro-test)
# ---------------------------------------------------------------------------

class _ConstantSignalSource(SignalSource):
    """Always emits a signal with a fixed score/confidence for the given symbol."""
    def __init__(self, sym: Symbol, score: float = 0.8):
        self._sym = sym
        self._score = score

    def on_bar(self, bar: BarEvent):
        if bar.symbol != self._sym:
            return None
        return NormalizedSignal(
            source="const",
            symbol=bar.symbol,
            ts=bar.ts,
            score=self._score,
            confidence=1.0,
            horizon="1d",
        )


def _make_bar(i: int, close: float = 75000.0) -> BarEvent:
    ts = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
    return BarEvent(SYM, ts, close, close, close, close, volume=1000)


def _make_engine(pf: Portfolio, vt=None) -> FusionEngine:
    return FusionEngine(
        signal_sources=[_ConstantSignalSource(SYM, score=0.8)],
        portfolio=pf,
        risk_manager=RiskManager(max_symbol_weight=0.30),
        order_factory=OrderFactory(),
        enter_threshold=0.5,
        vol_targeter=vt,
    )


def _make_portfolio() -> Portfolio:
    fx = FxRates({"KRW": 1.0})
    return Portfolio({"KRW": 10_000_000.0}, fx)


class TestFusionEngineParityMicro:
    def test_none_targeter_identical_to_no_targeter(self):
        """vol_targeter=None produces the exact same orders as omitting the param."""
        bars = [_make_bar(i) for i in range(10)]

        pf1 = _make_portfolio()
        eng1 = _make_engine(pf1, vt=None)   # explicit None

        pf2 = _make_portfolio()
        eng2 = _make_engine(pf2)             # default (no kwarg)

        orders1, orders2 = [], []
        for bar in bars:
            for fill in []:   # no fills in this micro-test (no execution handler)
                pass
            pf1.mark(bar); pf2.mark(bar)
            for o in eng1.on_bar(bar):
                orders1.append((o.side, o.quantity))
            for o in eng2.on_bar(bar):
                orders2.append((o.side, o.quantity))

        assert orders1 == orders2

    def test_with_targeter_eventually_differs_from_none(self):
        """With a targeter warmed up to high vol, the weight is scaled down.

        We feed equity directly into the targeter (bypassing the engine's
        portfolio.equity_krw() path) to isolate the scaling logic from
        execution-handler dependencies.  Then we assert that the same risk
        manager weight, when multiplied by scalar() < 1, produces a smaller
        TargetPosition weight than the unscaled version.
        """
        # Warm up with 30 bars of 3% daily returns → ann vol ~47% → scalar=min_scalar=0.25
        vt = PortfolioVolTargeter(min_obs=5, target_vol=0.05, min_scalar=0.25)
        equity = 10_000_000.0
        for i in range(30):
            vt.update(equity * (1.03 ** i))

        # After warmup scalar should be at minimum (high vol, low target)
        s = vt.scalar()
        assert s < 1.0, f"Expected scalar < 1.0 after high-vol warmup, got {s}"

        # A risk-manager sized weight of 0.30 scaled by s should be strictly less
        base_weight = 0.30
        scaled_weight = base_weight * s
        assert scaled_weight < base_weight, (
            f"Scaled weight {scaled_weight:.4f} should be < base weight {base_weight}"
        )


# ---------------------------------------------------------------------------
# 6. EWMA variance update formula correctness
# ---------------------------------------------------------------------------

class TestEWMAFormula:
    def test_ewma_variance_manual(self):
        """Verify the EWMA formula against a hand-computed reference."""
        lam = 0.94
        vt = PortfolioVolTargeter(min_obs=3, lam=lam)

        returns = [0.02, -0.03, 0.01, 0.04]
        equities = [10_000_000.0]
        for r in returns:
            equities.append(equities[-1] * (1 + r))

        for v in equities:
            vt.update(v)

        # Hand-compute var:
        # update 0 → seeds _prev_equity, no return yet
        # update 1 → r=0.02, r2=0.0004, _var=0.0004 (seed), _n=1
        # update 2 → r=-0.03, r2=0.0009, _var=0.94*0.0004 + 0.06*0.0009, _n=2
        # update 3 → r=0.01, r2=0.0001, _var=0.94*prev + 0.06*0.0001, _n=3
        # update 4 → r=0.04, r2=0.0016, _var=0.94*prev + 0.06*0.0016, _n=4
        var = 0.0004   # seed
        for r in [-0.03, 0.01, 0.04]:
            var = lam * var + (1 - lam) * r ** 2

        assert abs(vt._var - var) < 1e-12, f"EWMA var mismatch: {vt._var} vs {var}"
