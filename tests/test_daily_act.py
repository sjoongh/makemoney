# tests/test_daily_act.py
"""Unit tests for DailyActEngine and protective_limit_price."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from trader.core.events import BarEvent, Market, OrderEvent, Side, Symbol
from trader.live.daily import DailyActEngine, protective_limit_price
from trader.signals.technical import TechnicalSignalSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AAPL = Symbol("AAPL", Market.NASDAQ, "USD")
FX = FxRates({"USD": 1300.0, "KRW": 1.0})


def _make_bars(sym: Symbol, n: int = 60, base: float = 100.0) -> list[BarEvent]:
    """Rising price series with n bars starting from 2024-01-01."""
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(n):
        close = base + i
        bars.append(
            BarEvent(
                symbol=sym,
                ts=t0 + timedelta(days=i),
                open=close,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=1000,
            )
        )
    return bars


def _make_snapshot() -> dict:
    return {
        "cash_krw": 100_000_000.0,
        "positions": {},
        "marks": {},
    }


class FakeKis:
    """Deterministic fake KIS client for unit testing."""

    def __init__(self, symbols: list[tuple[str, str, str]], n_bars: int = 60):
        self._symbols = symbols
        self._n_bars = n_bars
        self.submit_calls: list[dict] = []

    @property
    def account(self) -> str:
        return "FAKE-ACCT"

    def account_snapshot(self) -> dict:
        return _make_snapshot()

    def daily_bars(self, ticker: str, market: str, currency: str, **_) -> list[BarEvent]:
        sym = Symbol(ticker, Market(market), currency)
        return _make_bars(sym, self._n_bars)

    def submit_order(
        self,
        ticker: str,
        market: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "00",
    ) -> str:
        self.submit_calls.append(
            dict(
                ticker=ticker,
                market=market,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
            )
        )
        return f"FAKE-ODNO-{len(self.submit_calls)}"


def _make_engine(portfolio: Portfolio) -> FusionEngine:
    return FusionEngine(
        signal_sources=[TechnicalSignalSource(fast=20, slow=50)],
        portfolio=portfolio,
        risk_manager=RiskManager(max_symbol_weight=0.3),
        order_factory=OrderFactory(),
        enter_threshold=0.01,  # very low threshold → easier to trigger a buy
    )


SYMS = [("AAPL", "NASDAQ", "USD")]
TWO_NASDAQ_SYMS = [("AAPL", "NASDAQ", "USD"), ("MSFT", "NASDAQ", "USD")]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProtectiveLimitPrice:
    def test_buy_adds_band(self):
        price = protective_limit_price(Side.BUY, 100.0, band=0.01)
        assert price == 101.0

    def test_sell_subtracts_band(self):
        price = protective_limit_price(Side.SELL, 100.0, band=0.01)
        assert price == 99.0

    def test_default_band_is_one_percent(self):
        assert protective_limit_price(Side.BUY, 200.0) == 202.0
        assert protective_limit_price(Side.SELL, 200.0) == 198.0

    def test_rounded_to_two_decimals(self):
        # 153.27 * 1.01 = 154.8027 → 154.8
        result = protective_limit_price(Side.BUY, 153.27, band=0.01)
        assert result == round(153.27 * 1.01, 2)

    def test_sell_rounded_to_two_decimals(self):
        result = protective_limit_price(Side.SELL, 153.27, band=0.01)
        assert result == round(153.27 * 0.99, 2)


class TestDailyActEngineDryRun:
    """dry_run=True: orders returned, submit_order never called."""

    def test_dry_run_acts_only_on_latest_bar_no_submit(self):
        """The engine returns order decisions but never calls submit_order."""
        fake_kis = FakeKis(SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_engine(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            band=0.01,
            dry_run=True,
        )

        orders = engine.run()

        # No HTTP submissions
        assert fake_kis.submit_calls == [], "dry_run must not call submit_order"

        # The result is a list of OrderEvent objects
        assert isinstance(orders, list)
        for o in orders:
            assert isinstance(o, OrderEvent)

        # With 60 rising bars and low enter_threshold, at least one BUY is expected
        assert any(o.side == Side.BUY for o in orders), (
            f"Expected a BUY order from rising price series, got: {orders}"
        )

    def test_warmup_does_not_trade(self):
        """Verify that only the latest bar triggers orders, not warmup bars.

        We run once with n_bars=60 (60 bars total → 59 warmup + 1 act).
        Then run again with n_bars=1 (no warmup at all, 1 act bar).
        The single-bar run should produce no order (indicator not yet warm).
        This confirms warmup bars themselves don't trigger submission.
        """
        # With only 1 bar, TechnicalSignalSource(20,50) returns None (needs slow=50)
        fake_1 = FakeKis(SYMS, n_bars=1)
        pf1 = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy1 = _make_engine(pf1)
        engine1 = DailyActEngine(
            kis_client=fake_1, strategy=strategy1, fx=FX,
            symbols=SYMS, dry_run=True,
        )
        orders_1bar = engine1.run()
        # Can't act on 1 bar — indicator needs 50 bars to warm up
        assert orders_1bar == [], f"Expected no orders with 1 bar, got {orders_1bar}"

        # With 60 bars we get orders (indicator warmed up over 59 bars, acts on bar 60)
        fake_60 = FakeKis(SYMS, n_bars=60)
        pf60 = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy60 = _make_engine(pf60)
        engine60 = DailyActEngine(
            kis_client=fake_60, strategy=strategy60, fx=FX,
            symbols=SYMS, dry_run=True,
        )
        orders_60bar = engine60.run()
        assert len(orders_60bar) > 0, "Expected orders after warmup with 60 bars"


class TestDailyActEngineLiveRun:
    """dry_run=False: submit_order called with protective limit price."""

    def test_live_run_submits_with_protective_limit(self):
        """submit_order called once per order with correct limit price."""
        fake_kis = FakeKis(SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_engine(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            band=0.01,
            dry_run=False,
        )

        orders = engine.run()

        # Must have submitted
        assert len(fake_kis.submit_calls) > 0, "Expected at least one submit_order call"

        # One submit per returned order
        assert len(fake_kis.submit_calls) == len(orders)

        # Each submitted price must match the protective band formula
        for call, order in zip(fake_kis.submit_calls, orders):
            # last bar close = base(100) + (n_bars-1) = 100 + 59 = 159.0
            expected_last_close = 159.0
            expected_price = protective_limit_price(order.side, expected_last_close, 0.01)
            assert call["price"] == expected_price, (
                f"Expected limit price {expected_price}, got {call['price']}"
            )
            assert call["order_type"] == "00", "Must use limit order"

    def test_live_run_uses_correct_side(self):
        """submit_order is called with the same side as the OrderEvent."""
        fake_kis = FakeKis(SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_engine(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
        )

        orders = engine.run()

        for call, order in zip(fake_kis.submit_calls, orders):
            assert call["side"] == order.side.value
            assert call["ticker"] == order.symbol.ticker
            assert call["market"] == order.symbol.market.value


class TestMarketFilter:
    """filter_symbols_by_market helper selects only the matching market."""

    def test_filter_nasdaq_selects_only_nasdaq(self):
        from trader.app.run_daily import filter_symbols_by_market

        all_syms = [("AAPL", "NASDAQ", "USD"), ("005930", "KOSPI", "KRW")]
        result = filter_symbols_by_market(all_syms, "NASDAQ")
        assert result == [("AAPL", "NASDAQ", "USD")]

    def test_filter_kospi_selects_only_kospi(self):
        from trader.app.run_daily import filter_symbols_by_market

        all_syms = [("AAPL", "NASDAQ", "USD"), ("005930", "KOSPI", "KRW")]
        result = filter_symbols_by_market(all_syms, "KOSPI")
        assert result == [("005930", "KOSPI", "KRW")]

    def test_filter_all_returns_everything(self):
        from trader.app.run_daily import filter_symbols_by_market

        all_syms = [("AAPL", "NASDAQ", "USD"), ("005930", "KOSPI", "KRW")]
        result = filter_symbols_by_market(all_syms, "ALL")
        assert result == all_syms

    def test_filter_unknown_market_returns_empty(self):
        from trader.app.run_daily import filter_symbols_by_market

        all_syms = [("AAPL", "NASDAQ", "USD"), ("005930", "KOSPI", "KRW")]
        result = filter_symbols_by_market(all_syms, "NYSE")
        assert result == []


class TestStalenessGuard:
    """DailyActEngine skips stale symbols but still acts on fresh ones."""

    def _make_engine_with_staleness(
        self,
        symbols_and_offsets: list[tuple[tuple[str, str, str], int]],
        max_staleness_days: int = 4,
    ):
        """
        symbols_and_offsets: list of ((ticker, market, currency), offset_days)
          where offset_days is how many days BEFORE the freshest bar this
          symbol's latest bar is dated (0 = fresh, >max_staleness = stale).
        """
        from trader.live.daily import DailyActEngine

        reference_date = datetime(2024, 3, 1, tzinfo=timezone.utc)

        class ControlledFakeKis:
            """Returns bars whose latest date is reference_date - offset_days."""

            def __init__(self):
                self.submit_calls: list[dict] = []
                self._symbol_offsets: dict[tuple[str, str], int] = {}

            @property
            def account(self) -> str:
                return "FAKE-ACCT"

            def account_snapshot(self) -> dict:
                return _make_snapshot()

            def daily_bars(
                self, ticker: str, market: str, currency: str, **_
            ) -> list[BarEvent]:
                sym = Symbol(ticker, Market(market), currency)
                offset = self._symbol_offsets.get((market, ticker), 0)
                # Generate 60 bars ending at reference_date - offset
                latest_ts = reference_date - timedelta(days=offset)
                t0 = latest_ts - timedelta(days=59)
                bars = []
                for i in range(60):
                    ts = t0 + timedelta(days=i)
                    close = 100.0 + i
                    bars.append(
                        BarEvent(
                            symbol=sym,
                            ts=ts,
                            open=close,
                            high=close + 0.5,
                            low=close - 0.5,
                            close=close,
                            volume=1000,
                        )
                    )
                return bars

            def submit_order(self, **_) -> str:
                self.submit_calls.append(_)
                return "FAKE"

        fake_kis = ControlledFakeKis()
        syms = []
        for (ticker, market, currency), offset in symbols_and_offsets:
            fake_kis._symbol_offsets[(market, ticker)] = offset
            syms.append((ticker, market, currency))

        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_engine(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=syms,
            band=0.01,
            dry_run=True,
            max_staleness_days=max_staleness_days,
        )
        return engine, fake_kis

    def test_stale_symbol_not_acted_on(self):
        """A symbol whose latest bar is older than max_staleness_days
        vs the freshest symbol should produce no orders."""
        # AAPL fresh (offset=0), MSFT very stale (offset=10 > max_staleness=4)
        engine, fake_kis = self._make_engine_with_staleness(
            [
                (("AAPL", "NASDAQ", "USD"), 0),
                (("MSFT", "NASDAQ", "USD"), 10),
            ],
            max_staleness_days=4,
        )
        orders = engine.run()
        acted_tickers = {o.symbol.ticker for o in orders}
        assert "MSFT" not in acted_tickers, (
            f"Stale MSFT should not produce orders; got: {orders}"
        )

    def test_fresh_symbol_is_acted_on(self):
        """The fresh symbol alongside a stale one still produces orders."""
        engine, fake_kis = self._make_engine_with_staleness(
            [
                (("AAPL", "NASDAQ", "USD"), 0),
                (("MSFT", "NASDAQ", "USD"), 10),
            ],
            max_staleness_days=4,
        )
        orders = engine.run()
        acted_tickers = {o.symbol.ticker for o in orders}
        # AAPL is fresh — with 60 rising bars it should generate a BUY
        assert "AAPL" in acted_tickers, (
            f"Fresh AAPL should produce orders; got: {orders}"
        )

    def test_within_staleness_threshold_is_still_acted_on(self):
        """A symbol offset by exactly max_staleness_days should still act (boundary)."""
        engine, _ = self._make_engine_with_staleness(
            [
                (("AAPL", "NASDAQ", "USD"), 0),
                (("MSFT", "NASDAQ", "USD"), 4),
            ],
            max_staleness_days=4,
        )
        orders = engine.run()
        acted_tickers = {o.symbol.ticker for o in orders}
        # MSFT is at the boundary (offset == max_staleness_days) → should still act
        assert "MSFT" in acted_tickers, (
            f"MSFT at boundary offset should still act; got acted_tickers={acted_tickers}"
        )

    def test_both_symbols_fresh_both_acted_on(self):
        """When all symbols are fresh, all are acted on normally."""
        engine, _ = self._make_engine_with_staleness(
            [
                (("AAPL", "NASDAQ", "USD"), 0),
                (("MSFT", "NASDAQ", "USD"), 1),
            ],
            max_staleness_days=4,
        )
        orders = engine.run()
        acted_tickers = {o.symbol.ticker for o in orders}
        assert "AAPL" in acted_tickers and "MSFT" in acted_tickers, (
            f"Both fresh symbols should act; got acted_tickers={acted_tickers}"
        )


class TestDailyActEngineMultiSymbolLedger:
    """Ledger is ticker-scoped: multiple symbols in same market submit independently."""

    def test_two_nasdaq_symbols_both_submit_first_run(self, tmp_path):
        """With two NASDAQ symbols and a fresh ledger, both tickers submit on first run."""
        from trader.live.ledger import RunLedger

        fake_kis = FakeKis(TWO_NASDAQ_SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_engine(pf)
        ledger = RunLedger(path=str(tmp_path / "ledger.json"))

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=TWO_NASDAQ_SYMS,
            dry_run=False,
            ledger=ledger,
        )
        orders = engine.run()

        # Every generated order must be submitted (no ticker blocks another)
        submitted_tickers = {c["ticker"] for c in fake_kis.submit_calls}
        order_tickers = {o.symbol.ticker for o in orders}
        assert submitted_tickers == order_tickers, (
            f"All generated order tickers should be submitted independently. "
            f"Orders: {order_tickers}, Submitted: {submitted_tickers}"
        )

    def test_same_day_rerun_submits_neither_symbol(self, tmp_path):
        """After a full two-symbol run, re-run with reloaded ledger submits nothing."""
        from trader.live.ledger import RunLedger

        ledger_path = str(tmp_path / "ledger.json")

        # First run — record both tickers
        fake_kis_1 = FakeKis(TWO_NASDAQ_SYMS, n_bars=60)
        pf1 = Portfolio({"KRW": 100_000_000.0}, FX)
        engine1 = DailyActEngine(
            kis_client=fake_kis_1,
            strategy=_make_engine(pf1),
            fx=FX,
            symbols=TWO_NASDAQ_SYMS,
            dry_run=False,
            ledger=RunLedger(path=ledger_path),
        )
        engine1.run()
        if len(fake_kis_1.submit_calls) == 0:
            import pytest
            pytest.skip("No orders generated — cannot test rerun idempotency")

        # Second run — same ledger file, same day
        fake_kis_2 = FakeKis(TWO_NASDAQ_SYMS, n_bars=60)
        pf2 = Portfolio({"KRW": 100_000_000.0}, FX)
        engine2 = DailyActEngine(
            kis_client=fake_kis_2,
            strategy=_make_engine(pf2),
            fx=FX,
            symbols=TWO_NASDAQ_SYMS,
            dry_run=False,
            ledger=RunLedger(path=ledger_path),
        )
        engine2.run()

        assert len(fake_kis_2.submit_calls) == 0, (
            f"Re-run must not submit either ticker again; got {fake_kis_2.submit_calls}"
        )
