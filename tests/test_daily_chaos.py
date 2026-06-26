# tests/test_daily_chaos.py
"""Adversarial / chaos integration tests for the live EOD reconcile path.

Drives DailyActEngine (dry_run=False) through a broker that reports an
OVER-fill / duplicate fill, and asserts the engine trips the kill switch via
the quantity-level reconciliation wired into _eod_reconcile_and_cancel.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trader.core.events import BarEvent, Market, Symbol
from trader.live.daily import DailyActEngine
from trader.signals.technical import TechnicalSignalSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager

FX = FxRates({"USD": 1300.0, "KRW": 1.0})
SYMS = [("AAPL", "NASDAQ", "USD")]


def _bars(sym: Symbol, n: int = 60, base: float = 100.0) -> list[BarEvent]:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        BarEvent(sym, t0 + timedelta(days=i), base + i, base + i + 0.5,
                 base + i - 0.5, base + i, 1000)
        for i in range(n)
    ]


class _ChaosKis:
    """Fake KIS that fills orders with a configurable quantity multiplier."""

    def __init__(self, fill_mult: float = 1.0, n_bars: int = 60):
        self._mult = fill_mult
        self._n_bars = n_bars
        self.submit_calls: list[dict] = []
        self.cancels: list[str] = []

    @property
    def account(self) -> str:
        return "FAKE-ACCT"

    def account_snapshot(self) -> dict:
        return {"cash_krw": 100_000_000.0, "positions": {}, "marks": {}}

    def daily_bars(self, ticker, market, currency, **_):
        return _bars(Symbol(ticker, Market(market), currency), self._n_bars)

    def submit_order(self, ticker, market, side, quantity, price=0.0, order_type="00") -> str:
        self.submit_calls.append(dict(ticker=ticker, market=market, side=side,
                                      quantity=quantity, price=price))
        return f"ODNO-{len(self.submit_calls)}"

    def filled_orders(self) -> list[dict]:
        # report each submitted order filled at mult × the ordered quantity
        out = []
        for i, c in enumerate(self.submit_calls, start=1):
            out.append({
                "order_id": f"ODNO-{i}",
                "ticker": c["ticker"],
                "market": c["market"],
                "side": c["side"],
                "qty": int(c["quantity"] * self._mult),
                "price": c["price"],
                "commission": 0.0,
            })
        return out

    def cancel_order(self, market, original_odno, ticker, quantity):
        self.cancels.append(original_odno)


class _FakeKillSwitch:
    def __init__(self):
        self.trips: list[dict] = []

    def is_active(self) -> bool:
        return bool(self.trips)

    def status(self) -> dict:
        return self.trips[-1] if self.trips else {}

    def trip(self, reason: str, source: str, ts=None) -> None:
        self.trips.append({"reason": reason, "source": source})


class _RecordingMonitor:
    def __init__(self):
        self.alerts: list[tuple] = []

    def alert(self, severity, code, payload):
        self.alerts.append((severity, code, payload))


def _engine(kis, killswitch, monitor):
    pf = Portfolio({"KRW": 100_000_000.0}, FX)
    strategy = FusionEngine(
        signal_sources=[TechnicalSignalSource(fast=20, slow=50)],
        portfolio=pf,
        risk_manager=RiskManager(max_symbol_weight=0.3),
        order_factory=OrderFactory(),
        enter_threshold=0.01,
    )
    return DailyActEngine(
        kis_client=kis, strategy=strategy, fx=FX, symbols=SYMS,
        dry_run=False, killswitch=killswitch, monitor=monitor,
    )


def test_overfill_trips_kill_switch():
    kis = _ChaosKis(fill_mult=2.0)        # broker reports 2× the ordered qty
    ks = _FakeKillSwitch()
    mon = _RecordingMonitor()
    engine = _engine(kis, ks, mon)

    orders = engine.run()
    assert len(orders) > 0, "precondition: engine must submit at least one order"
    assert ks.is_active(), "OVER-fill must trip the kill switch"
    assert any(t["source"] == "eod_reconcile" for t in ks.trips)
    assert any(code == "EOD_OVERFILL" for _, code, _ in mon.alerts)


def test_exact_fill_does_not_trip():
    kis = _ChaosKis(fill_mult=1.0)        # clean full fill
    ks = _FakeKillSwitch()
    mon = _RecordingMonitor()
    engine = _engine(kis, ks, mon)

    orders = engine.run()
    assert len(orders) > 0
    assert not ks.is_active(), "a clean full fill must NOT trip the kill switch"
    assert not any(code == "EOD_OVERFILL" for _, code, _ in mon.alerts)
