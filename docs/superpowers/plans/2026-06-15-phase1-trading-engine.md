# Phase 1 Trading Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 백테스트와 KIS 모의투자가 **정확히 같은 신호·판단 코드경로**를 타는, 신호 융합 기반 일봉 자동매매 엔진의 작동하는 뼈대를 만든다.

**Architecture:** 이벤트 드리븐 단일 스레드 루프. 전략(`FusionEngine`)은 모드를 모르고 `BarEvent`만 소비해 `OrderEvent`를 낸다. 백테스트/모의투자의 차이는 `DataFeed`와 `ExecutionHandler` 어댑터 교체뿐. 체결은 **다음 봉 시가**에 실현(룩어헤드 차단).

**Tech Stack:** Python 3.11+, pytest, numpy, pydantic v2, pyarrow/parquet, httpx, structlog, rich. 백테스트 프레임워크(backtrader/zipline/vectorbt) **금지** — 제2 코드경로 방지.

**설계 근거:** `docs/superpowers/specs/2026-06-15-phase1-trading-engine-design.md` + Claude/Codex 교차검증 빌드순서(`.omc/artifacts/ask/codex-...2026-06-15T06-23-35-210Z.md`).

**핵심 계약 (전 태스크 공통, 이름 고정):**
- `ExecutionHandler.submit_order(order) -> None` (큐잉) / `.on_bar(bar) -> list[FillEvent]` (해당 봉 **시가**에 체결).
- 엔진 루프 순서: `execution.on_bar(bar)`(전일 주문 체결) → `portfolio.apply_fill` → `portfolio.mark(bar)` → `strategy.on_bar(bar)`(종가 판단) → `execution.submit_order`(다음 봉 대기).
- 통화: 포트폴리오는 통화별 현금 버킷, 평가액은 **KRW 기준**(`FxRates.to_krw`).
- 주식 수량은 **정수**, 포지션 **롱/현금만**.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `trader/core/events.py` | 불변 이벤트/값 객체 + 검증 |
| `trader/core/clock.py` | 결정적 시계 추상 |
| `trader/data/interfaces.py` | `DataFeed` 프로토콜 |
| `trader/data/historical_feed.py` | `InMemoryDailyFeed` |
| `trader/data/calendar.py` | 최소 거래일 시퀀스 |
| `trader/data/storage.py` | parquet 적재/조회 |
| `trader/data/recorder.py` | 라이브 이벤트 녹화 |
| `trader/data/kis_live_feed.py` | KIS 일봉 → BarEvent |
| `trader/signals/interfaces.py` | `SignalSource` 프로토콜 |
| `trader/signals/technical.py` | MA/RSI/MACD/Bollinger 소스 |
| `trader/strategy/portfolio.py` | 포지션·통화별 현금·FX 평가 |
| `trader/strategy/risk.py` | 사이징·한도·킬스위치 |
| `trader/strategy/order_factory.py` | 목표비중 → 정수 주문 델타 |
| `trader/strategy/fusion_engine.py` | 신호 융합·판단(모드 무지) |
| `trader/execution/interfaces.py` | `ExecutionHandler` 프로토콜 |
| `trader/execution/costs.py` | 수수료/슬리피지 |
| `trader/execution/simulated.py` | 시뮬 체결(다음봉 시가) |
| `trader/execution/kis_client.py` | KIS REST 래퍼 |
| `trader/execution/kis_paper.py` | KIS 모의 체결 핸들러 |
| `trader/backtest/engine.py` | 백테스트 루프 |
| `trader/backtest/metrics.py` | 수익률·MDD 등 |
| `trader/backtest/report.py` | 결과 출력 |
| `trader/live/engine.py` | 라이브 루프 |
| `trader/observability/{logging,audit}.py` | 로그·감사추적 |

---

## Task 0: Project scaffold

**Files:**
- Create: `pyproject.toml`, `trader/__init__.py` (+ 빈 `__init__.py` 각 서브패키지), `tests/__init__.py`, `pytest.ini`

- [ ] **Step 1: pyproject.toml 작성**

```toml
[project]
name = "trader"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["numpy", "pydantic>=2", "pyarrow", "httpx", "structlog", "rich"]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: 패키지 디렉터리 생성**

```bash
mkdir -p trader/{core,data,signals,strategy,execution,backtest,live,observability} tests
for d in trader trader/core trader/data trader/signals trader/strategy trader/execution trader/backtest trader/live trader/observability tests; do touch $d/__init__.py; done
```

- [ ] **Step 3: 설치 & sanity**

Run: `python -m pip install -e ".[dev]" && python -c "import trader; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml trader tests
git commit -m "chore: project scaffold for trader package"
```

---

## Task 1: Core events & value objects

**Files:**
- Create: `trader/core/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_events.py
import pytest
from datetime import datetime, timezone
from trader.core.events import Market, Side, Symbol, BarEvent, NormalizedSignal

def _ts(): return datetime(2026, 1, 2, tzinfo=timezone.utc)

def test_symbol_and_bar_are_immutable():
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    bar = BarEvent(sym, _ts(), 10.0, 11.0, 9.5, 10.5, 1000)
    assert bar.is_closed and bar.timeframe == "1d"
    with pytest.raises(Exception):
        bar.close = 99  # frozen

def test_normalized_signal_rejects_out_of_range():
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    with pytest.raises(ValueError):
        NormalizedSignal("technical", sym, _ts(), score=2.0, confidence=0.5, horizon="1d", features={})
    with pytest.raises(ValueError):
        NormalizedSignal("technical", sym, _ts(), score=0.1, confidence=1.5, horizon="1d", features={})

def test_bar_ts_must_be_timezone_aware():
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    with pytest.raises(ValueError):
        BarEvent(sym, datetime(2026, 1, 2), 1, 1, 1, 1, 1)  # naive
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_events.py -v`
Expected: FAIL (`ModuleNotFoundError: trader.core.events`)

- [ ] **Step 3: 구현**

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_events.py -v` → Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add trader/core/events.py tests/test_events.py
git commit -m "feat: core immutable events and value objects with validation"
```

---

## Task 2: Clock & minimal calendar

**Files:**
- Create: `trader/core/clock.py`, `trader/data/calendar.py`
- Test: `tests/test_clock.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_clock.py
from datetime import datetime, timezone
from trader.core.clock import BacktestClock
from trader.data.calendar import trading_days

def test_backtest_clock_returns_injected_time():
    t = datetime(2026, 1, 2, tzinfo=timezone.utc)
    c = BacktestClock(); c.set(t)
    assert c.now() == t

def test_trading_days_are_ordered_and_weekday_only():
    days = trading_days(datetime(2026,1,1,tzinfo=timezone.utc), datetime(2026,1,8,tzinfo=timezone.utc))
    assert days == sorted(days)
    assert all(d.weekday() < 5 for d in days)
```

- [ ] **Step 2: 실패 확인** → Run: `pytest tests/test_clock.py -v` → FAIL

- [ ] **Step 3: 구현**

```python
# trader/core/clock.py
from __future__ import annotations
from datetime import datetime
from typing import Protocol

class Clock(Protocol):
    def now(self) -> datetime: ...

class BacktestClock:
    def __init__(self): self._t: datetime | None = None
    def set(self, t: datetime) -> None: self._t = t
    def now(self) -> datetime:
        if self._t is None: raise RuntimeError("clock not set")
        return self._t
```

```python
# trader/data/calendar.py
from __future__ import annotations
from datetime import datetime, timedelta

def trading_days(start: datetime, end: datetime) -> list[datetime]:
    """주말 제외 일별 시퀀스. (휴장일은 Phase 1 stub — 후속 exchange-calendars로 대체)"""
    out, d = [], start
    while d <= end:
        if d.weekday() < 5: out.append(d)
        d += timedelta(days=1)
    return out
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/core/clock.py trader/data/calendar.py tests/test_clock.py
git commit -m "feat: deterministic backtest clock and minimal trading calendar"
```

---

## Task 3: Adapter interfaces + fakes

**Files:**
- Create: `trader/data/interfaces.py`, `trader/signals/interfaces.py`, `trader/execution/interfaces.py`
- Test: `tests/test_interfaces.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_interfaces.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, OrderEvent, FillEvent, Side
from trader.data.interfaces import DataFeed
from trader.execution.interfaces import ExecutionHandler

SYM = Symbol("AAPL", Market.NASDAQ, "USD")

class FakeFeed:
    def __init__(self, bars): self._bars = bars
    def events(self): return iter(self._bars)

class FakeExec:
    def __init__(self): self.queued = []
    def submit_order(self, order): self.queued.append(order)
    def on_bar(self, bar): return []

def test_fakes_satisfy_protocols():
    bar = BarEvent(SYM, datetime(2026,1,2,tzinfo=timezone.utc),1,1,1,1,1)
    feed: DataFeed = FakeFeed([bar])
    ex: ExecutionHandler = FakeExec()
    assert next(feed.events()) is bar
    ex.submit_order(OrderEvent(uuid4(), SYM, bar.ts, Side.BUY, 1))
    assert ex.on_bar(bar) == [] and len(ex.queued) == 1
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/data/interfaces.py
from __future__ import annotations
from typing import Protocol, Iterator
from trader.core.events import BarEvent

class DataFeed(Protocol):
    def events(self) -> Iterator[BarEvent]:
        """시간순 증가하는 '닫힌' BarEvent를 1개씩 yield. 과거/라이브 동일 계약."""
        ...
```

```python
# trader/signals/interfaces.py
from __future__ import annotations
from typing import Protocol
from trader.core.events import BarEvent, NormalizedSignal

class SignalSource(Protocol):
    name: str
    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
        """닫힌 봉 1개 → 정규화 신호 0/1개. 내부 롤링 상태만, 미래 데이터 접근 금지."""
        ...
```

```python
# trader/execution/interfaces.py
from __future__ import annotations
from typing import Protocol
from trader.core.events import BarEvent, OrderEvent, FillEvent

class ExecutionHandler(Protocol):
    def submit_order(self, order: OrderEvent) -> None:
        """주문 접수/큐잉. 즉시 체결하지 않는다."""
        ...
    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
        """이 봉의 '시가'에 실현된 체결 반환(다음봉 시가 체결 보장). 라이브=확인된 체결 대사."""
        ...
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/data/interfaces.py trader/signals/interfaces.py trader/execution/interfaces.py tests/test_interfaces.py
git commit -m "feat: DataFeed / SignalSource / ExecutionHandler protocols"
```

---

## Task 4: InMemoryDailyFeed

**Files:**
- Create: `trader/data/historical_feed.py`
- Test: `tests/test_historical_feed.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_historical_feed.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.data.historical_feed import InMemoryDailyFeed

def _bar(sym, day, c): 
    t = datetime(2026,1,day,tzinfo=timezone.utc)
    return BarEvent(sym, t, c, c, c, c, 100)

def test_feed_yields_in_timestamp_order_across_symbols():
    a = Symbol("AAPL", Market.NASDAQ, "USD"); k = Symbol("005930", Market.KOSPI, "KRW")
    bars = [_bar(a,3,3),_bar(k,2,2),_bar(a,2,2.5),_bar(k,3,3.5)]
    feed = InMemoryDailyFeed(bars)
    out = list(feed.events())
    assert [b.ts for b in out] == sorted(b.ts for b in out)
    assert len(out) == 4
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/data/historical_feed.py
from __future__ import annotations
from typing import Iterator
from trader.core.events import BarEvent

class InMemoryDailyFeed:
    """메모리 일봉 소스. 타임스탬프 오름차순으로 1개씩 yield.
    (parquet 로딩은 storage.py가 담당, 여기 주입)"""
    def __init__(self, bars: list[BarEvent]):
        self._bars = sorted(bars, key=lambda b: (b.ts, b.symbol.ticker))
    def events(self) -> Iterator[BarEvent]:
        yield from self._bars
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/data/historical_feed.py tests/test_historical_feed.py
git commit -m "feat: in-memory daily historical feed (timestamp-ordered)"
```

---

## Task 5: Cost model

**Files:**
- Create: `trader/execution/costs.py`
- Test: `tests/test_costs.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_costs.py
from trader.execution.costs import BpsCostModel

def test_bps_cost_is_notional_times_bps():
    m = BpsCostModel(bps=5.0)  # 5bp
    assert m.commission(price=100.0, quantity=10) == 100.0*10*0.0005
def test_zero_cost():
    assert BpsCostModel(bps=0.0).commission(123.0, 7) == 0.0
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/execution/costs.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class BpsCostModel:
    """명목가 * bps. 시장별 세금 nuance는 후속 보강(stub)."""
    bps: float = 0.0
    def commission(self, price: float, quantity: int) -> float:
        return price * quantity * (self.bps / 10_000.0)
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/execution/costs.py tests/test_costs.py
git commit -m "feat: bps-based cost model"
```

---

## Task 6: SimulatedExecutionHandler (next-bar-open fills)

**Files:**
- Create: `trader/execution/simulated.py`
- Test: `tests/test_execution_sim.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_execution_sim.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, OrderEvent, Side
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import BpsCostModel

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def bar(day, o): 
    t = datetime(2026,1,day,tzinfo=timezone.utc)
    return BarEvent(SYM, t, open=o, high=o+1, low=o-1, close=o+0.5, volume=100)

def test_order_fills_at_next_bar_open_not_same_bar():
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))
    b1, b2 = bar(2, 10.0), bar(3, 12.0)
    assert ex.on_bar(b1) == []                       # 대기 주문 없음
    ex.submit_order(OrderEvent(uuid4(), SYM, b1.ts, Side.BUY, 5))  # b1 종가 후 주문
    fills = ex.on_bar(b2)                              # 다음 봉
    assert len(fills) == 1
    assert fills[0].price == 12.0                      # b2 '시가'에 체결
    assert fills[0].quantity == 5 and fills[0].side == Side.BUY
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/execution/simulated.py
from __future__ import annotations
from trader.core.events import BarEvent, OrderEvent, FillEvent
from trader.execution.costs import BpsCostModel

class SimulatedExecutionHandler:
    """주문은 큐잉, 체결은 다음 호출되는 on_bar의 '시가'에 실현 → 룩어헤드 구조적 차단."""
    def __init__(self, cost_model: BpsCostModel | None = None):
        self._cost = cost_model or BpsCostModel(0.0)
        self._pending: list[OrderEvent] = []
    def submit_order(self, order: OrderEvent) -> None:
        self._pending.append(order)
    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
        fills: list[FillEvent] = []
        still: list[OrderEvent] = []
        for o in self._pending:
            if o.symbol == bar.symbol:
                price = bar.open
                fills.append(FillEvent(o.order_id, o.symbol, bar.ts, o.side,
                                       o.quantity, price,
                                       self._cost.commission(price, o.quantity),
                                       o.symbol.currency))
            else:
                still.append(o)
        self._pending = still
        return fills
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/execution/simulated.py tests/test_execution_sim.py
git commit -m "feat: simulated execution with next-bar-open fills"
```

---

## Task 7: Portfolio (currency buckets + FX equity)

**Files:**
- Create: `trader/strategy/portfolio.py`
- Test: `tests/test_fx_portfolio.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_fx_portfolio.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, FillEvent, Side
from trader.strategy.portfolio import Portfolio, FxRates

USD = Symbol("AAPL", Market.NASDAQ, "USD")
def _t(): return datetime(2026,1,3,tzinfo=timezone.utc)

def test_equity_in_krw_after_usd_buy_and_mark():
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    p = Portfolio(cash={"KRW": 13_000_000.0}, fx=fx)   # 1300만원, USD현금 0
    # USD 매수 10주 @ $100 → USD 현금 -$1000. KRW 현금에서 환전했다고 가정: 사전 환전 모델
    p.deposit("USD", 2000.0)                            # 테스트 단순화: USD 현금 시드
    p.apply_fill(FillEvent(uuid4(), USD, _t(), Side.BUY, 10, 100.0, 0.0, "USD"))
    assert p.position(USD) == 10
    assert p.cash["USD"] == 1000.0
    p.mark(BarEvent(USD, _t(), 110,110,110,110, 1))     # 종가 $110
    # equity_krw = KRW현금 + USD현금*1300 + 10*110*1300
    assert round(p.equity_krw()) == round(13_000_000 + 1000*1300 + 10*110*1300)
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/strategy/portfolio.py
from __future__ import annotations
from dataclasses import dataclass, field
from trader.core.events import Symbol, BarEvent, FillEvent, Side

@dataclass
class FxRates:
    rates: dict[str, float]            # 통화→KRW 환율 (KRW=1.0)
    def to_krw(self, amount: float, ccy: str) -> float:
        return amount * self.rates[ccy]

class Portfolio:
    def __init__(self, cash: dict[str, float], fx: FxRates):
        self.cash: dict[str, float] = dict(cash)
        self.fx = fx
        self._pos: dict[str, int] = {}          # ticker -> qty
        self._sym: dict[str, Symbol] = {}
        self._mark: dict[str, float] = {}       # ticker -> last close (해당 통화)
    def deposit(self, ccy: str, amount: float) -> None:
        self.cash[ccy] = self.cash.get(ccy, 0.0) + amount
    def position(self, sym: Symbol) -> int:
        return self._pos.get(sym.ticker, 0)
    def apply_fill(self, fill: FillEvent) -> None:
        notional = fill.price * fill.quantity + fill.commission
        sign = 1 if fill.side == Side.BUY else -1
        self.cash[fill.currency] = self.cash.get(fill.currency, 0.0) - sign * (fill.price*fill.quantity) - fill.commission
        self._pos[fill.symbol.ticker] = self._pos.get(fill.symbol.ticker, 0) + sign * fill.quantity
        self._sym[fill.symbol.ticker] = fill.symbol
        self._mark.setdefault(fill.symbol.ticker, fill.price)
    def mark(self, bar: BarEvent) -> None:
        self._mark[bar.symbol.ticker] = bar.close
        self._sym[bar.symbol.ticker] = bar.symbol
    def equity_krw(self) -> float:
        eq = sum(self.fx.to_krw(amt, ccy) for ccy, amt in self.cash.items())
        for tkr, qty in self._pos.items():
            sym = self._sym[tkr]
            eq += self.fx.to_krw(qty * self._mark.get(tkr, 0.0), sym.currency)
        return eq
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/strategy/portfolio.py tests/test_fx_portfolio.py
git commit -m "feat: portfolio with currency buckets and KRW-base FX equity"
```

---

## Task 8: Risk gate

**Files:**
- Create: `trader/strategy/risk.py`
- Test: `tests/test_risk.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_risk.py
from trader.core.events import Symbol, Market, TargetPosition
from trader.strategy.risk import RiskManager

SYM = Symbol("AAPL", Market.NASDAQ, "USD")

def test_clamps_to_max_weight_and_no_short():
    rm = RiskManager(max_symbol_weight=0.3)
    assert rm.size_target(TargetPosition(SYM, 0.9)).target_weight == 0.3   # 클램프
    assert rm.size_target(TargetPosition(SYM, -0.5)).target_weight == 0.0  # 롱/현금만

def test_kill_switch_forces_flat():
    rm = RiskManager(max_symbol_weight=0.3); rm.trip_kill_switch()
    assert rm.size_target(TargetPosition(SYM, 0.9)).target_weight == 0.0
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
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
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/strategy/risk.py tests/test_risk.py
git commit -m "feat: risk gate (max weight, long/cash only, kill switch)"
```

---

## Task 9: OrderFactory (target weight → integer share delta)

**Files:**
- Create: `trader/strategy/order_factory.py`
- Test: `tests/test_order_factory.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_order_factory.py
from datetime import datetime, timezone
from trader.core.events import Symbol, Market, TargetPosition, Side
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.order_factory import OrderFactory

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _t(): return datetime(2026,1,3,tzinfo=timezone.utc)

def test_target_weight_to_integer_buy():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    p = Portfolio(cash={"KRW":13_000_000.0}, fx=fx)   # equity=1300만, 포지션 0
    of = OrderFactory()
    # 목표 50% → 650만원 / (100*1300=13만/주) = 50주
    orders = of.orders_for_target(TargetPosition(SYM, 0.5), p, price=100.0, ts=_t())
    assert len(orders) == 1 and orders[0].side == Side.BUY and orders[0].quantity == 50

def test_no_order_when_delta_zero():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    p = Portfolio(cash={"KRW":0.0}, fx=fx)
    of = OrderFactory()
    assert of.orders_for_target(TargetPosition(SYM, 0.0), p, price=100.0, ts=_t()) == []
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/strategy/order_factory.py
from __future__ import annotations
import math
from datetime import datetime
from uuid import uuid4
from trader.core.events import OrderEvent, Side, TargetPosition
from trader.strategy.portfolio import Portfolio

class OrderFactory:
    """목표비중 → 정수 주식 델타. 가격은 해당 통화, equity는 KRW 기준으로 환산해 사이징."""
    def orders_for_target(self, target: TargetPosition, portfolio: Portfolio,
                          price: float, ts: datetime) -> list[OrderEvent]:
        sym = target.symbol
        price_krw = portfolio.fx.to_krw(price, sym.currency)
        if price_krw <= 0: return []
        target_value_krw = target.target_weight * portfolio.equity_krw()
        target_qty = int(math.floor(target_value_krw / price_krw))
        delta = target_qty - portfolio.position(sym)
        if delta == 0: return []
        side = Side.BUY if delta > 0 else Side.SELL
        return [OrderEvent(uuid4(), sym, ts, side, abs(delta), reason=target.reason)]
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/strategy/order_factory.py tests/test_order_factory.py
git commit -m "feat: order factory converting target weight to integer share delta"
```

---

## Task 10: TechnicalSignalSource — MA crossover (pipeline 증명)

**Files:**
- Create: `trader/signals/technical.py`
- Test: `tests/test_technical_signal.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_technical_signal.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.signals.technical import TechnicalSignalSource

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

def test_warmup_returns_none_until_enough_bars():
    src = TechnicalSignalSource(fast=2, slow=4)
    bars = _bars([1,2,3])
    sigs = [src.on_bar(b) for b in bars]
    assert sigs[-1] is None  # slow window 미충족

def test_uptrend_yields_positive_score():
    src = TechnicalSignalSource(fast=2, slow=4)
    sig = None
    for b in _bars([1,2,3,4,5,6]): sig = src.on_bar(b) or sig
    assert sig is not None and sig.score > 0 and sig.source == "technical"
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현 (Phase 1: MA crossover만, RSI/MACD/BB는 Task 14에서 추가)**

```python
# trader/signals/technical.py
from __future__ import annotations
from collections import deque
from trader.core.events import BarEvent, NormalizedSignal

class TechnicalSignalSource:
    """롤링/증분. 닫힌 봉만 누적 — 미래 데이터 접근 없음. Phase 1: 이동평균 교차."""
    name = "technical"
    def __init__(self, fast: int = 20, slow: int = 50):
        self.fast, self.slow = fast, slow
        self._closes: deque[float] = deque(maxlen=slow)
    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
        self._closes.append(bar.close)
        if len(self._closes) < self.slow:
            return None
        closes = list(self._closes)
        ma_fast = sum(closes[-self.fast:]) / self.fast
        ma_slow = sum(closes) / self.slow
        spread = (ma_fast - ma_slow) / ma_slow if ma_slow else 0.0
        score = max(-1.0, min(1.0, spread * 10.0))  # 정규화
        return NormalizedSignal("technical", bar.symbol, bar.ts,
                                score=score, confidence=0.6, horizon="1d",
                                features={"ma_fast": ma_fast, "ma_slow": ma_slow})
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/signals/technical.py tests/test_technical_signal.py
git commit -m "feat: technical signal source (MA crossover) emitting NormalizedSignal"
```

---

## Task 11: FusionEngine (mode-agnostic)

**Files:**
- Create: `trader/strategy/fusion_engine.py`
- Test: `tests/test_fusion_engine.py`

- [ ] **Step 1: 실패 테스트**

```python
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
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/strategy/fusion_engine.py
from __future__ import annotations
from typing import Sequence
from trader.core.events import BarEvent, OrderEvent, FillEvent, NormalizedSignal, TargetPosition
from trader.signals.interfaces import SignalSource

class FusionEngine:
    """모드 무지. 신호 융합 → 목표비중 → 리스크 → 주문. 브로커/DB/시계 직접 접근 없음."""
    def __init__(self, signal_sources: Sequence[SignalSource], portfolio,
                 risk_manager, order_factory, enter_threshold: float = 0.35,
                 source_weight: dict[str, float] | None = None):
        self.sources = signal_sources
        self.portfolio = portfolio
        self.risk = risk_manager
        self.order_factory = order_factory
        self.enter_threshold = enter_threshold
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
        weight = combined if combined >= self.enter_threshold else 0.0
        sized = self.risk.size_target(TargetPosition(bar.symbol, weight, reason=f"combined={combined:.2f}"))
        return self.order_factory.orders_for_target(sized, self.portfolio, price=bar.close, ts=bar.ts)
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/strategy/fusion_engine.py tests/test_fusion_engine.py
git commit -m "feat: mode-agnostic FusionEngine (combine -> risk -> orders)"
```

---

## Task 12: BacktestEngine (end-to-end loop)

**Files:**
- Create: `trader/backtest/engine.py`
- Test: `tests/test_backtest_engine.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_backtest_engine.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.data.historical_feed import InMemoryDailyFeed
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import BpsCostModel
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource
from trader.backtest.engine import BacktestEngine

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

def _wire():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    pf = Portfolio({"KRW":13_000_000.0}, fx)
    eng = FusionEngine([TechnicalSignalSource(2,4)], pf, RiskManager(0.5), OrderFactory(), enter_threshold=0.02)
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))
    return pf, eng, ex

def test_backtest_runs_and_takes_a_position():
    pf, eng, ex = _wire()
    feed = InMemoryDailyFeed(_bars([1,2,3,4,5,6,7,8]))
    BacktestEngine(feed, eng, ex, pf).run()
    assert pf.position(SYM) > 0          # 상승추세에서 매수 진입
    assert pf.equity_krw() > 0
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/backtest/engine.py
from __future__ import annotations
from trader.data.interfaces import DataFeed
from trader.execution.interfaces import ExecutionHandler
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio

class BacktestEngine:
    """표준 이벤트 루프. live/engine.py와 동일한 순서를 따른다 (패리티의 근간)."""
    def __init__(self, feed: DataFeed, strategy: FusionEngine,
                 execution: ExecutionHandler, portfolio: Portfolio, audit=None):
        self.feed, self.strategy, self.execution, self.portfolio = feed, strategy, execution, portfolio
        self.audit = audit
    def run(self) -> None:
        for bar in self.feed.events():
            for fill in self.execution.on_bar(bar):     # 전일 주문을 이 봉 '시가'에 체결
                self.strategy.on_fill(fill)
                if self.audit: self.audit.record_fill(fill)
            self.portfolio.mark(bar)                      # 종가 마킹
            orders = self.strategy.on_bar(bar)            # 종가 판단
            for order in orders:
                self.execution.submit_order(order)        # 다음 봉 대기
                if self.audit: self.audit.record_order(order)
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/backtest/engine.py tests/test_backtest_engine.py
git commit -m "feat: backtest event loop (on_bar fills -> mark -> decide -> queue)"
```

---

## Task 13: ★ Parity harness — backtest == fake-live (불변식 증명)

**Files:**
- Create: `trader/live/engine.py`
- Test: `tests/test_backtest_live_parity.py`

이 태스크가 **#1 원칙의 증명**이다. `LiveEngine`은 `BacktestEngine`과 **글자 그대로 같은 루프 순서**를 쓰되, 피드/실행이 어댑터일 뿐임을 보인다. 가짜 라이브 = 같은 in-memory feed + 같은 simulated execution을 stepwise로.

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_backtest_live_parity.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent, Side
from trader.data.historical_feed import InMemoryDailyFeed
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import BpsCostModel
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource
from trader.backtest.engine import BacktestEngine
from trader.live.engine import LiveEngine

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

class RecordingExec(SimulatedExecutionHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.orders=[]
    def submit_order(self, order):
        self.orders.append((order.side, order.quantity)); super().submit_order(order)

def _wire():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    pf = Portfolio({"KRW":13_000_000.0}, fx)
    eng = FusionEngine([TechnicalSignalSource(2,4)], pf, RiskManager(0.5), OrderFactory(), enter_threshold=0.02)
    ex = RecordingExec(BpsCostModel(0.0))
    return pf, eng, ex

def test_backtest_and_live_produce_identical_orders_and_equity():
    closes = [1,2,3,4,5,6,5,4,5,6,7,8]
    pf1, e1, x1 = _wire(); BacktestEngine(InMemoryDailyFeed(_bars(closes)), e1, x1, pf1).run()
    pf2, e2, x2 = _wire(); LiveEngine(InMemoryDailyFeed(_bars(closes)), e2, x2, pf2).run()
    assert x1.orders == x2.orders                       # 동일 주문 시퀀스
    assert round(pf1.equity_krw()) == round(pf2.equity_krw())  # 동일 최종 자산
```

- [ ] **Step 2: 실패 확인** → FAIL (`trader.live.engine` 없음)

- [ ] **Step 3: 구현 (BacktestEngine과 동일 순서 — 의도적으로 동일)**

```python
# trader/live/engine.py
from __future__ import annotations
from trader.data.interfaces import DataFeed
from trader.execution.interfaces import ExecutionHandler
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio

class LiveEngine:
    """라이브 루프. BacktestEngine과 동일한 이벤트 처리 순서 — 이것이 패리티의 근간.
    실거래에서는 feed=KIS라이브, execution=KIS페이퍼로만 바뀐다."""
    def __init__(self, feed: DataFeed, strategy: FusionEngine,
                 execution: ExecutionHandler, portfolio: Portfolio,
                 audit=None, recorder=None):
        self.feed, self.strategy, self.execution, self.portfolio = feed, strategy, execution, portfolio
        self.audit, self.recorder = audit, recorder
    def run(self) -> None:
        for bar in self.feed.events():
            if self.recorder: self.recorder.record_bar(bar)
            for fill in self.execution.on_bar(bar):
                self.strategy.on_fill(fill)
                if self.audit: self.audit.record_fill(fill)
            self.portfolio.mark(bar)
            for order in self.strategy.on_bar(bar):
                self.execution.submit_order(order)
                if self.audit: self.audit.record_order(order)
```

- [ ] **Step 4: 통과 확인** → PASS — **이 시점에서 백테스트=실거래 코드경로가 증명됨**
- [ ] **Step 5: Commit**

```bash
git add trader/live/engine.py tests/test_backtest_live_parity.py
git commit -m "feat: live engine + backtest/live parity test (proves single code path)"
```

---

## Task 14: 지표 보강 (RSI/MACD/Bollinger) + no-lookahead 테스트

**Files:**
- Modify: `trader/signals/technical.py`
- Test: `tests/test_no_lookahead.py`, `tests/test_technical_indicators.py`

- [ ] **Step 1: 실패 테스트 (룩어헤드 + 추가 지표)**

```python
# tests/test_no_lookahead.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.signals.technical import TechnicalSignalSource

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

def test_signal_at_bar_t_unaffected_by_future_bars():
    """봉 t에서의 신호는 t 이후 봉을 추가로 줘도 동일해야 한다 (증분/롤링 보장)."""
    closes = [1,2,3,4,5,6,7,8,9,10]
    a = TechnicalSignalSource(3,6); b = TechnicalSignalSource(3,6)
    bars = _bars(closes)
    sig_a = None
    for bar in bars[:7]: sig_a = a.on_bar(bar) or sig_a
    sig_b = None
    for bar in bars: sig_b_t7 = b.on_bar(bar);  sig_b = sig_b_t7 if bar is bars[6] else sig_b
    # 7번째 봉까지 본 a의 마지막 신호 == 전체를 본 b가 7번째 봉에서 낸 신호
    assert sig_a is not None and sig_b is not None
    assert abs(sig_a.score - sig_b.score) < 1e-9
```

```python
# tests/test_technical_indicators.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.signals.technical import TechnicalSignalSource

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def test_features_include_rsi_macd_bollinger():
    src = TechnicalSignalSource(3,6)
    t0 = datetime(2026,1,1,tzinfo=timezone.utc); sig=None
    for i,c in enumerate([1,2,1,3,2,4,3,5,4,6,5,7]):
        sig = src.on_bar(BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100)) or sig
    assert sig is not None
    for k in ("rsi","macd_hist","bb_pos"): assert k in sig.features
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현 (technical.py 확장 — 합성 점수)**

```python
# trader/signals/technical.py  (전체 교체)
from __future__ import annotations
from collections import deque
import numpy as np
from trader.core.events import BarEvent, NormalizedSignal

def _rsi(closes: list[float], n: int = 14) -> float:
    if len(closes) < n + 1: return 50.0
    d = np.diff(closes[-(n+1):])
    up = d[d > 0].sum() / n; dn = -d[d < 0].sum() / n
    if dn == 0: return 100.0
    rs = up / dn
    return 100.0 - 100.0 / (1.0 + rs)

def _ema(vals: list[float], n: int) -> float:
    k = 2.0 / (n + 1); e = vals[0]
    for v in vals[1:]: e = v * k + e * (1 - k)
    return e

class TechnicalSignalSource:
    """롤링/증분, 닫힌 봉만. MA 교차 + RSI + MACD + Bollinger 합성."""
    name = "technical"
    def __init__(self, fast: int = 20, slow: int = 50):
        self.fast, self.slow = fast, slow
        self._closes: deque[float] = deque(maxlen=max(slow, 60))
    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
        self._closes.append(bar.close)
        if len(self._closes) < self.slow: return None
        c = list(self._closes)
        ma_fast = sum(c[-self.fast:]) / self.fast
        ma_slow = sum(c[-self.slow:]) / self.slow
        ma_score = max(-1.0, min(1.0, ((ma_fast - ma_slow) / ma_slow if ma_slow else 0.0) * 10))
        rsi = _rsi(c); rsi_score = max(-1.0, min(1.0, (rsi - 50.0) / 50.0))
        macd_hist = _ema(c, 12) - _ema(c, 26)
        macd_score = max(-1.0, min(1.0, macd_hist / (ma_slow or 1.0) * 10))
        window = c[-self.fast:]; mean = sum(window)/len(window)
        std = (sum((x-mean)**2 for x in window)/len(window)) ** 0.5
        bb_pos = (bar.close - mean) / (2*std) if std else 0.0
        bb_score = max(-1.0, min(1.0, bb_pos))
        score = float(np.clip(np.mean([ma_score, rsi_score, macd_score, bb_score]), -1.0, 1.0))
        return NormalizedSignal("technical", bar.symbol, bar.ts, score=score, confidence=0.6,
                                horizon="1d",
                                features={"ma_fast":ma_fast,"ma_slow":ma_slow,"rsi":rsi,
                                          "macd_hist":macd_hist,"bb_pos":bb_pos})
```

- [ ] **Step 4: 통과 확인** → Run: `pytest tests/test_no_lookahead.py tests/test_technical_indicators.py tests/test_backtest_live_parity.py -v` → PASS (패리티 회귀 없음 확인)
- [ ] **Step 5: Commit**

```bash
git add trader/signals/technical.py tests/test_no_lookahead.py tests/test_technical_indicators.py
git commit -m "feat: add RSI/MACD/Bollinger to technical source + no-lookahead test"
```

---

## Task 15: Audit & logging

**Files:**
- Create: `trader/observability/audit.py`, `trader/observability/logging.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_audit.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, OrderEvent, FillEvent, Side
from trader.observability.audit import InMemoryAudit

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _t(): return datetime(2026,1,3,tzinfo=timezone.utc)

def test_audit_records_orders_and_fills_in_order():
    a = InMemoryAudit()
    a.record_order(OrderEvent(uuid4(), SYM, _t(), Side.BUY, 5))
    a.record_fill(FillEvent(uuid4(), SYM, _t(), Side.BUY, 5, 10.0, 0.0, "USD"))
    kinds = [r["kind"] for r in a.records]
    assert kinds == ["order", "fill"]
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/observability/logging.py
from __future__ import annotations
import structlog
def get_logger(name: str = "trader"):
    return structlog.get_logger(name)
```

```python
# trader/observability/audit.py
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from trader.core.events import OrderEvent, FillEvent

def _row(kind, ev):
    d = {"kind": kind, "ts": ev.ts.isoformat(), "ticker": ev.symbol.ticker,
         "side": ev.side.value, "qty": ev.quantity}
    if isinstance(ev, FillEvent): d["price"] = ev.price; d["commission"] = ev.commission
    return d

class InMemoryAudit:
    """결정 재생에 충분한 순서 보존 추적. 영속 백엔드는 storage가 담당(후속)."""
    def __init__(self): self.records: list[dict] = []
    def record_order(self, o: OrderEvent) -> None: self.records.append(_row("order", o))
    def record_fill(self, f: FillEvent) -> None: self.records.append(_row("fill", f))
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/observability/audit.py trader/observability/logging.py tests/test_audit.py
git commit -m "feat: in-memory audit trail and structlog logger"
```

---

## Task 16: Metrics & report

**Files:**
- Create: `trader/backtest/metrics.py`, `trader/backtest/report.py`
- Test: `tests/test_metrics.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_metrics.py
from trader.backtest.metrics import total_return, max_drawdown

def test_total_return():
    assert round(total_return([100, 110]), 4) == 0.10
def test_max_drawdown():
    assert round(max_drawdown([100, 120, 90, 110]), 4) == round((90-120)/120, 4)
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/backtest/metrics.py
from __future__ import annotations

def total_return(equity_curve: list[float]) -> float:
    if len(equity_curve) < 2 or equity_curve[0] == 0: return 0.0
    return equity_curve[-1] / equity_curve[0] - 1.0

def max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]; mdd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak: mdd = min(mdd, (v - peak) / peak)
    return mdd
```

```python
# trader/backtest/report.py
from __future__ import annotations
from rich.console import Console
from trader.backtest.metrics import total_return, max_drawdown

def print_report(equity_curve: list[float], final_equity_krw: float) -> dict:
    stats = {"total_return": total_return(equity_curve),
             "max_drawdown": max_drawdown(equity_curve),
             "final_equity_krw": final_equity_krw}
    Console().print(stats)
    return stats
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/backtest/metrics.py trader/backtest/report.py tests/test_metrics.py
git commit -m "feat: backtest metrics (return, drawdown) and report"
```

---

## Task 17: Storage + recorder + replay-parity (보강 #1)

**Files:**
- Create: `trader/data/storage.py`, `trader/data/recorder.py`
- Test: `tests/test_replay_parity.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_replay_parity.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.data.historical_feed import InMemoryDailyFeed
from trader.data.recorder import BarRecorder
from trader.data.storage import save_bars, load_bars

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c+1,c-1,c+0.5,100) for i,c in enumerate(closes)]

def test_recorded_bars_roundtrip_identical(tmp_path):
    rec = BarRecorder()
    for b in _bars([1,2,3,4]): rec.record_bar(b)
    p = tmp_path / "rec.parquet"
    save_bars(rec.bars, str(p))
    loaded = load_bars(str(p))
    # 재적재한 봉으로 만든 feed가 원본과 동일한 시퀀스를 낸다
    assert [(b.symbol.ticker, b.ts, b.close) for b in InMemoryDailyFeed(loaded).events()] == \
           [(b.symbol.ticker, b.ts, b.close) for b in InMemoryDailyFeed(rec.bars).events()]
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/data/recorder.py
from __future__ import annotations
from trader.core.events import BarEvent

class BarRecorder:
    """라이브 세션 봉 스트림 녹화 → 후일 백테스트로 재생(비트단위 패리티 검증)."""
    def __init__(self): self.bars: list[BarEvent] = []
    def record_bar(self, bar: BarEvent) -> None: self.bars.append(bar)
```

```python
# trader/data/storage.py
from __future__ import annotations
import pyarrow as pa, pyarrow.parquet as pq
from datetime import datetime, timezone
from trader.core.events import BarEvent, Symbol, Market

def save_bars(bars: list[BarEvent], path: str) -> None:
    cols = {k: [] for k in ("ticker","market","currency","ts","open","high","low","close","volume","timeframe")}
    for b in bars:
        cols["ticker"].append(b.symbol.ticker); cols["market"].append(b.symbol.market.value)
        cols["currency"].append(b.symbol.currency); cols["ts"].append(b.ts.isoformat())
        cols["open"].append(b.open); cols["high"].append(b.high); cols["low"].append(b.low)
        cols["close"].append(b.close); cols["volume"].append(b.volume); cols["timeframe"].append(b.timeframe)
    pq.write_table(pa.table(cols), path)

def load_bars(path: str) -> list[BarEvent]:
    t = pq.read_table(path).to_pylist()
    out = []
    for r in t:
        sym = Symbol(r["ticker"], Market(r["market"]), r["currency"])
        ts = datetime.fromisoformat(r["ts"])
        if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
        out.append(BarEvent(sym, ts, r["open"], r["high"], r["low"], r["close"], r["volume"], r["timeframe"]))
    return out
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/data/storage.py trader/data/recorder.py tests/test_replay_parity.py
git commit -m "feat: parquet storage + bar recorder + replay parity test"
```

---

## Task 18: KisClient (mocked HTTP)

**Files:**
- Create: `trader/execution/kis_client.py`
- Test: `tests/test_kis_client.py`

KIS 자격증명 없이 테스트 가능하도록 `httpx.MockTransport` 사용. 국내/해외 차이는 이 클래스 내부에 격리.

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_kis_client.py
import httpx
from trader.execution.kis_client import KisClient

def _mock(handler): return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://mock")

def test_daily_bars_normalize_for_nasdaq_and_kospi():
    def handler(req):
        return httpx.Response(200, json={"output":[{"date":"20260102","open":"10","high":"11","low":"9","close":"10.5","volume":"100"}]})
    c = KisClient(client=_mock(handler), app_key="k", app_secret="s", account="acct", paper=True)
    bars = c.daily_bars(ticker="AAPL", market="NASDAQ", currency="USD")
    assert len(bars) == 1 and bars[0].close == 10.5 and bars[0].symbol.currency == "USD"
    bars_kr = c.daily_bars(ticker="005930", market="KOSPI", currency="KRW")
    assert bars_kr[0].symbol.currency == "KRW"
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현 (Phase 1: 일봉 조회 + 주문 제출/조회 시그니처. 실제 엔드포인트/TR_ID는 KIS 문서 기준으로 채움)**

```python
# trader/execution/kis_client.py
from __future__ import annotations
from datetime import datetime, timezone
import httpx
from trader.core.events import BarEvent, Symbol, Market

class KisClient:
    """KIS REST 래퍼. 국내/해외 차이(엔드포인트·호가단위·통화·TR_ID)를 이 안에 격리.
    외부에는 표준 BarEvent / 주문 인터페이스만 노출."""
    def __init__(self, client: httpx.Client, app_key: str, app_secret: str, account: str, paper: bool = True):
        self._c = client; self.app_key = app_key; self.app_secret = app_secret
        self.account = account; self.paper = paper
    def _parse_bar(self, row: dict, sym: Symbol) -> BarEvent:
        ts = datetime.strptime(row["date"], "%Y%m%d").replace(tzinfo=timezone.utc)
        return BarEvent(sym, ts, float(row["open"]), float(row["high"]), float(row["low"]),
                        float(row["close"]), int(float(row["volume"])))
    def daily_bars(self, ticker: str, market: str, currency: str) -> list[BarEvent]:
        sym = Symbol(ticker, Market(market), currency)
        path = "/overseas/daily" if market == "NASDAQ" else "/domestic/daily"  # 실제 KIS 경로로 교체
        r = self._c.get(path, params={"symbol": ticker})
        r.raise_for_status()
        return [self._parse_bar(row, sym) for row in r.json()["output"]]
    def submit_order(self, ticker: str, market: str, side: str, quantity: int) -> str:
        path = "/overseas/order" if market == "NASDAQ" else "/domestic/order"  # 실제 KIS 경로로 교체
        r = self._c.post(path, json={"symbol": ticker, "side": side, "qty": quantity})
        r.raise_for_status()
        return r.json().get("order_id", "")
    def filled_orders(self) -> list[dict]:
        r = self._c.get("/orders/filled"); r.raise_for_status()
        return r.json().get("output", [])
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/execution/kis_client.py tests/test_kis_client.py
git commit -m "feat: KIS REST client wrapper (mocked) normalizing domestic/overseas bars"
```

---

## Task 19: KisLiveFeed (mocked)

**Files:**
- Create: `trader/data/kis_live_feed.py`
- Test: `tests/test_kis_live_feed.py`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_kis_live_feed.py
from trader.data.kis_live_feed import KisLiveFeed
from trader.core.events import BarEvent

class FakeKis:
    def daily_bars(self, ticker, market, currency):
        from datetime import datetime, timezone
        return [BarEvent(__import__("trader.core.events", fromlist=["Symbol"]).Symbol(ticker, __import__("trader.core.events", fromlist=["Market"]).Market(market), currency),
                         datetime(2026,1,2,tzinfo=timezone.utc), 1,1,1,1,1)]

def test_live_feed_yields_canonical_bars():
    feed = KisLiveFeed(FakeKis(), [("AAPL","NASDAQ","USD")])
    bars = list(feed.events())
    assert len(bars) == 1 and isinstance(bars[0], BarEvent)
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/data/kis_live_feed.py
from __future__ import annotations
from typing import Iterator
from trader.core.events import BarEvent

class KisLiveFeed:
    """KIS 일봉을 표준 BarEvent로. Phase 1은 '최신 닫힌 일봉' 폴링 모델.
    (실거래에서는 장 마감 후 1회/스케줄 폴링; 인트라데이/웹소켓은 후속)"""
    def __init__(self, kis_client, symbols: list[tuple[str, str, str]]):
        self._kis = kis_client; self._symbols = symbols
    def events(self) -> Iterator[BarEvent]:
        bars: list[BarEvent] = []
        for ticker, market, currency in self._symbols:
            bars.extend(self._kis.daily_bars(ticker, market, currency))
        for b in sorted(bars, key=lambda x: (x.ts, x.symbol.ticker)):
            yield b
```

- [ ] **Step 4: 통과 확인** → PASS
- [ ] **Step 5: Commit**

```bash
git add trader/data/kis_live_feed.py tests/test_kis_live_feed.py
git commit -m "feat: KIS live data feed yielding canonical bars"
```

---

## Task 20: KisPaperExecutionHandler (mocked) + run scripts

**Files:**
- Create: `trader/execution/kis_paper.py`, `trader/app/config.py`, `trader/app/run_backtest.py`, `trader/app/run_paper.py`
- Test: `tests/test_kis_paper.py`

`KisPaperExecutionHandler`는 `submit_order`(KIS 제출)/`on_bar`(확인된 체결만 `FillEvent`로 대사) 계약을 따른다 — **시뮬과 동일 인터페이스**라 `FusionEngine`/엔진은 그대로.

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_kis_paper.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, OrderEvent, Side
from trader.execution.kis_paper import KisPaperExecutionHandler

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _t(d=2): return datetime(2026,1,d,tzinfo=timezone.utc)

class FakeKis:
    def __init__(self): self.submitted=[]; self._fill_next=False
    def submit_order(self, ticker, market, side, quantity):
        self.submitted.append((ticker, side, quantity)); self._fill_next=True; return "OID1"
    def filled_orders(self):
        if self._fill_next:
            self._fill_next=False
            return [{"order_id":"OID1","ticker":"AAPL","market":"NASDAQ","currency":"USD",
                     "side":"BUY","qty":5,"price":12.0,"commission":0.1}]
        return []

def test_submit_then_reconcile_fill_on_next_bar():
    kis = FakeKis(); ex = KisPaperExecutionHandler(kis)
    assert ex.on_bar(BarEvent(SYM,_t(2),10,10,10,10,1)) == []
    ex.submit_order(OrderEvent(uuid4(), SYM, _t(2), Side.BUY, 5))
    assert kis.submitted == [("AAPL","BUY",5)]
    fills = ex.on_bar(BarEvent(SYM,_t(3),12,12,12,12,1))
    assert len(fills)==1 and fills[0].price==12.0 and fills[0].quantity==5
```

- [ ] **Step 2: 실패 확인** → FAIL

- [ ] **Step 3: 구현**

```python
# trader/execution/kis_paper.py
from __future__ import annotations
from uuid import UUID, uuid4
from trader.core.events import BarEvent, OrderEvent, FillEvent, Symbol, Market, Side

class KisPaperExecutionHandler:
    """KIS 모의투자 실행. submit_order=KIS 제출, on_bar=확인된 체결만 FillEvent로 대사.
    주문 제출 != 체결 — 포트폴리오는 확인 체결로만 갱신."""
    def __init__(self, kis_client):
        self._kis = kis_client
    def submit_order(self, order: OrderEvent) -> None:
        self._kis.submit_order(order.symbol.ticker, order.symbol.market.value,
                               order.side.value, order.quantity)
    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
        out: list[FillEvent] = []
        for f in self._kis.filled_orders():
            sym = Symbol(f["ticker"], Market(f["market"]), f["currency"])
            out.append(FillEvent(uuid4(), sym, bar.ts, Side(f["side"]), int(f["qty"]),
                                 float(f["price"]), float(f["commission"]), f["currency"]))
        return out
```

```python
# trader/app/config.py
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    kis_app_key: str; kis_app_secret: str; kis_account: str; paper: bool = True
    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(os.environ["KIS_APP_KEY"], os.environ["KIS_APP_SECRET"],
                   os.environ["KIS_ACCOUNT"], os.environ.get("KIS_PAPER","1")=="1")
```

```python
# trader/app/run_backtest.py
from __future__ import annotations
from trader.data.storage import load_bars
from trader.data.historical_feed import InMemoryDailyFeed
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import BpsCostModel
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource
from trader.backtest.engine import BacktestEngine
from trader.backtest.report import print_report

def main(parquet_path: str) -> None:
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    pf = Portfolio({"KRW":10_000_000.0}, fx)
    eng = FusionEngine([TechnicalSignalSource(20,50)], pf, RiskManager(0.3), OrderFactory())
    ex = SimulatedExecutionHandler(BpsCostModel(5.0))
    curve: list[float] = []
    feed = InMemoryDailyFeed(load_bars(parquet_path))
    class _Track(BacktestEngine):
        def run(self):
            for bar in self.feed.events():
                for fill in self.execution.on_bar(bar): self.strategy.on_fill(fill)
                self.portfolio.mark(bar)
                for o in self.strategy.on_bar(bar): self.execution.submit_order(o)
                curve.append(self.portfolio.equity_krw())
    _Track(feed, eng, ex, pf).run()
    print_report(curve, pf.equity_krw())

if __name__ == "__main__":
    import sys; main(sys.argv[1])
```

```python
# trader/app/run_paper.py
from __future__ import annotations
import httpx
from trader.app.config import AppConfig
from trader.execution.kis_client import KisClient
from trader.data.kis_live_feed import KisLiveFeed
from trader.execution.kis_paper import KisPaperExecutionHandler
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource
from trader.live.engine import LiveEngine
from trader.data.recorder import BarRecorder

def main() -> None:
    cfg = AppConfig.from_env()
    kis = KisClient(httpx.Client(base_url="https://openapivts.koreainvestment.com:29443"),
                    cfg.kis_app_key, cfg.kis_app_secret, cfg.kis_account, paper=True)
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    pf = Portfolio({"KRW":10_000_000.0}, fx)
    eng = FusionEngine([TechnicalSignalSource(20,50)], pf, RiskManager(0.3), OrderFactory())
    feed = KisLiveFeed(kis, [("AAPL","NASDAQ","USD"), ("005930","KOSPI","KRW")])
    LiveEngine(feed, eng, KisPaperExecutionHandler(kis), pf, recorder=BarRecorder()).run()

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 통과 확인** → Run: `pytest -q` (전체) → ALL PASS
- [ ] **Step 5: Commit**

```bash
git add trader/execution/kis_paper.py trader/app tests/test_kis_paper.py
git commit -m "feat: KIS paper execution handler + run_backtest/run_paper entrypoints"
```

---

## Definition of Done (Phase 1) — 검증 체크리스트

- [ ] `pytest -q` 전체 통과 (특히 `test_backtest_live_parity`, `test_replay_parity`, `test_no_lookahead`).
- [ ] `run_backtest.py`가 parquet 일봉으로 백테스트→수익률/MDD 리포트 출력.
- [ ] `run_paper.py`가 (자격증명 주입 시) KIS 모의계좌에 주문→체결 대사→포트폴리오 반영.
- [ ] `FusionEngine` 생성 코드가 백테스트/라이브에서 글자 그대로 동일.
- [ ] 기술지표(MA/RSI/MACD/Bollinger)가 `NormalizedSignal` 방출.
- [ ] KRW 기준 통화별 포트폴리오 평가 + 킬스위치 동작.

---

## Self-Review 결과 (작성자 점검)

- **Spec 커버리지:** §3 모듈 → Task 0~20 전부 매핑. §6 정규화신호 → Task 1/10/11. §8 FX → Task 7. §9 녹화재생 → Task 17. §10 함정 5개 → Task 6(룩어헤드)/13(분기)/17(라이브≠과거)/18(KIS격리)/20(체결대사). 갭 없음.
- **Placeholder 스캔:** "실제 KIS 경로로 교체"는 의도적 외부 의존(KIS 문서값) 표기 — 코드는 동작하는 mock 기반으로 완결. 그 외 TBD/TODO 없음.
- **타입 일관성:** `ExecutionHandler`는 전 태스크에서 `submit_order(order)->None` + `on_bar(bar)->list[FillEvent]` 통일. `TargetPosition`, `NormalizedSignal(score,confidence)`, `Portfolio.equity_krw()`, `OrderFactory.orders_for_target(target, portfolio, price, ts)` 시그니처 전 태스크 일치 확인.
- **순서 함정 회피:** 체결 시맨틱(Task6) → 엔진(Task12) → 패리티(Task13) → KIS(Task18~20). codex 지적 3대 함정 모두 순서로 방지.
