# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-06-15T10:46:03.966Z

## Original task

Design the risk-layer enhancement for a Python event-driven daily-bar trading engine, preserving backtest=live parity (risk logic must stay DETERMINISTIC — no wall clock/random/IO; only data it's fed).

CURRENT (read these): trader/strategy/risk.py (RiskManager(max_symbol_weight).size_target(TargetPosition)->TargetPosition, plus kill switch), trader/strategy/fusion_engine.py (calls self.risk.size_target(TargetPosition(symbol, weight, reason)) then order_factory.orders_for_target(sized, portfolio, price=bar.close, ts=bar.ts)), trader/strategy/portfolio.py (position(sym), equity_krw(), cash, marks per (market,ticker)), trader/core/events.py (BarEvent, Symbol, TargetPosition).

GOAL — add these, each testable & deterministic:
1. Volatility (ATR-based) position sizing — scale target weight down when the symbol is more volatile.
2. Daily loss limit — when portfolio equity drops >X% from the day's start equity, force flat / stop new entries (trip kill switch for the day).
3. Per-market exposure cap — total weight in NASDAQ and in KOSPI each capped.
4. Max number of concurrent positions.

KEY DESIGN QUESTIONS — answer concretely:
A. The risk layer now needs more context than just TargetPosition: it needs the bar (for ATR & 'today' boundary), the portfolio (positions, equity, per-market exposure), and per-symbol volatility history. What is the cleanest INTERFACE change? Options: (i) risk.on_bar(bar) to update internal ATR + day-rollover state, plus size_target(target, portfolio, bar); (ii) pass everything into one call. Recommend one and give the exact method signatures.
B. ATR needs high/low/close history per symbol — should RiskManager maintain its own per-symbol bar buffer (fed via on_bar), or consume volatility from the technical signal's features? Recommend.
C. Daily loss limit needs 'start-of-day equity' — how to detect day rollover deterministically from bar timestamps (no wall clock)? 
D. Where do per-market cap and max-positions checks belong — in size_target (per-symbol, but needs whole-portfolio view) — is that sufficient, or is a portfolio-level pass needed?
E. How to keep this deterministic so the parity test (same bars -> same orders) still holds?
Give exact signatures and a terse implementation sketch. Senior, opinionated, no fluff.

## Final prompt

Design the risk-layer enhancement for a Python event-driven daily-bar trading engine, preserving backtest=live parity (risk logic must stay DETERMINISTIC — no wall clock/random/IO; only data it's fed).

CURRENT (read these): trader/strategy/risk.py (RiskManager(max_symbol_weight).size_target(TargetPosition)->TargetPosition, plus kill switch), trader/strategy/fusion_engine.py (calls self.risk.size_target(TargetPosition(symbol, weight, reason)) then order_factory.orders_for_target(sized, portfolio, price=bar.close, ts=bar.ts)), trader/strategy/portfolio.py (position(sym), equity_krw(), cash, marks per (market,ticker)), trader/core/events.py (BarEvent, Symbol, TargetPosition).

GOAL — add these, each testable & deterministic:
1. Volatility (ATR-based) position sizing — scale target weight down when the symbol is more volatile.
2. Daily loss limit — when portfolio equity drops >X% from the day's start equity, force flat / stop new entries (trip kill switch for the day).
3. Per-market exposure cap — total weight in NASDAQ and in KOSPI each capped.
4. Max number of concurrent positions.

KEY DESIGN QUESTIONS — answer concretely:
A. The risk layer now needs more context than just TargetPosition: it needs the bar (for ATR & 'today' boundary), the portfolio (positions, equity, per-market exposure), and per-symbol volatility history. What is the cleanest INTERFACE change? Options: (i) risk.on_bar(bar) to update internal ATR + day-rollover state, plus size_target(target, portfolio, bar); (ii) pass everything into one call. Recommend one and give the exact method signatures.
B. ATR needs high/low/close history per symbol — should RiskManager maintain its own per-symbol bar buffer (fed via on_bar), or consume volatility from the technical signal's features? Recommend.
C. Daily loss limit needs 'start-of-day equity' — how to detect day rollover deterministically from bar timestamps (no wall clock)? 
D. Where do per-market cap and max-positions checks belong — in size_target (per-symbol, but needs whole-portfolio view) — is that sufficient, or is a portfolio-level pass needed?
E. How to keep this deterministic so the parity test (same bars -> same orders) still holds?
Give exact signatures and a terse implementation sketch. Senior, opinionated, no fluff.

## Raw output

```text
Use **two-phase risk**: deterministic state update on each bar, then deterministic target sizing with explicit context.

**A. Interface**
Recommend option **(i)**.

```python
class RiskManager:
    def on_bar(self, bar: BarEvent, portfolio: Portfolio) -> None:
        """Update deterministic risk state: ATR buffers, daily equity anchor, daily kill switch."""

    def size_target(
        self,
        target: TargetPosition,
        portfolio: Portfolio,
        bar: BarEvent,
    ) -> TargetPosition:
        """Return risk-adjusted target for this symbol at this bar."""
```

Engine flow should become:

```python
def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
    self.portfolio.mark(bar)
    self.risk.on_bar(bar, self.portfolio)

    signals = [...]
    combined = self._combine(signals)

    ...
    raw = TargetPosition(bar.symbol, weight, reason=f"combined={combined:.2f}")
    sized = self.risk.size_target(raw, self.portfolio, bar)

    return self.order_factory.orders_for_target(
        sized, self.portfolio, price=bar.close, ts=bar.ts
    )
```

Do **not** hide `portfolio` or `bar` inside the risk manager. `on_bar()` mutates only risk-owned deterministic state. `size_target()` is pure with respect to the current decision except for reading that state.

Constructor sketch:

```python
class RiskManager:
    def __init__(
        self,
        max_symbol_weight: float = 0.30,
        atr_period: int = 14,
        target_atr_pct: float = 0.03,
        daily_loss_limit_pct: float = 0.03,
        max_market_weight: dict[Market, float] | None = None,
        max_positions: int | None = None,
    ):
        ...
```

**B. ATR Ownership**
RiskManager should maintain its own per-symbol ATR buffer, fed only by `on_bar(bar, portfolio)`.

Do **not** consume ATR from signal features. Risk constraints should not depend on whichever signal source happened to run, how features are named, or whether a model emitted them. ATR is risk infrastructure, not alpha data.

State sketch:

```python
@dataclass
class AtrState:
    prev_close: float | None = None
    trs: deque[float] = field(default_factory=deque)
    atr: float | None = None
```

Update:

```python
def _update_atr(self, bar: BarEvent) -> None:
    st = self._atr[_sym_key(bar.symbol)]

    if st.prev_close is None:
        tr = bar.high - bar.low
    else:
        tr = max(
            bar.high - bar.low,
            abs(bar.high - st.prev_close),
            abs(bar.low - st.prev_close),
        )

    st.trs.append(tr)
    if len(st.trs) > self.atr_period:
        st.trs.popleft()

    st.prev_close = bar.close

    if len(st.trs) == self.atr_period:
        st.atr = sum(st.trs) / self.atr_period
```

Sizing multiplier:

```python
def _vol_scaled_weight(self, symbol: Symbol, raw_weight: float, close: float) -> float:
    st = self._atr.get(_sym_key(symbol))
    if not st or st.atr is None or close <= 0:
        return raw_weight

    atr_pct = st.atr / close
    if atr_pct <= 0:
        return raw_weight

    vol_mult = min(1.0, self.target_atr_pct / atr_pct)
    return raw_weight * vol_mult
```

So if target ATR is `3%` and symbol ATR is `6%`, requested weight is halved.

**C. Daily Loss Rollover**
Detect the day from `bar.ts`, not wall clock.

Use the timestamp’s own timezone and derive:

```python
day = bar.ts.date()
```

Risk state:

```python
self._current_day: date | None = None
self._day_start_equity_krw: float | None = None
self._daily_killed: bool = False
```

Rollover:

```python
def _roll_day_if_needed(self, bar: BarEvent, portfolio: Portfolio) -> None:
    day = bar.ts.date()

    if self._current_day != day:
        self._current_day = day
        self._day_start_equity_krw = portfolio.equity_krw()
        self._daily_killed = False
```

Loss check:

```python
def _check_daily_loss(self, portfolio: Portfolio) -> None:
    if self._day_start_equity_krw is None or self._day_start_equity_krw <= 0:
        return

    equity = portfolio.equity_krw()
    drawdown = 1.0 - equity / self._day_start_equity_krw

    if drawdown > self.daily_loss_limit_pct:
        self._daily_killed = True
```

Important: call `portfolio.mark(bar)` before `risk.on_bar(bar, portfolio)`, otherwise equity uses stale marks.

**D. Market Cap And Max Positions**
Put the checks in `size_target(...)`, but implement them using whole-portfolio helper calculations. A separate portfolio-level optimizer/pass is unnecessary for the current single-symbol event-driven engine.

However, be explicit about the limitation: `size_target()` can correctly gate or shrink the **current symbol’s** target against current portfolio exposure. It does not rebalance multiple symbols simultaneously. That is acceptable for this engine because one bar produces one target and one order decision.

Recommended helpers:

```python
def market_exposure_weight(portfolio: Portfolio, market: Market) -> float:
    ...

def open_position_count(portfolio: Portfolio) -> int:
    ...

def symbol_weight(portfolio: Portfolio, symbol: Symbol) -> float:
    ...
```

These probably belong on `Portfolio`, because risk should not reach into `_pos`, `_mark`, and `_sym` long-term:

```python
class Portfolio:
    def position_value_krw(self, sym: Symbol) -> float: ...

    def position_weight(self, sym: Symbol) -> float: ...

    def market_weight(self, market: Market) -> float: ...

    def open_position_count(self) -> int: ...
```

`size_target()` order:

```python
def size_target(
    self,
    target: TargetPosition,
    portfolio: Portfolio,
    bar: BarEvent,
) -> TargetPosition:
    raw = target.target_weight

    if raw <= 0.0:
        return TargetPosition(target.symbol, 0.0, target.reason)

    if self._killed or self._daily_killed:
        return TargetPosition(target.symbol, 0.0, target.reason + "|risk=daily_kill")

    weight = min(raw, self.max_symbol_weight)
    weight = self._vol_scaled_weight(target.symbol, weight, bar.close)

    weight = self._apply_market_cap(target.symbol, weight, portfolio)
    weight = self._apply_max_positions(target.symbol, weight, portfolio)

    return TargetPosition(target.symbol, max(0.0, weight), target.reason)
```

Market cap:

```python
def _apply_market_cap(
    self,
    symbol: Symbol,
    desired_weight: float,
    portfolio: Portfolio,
) -> float:
    cap = self.max_market_weight.get(symbol.market)
    if cap is None:
        return desired_weight

    current_market = portfolio.market_weight(symbol.market)
    current_symbol = portfolio.position_weight(symbol)

    # Existing symbol weight can be replaced by the new target.
    available_for_symbol = cap - (current_market - current_symbol)

    return min(desired_weight, max(0.0, available_for_symbol))
```

Max positions:

```python
def _apply_max_positions(
    self,
    symbol: Symbol,
    desired_weight: float,
    portfolio: Portfolio,
) -> float:
    if self.max_positions is None:
        return desired_weight

    already_open = portfolio.position(symbol) != 0
    if already_open:
        return desired_weight

    if portfolio.open_position_count() >= self.max_positions:
        return 0.0

    return desired_weight
```

**E. Determinism Rules**
Keep these hard rules:

1. No wall clock. Day comes only from `bar.ts.date()`.
2. No random.
3. No IO inside risk.
4. No broker/API/database reads inside risk.
5. ATR state is updated only from received `BarEvent`s, in received order.
6. Equity comes only from the passed `Portfolio` state.
7. Use stable keys: `(symbol.market.value, symbol.ticker)`.
8. Do not use unordered iteration for decisions unless sorted first.
9. Same bar stream + same fills + same initial portfolio + same config must produce same targets/orders.
10. In tests, replay identical bars through backtest/live paths and compare emitted `OrderEvent`s.

One subtle point: daily loss kill should be checked after marking the current bar. That means the bar that causes the drawdown can immediately force the current symbol flat and block entries afterward. That is deterministic and consistent between backtest and live as long as both paths feed closed daily bars in the same order.


OpenAI Codex v0.139.0
--------
workdir: /Users/manager/side/makemoney
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019ecae2-b817-7442-a2cc-10651cb8244c
--------
user
Design the risk-layer enhancement for a Python event-driven daily-bar trading engine, preserving backtest=live parity (risk logic must stay DETERMINISTIC — no wall clock/random/IO; only data it's fed).

CURRENT (read these): trader/strategy/risk.py (RiskManager(max_symbol_weight).size_target(TargetPosition)->TargetPosition, plus kill switch), trader/strategy/fusion_engine.py (calls self.risk.size_target(TargetPosition(symbol, weight, reason)) then order_factory.orders_for_target(sized, portfolio, price=bar.close, ts=bar.ts)), trader/strategy/portfolio.py (position(sym), equity_krw(), cash, marks per (market,ticker)), trader/core/events.py (BarEvent, Symbol, TargetPosition).

GOAL — add these, each testable & deterministic:
1. Volatility (ATR-based) position sizing — scale target weight down when the symbol is more volatile.
2. Daily loss limit — when portfolio equity drops >X% from the day's start equity, force flat / stop new entries (trip kill switch for the day).
3. Per-market exposure cap — total weight in NASDAQ and in KOSPI each capped.
4. Max number of concurrent positions.

KEY DESIGN QUESTIONS — answer concretely:
A. The risk layer now needs more context than just TargetPosition: it needs the bar (for ATR & 'today' boundary), the portfolio (positions, equity, per-market exposure), and per-symbol volatility history. What is the cleanest INTERFACE change? Options: (i) risk.on_bar(bar) to update internal ATR + day-rollover state, plus size_target(target, portfolio, bar); (ii) pass everything into one call. Recommend one and give the exact method signatures.
B. ATR needs high/low/close history per symbol — should RiskManager maintain its own per-symbol bar buffer (fed via on_bar), or consume volatility from the technical signal's features? Recommend.
C. Daily loss limit needs 'start-of-day equity' — how to detect day rollover deterministically from bar timestamps (no wall clock)? 
D. Where do per-market cap and max-positions checks belong — in size_target (per-symbol, but needs whole-portfolio view) — is that sufficient, or is a portfolio-level pass needed?
E. How to keep this deterministic so the parity test (same bars -> same orders) still holds?
Give exact signatures and a terse implementation sketch. Senior, opinionated, no fluff.
codex
I’ll inspect the current risk, engine, portfolio, and event shapes first so the proposed interface fits the code that exists rather than inventing a parallel API.
exec
/bin/zsh -lc "sed -n '1,240p' trader/strategy/risk.py" in /Users/manager/side/makemoney
exec
/bin/zsh -lc "sed -n '1,260p' trader/strategy/portfolio.py" in /Users/manager/side/makemoney
exec
/bin/zsh -lc "sed -n '1,260p' trader/strategy/fusion_engine.py" in /Users/manager/side/makemoney
exec
/bin/zsh -lc "sed -n '1,240p' trader/core/events.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
# trader/core/events.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping
from uuid import UUID

class Market(str, Enum):
    NASDAQ = "NASDAQ"; KOSPI = "KOSPI"

class Side(str, Enum):
    BUY = "BUY"; SELL = "SELL"

def _require_tz(ts: datetime) -> None:
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

@dataclass(frozen=True)
class Symbol:
    ticker: str; market: Market; currency: str

@dataclass(frozen=True)
class BarEvent:
    symbol: Symbol; ts: datetime
    open: float; high: float; low: float; close: float; volume: int
    timeframe: str = "1d"; is_closed: bool = True
    def __post_init__(self): _require_tz(self.ts)

@dataclass(frozen=True)
class NormalizedSignal:
    source: str; symbol: Symbol; ts: datetime
    score: float; confidence: float; horizon: str
    features: Mapping[str, float] = field(default_factory=dict)
    def __post_init__(self):
        _require_tz(self.ts)
        if not -1.0 <= self.score <= 1.0: raise ValueError("score must be in [-1,1]")
        if not 0.0 <= self.confidence <= 1.0: raise ValueError("confidence must be in [0,1]")

@dataclass(frozen=True)
class OrderEvent:
    order_id: UUID; symbol: Symbol; ts: datetime
    side: Side; quantity: int; order_type: str = "MARKET"
    limit_price: float | None = None; reason: str = ""
    def __post_init__(self):
        _require_tz(self.ts)
        if self.quantity <= 0: raise ValueError("quantity must be positive")

@dataclass(frozen=True)
class FillEvent:
    order_id: UUID; symbol: Symbol; ts: datetime
    side: Side; quantity: int; price: float
    commission: float; currency: str
    def __post_init__(self): _require_tz(self.ts)

@dataclass(frozen=True)
class TargetPosition:
    symbol: Symbol; target_weight: float; reason: str = ""

 succeeded in 0ms:
# trader/strategy/risk.py
from __future__ import annotations
from trader.core.events import TargetPosition

class RiskManager:
    def __init__(self, max_symbol_weight: float = 0.3):
        self.max_symbol_weight = max_symbol_weight
        self._killed = False
    def trip_kill_switch(self) -> None: self._killed = True
    def size_target(self, target: TargetPosition) -> TargetPosition:
        w = target.target_weight
        if self._killed or w <= 0.0:
            w = 0.0
        else:
            w = min(w, self.max_symbol_weight)
        return TargetPosition(target.symbol, w, target.reason)

 succeeded in 0ms:
# trader/strategy/fusion_engine.py
from __future__ import annotations
from typing import Sequence
from trader.core.events import BarEvent, OrderEvent, FillEvent, NormalizedSignal, TargetPosition
from trader.signals.interfaces import SignalSource

class FusionEngine:
    """모드 무지. 신호 융합 → 목표비중 → 리스크 → 주문. 브로커/DB/시계 직접 접근 없음."""
    def __init__(self, signal_sources: Sequence[SignalSource], portfolio,
                 risk_manager, order_factory, enter_threshold: float = 0.35,
                 exit_threshold: float | None = None,
                 source_weight: dict[str, float] | None = None):
        self.sources = signal_sources
        self.portfolio = portfolio
        self.risk = risk_manager
        self.order_factory = order_factory
        self.enter_threshold = enter_threshold
        self.exit_threshold = exit_threshold if exit_threshold is not None else -enter_threshold
        self.source_weight = source_weight or {}
    def on_fill(self, fill: FillEvent) -> None:
        self.portfolio.apply_fill(fill)
    def _combine(self, signals: list[NormalizedSignal]) -> float:
        if not signals: return 0.0
        num = den = 0.0
        for s in signals:
            w = s.confidence * self.source_weight.get(s.source, 1.0)
            num += s.score * w; den += w
        return num / den if den else 0.0
    def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
        signals = [s for src in self.sources if (s := src.on_bar(bar)) is not None]
        combined = self._combine(signals)
        if combined >= self.enter_threshold:
            weight = combined
        elif combined <= self.exit_threshold:
            weight = 0.0
        else:
            return []  # 중립 구간: 포지션 유지, 주문 없음
        sized = self.risk.size_target(TargetPosition(bar.symbol, weight, reason=f"combined={combined:.2f}"))
        return self.order_factory.orders_for_target(sized, self.portfolio, price=bar.close, ts=bar.ts)

 succeeded in 0ms:
# trader/strategy/portfolio.py
from __future__ import annotations
from dataclasses import dataclass, field
from trader.core.events import Symbol, BarEvent, FillEvent, Side

@dataclass
class FxRates:
    rates: dict[str, float]            # 통화→KRW 환율 (KRW=1.0)
    def to_krw(self, amount: float, ccy: str) -> float:
        return amount * self.rates[ccy]

def _sym_key(sym: Symbol) -> tuple[str, str]:
    """시장+티커 복합키 — 동일 티커가 다른 시장에 상장된 경우 충돌 방지."""
    return (sym.market.value, sym.ticker)

class Portfolio:
    def __init__(self, cash: dict[str, float], fx: FxRates):
        self.cash: dict[str, float] = dict(cash)
        self.fx = fx
        self._pos: dict[tuple[str, str], int] = {}          # (market, ticker) -> qty
        self._sym: dict[tuple[str, str], Symbol] = {}
        self._mark: dict[tuple[str, str], float] = {}       # (market, ticker) -> last close (해당 통화)
    def deposit(self, ccy: str, amount: float) -> None:
        self.cash[ccy] = self.cash.get(ccy, 0.0) + amount
    def position(self, sym: Symbol) -> int:
        return self._pos.get(_sym_key(sym), 0)
    def apply_fill(self, fill: FillEvent) -> None:
        key = _sym_key(fill.symbol)
        notional_krw = self.fx.to_krw(fill.price * fill.quantity, fill.currency)
        comm_krw = self.fx.to_krw(fill.commission, fill.currency)
        if fill.side == Side.BUY:
            self.cash["KRW"] = self.cash.get("KRW", 0.0) - notional_krw - comm_krw
            self._pos[key] = self._pos.get(key, 0) + fill.quantity
        else:
            self.cash["KRW"] = self.cash.get("KRW", 0.0) + notional_krw - comm_krw
            self._pos[key] = self._pos.get(key, 0) - fill.quantity
        self._sym[key] = fill.symbol
        self._mark.setdefault(key, fill.price)
    def mark(self, bar: BarEvent) -> None:
        key = _sym_key(bar.symbol)
        self._mark[key] = bar.close
        self._sym[key] = bar.symbol
    def equity_krw(self) -> float:
        eq = sum(self.fx.to_krw(amt, ccy) for ccy, amt in self.cash.items())
        for key, qty in self._pos.items():
            sym = self._sym[key]
            eq += self.fx.to_krw(qty * self._mark.get(key, 0.0), sym.currency)
        return eq

codex
Use **two-phase risk**: deterministic state update on each bar, then deterministic target sizing with explicit context.

**A. Interface**
Recommend option **(i)**.

```python
class RiskManager:
    def on_bar(self, bar: BarEvent, portfolio: Portfolio) -> None:
        """Update deterministic risk state: ATR buffers, daily equity anchor, daily kill switch."""

    def size_target(
        self,
        target: TargetPosition,
        portfolio: Portfolio,
        bar: BarEvent,
    ) -> TargetPosition:
        """Return risk-adjusted target for this symbol at this bar."""
```

Engine flow should become:

```python
def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
    self.portfolio.mark(bar)
    self.risk.on_bar(bar, self.portfolio)

    signals = [...]
    combined = self._combine(signals)

    ...
    raw = TargetPosition(bar.symbol, weight, reason=f"combined={combined:.2f}")
    sized = self.risk.size_target(raw, self.portfolio, bar)

    return self.order_factory.orders_for_target(
        sized, self.portfolio, price=bar.close, ts=bar.ts
    )
```

Do **not** hide `portfolio` or `bar` inside the risk manager. `on_bar()` mutates only risk-owned deterministic state. `size_target()` is pure with respect to the current decision except for reading that state.

Constructor sketch:

```python
class RiskManager:
    def __init__(
        self,
        max_symbol_weight: float = 0.30,
        atr_period: int = 14,
        target_atr_pct: float = 0.03,
        daily_loss_limit_pct: float = 0.03,
        max_market_weight: dict[Market, float] | None = None,
        max_positions: int | None = None,
    ):
        ...
```

**B. ATR Ownership**
RiskManager should maintain its own per-symbol ATR buffer, fed only by `on_bar(bar, portfolio)`.

Do **not** consume ATR from signal features. Risk constraints should not depend on whichever signal source happened to run, how features are named, or whether a model emitted them. ATR is risk infrastructure, not alpha data.

State sketch:

```python
@dataclass
class AtrState:
    prev_close: float | None = None
    trs: deque[float] = field(default_factory=deque)
    atr: float | None = None
```

Update:

```python
def _update_atr(self, bar: BarEvent) -> None:
    st = self._atr[_sym_key(bar.symbol)]

    if st.prev_close is None:
        tr = bar.high - bar.low
    else:
        tr = max(
            bar.high - bar.low,
            abs(bar.high - st.prev_close),
            abs(bar.low - st.prev_close),
        )

    st.trs.append(tr)
    if len(st.trs) > self.atr_period:
        st.trs.popleft()

    st.prev_close = bar.close

    if len(st.trs) == self.atr_period:
        st.atr = sum(st.trs) / self.atr_period
```

Sizing multiplier:

```python
def _vol_scaled_weight(self, symbol: Symbol, raw_weight: float, close: float) -> float:
    st = self._atr.get(_sym_key(symbol))
    if not st or st.atr is None or close <= 0:
        return raw_weight

    atr_pct = st.atr / close
    if atr_pct <= 0:
        return raw_weight

    vol_mult = min(1.0, self.target_atr_pct / atr_pct)
    return raw_weight * vol_mult
```

So if target ATR is `3%` and symbol ATR is `6%`, requested weight is halved.

**C. Daily Loss Rollover**
Detect the day from `bar.ts`, not wall clock.

Use the timestamp’s own timezone and derive:

```python
day = bar.ts.date()
```

Risk state:

```python
self._current_day: date | None = None
self._day_start_equity_krw: float | None = None
self._daily_killed: bool = False
```

Rollover:

```python
def _roll_day_if_needed(self, bar: BarEvent, portfolio: Portfolio) -> None:
    day = bar.ts.date()

    if self._current_day != day:
        self._current_day = day
        self._day_start_equity_krw = portfolio.equity_krw()
        self._daily_killed = False
```

Loss check:

```python
def _check_daily_loss(self, portfolio: Portfolio) -> None:
    if self._day_start_equity_krw is None or self._day_start_equity_krw <= 0:
        return

    equity = portfolio.equity_krw()
    drawdown = 1.0 - equity / self._day_start_equity_krw

    if drawdown > self.daily_loss_limit_pct:
        self._daily_killed = True
```

Important: call `portfolio.mark(bar)` before `risk.on_bar(bar, portfolio)`, otherwise equity uses stale marks.

**D. Market Cap And Max Positions**
Put the checks in `size_target(...)`, but implement them using whole-portfolio helper calculations. A separate portfolio-level optimizer/pass is unnecessary for the current single-symbol event-driven engine.

However, be explicit about the limitation: `size_target()` can correctly gate or shrink the **current symbol’s** target against current portfolio exposure. It does not rebalance multiple symbols simultaneously. That is acceptable for this engine because one bar produces one target and one order decision.

Recommended helpers:

```python
def market_exposure_weight(portfolio: Portfolio, market: Market) -> float:
    ...

def open_position_count(portfolio: Portfolio) -> int:
    ...

def symbol_weight(portfolio: Portfolio, symbol: Symbol) -> float:
    ...
```

These probably belong on `Portfolio`, because risk should not reach into `_pos`, `_mark`, and `_sym` long-term:

```python
class Portfolio:
    def position_value_krw(self, sym: Symbol) -> float: ...

    def position_weight(self, sym: Symbol) -> float: ...

    def market_weight(self, market: Market) -> float: ...

    def open_position_count(self) -> int: ...
```

`size_target()` order:

```python
def size_target(
    self,
    target: TargetPosition,
    portfolio: Portfolio,
    bar: BarEvent,
) -> TargetPosition:
    raw = target.target_weight

    if raw <= 0.0:
        return TargetPosition(target.symbol, 0.0, target.reason)

    if self._killed or self._daily_killed:
        return TargetPosition(target.symbol, 0.0, target.reason + "|risk=daily_kill")

    weight = min(raw, self.max_symbol_weight)
    weight = self._vol_scaled_weight(target.symbol, weight, bar.close)

    weight = self._apply_market_cap(target.symbol, weight, portfolio)
    weight = self._apply_max_positions(target.symbol, weight, portfolio)

    return TargetPosition(target.symbol, max(0.0, weight), target.reason)
```

Market cap:

```python
def _apply_market_cap(
    self,
    symbol: Symbol,
    desired_weight: float,
    portfolio: Portfolio,
) -> float:
    cap = self.max_market_weight.get(symbol.market)
    if cap is None:
        return desired_weight

    current_market = portfolio.market_weight(symbol.market)
    current_symbol = portfolio.position_weight(symbol)

    # Existing symbol weight can be replaced by the new target.
    available_for_symbol = cap - (current_market - current_symbol)

    return min(desired_weight, max(0.0, available_for_symbol))
```

Max positions:

```python
def _apply_max_positions(
    self,
    symbol: Symbol,
    desired_weight: float,
    portfolio: Portfolio,
) -> float:
    if self.max_positions is None:
        return desired_weight

    already_open = portfolio.position(symbol) != 0
    if already_open:
        return desired_weight

    if portfolio.open_position_count() >= self.max_positions:
        return 0.0

    return desired_weight
```

**E. Determinism Rules**
Keep these hard rules:

1. No wall clock. Day comes only from `bar.ts.date()`.
2. No random.
3. No IO inside risk.
4. No broker/API/database reads inside risk.
5. ATR state is updated only from received `BarEvent`s, in received order.
6. Equity comes only from the passed `Portfolio` state.
7. Use stable keys: `(symbol.market.value, symbol.ticker)`.
8. Do not use unordered iteration for decisions unless sorted first.
9. Same bar stream + same fills + same initial portfolio + same config must produce same targets/orders.
10. In tests, replay identical bars through backtest/live paths and compare emitted `OrderEvent`s.

One subtle point: daily loss kill should be checked after marking the current bar. That means the bar that causes the drawdown can immediately force the current symbol flat and block entries afterward. That is deterministic and consistent between backtest and live as long as both paths feed closed daily bars in the same order.
tokens used
6,961

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
