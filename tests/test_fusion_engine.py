# tests/test_fusion_engine.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent, Side
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

def _engine():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    return FusionEngine([TechnicalSignalSource(2,4)],
                        Portfolio({"KRW":13_000_000.0}, fx),
                        RiskManager(0.5), OrderFactory(),
                        enter_threshold=0.05)

def test_uptrend_produces_buy_order():
    eng = _engine(); orders = []
    for b in _bars([1,2,3,4,5,6]): orders = eng.on_bar(b) or orders
    assert any(o.side == Side.BUY for o in orders)

def test_same_inputs_same_orders_determinism():
    seq = _bars([1,2,3,4,5,6])
    a = _engine(); b = _engine()
    out_a = [eng_out for x in seq for eng_out in a.on_bar(x)]
    out_b = [eng_out for x in seq for eng_out in b.on_bar(x)]
    assert [(o.side,o.quantity) for o in out_a] == [(o.side,o.quantity) for o in out_b]

def test_neutral_signal_holds_emits_no_orders():
    # 중립 구간(enter/exit 사이)에서는 주문을 내지 않는다(보유 유지, 청산 금지)
    import trader.strategy.fusion_engine as fe
    from trader.core.events import Symbol, Market, BarEvent, FillEvent, Side
    from trader.strategy.portfolio import Portfolio, FxRates
    from trader.strategy.risk import RiskManager
    from trader.strategy.order_factory import OrderFactory
    from datetime import datetime, timezone
    from uuid import uuid4
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    # enter_threshold 높게, exit_threshold 낮게 → 0.1 신호는 중립 구간
    class FlatSrc:
        name="technical"
        def on_bar(self, bar):
            from trader.core.events import NormalizedSignal
            return NormalizedSignal("technical", bar.symbol, bar.ts, 0.1, 0.6, "1d", {})
    portfolio = Portfolio({"KRW":13_000_000.0, "USD": 10_000.0}, fx)
    # 기존 포지션 10주를 심어 둔다 — 중립 신호 시 청산 주문이 나오면 버그
    portfolio.apply_fill(FillEvent(uuid4(), sym, datetime(2026,1,1,tzinfo=timezone.utc),
                                   Side.BUY, 10, 100.0, 0.0, "USD"))
    assert portfolio.position(sym) == 10
    eng = fe.FusionEngine([FlatSrc()], portfolio,
                          RiskManager(0.5), OrderFactory(), enter_threshold=0.35)
    orders = eng.on_bar(BarEvent(sym, datetime(2026,1,2,tzinfo=timezone.utc),10,10,10,10,100))
    assert orders == []   # 중립 → 무주문(홀드, 청산 금지)


def test_warmup_does_not_emit_orders():
    """warmup_bar over a rising series produces no orders (returns None),
    and after warmup, on_bar on the next bar still works correctly."""
    from datetime import datetime, timezone, timedelta
    from trader.core.events import Symbol, Market, BarEvent

    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [BarEvent(sym, t0 + timedelta(days=i), float(i+1), float(i+1),
                     float(i+1), float(i+1), 100) for i in range(6)]

    eng = _engine()
    # Warmup over first 5 bars — must return None, never orders
    for b in bars[:5]:
        result = eng.warmup_bar(b)
        assert result is None, f"warmup_bar must return None, got {result!r}"

    # After warmup, on_bar on the 6th bar must still work
    orders = eng.on_bar(bars[5])
    assert isinstance(orders, list)  # can be [] or [order], but must not raise


def test_on_bar_equals_decide_of_observe():
    """on_bar(bar) == decide_orders(bar, observe_bar(bar)) for identical engines.

    Because observe_bar mutates state (signals + risk), we use two identical
    engines — one via on_bar, one via the split path — and compare results.
    """
    from datetime import datetime, timezone, timedelta
    from trader.core.events import Symbol, Market, BarEvent

    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [BarEvent(sym, t0 + timedelta(days=i), float(i+1), float(i+1),
                     float(i+1), float(i+1), 100) for i in range(6)]

    eng_a = _engine()   # driven via on_bar
    eng_b = _engine()   # driven via observe_bar + decide_orders

    for b in bars:
        orders_a = eng_a.on_bar(b)
        signals  = eng_b.observe_bar(b)
        orders_b = eng_b.decide_orders(b, signals)
        assert [(o.side, o.quantity) for o in orders_a] == \
               [(o.side, o.quantity) for o in orders_b], \
               f"Mismatch on bar {b.ts}: on_bar={orders_a} vs split={orders_b}"
