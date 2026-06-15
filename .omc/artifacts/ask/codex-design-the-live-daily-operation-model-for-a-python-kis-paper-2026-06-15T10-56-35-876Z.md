# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-06-15T10:56:35.878Z

## Original task

Design the LIVE DAILY OPERATION model for a Python KIS paper-trading system. Current state: a single in-memory event loop replays bars from a feed; KisLiveFeed.daily_bars returns the most-recent ~100 historical daily bars per symbol. PROBLEM: if we run the live engine over those, it replays history and submits a REAL order on every historical bar — wrong.

I need the correct once-per-day operation model. Address concretely with signatures/sketch:

1. WARM-UP vs ACT: the strategy/signal sources need history to warm indicators, but we must submit orders ONLY for the latest bar (today's close), once. How to structure this cleanly given the existing FusionEngine.on_bar(bar)->orders and engines that loop feed→fills→mark→on_bar→submit? Proposal: a 'warmup' replay that feeds all-but-last bars through signal sources WITHOUT submitting orders, then process only the final bar for the real order. What's the cleanest implementation that does NOT duplicate the strategy decision logic and keeps determinism for the parts that are deterministic?

2. PORTFOLIO SYNC: each daily run is a fresh process, so the in-memory Portfolio must be initialized from the ACTUAL KIS account (cash + positions) via a balance inquiry, not from a hardcoded 10M KRW. Which KIS paper endpoints/TR_IDs for overseas (US) balance and domestic (KOSPI) balance? How to map them into the existing Portfolio (cash buckets keyed... actually KRW-settled; positions keyed by (market,ticker))? 

3. IDEMPOTENCY/SCHEDULING: running once per trading day. How to avoid double-submitting if the script runs twice the same day? (e.g., check existing open orders / a local run-marker keyed by trading date). And how to schedule (cron after each market close — note US and KR have different close times/timezones).

4. ORDER PRICE for daily: we submit after close for next session. Market order vs limit at last close? KIS paper overseas may only support limit. Recommend.

5. What can be verified RIGHT NOW with markets CLOSED (read-only balance/bars + order acceptance) vs what needs market hours.

Terse, senior, concrete signatures. Reference KIS TR_IDs where known (paper, V-prefix).

## Final prompt

Design the LIVE DAILY OPERATION model for a Python KIS paper-trading system. Current state: a single in-memory event loop replays bars from a feed; KisLiveFeed.daily_bars returns the most-recent ~100 historical daily bars per symbol. PROBLEM: if we run the live engine over those, it replays history and submits a REAL order on every historical bar — wrong.

I need the correct once-per-day operation model. Address concretely with signatures/sketch:

1. WARM-UP vs ACT: the strategy/signal sources need history to warm indicators, but we must submit orders ONLY for the latest bar (today's close), once. How to structure this cleanly given the existing FusionEngine.on_bar(bar)->orders and engines that loop feed→fills→mark→on_bar→submit? Proposal: a 'warmup' replay that feeds all-but-last bars through signal sources WITHOUT submitting orders, then process only the final bar for the real order. What's the cleanest implementation that does NOT duplicate the strategy decision logic and keeps determinism for the parts that are deterministic?

2. PORTFOLIO SYNC: each daily run is a fresh process, so the in-memory Portfolio must be initialized from the ACTUAL KIS account (cash + positions) via a balance inquiry, not from a hardcoded 10M KRW. Which KIS paper endpoints/TR_IDs for overseas (US) balance and domestic (KOSPI) balance? How to map them into the existing Portfolio (cash buckets keyed... actually KRW-settled; positions keyed by (market,ticker))? 

3. IDEMPOTENCY/SCHEDULING: running once per trading day. How to avoid double-submitting if the script runs twice the same day? (e.g., check existing open orders / a local run-marker keyed by trading date). And how to schedule (cron after each market close — note US and KR have different close times/timezones).

4. ORDER PRICE for daily: we submit after close for next session. Market order vs limit at last close? KIS paper overseas may only support limit. Recommend.

5. What can be verified RIGHT NOW with markets CLOSED (read-only balance/bars + order acceptance) vs what needs market hours.

Terse, senior, concrete signatures. Reference KIS TR_IDs where known (paper, V-prefix).

## Raw output

```text
**Model**
Do not run [LiveEngine.run](/Users/manager/side/makemoney/trader/live/engine.py:14) against `KisLiveFeed.events()` for daily live trading. That method is a replay loop. Daily live needs a separate “warm history, act latest bar only” runner.

```python
@dataclass(frozen=True)
class AccountSnapshot:
    asof: datetime
    cash: dict[str, float]              # keep current engine: {"KRW": ...}
    positions: dict[tuple[str, str], int]  # (market, ticker) -> qty
    marks: dict[tuple[str, str], float]
    fx: dict[str, float]                # {"KRW": 1.0, "USD": usdk_rw}
```

**1. Warm-Up vs Act**
Refactor [FusionEngine.on_bar](/Users/manager/side/makemoney/trader/strategy/fusion_engine.py:29) into observe/decide. Warm-up updates deterministic state, but never calls `order_factory`.

```python
class FusionEngine:
    def observe_bar(self, bar: BarEvent) -> list[NormalizedSignal]:
        self.risk.on_bar(bar, self.portfolio)
        return [s for src in self.sources if (s := src.on_bar(bar)) is not None]

    def decide_orders(
        self, bar: BarEvent, signals: list[NormalizedSignal]
    ) -> list[OrderEvent]:
        combined = self._combine(signals)
        if combined >= self.enter_threshold:
            weight = combined
        elif combined <= self.exit_threshold:
            weight = 0.0
        else:
            return []
        target = TargetPosition(bar.symbol, weight, reason=f"combined={combined:.2f}")
        sized = self.risk.size_target(target, self.portfolio, bar)
        return self.order_factory.orders_for_target(
            sized, self.portfolio, price=bar.close, ts=bar.ts
        )

    def warmup_bar(self, bar: BarEvent) -> None:
        self.observe_bar(bar)

    def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
        return self.decide_orders(bar, self.observe_bar(bar))
```

Daily runner:

```python
class DailyActEngine:
    def run(self, trading_date: date) -> list[OrderEvent]:
        snapshot = self.kis.account_snapshot()
        self.portfolio = Portfolio.from_snapshot(snapshot)

        bars = self.feed.daily_history()  # not feed.events()
        act_bars = latest_closed_bars_by_symbol(bars)

        for bar in sorted(b for b in bars if b not in act_bars):
            self.portfolio.mark(bar)
            self.strategy.warmup_bar(bar)

        orders: list[OrderEvent] = []
        for bar in sorted(act_bars, key=lambda b: (b.ts, b.symbol.market.value, b.symbol.ticker)):
            self.portfolio.mark(bar)
            orders.extend(self.strategy.on_bar(bar))

        return self.submit_once(trading_date, orders)
```

Better feed contract:

```python
class DailyHistoryFeed(Protocol):
    def daily_history(self) -> list[BarEvent]: ...
    def latest_closed_date(self, market: Market) -> date: ...
```

Key rule: `warmup_bar()` may update indicators, risk state, caches, and marks. It must not submit, audit as submitted, mutate broker state, or apply synthetic fills.

**2. Portfolio Sync**
Add KIS snapshot before strategy construction or before daily runner starts. Do not use hardcoded `10_000_000`.

KIS paper TR IDs:

```text
Domestic KOSPI balance:
GET /uapi/domestic-stock/v1/trading/inquire-balance
paper tr_id = VTTC8434R
real  tr_id = TTTC8434R

Overseas US stock balance:
GET /uapi/overseas-stock/v1/trading/inquire-balance
paper tr_id = VTTS3012R
real  tr_id = TTTS3012R

Overseas present/settlement-style balance:
GET /uapi/overseas-stock/v1/trading/inquire-present-balance
paper tr_id = VTRP6504R
real  tr_id = CTRP6504R
```

KIS’s official sample repo shows those paths/TR IDs for overseas balance, overseas present balance, and domestic balance respectively: [overseas balance](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py), [overseas present balance](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py), [domestic balance](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py).

Mapping:

```python
class KisClient:
    def domestic_balance(self) -> BrokerBalance: ...
    def overseas_balance(self, exchange: str = "NASD", ccy: str = "USD") -> BrokerBalance: ...
    def account_snapshot(self) -> AccountSnapshot: ...
```

```python
class Portfolio:
    @classmethod
    def from_snapshot(cls, s: AccountSnapshot) -> "Portfolio":
        p = cls(cash=s.cash, fx=FxRates(s.fx))
        for (market, ticker), qty in s.positions.items():
            sym = Symbol(ticker, Market(market), "USD" if market == "NASDAQ" else "KRW")
            p._pos[(market, ticker)] = qty
            p._sym[(market, ticker)] = sym
            p._mark[(market, ticker)] = s.marks.get((market, ticker), 0.0)
        return p
```

Given current [Portfolio.apply_fill](/Users/manager/side/makemoney/trader/strategy/portfolio.py:29) converts all fills into `cash["KRW"]`, keep the live snapshot KRW-settled too: `cash={"KRW": broker_available_cash_krw}` plus positions keyed by `(market, ticker)`. Do not introduce `USD` cash unless you also change order sizing and fill accounting.

**3. Idempotency / Scheduling**
Use both broker inquiry and a local atomic marker.

```python
@dataclass(frozen=True)
class DailyRunKey:
    env: str              # paper/real
    account: str
    market: Market
    trading_date: date
    strategy_id: str

class RunLedger:
    def acquire(self, key: DailyRunKey) -> bool: ...
    def record_intents(self, key: DailyRunKey, intents: list[OrderIntent]) -> None: ...
    def record_submitted(self, key: DailyRunKey, intent_hash: str, odno: str) -> None: ...
    def complete(self, key: DailyRunKey) -> None: ...
```

Submit flow:

```python
if not ledger.acquire(key):
    return []

existing = kis.today_orders_or_open_orders(key.trading_date)
if has_matching_order(existing, deterministic_intent_hash(order)):
    ledger.complete(key)
    return []

ledger.record_intents(key, intents)
for order in orders:
    odno = execution.submit_order(order)
    ledger.record_submitted(key, hash_order(order), odno)
ledger.complete(key)
```

Relevant order inquiry TRs already in your repo/docs: overseas execution inquiry `VTTS3035R`, domestic daily order/filled inquiry `VTTC0081R`. For overseas open orders, KIS samples show `/uapi/overseas-stock/v1/trading/inquire-nccs`; verify paper support before relying on it.

Scheduling:

```cron
# KRX close 15:30 KST; run after data has settled
40 15 * * 1-5 TZ=Asia/Seoul cd /app && python -m trader.app.run_daily --market KOSPI

# US regular close 16:00 ET; run after close, expressed in New York time
10 16 * * 1-5 TZ=America/New_York cd /app && python -m trader.app.run_daily --market NASDAQ
```

Use an exchange calendar, not weekday-only cron, to skip holidays/early closes.

**4. Daily Order Price**
For US paper, assume regular overseas stock order supports limit only unless live-tested otherwise. Your current code already encodes NASDAQ as `ORD_DVSN="00"` limit.

Recommendation:

```python
def daily_order_price(side: Side, last_close: float, band: float = 0.01) -> tuple[str, float]:
    if side == Side.BUY:
        return "LIMIT", round_tick(last_close * (1 + band))
    return "LIMIT", round_tick(last_close * (1 - band))
```

A limit exactly at last close is deterministic but often misses after a gap. A marketable protective limit is the practical daily model. For KOSPI, market order is acceptable if your risk model tolerates open slippage; otherwise use the same protective-limit approach.

**5. Verify Now vs Market Hours**
Can verify now, read-only:

```text
- token cache
- overseas/domestic daily bars
- domestic balance VTTC8434R
- overseas balance VTTS3012R
- overseas present balance VTRP6504R
- today order/fill inquiries, including empty responses
- local warmup/act determinism tests with MockTransport
- idempotency marker behavior
```

Can partially verify now:

```text
- order endpoint schema/auth/TR_ID with paper order call, expecting market-closed/pre-open business error
```

Needs market/session or supported reservation endpoint:

```text
- actual order acceptance
- fill lifecycle
- cancel/replace
- open-order inquiry after a live accepted order
- whether overseas paper accepts after-close queued orders through the regular order endpoint
```

Bottom line: build a separate daily runner. Historical bars are input for state only; the only broker-mutating path is `act_bars == latest_closed_bar_per_symbol`, guarded by account sync plus idempotency.


OpenAI Codex v0.139.0
--------
workdir: /Users/manager/side/makemoney
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019ecaea-efc9-7842-9b2b-f8a687d15f18
--------
user
Design the LIVE DAILY OPERATION model for a Python KIS paper-trading system. Current state: a single in-memory event loop replays bars from a feed; KisLiveFeed.daily_bars returns the most-recent ~100 historical daily bars per symbol. PROBLEM: if we run the live engine over those, it replays history and submits a REAL order on every historical bar — wrong.

I need the correct once-per-day operation model. Address concretely with signatures/sketch:

1. WARM-UP vs ACT: the strategy/signal sources need history to warm indicators, but we must submit orders ONLY for the latest bar (today's close), once. How to structure this cleanly given the existing FusionEngine.on_bar(bar)->orders and engines that loop feed→fills→mark→on_bar→submit? Proposal: a 'warmup' replay that feeds all-but-last bars through signal sources WITHOUT submitting orders, then process only the final bar for the real order. What's the cleanest implementation that does NOT duplicate the strategy decision logic and keeps determinism for the parts that are deterministic?

2. PORTFOLIO SYNC: each daily run is a fresh process, so the in-memory Portfolio must be initialized from the ACTUAL KIS account (cash + positions) via a balance inquiry, not from a hardcoded 10M KRW. Which KIS paper endpoints/TR_IDs for overseas (US) balance and domestic (KOSPI) balance? How to map them into the existing Portfolio (cash buckets keyed... actually KRW-settled; positions keyed by (market,ticker))? 

3. IDEMPOTENCY/SCHEDULING: running once per trading day. How to avoid double-submitting if the script runs twice the same day? (e.g., check existing open orders / a local run-marker keyed by trading date). And how to schedule (cron after each market close — note US and KR have different close times/timezones).

4. ORDER PRICE for daily: we submit after close for next session. Market order vs limit at last close? KIS paper overseas may only support limit. Recommend.

5. What can be verified RIGHT NOW with markets CLOSED (read-only balance/bars + order acceptance) vs what needs market hours.

Terse, senior, concrete signatures. Reference KIS TR_IDs where known (paper, V-prefix).
codex
I’ll check the local code shape first so the signatures fit the existing engine, and I’ll verify the KIS TR IDs against current references before giving the model.
exec
/bin/zsh -lc 'rg --files' in /Users/manager/side/makemoney
exec
/bin/zsh -lc 'rg -n "class FusionEngine|def on_bar|class KisLiveFeed|daily_bars|class Portfolio|submit|balance|TR_ID|tr_id" -S .' in /Users/manager/side/makemoney
 succeeded in 0ms:
docs/superpowers/specs/2026-06-15-phase1-trading-engine-design.md
docs/superpowers/specs/2026-06-15-phase2-news-llm-signal-design.md
docs/superpowers/plans/2026-06-15-phase2-news-llm-signal.md
docs/superpowers/plans/2026-06-15-phase1-trading-engine.md
docs/kis-api-reference.md
tests/test_news_models.py
tests/test_technical_indicators.py
tests/test_portfolio_helpers.py
tests/test_news_providers.py
tests/test_fx_portfolio.py
tests/test_kis_live_feed.py
tests/test_news_prompts.py
tests/test_no_lookahead.py
tests/test_clock.py
tests/test_interfaces.py
tests/test_technical_signal.py
tests/test_events.py
tests/test_backtest_engine.py
tests/test_news_cache.py
tests/test_fetch_data.py
tests/test_kis_orders.py
tests/test_backtest_live_parity.py
tests/test_audit.py
tests/test_kis_client.py
tests/test_risk.py
tests/test_phase2_integration.py
tests/test_kis_paper.py
tests/test_execution_sim.py
tests/__init__.py
tests/test_historical_feed.py
tests/test_kis_live_integration.py
tests/test_news_sentiment.py
tests/test_metrics.py
tests/test_fusion_engine.py
tests/test_news_source.py
tests/test_costs.py
tests/test_replay_parity.py
tests/test_order_factory.py
pyproject.toml
trader/strategy/portfolio.py
trader/strategy/risk.py
trader/strategy/__init__.py
trader/strategy/order_factory.py
trader/strategy/fusion_engine.py
trader/data/historical_feed.py
trader/data/kis_live_feed.py
trader/data/storage.py
trader/data/calendar.py
trader/data/__init__.py
trader/data/recorder.py
trader/data/interfaces.py
trader/live/engine.py
trader/live/__init__.py
trader/execution/kis_paper.py
trader/execution/costs.py
trader/execution/__init__.py
trader/execution/kis_client.py
trader/execution/simulated.py
trader/execution/interfaces.py
trader/backtest/report.py
trader/backtest/engine.py
trader/backtest/__init__.py
trader/backtest/metrics.py
trader/observability/__init__.py
trader/observability/audit.py
trader/observability/logging.py
trader/__init__.py
trader/signals/news/source.py
trader/signals/news/providers.py
trader/signals/news/prompts.py
trader/signals/news/__init__.py
trader/signals/news/cache.py
trader/signals/news/sentiment.py
trader/signals/news/models.py
trader/signals/__init__.py
trader/signals/technical.py
trader/signals/interfaces.py
trader/app/run_backtest.py
trader/app/run_paper.py
trader/app/__init__.py
trader/app/fetch_data.py
trader/app/config.py
trader/core/__init__.py
trader/core/clock.py
trader/core/events.py

 succeeded in 0ms:
./docs/superpowers/specs/2026-06-15-phase1-trading-engine-design.md:167:    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None: ...
./docs/superpowers/specs/2026-06-15-phase1-trading-engine-design.md:171:    def submit_order(self, order: OrderEvent) -> list[FillEvent]: ...
./docs/superpowers/specs/2026-06-15-phase1-trading-engine-design.md:174:class FusionEngine:           # 전략 = 모드 무지
./docs/superpowers/specs/2026-06-15-phase1-trading-engine-design.md:175:    def on_bar(self, bar) -> list[OrderEvent]: ...
./docs/superpowers/specs/2026-06-15-phase1-trading-engine-design.md:197:        for fill in execution.submit_order(order):
./docs/superpowers/specs/2026-06-15-phase2-news-llm-signal-design.md:88:    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None: ...
./docs/kis-api-reference.md:4:> (실거래는 `https://openapi.koreainvestment.com:9443`, TR_ID도 V접두 → 비V로 다름)
./docs/kis-api-reference.md:17:tr_id: {TR_ID}
./docs/kis-api-reference.md:24:| 용도 | Method + Path | tr_id (모의) | 검증 |
./docs/kis-api-reference.md:29:| 해외 주문 | `POST /uapi/overseas-stock/v1/trading/order` | 매수 `VTTT1002U` / 매도 `VTTT1006U` | ✅ rt_cd=1 msg1="모의투자 장시작전 입니다." (장마감 시간대 — 인증/TR_ID/body 정상 수락, 비즈니스 오류) |
./docs/kis-api-reference.md:44:- 해외 주문 (`VTTT1002U`): 라이브 검증 완료 — rt_cd=1 "모의투자 장시작전 입니다." (장마감 시간대 비즈니스 오류. 인증/TR_ID/path/body 정상 수락 확인.)
./trader/strategy/portfolio.py:16:class Portfolio:
./tests/test_kis_client.py:86:def test_overseas_daily_bars_normalize_and_sorted(tmp_path):
./tests/test_kis_client.py:87:    bars = _client(tmp_path).daily_bars("AAPL", "NASDAQ", "USD")
./tests/test_kis_client.py:97:def test_domestic_daily_bars_normalize(tmp_path):
./tests/test_kis_client.py:98:    bars = _client(tmp_path).daily_bars("005930", "KOSPI", "KRW")
./tests/test_kis_client.py:106:    """Two daily_bars calls on the same client must not re-issue the token."""
./tests/test_kis_client.py:108:    c.daily_bars("AAPL", "NASDAQ", "USD")
./tests/test_kis_client.py:109:    c.daily_bars("AAPL", "NASDAQ", "USD")
./tests/test_kis_client.py:124:    c1.daily_bars("AAPL", "NASDAQ", "USD")
./tests/test_kis_client.py:133:    bars = client2.daily_bars("AAPL", "NASDAQ", "USD")
./tests/test_kis_client.py:190:    bars = kis.daily_bars("AAPL", "NASDAQ", "USD")
./tests/test_kis_client.py:215:        kis.daily_bars("AAPL", "NASDAQ", "USD")
./tests/test_kis_client.py:218:def test_submit_order_returns_odno(tmp_path):
./tests/test_kis_client.py:219:    """submit_order calls the overseas order endpoint and returns ODNO."""
./tests/test_kis_client.py:233:    result = kis.submit_order("AAPL", "NASDAQ", "BUY", 1, price=1.0)
./trader/strategy/risk.py:44:    def on_bar(self, bar: BarEvent, portfolio: Portfolio) -> None:
./trader/data/kis_live_feed.py:6:class KisLiveFeed:
./trader/data/kis_live_feed.py:15:            bars.extend(self._kis.daily_bars(ticker, market, currency))
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:14:- `ExecutionHandler.submit_order(order) -> None` (큐잉) / `.on_bar(bar) -> list[FillEvent]` (해당 봉 **시가**에 체결).
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:15:- 엔진 루프 순서: `execution.on_bar(bar)`(전일 주문 체결) → `portfolio.apply_fill` → `portfolio.mark(bar)` → `strategy.on_bar(bar)`(종가 판단) → `execution.submit_order`(다음 봉 대기).
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:306:    def submit_order(self, order): self.queued.append(order)
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:307:    def on_bar(self, bar): return []
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:314:    ex.submit_order(OrderEvent(uuid4(), SYM, bar.ts, Side.BUY, 1))
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:342:    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:354:    def submit_order(self, order: OrderEvent) -> None:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:357:    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:499:    ex.submit_order(OrderEvent(uuid4(), SYM, b1.ts, Side.BUY, 5))  # b1 종가 후 주문
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:521:    def submit_order(self, order: OrderEvent) -> None:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:523:    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:596:class Portfolio:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:812:    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:890:class FusionEngine:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:910:    def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:996:                self.execution.submit_order(order)        # 다음 봉 대기
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1043:    def submit_order(self, order):
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1044:        self.orders.append((order.side, order.quantity)); super().submit_order(order)
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1089:                self.execution.submit_order(order)
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1182:    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1443:def test_daily_bars_normalize_for_nasdaq_and_kospi():
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1447:    bars = c.daily_bars(ticker="AAPL", market="NASDAQ", currency="USD")
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1449:    bars_kr = c.daily_bars(ticker="005930", market="KOSPI", currency="KRW")
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1455:- [ ] **Step 3: 구현 (Phase 1: 일봉 조회 + 주문 제출/조회 시그니처. 실제 엔드포인트/TR_ID는 KIS 문서 기준으로 채움)**
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1465:    """KIS REST 래퍼. 국내/해외 차이(엔드포인트·호가단위·통화·TR_ID)를 이 안에 격리.
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1474:    def daily_bars(self, ticker: str, market: str, currency: str) -> list[BarEvent]:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1480:    def submit_order(self, ticker: str, market: str, side: str, quantity: int) -> str:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1514:    def daily_bars(self, ticker, market, currency):
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1535:class KisLiveFeed:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1543:            bars.extend(self._kis.daily_bars(ticker, market, currency))
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1564:`KisPaperExecutionHandler`는 `submit_order`(KIS 제출)/`on_bar`(확인된 체결만 `FillEvent`로 대사) 계약을 따른다 — **시뮬과 동일 인터페이스**라 `FusionEngine`/엔진은 그대로.
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1579:    def __init__(self): self.submitted=[]; self._fill_next=False
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1580:    def submit_order(self, ticker, market, side, quantity):
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1581:        self.submitted.append((ticker, side, quantity)); self._fill_next=True; return "OID1"
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1589:def test_submit_then_reconcile_fill_on_next_bar():
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1592:    ex.submit_order(OrderEvent(uuid4(), SYM, _t(2), Side.BUY, 5))
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1593:    assert kis.submitted == [("AAPL","BUY",5)]
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1609:    """KIS 모의투자 실행. submit_order=KIS 제출, on_bar=확인된 체결만 FillEvent로 대사.
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1613:    def submit_order(self, order: OrderEvent) -> None:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1614:        self._kis.submit_order(order.symbol.ticker, order.symbol.market.value,
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1616:    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1667:                for o in self.strategy.on_bar(bar): self.execution.submit_order(o)
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1731:- **타입 일관성:** `ExecutionHandler`는 전 태스크에서 `submit_order(order)->None` + `on_bar(bar)->list[FillEvent]` 통일. `TargetPosition`, `NormalizedSignal(score,confidence)`, `Portfolio.equity_krw()`, `OrderFactory.orders_for_target(target, portfolio, price, ts)` 시그니처 전 태스크 일치 확인.
./tests/test_fusion_engine.py:48:        def on_bar(self, bar):
./trader/signals/news/source.py:70:    def on_bar(self, bar: BarEvent) -> Optional[NormalizedSignal]:
./tests/test_kis_paper.py:11:    def __init__(self): self.submitted=[]; self._fill_next=False
./tests/test_kis_paper.py:12:    def submit_order(self, ticker, market, side, quantity):
./tests/test_kis_paper.py:13:        self.submitted.append((ticker, side, quantity)); self._fill_next=True; return "OID1"
./tests/test_kis_paper.py:29:        def submit_order(self, ticker, market, side, quantity): return "OID1"
./tests/test_kis_paper.py:34:    ex.submit_order(OrderEvent(uuid4(), sym, t(2), Side.BUY, 5))
./tests/test_kis_paper.py:39:def test_submit_then_reconcile_fill_on_next_bar():
./tests/test_kis_paper.py:42:    ex.submit_order(OrderEvent(uuid4(), SYM, _t(2), Side.BUY, 5))
./tests/test_kis_paper.py:43:    assert kis.submitted == [("AAPL","BUY",5)]
./trader/strategy/fusion_engine.py:7:class FusionEngine:
./trader/strategy/fusion_engine.py:29:    def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
./tests/test_kis_live_feed.py:7:    def daily_bars(self, ticker, market, currency):
./tests/test_execution_sim.py:17:    ex.submit_order(OrderEvent(uuid4(), SYM, b1.ts, Side.BUY, 5))  # b1 종가 후 주문
./tests/test_execution_sim.py:26:    ex.submit_order(OrderEvent(uuid4(), SYM, bar(2, 10.0).ts, Side.BUY, 5))
./trader/signals/technical.py:26:    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
./trader/signals/news/prompts.py:56:- If positive and negative implications are balanced or unclear, use a near-zero score.
./trader/signals/interfaces.py:8:    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
./tests/test_kis_live_integration.py:50:def test_live_overseas_daily_bars():
./tests/test_kis_live_integration.py:52:    bars = _live_client().daily_bars("AAPL", "NASDAQ", "USD")
./tests/test_kis_live_integration.py:73:    _live_client().daily_bars("AAPL", "NASDAQ", "USD")
./trader/live/engine.py:24:                self.execution.submit_order(order)
./tests/test_interfaces.py:16:    def submit_order(self, order): self.queued.append(order)
./tests/test_interfaces.py:17:    def on_bar(self, bar): return []
./tests/test_interfaces.py:24:    ex.submit_order(OrderEvent(uuid4(), SYM, bar.ts, Side.BUY, 1))
./trader/app/fetch_data.py:80:        bars.extend(client.daily_bars(ticker, market, currency, start=start, end=end))
./trader/app/run_backtest.py:27:                for o in self.strategy.on_bar(bar): self.execution.submit_order(o)
./tests/test_fetch_data.py:16:    def daily_bars(
./tests/test_fetch_data.py:69:        def daily_bars(self, ticker, market, currency, start=None, end=None):
./trader/execution/kis_paper.py:7:    """KIS 모의투자 실행. submit_order=KIS 제출, on_bar=확인된 체결만 FillEvent로 대사.
./trader/execution/kis_paper.py:15:    def submit_order(self, order: OrderEvent) -> None:
./trader/execution/kis_paper.py:16:        broker_id = self._kis.submit_order(order.symbol.ticker, order.symbol.market.value,
./trader/execution/kis_paper.py:21:    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
./trader/execution/simulated.py:15:    def submit_order(self, order: OrderEvent) -> None:
./trader/execution/simulated.py:17:    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
./trader/execution/interfaces.py:7:    def submit_order(self, order: OrderEvent) -> None:
./trader/execution/interfaces.py:10:    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
./tests/test_kis_orders.py:1:"""Unit tests for KisClient.submit_order and filled_orders — MockTransport only."""
./tests/test_kis_orders.py:38:# Test (a): NASDAQ BUY — overseas order path, correct tr_id and body, returns ODNO
./tests/test_kis_orders.py:50:            captured["tr_id"] = req.headers.get("tr_id")
./tests/test_kis_orders.py:63:    result = kis.submit_order("AAPL", "NASDAQ", "BUY", 5, price=150.0)
./tests/test_kis_orders.py:66:    assert captured["tr_id"] == "VTTT1002U"
./tests/test_kis_orders.py:88:            captured["tr_id"] = req.headers.get("tr_id")
./tests/test_kis_orders.py:96:    result = kis.submit_order("AAPL", "NASDAQ", "SELL", 3, price=200.0)
./tests/test_kis_orders.py:98:    assert captured["tr_id"] == "VTTT1006U"
./tests/test_kis_orders.py:102:# Test (b): KOSPI BUY — order-cash path, correct tr_id VTTC0012U
./tests/test_kis_orders.py:114:            captured["tr_id"] = req.headers.get("tr_id")
./tests/test_kis_orders.py:123:    result = kis.submit_order("005930", "KOSPI", "BUY", 10, price=70000.0)
./tests/test_kis_orders.py:126:    assert captured["tr_id"] == "VTTC0012U"
./tests/test_kis_orders.py:146:            captured["tr_id"] = req.headers.get("tr_id")
./tests/test_kis_orders.py:154:    result = kis.submit_order("005930", "KOSPI", "SELL", 5, price=70000.0)
./tests/test_kis_orders.py:156:    assert captured["tr_id"] == "VTTC0011U"
./tests/test_kis_orders.py:229:def test_filled_orders_uses_vtts3035r_tr_id(tmp_path):
./tests/test_kis_orders.py:237:            captured["tr_id"] = req.headers.get("tr_id")
./tests/test_kis_orders.py:246:    assert captured["tr_id"] == "VTTS3035R"
./tests/test_kis_orders.py:268:def test_submit_order_raises_on_nonzero_rt_cd(tmp_path):
./tests/test_kis_orders.py:280:        kis.submit_order("AAPL", "NASDAQ", "BUY", 1, price=1.0)
./trader/backtest/engine.py:27:                self.execution.submit_order(order)        # 다음 봉 대기
./tests/test_backtest_live_parity.py:23:    def submit_order(self, order):
./tests/test_backtest_live_parity.py:24:        self.orders.append((order.side, order.quantity)); super().submit_order(order)
./trader/execution/kis_client.py:127:    def _headers(self, tr_id: str) -> dict:
./trader/execution/kis_client.py:134:            "tr_id": tr_id,
./trader/execution/kis_client.py:142:    def daily_bars(
./trader/execution/kis_client.py:162:            bars = self._daily_bars_overseas(sym, ticker, end)
./trader/execution/kis_client.py:165:            bars = self._daily_bars_domestic(
./trader/execution/kis_client.py:179:    def _daily_bars_overseas(
./trader/execution/kis_client.py:199:                f"KIS overseas daily_bars error: {body.get('msg1', body)}"
./trader/execution/kis_client.py:225:    def _daily_bars_domestic(
./trader/execution/kis_client.py:245:                f"KIS domestic daily_bars error: {body.get('msg1', body)}"
./trader/execution/kis_client.py:273:    def submit_order(
./trader/execution/kis_client.py:301:            tr_id = "VTTT1002U" if side == "BUY" else "VTTT1006U"
./trader/execution/kis_client.py:314:            tr_id = "VTTC0012U" if side == "BUY" else "VTTC0011U"
./trader/execution/kis_client.py:331:        resp = self._c.post(path, headers=self._headers(tr_id), json=body)
./trader/execution/kis_client.py:336:                f"KIS submit_order error [{data.get('rt_cd')}]: {data.get('msg1', data)}"

codex
The repo already has the dangerous shape you described: live engine iterates every bar and calls `strategy.on_bar` on each. I’m reading the small set of strategy/portfolio/KIS files now to anchor the proposed contract.
exec
/bin/zsh -lc "sed -n '1,380p' trader/execution/kis_client.py" in /Users/manager/side/makemoney
exec
/bin/zsh -lc "sed -n '1,260p' trader/strategy/portfolio.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
# trader/strategy/portfolio.py
from __future__ import annotations
from dataclasses import dataclass, field
from trader.core.events import Symbol, Market, BarEvent, FillEvent, Side

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

    def position_value_krw(self, sym: Symbol) -> float:
        """qty * mark * fx; returns 0 if no position or no mark."""
        key = _sym_key(sym)
        qty = self._pos.get(key, 0)
        if qty == 0:
            return 0.0
        mark = self._mark.get(key, 0.0)
        return self.fx.to_krw(qty * mark, sym.currency)

    def position_weight(self, sym: Symbol) -> float:
        """position_value_krw / equity_krw; returns 0 if equity <= 0."""
        eq = self.equity_krw()
        if eq <= 0:
            return 0.0
        return self.position_value_krw(sym) / eq

    def market_weight(self, market: Market) -> float:
        """Sum of position_value_krw for all symbols in market / equity_krw."""
        eq = self.equity_krw()
        if eq <= 0:
            return 0.0
        total = 0.0
        for key, qty in self._pos.items():
            sym = self._sym[key]
            if sym.market == market and qty != 0:
                total += self.fx.to_krw(qty * self._mark.get(key, 0.0), sym.currency)
        return total / eq

    def open_position_count(self) -> int:
        """Number of symbols with nonzero position."""
        return sum(1 for qty in self._pos.values() if qty != 0)

 succeeded in 0ms:
# trader/execution/kis_client.py
"""KIS Open API client — paper trading, Phase 1.5.

Operational constraints (from docs/kis-api-reference.md):
  1. Token caching: KIS rate-limits re-issuance (~1/min). Never re-request a valid token.
  2. Throttle: KIS 500s on bursts. Enforce min_interval between every request.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from trader.core.events import BarEvent, Market, Symbol


class KisClient:
    """KIS REST wrapper. Isolates domestic/overseas differences inside.

    Args:
        client: httpx.Client with base_url set (real or MockTransport for tests).
        app_key, app_secret, account: KIS credentials.
        paper: True = paper trading domain (openapivts…).
        min_interval: Minimum seconds between consecutive requests (throttle).
        token_cache_path: Path for JSON token disk cache.
    """

    def __init__(
        self,
        client: httpx.Client,
        app_key: str,
        app_secret: str,
        account: str,
        paper: bool = True,
        min_interval: float = 0.5,
        token_cache_path: str = ".kis_token.json",
    ):
        self._c = client
        self.app_key = app_key
        self.app_secret = app_secret
        self.account = account
        self.paper = paper
        self.min_interval = min_interval
        self.token_cache_path = token_cache_path

        # In-memory token cache
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

        # Throttle: track time of last request
        self._last_request_at: float = 0.0

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """Return a valid access token, using cache where possible."""
        now = time.time()

        # 1) In-memory cache
        if self._token and now < self._token_expires_at:
            return self._token

        # 2) Disk cache
        if os.path.exists(self.token_cache_path):
            try:
                with open(self.token_cache_path) as f:
                    cached = json.load(f)
                if now < cached.get("expires_at", 0):
                    self._token = cached["access_token"]
                    self._token_expires_at = cached["expires_at"]
                    return self._token
            except (json.JSONDecodeError, KeyError, OSError):
                pass  # corrupt cache — fall through to re-issue

        # 3) Issue new token (counts against KIS rate limit)
        self._throttle()
        resp = self._c.post(
            "/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        expires_in = int(data.get("expires_in", 86400))
        expires_at = now + expires_in - 600  # 10-min safety margin

        # Store in memory
        self._token = token
        self._token_expires_at = expires_at

        # Persist to disk
        try:
            with open(self.token_cache_path, "w") as f:
                json.dump({"access_token": token, "expires_at": expires_at}, f)
        except OSError:
            pass  # disk write failure is non-fatal

        return token

    # ------------------------------------------------------------------
    # Throttle
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Sleep if needed to honour min_interval between requests."""
        if self.min_interval <= 0:
            return
        elapsed = time.time() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_at = time.time()

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------

    def _headers(self, tr_id: str) -> dict:
        token = self._get_token()
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def daily_bars(
        self,
        ticker: str,
        market: str,
        currency: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> list[BarEvent]:
        """Fetch daily OHLCV bars sorted ascending by timestamp.

        Args:
            ticker: e.g. "AAPL" or "005930".
            market: "NASDAQ" or "KOSPI".
            currency: "USD" or "KRW".
            start: YYYYMMDD (used by domestic; ignored for overseas).
            end: YYYYMMDD (used by both; empty string = most recent).
        """
        sym = Symbol(ticker, Market(market), currency)

        if market == "NASDAQ":
            bars = self._daily_bars_overseas(sym, ticker, end)
        elif market == "KOSPI":
            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            bars = self._daily_bars_domestic(
                sym, ticker, start or "20240101", end or today_str
            )
        else:
            raise ValueError(f"Unsupported market: {market}")

        # Sort ascending by timestamp
        bars.sort(key=lambda b: b.ts)
        return bars

    # ------------------------------------------------------------------
    # Overseas (NASDAQ)
    # ------------------------------------------------------------------

    def _daily_bars_overseas(
        self, sym: Symbol, ticker: str, end: Optional[str]
    ) -> list[BarEvent]:
        self._throttle()
        resp = self._c.get(
            "/uapi/overseas-price/v1/quotations/dailyprice",
            headers=self._headers("HHDFS76240000"),
            params={
                "AUTH": "",
                "EXCD": "NAS",
                "SYMB": ticker,
                "GUBN": "0",
                "BYMD": end or "",
                "MODP": "0",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS overseas daily_bars error: {body.get('msg1', body)}"
            )

        bars: list[BarEvent] = []
        for row in body.get("output2", []):
            close_val = row.get("clos", "")
            if not close_val or float(close_val) == 0:
                continue
            ts = datetime.strptime(row["xymd"], "%Y%m%d").replace(tzinfo=timezone.utc)
            bars.append(
                BarEvent(
                    symbol=sym,
                    ts=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(close_val),
                    volume=int(row.get("tvol", 0)),
                )
            )
        return bars

    # ------------------------------------------------------------------
    # Domestic (KOSPI)
    # ------------------------------------------------------------------

    def _daily_bars_domestic(
        self, sym: Symbol, ticker: str, start: str, end: str
    ) -> list[BarEvent]:
        self._throttle()
        resp = self._c.get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            headers=self._headers("FHKST03010100"),
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_INPUT_DATE_1": start,
                "FID_INPUT_DATE_2": end,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS domestic daily_bars error: {body.get('msg1', body)}"
            )

        bars: list[BarEvent] = []
        for row in body.get("output2", []):
            close_val = row.get("stck_clpr", "")
            if not close_val or float(close_val) == 0:
                continue
            ts = datetime.strptime(row["stck_bsop_date"], "%Y%m%d").replace(
                tzinfo=timezone.utc
            )
            bars.append(
                BarEvent(
                    symbol=sym,
                    ts=ts,
                    open=float(row["stck_oprc"]),
                    high=float(row["stck_hgpr"]),
                    low=float(row["stck_lwpr"]),
                    close=float(close_val),
                    volume=int(row.get("acml_vol", 0)),
                )
            )
        return bars

    # ------------------------------------------------------------------
    # Order submission
    # ------------------------------------------------------------------

    def submit_order(
        self,
        ticker: str,
        market: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "00",
    ) -> str:
        """Submit a paper order and return the broker order id (ODNO).

        Args:
            ticker: e.g. "AAPL" or "005930".
            market: "NASDAQ" or "KOSPI".
            side: "BUY" or "SELL".
            quantity: Number of shares.
            price: Limit price (0.0 for market orders on KOSPI).
            order_type: KIS ORD_DVSN code — "00" limit / "01" market.
                        For NASDAQ paper trading only limit ("00") is supported.
                        For KOSPI default is "01" (market); caller may override.

        Returns:
            ODNO (broker order number) as a string.

        Raises:
            RuntimeError: if rt_cd != "0" in the KIS response.
        """
        if market == "NASDAQ":
            tr_id = "VTTT1002U" if side == "BUY" else "VTTT1006U"
            path = "/uapi/overseas-stock/v1/trading/order"
            body = {
                "CANO": self.account,
                "ACNT_PRDT_CD": "01",
                "OVRS_EXCG_CD": "NASD",
                "PDNO": ticker,
                "ORD_QTY": str(quantity),
                "OVRS_ORD_UNPR": str(price),
                "ORD_DVSN": order_type,
                "ORD_SVR_DVSN_CD": "0",
            }
        elif market == "KOSPI":
            tr_id = "VTTC0012U" if side == "BUY" else "VTTC0011U"
            path = "/uapi/domestic-stock/v1/trading/order-cash"
            # KOSPI default: market order ("01"); caller may pass "00" for limit
            kospi_ord_dvsn = order_type if order_type != "00" else "01"
            body = {
                "CANO": self.account,
                "ACNT_PRDT_CD": "01",
                "PDNO": ticker,
                "ORD_DVSN": kospi_ord_dvsn,
                "ORD_QTY": str(quantity),
                "ORD_UNPR": str(int(price)),
                "EXCG_ID_DVSN_CD": "KRX",
            }
        else:
            raise ValueError(f"Unsupported market: {market}")

        self._throttle()
        resp = self._c.post(path, headers=self._headers(tr_id), json=body)
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS submit_order error [{data.get('rt_cd')}]: {data.get('msg1', data)}"
            )

        output = data.get("output", {})
        odno = output.get("ODNO", "")
        return odno

    # ------------------------------------------------------------------
    # Fill inquiry
    # ------------------------------------------------------------------

    def filled_orders(self) -> list[dict]:
        """Query today's overseas (NASDAQ) executions.

        Returns a list of dicts with keys:
            order_id, ticker, market, currency, side,
            qty, price, commission

        Domestic fill inquiry is a TODO stub (returns []).
        Only rows with executed qty > 0 are included.

        KIS overseas side codes: "02" = BUY, "01" = SELL.
        """
        today = datetime.now(timezone.utc).strftime("%Y%m%d")

        self._throttle()
        resp = self._c.get(
            "/uapi/overseas-stock/v1/trading/inquire-ccnl",
            headers=self._headers("VTTS3035R"),
            params={
                "CANO": self.account,
                "ACNT_PRDT_CD": "01",
                "PDNO": "",
                "ORD_STRT_DT": today,
                "ORD_END_DT": today,
                "SLL_BUY_DVSN": "00",
                "CCLD_NCCS_DVSN": "00",
                "OVRS_EXCG_CD": "",
                "SORT_SQN": "DS",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
                "ORD_DT": "",
                "ORD_GNO_BRNO": "",
                "ODNO": "",
            },

exec
/bin/zsh -lc "sed -n '1,220p' trader/live/engine.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
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

exec
/bin/zsh -lc "sed -n '1,120p' trader/data/kis_live_feed.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
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

exec
/bin/zsh -lc "sed -n '1,220p' trader/strategy/fusion_engine.py" in /Users/manager/side/makemoney
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
        self.risk.on_bar(bar, self.portfolio)  # two-phase: update ATR + daily loss state first
        signals = [s for src in self.sources if (s := src.on_bar(bar)) is not None]
        combined = self._combine(signals)
        if combined >= self.enter_threshold:
            weight = combined
        elif combined <= self.exit_threshold:
            weight = 0.0
        else:
            return []  # 중립 구간: 포지션 유지, 주문 없음
        sized = self.risk.size_target(TargetPosition(bar.symbol, weight, reason=f"combined={combined:.2f}"),
                                      self.portfolio, bar)
        return self.order_factory.orders_for_target(sized, self.portfolio, price=bar.close, ts=bar.ts)

exec
/bin/zsh -lc "sed -n '380,520p' trader/execution/kis_client.py && sed -n '1,180p' trader/core/events.py && sed -n '1,140p' docs/kis-api-reference.md" in /Users/manager/side/makemoney
 succeeded in 0ms:
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS filled_orders error [{data.get('rt_cd')}]: {data.get('msg1', data)}"
            )

        fills: list[dict] = []
        _side_map = {"02": "BUY", "01": "SELL"}

        for row in data.get("output", []):
            filled_qty_raw = row.get("ft_ccld_qty", "0")
            try:
                filled_qty = int(filled_qty_raw)
            except (ValueError, TypeError):
                filled_qty = 0
            if filled_qty <= 0:
                continue  # skip unfilled / zero rows

            sll_buy_code = row.get("sll_buy_dvsn_cd", "")
            side_str = _side_map.get(sll_buy_code, sll_buy_code)

            fills.append(
                {
                    "order_id": row.get("odno", ""),
                    "ticker": row.get("pdno", ""),
                    "market": "NASDAQ",
                    "currency": "USD",
                    "side": side_str,
                    "qty": filled_qty,
                    "price": float(row.get("ft_ccld_unpr3", "0") or "0"),
                    "commission": 0.0,
                }
            )

        # TODO: domestic (KOSPI) fill inquiry — VTTC0081R — not yet implemented
        return fills
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
# KIS Open API 레퍼런스 (모의투자 / Phase 1.5)

> codex 조사 + **라이브 검증** 기반. 모의투자 도메인: `https://openapivts.koreainvestment.com:29443`
> (실거래는 `https://openapi.koreainvestment.com:9443`, TR_ID도 V접두 → 비V로 다름)

## ⚠️ 운영 제약 (라이브 검증으로 확인 — 구현 필수)

1. **토큰 캐싱 필수.** `POST /oauth2/tokenP`로 받은 access_token은 **24h 유효**(`expires_in: 86400`). KIS는 **토큰 재발급을 분당 1회 수준으로 제한** — 호출마다 새 토큰 요청하면 거부됨(`EGW00133` 류). → 토큰을 디스크/메모리에 캐싱하고 만료 전 재사용.
2. **요청 throttle 필수.** 초당 요청 한도가 있음 — 검증 중 연속 호출 시 `HTTP 500 rt_cd=1 "초당 거래건수를 초과하였습니다"` 발생. → 호출 간 최소 간격(≈0.3~0.5s) 두거나 토큰버킷.

## 공통 헤더
```
content-type: application/json
authorization: Bearer {access_token}
appkey: {APP_KEY}
appsecret: {APP_SECRET}
tr_id: {TR_ID}
custtype: P
tr_cont: ""        # 연속조회 시 "N"
```

## 엔드포인트 (검증 상태 표기)

| 용도 | Method + Path | tr_id (모의) | 검증 |
|---|---|---|---|
| 토큰 발급 | `POST /oauth2/tokenP` (body: grant_type=client_credentials, appkey, appsecret) | — | ✅ 200 |
| 해외 일봉 | `GET /uapi/overseas-price/v1/quotations/dailyprice` | `HHDFS76240000` | ✅ AAPL 실데이터 수신 |
| 국내 일봉 | `GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` | `FHKST03010100` | ⚠️ 스펙OK(레이트리밋만 겪음) |
| 해외 주문 | `POST /uapi/overseas-stock/v1/trading/order` | 매수 `VTTT1002U` / 매도 `VTTT1006U` | ✅ rt_cd=1 msg1="모의투자 장시작전 입니다." (장마감 시간대 — 인증/TR_ID/body 정상 수락, 비즈니스 오류) |
| 국내 주문 | `POST /uapi/domestic-stock/v1/trading/order-cash` | 매수 `VTTC0012U` / 매도 `VTTC0011U` | ⬜ 미검증 (단위테스트만) |
| 해외 체결조회 | `GET /uapi/overseas-stock/v1/trading/inquire-ccnl` | `VTTS3035R` | ✅ rt_cd=0, 빈 리스트 반환 (정상 수락) |
| 국내 체결조회 | `GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld` | 3개월내 `VTTC0081R` | ⬜ 미검증 (TODO) |

### 파라미터 메모
- **해외 일봉**: query `AUTH=""`, `EXCD="NAS"`(NASDAQ), `SYMB="AAPL"`, `GUBN="0"`(일), `BYMD=""`(기준일, 빈값=최근), `MODP="0"`. 응답 `output2[]` 각 행: `xymd`(YYYYMMDD), `open/high/low/clos`, `tvol`.
- **국내 일봉**: query `FID_COND_MRKT_DIV_CODE="J"`, `FID_INPUT_ISCD="005930"`, `FID_INPUT_DATE_1/2`(기간 YYYYMMDD), `FID_PERIOD_DIV_CODE="D"`, `FID_ORG_ADJ_PRC="0"`(수정주가). 응답 `output2[]`: `stck_bsop_date`, `stck_oprc/hgpr/lwpr/clpr`, `acml_vol`.
- **해외 주문 body**(대문자): `CANO`, `ACNT_PRDT_CD`, `OVRS_EXCG_CD="NASD"`, `PDNO`, `ORD_QTY`, `OVRS_ORD_UNPR`, `ORD_DVSN="00"`(지정가; 모의 US는 지정가만 지원 가능성), `ORD_SVR_DVSN_CD="0"`.
- **국내 주문 body**: `CANO`, `ACNT_PRDT_CD`, `PDNO`, `ORD_DVSN`(00 지정가/01 시장가), `ORD_QTY`, `ORD_UNPR`, `EXCG_ID_DVSN_CD="KRX"`.
- 계좌번호 `50193330` → `CANO=50193330`, `ACNT_PRDT_CD="01"`(모의 종합 추정 — 주문 검증 시 확정).
- `hashkey`(`POST /uapi/hashkey`)는 선택. 주문 위변조 체크 원하면 사용.

### 검증 코드 위치
- 읽기 검증 완료: 해외 일봉.
- 해외 주문 (`VTTT1002U`): 라이브 검증 완료 — rt_cd=1 "모의투자 장시작전 입니다." (장마감 시간대 비즈니스 오류. 인증/TR_ID/path/body 정상 수락 확인.)
- 해외 체결조회 (`VTTS3035R`): 라이브 검증 완료 — rt_cd=0, 정상 응답 확인.
- 국내 주문/체결조회 (`VTTC0012U`, `VTTC0011U`, `VTTC0081R`): 단위테스트만, 라이브 미검증.

web search: 
web search: KIS Open API 모의투자 해외주식 잔고조회 TR_ID VTRP6504R
web search: 
web search: site:github.com/koreainvestment/open-trading-api inquire-balance VTRP6504R
codex
The local docs already confirm daily bars, order, and overseas fill TR IDs, but balance sync is missing. I’m checking KIS’s published sample/API references now because balance TR IDs are exactly the kind of detail that drifts.
exec
/bin/zsh -lc 'tmp=$(mktemp -d); git clone --depth 1 https://github.com/koreainvestment/open-trading-api.git "$tmp/open-trading-api" >/dev/null 2>&1 && rg -n "inquire-balance|inquire-present-balance|VTTC8434R|TTTC8434R|VTRP|TR_ID|balance" "$tmp/open-trading-api" -S' in /Users/manager/side/makemoney
codex
That clone/search is still running; I’ll pull its output, then I’ll distill this into an implementation contract instead of modifying code unless you ask for the actual patch.
 succeeded in 4294ms:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/rest/kis_api.py:270:def get_acct_balance(rtCashFlag=False):
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/rest/kis_api.py:271:    url = '/uapi/domestic-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/rest/kis_api.py:272:    tr_id = "TTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:20:def after_hour_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:61:        >>> df = after_hour_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:75:    api_url = "/uapi/domestic-stock/v1/ranking/after-hour-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:142:            return after_hour_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:743:def credit_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:776:        >>> df1, df2 = credit_balance('11701', '0000', '2', 'J', '0')
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:780:    api_url = "/uapi/domestic-stock/v1/ranking/credit-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:867:            return credit_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:1019:def daily_credit_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:1050:        >>> df = daily_credit_balance("J", "20476", "005930", "20240313")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:1053:    api_url = "/uapi/domestic-stock/v1/quotations/daily-credit-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:1098:            return daily_credit_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:2160:def finance_balance_sheet(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:2187:        >>> df = finance_balance_sheet("0", "J", "000660")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:2190:    api_url = "/uapi/domestic-stock/v1/finance/balance-sheet"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:2242:            return finance_balance_sheet(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3552:def inquire_account_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3573:        >>> df1, df2 = inquire_account_balance("12345678", "21")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3577:    api_url = "/uapi/domestic-stock/v1/trading/inquire-account-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3647:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3679:def inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3726:        >>> df1, df2 = inquire_balance(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, afhr_flpr_yn="N", inqr_dvsn="01", unpr_dvsn="01", fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3730:    api_url = "/uapi/domestic-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3770:        tr_id = "TTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3772:        tr_id = "VTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3814:            return inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3831:def inquire_balance_rlz_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3878:        >>> df1, df2 = inquire_balance_rlz_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, afhr_flpr_yn="N", inqr_dvsn="02", unpr_dvsn="01", fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="01")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3882:    api_url = "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3958:            return inquire_balance_rlz_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:4527:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:4596:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:6933:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11330:def pension_inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11366:        >>> df1, df2 = pension_inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, acca_dvsn_cd="00", inqr_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11370:    api_url = "/uapi/domestic-stock/v1/trading/pension/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11427:            return pension_inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11610:def pension_inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11634:        >>> df1, df2 = pension_inquire_present_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, user_dvsn_cd="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11638:    api_url = "/uapi/domestic-stock/v1/trading/pension/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:12390:def quote_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:12427:        >>> df = quote_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:12441:    api_url = "/uapi/domestic-stock/v1/ranking/quote-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:12495:            return quote_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/README.md:284:| `GET` | `/api/account/balance` | 예수금 / 평가금액 |
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:402:            string url = "/uapi/overseas-stock/v1/trading/inquire-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:435:            string url = "/uapi/overseas-stock/v1/trading/inquire-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:633:            string url = "/uapi/overseas-stock/v1/trading/inquire-present-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:634:            string trID = "CTRP6504R"; // 모의투자 VTRP6504R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:1127:            string url = "/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:22:df = after_hour_balance(fid_input_price_1="", fid_cond_mrkt_div_code="J", fid_cond_scr_div_code="20176",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:89:df1, df2 = credit_balance(fid_cond_scr_div_code="11701", fid_input_iscd="0000", fid_option="2",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:106:result1 = daily_credit_balance(fid_cond_mrkt_div_code="J", fid_cond_scr_div_code="20476",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:215:df = finance_balance_sheet(fid_div_cls_code="0", fid_cond_mrkt_div_code="J", fid_input_iscd="000660")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:338:result1, result2 = inquire_account_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:355:result1, result2 = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:373:result1, result2 = inquire_balance_rlz_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:1081:result1, result2 = pension_inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, acca_dvsn_cd="00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:1106:result1, result2 = pension_inquire_present_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:1186:df = quote_balance(fid_vol_cnt="1000", fid_cond_mrkt_div_code="J", fid_cond_scr_div_code="20172", fid_input_iscd="0001",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:12:    uv run python examples/portfolio_analysis.py --example rebalance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:322:def example_rebalance_simulation():
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:357:            result = client.simulate_rebalance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:370:            print(f"   리밸런싱 횟수: {len(result.rebalance_dates)}회")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:375:        print(f"   최종 수익률: {results['monthly'].no_rebalance_return:+.2%}")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:384:            benefit = result.rebalance_benefit
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:393:        fig = PortfolioVisualizer.rebalance_comparison(results["monthly"])
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:395:        output_path = Path("./examples/output/reports/rebalance_comparison.html")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:437:        rebalance = client.simulate_rebalance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:460:            rebalance_result=rebalance,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:467:        return metrics, rebalance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:490:  rebalance   - 리밸런싱 시뮬레이션
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:500:        choices=["basic", "correlation", "frontier", "rebalance", "report", "all"],
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/portfolio_analysis.py:515:        "rebalance": example_rebalance_simulation,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_examples.py:62:df = inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_excg_cd="NASD", tr_crcy_cd="USD")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_examples.py:86:df1, df2, df3 = inquire_paymt_stdr_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, bass_dt="20250630",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_examples.py:116:df1, df2, df3 = inquire_present_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, wcrc_frcr_dvsn_cd="02",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1391:    "inquire_present_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1394:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1395:      "method": "inquire_present_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1396:      "api_path": "/uapi/overseas-stock/v1/trading/inquire-present-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1491:    "inquire_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1494:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1495:      "method": "inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1496:      "api_path": "/uapi/overseas-stock/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:2157:    "inquire_paymt_stdr_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:2160:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_paymt_stdr_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:2161:      "method": "inquire_paymt_stdr_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:2162:      "api_path": "/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:567:def inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:604:        >>> df1, df2 = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:642:    api_url = "/uapi/overseas-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:703:            return inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1038:def inquire_paymt_stdr_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1073:        >>> df1, df2, df3 = inquire_paymt_stdr_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1107:    api_url = "/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1188:            return inquire_paymt_stdr_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1599:def inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1638:        >>> df1, df2, df3 = inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1679:        tr_id = "VTRP6504R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1683:    api_url = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1762:            return inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:272:    "inquire_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:275:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:276:      "method": "inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:277:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:346:    "inquire_ngt_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:349:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_ngt_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:350:      "method": "inquire_ngt_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:351:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1005:    "inquire_balance_valuation_pl": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1008:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_balance_valuation_pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1009:      "method": "inquire_balance_valuation_pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1010:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1095:    "inquire_balance_settlement_pl": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1098:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_balance_settlement_pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1099:      "method": "inquire_balance_settlement_pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1100:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_examples.py:57:df = inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_cndt="00", pdno="", buy_dt="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1041:										"value": "TTTC8434R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1042:										"description": "[실전투자]\nTTTC8434R : 주식 잔고 조회\n\n[모의투자]\nVTTC8434R : 주식 잔고 조회",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1056:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=01&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=00&CTX_AREA_FK100&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1065:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1778:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/pension/inquire-present-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=29&USER_DVSN_CD=00&CTX_AREA_FK100=&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1788:										"inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2256:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/pension/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=29&ACCA_DVSN_CD=00&INQR_DVSN=00&CTX_AREA_FK100&CTX_AREA_NK100",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2266:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2342:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=02&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=01&COST_ICLD_YN=N&CTX_AREA_FK100=&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2351:										"inquire-balance-rlz-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2614:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/inquire-account-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=21&INQR_DVSN_1&BSPR_BF_DT_APLY_YN",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2623:										"inquire-account-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:8273:									"raw": "{{PROD}}/uapi/domestic-stock/v1/finance/balance-sheet?fid_cond_mrkt_div_code=J&fid_input_iscd=005930&fid_div_cls_code=1",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:8282:										"balance-sheet"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:11233:									"raw": "{{PROD}}/uapi/domestic-stock/v1/quotations/daily-credit-balance?fid_cond_mrkt_div_code=J&fid_cond_scr_div_code=20476&fid_input_iscd=068270&fid_input_date_1=20240508",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:11242:										"daily-credit-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:13755:									"raw": "{{PROD}}/uapi/domestic-stock/v1/ranking/after-hour-balance?fid_cond_mrkt_div_code=J&fid_cond_scr_div_code=20176&fid_rank_sort_cls_code=1&fid_div_cls_code=0&fid_input_iscd=0000&fid_trgt_cls_code=0&fid_trgt_exls_cls_code=0&fid_input_price_1=&fid_input_price_2=&fid_vol_cnt=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:13764:										"after-hour-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:13992:									"raw": "{{PROD}}/uapi/domestic-stock/v1/ranking/quote-balance?fid_cond_mrkt_div_code=J&fid_cond_scr_div_code=20172&fid_input_iscd=0000&fid_rank_sort_cls_code=0&fid_div_cls_code=0&fid_trgt_cls_code=0&fid_trgt_exls_cls_code=0&fid_input_price_1=&fid_input_price_2=&fid_vol_cnt=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:14001:										"quote-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:15251:									"raw": "{{PROD}}/uapi/domestic-stock/v1/ranking/credit-balance?fid_cond_scr_div_code=11701&fid_input_iscd=0000&fid_option=2&fid_cond_mrkt_div_code=J&fid_rank_sort_cls_code=0",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:15260:										"credit-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16072:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-balance?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&MGNA_DVSN=01&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16081:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16472:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&ACNT_PWD=&MGNA_DVSN=01&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16481:										"inquire-ngt-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16725:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&INQR_DT=20230906&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16734:										"inquire-balance-settlement-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16942:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&MGNA_DVSN=02&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16951:										"inquire-balance-valuation-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19867:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=NASD&TR_CRCY_CD=USD&CTX_AREA_FK200=&CTX_AREA_NK200",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19876:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20102:										"description": "[실전투자]\nCTRP6504R\n\n[모의투자]\nVTRP6504R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20111:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-present-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&NATN_CD=000&WCRC_FRCR_DVSN_CD=01&TR_MKET_CD=00&INQR_DVSN_CD=00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20120:										"inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:21187:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&BASS_DT=20240625&WCRC_FRCR_DVSN_CD=01&INQR_DVSN_CD=00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:21196:										"inquire-paymt-stdr-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:25929:									"raw": "{{PROD}}/uapi/domestic-bond/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&INQR_CNDT=00&PDNO=&BUY_DT=&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:25938:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:2689:    "inquire_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:2692:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:2693:      "method": "inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:2694:      "api_path": "/uapi/domestic-stock/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3155:    "inquire_balance_rlz_pl": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3158:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_balance_rlz_pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3159:      "method": "inquire_balance_rlz_pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3160:      "api_path": "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3633:    "inquire_account_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3636:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_account_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3637:      "method": "inquire_account_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3638:      "api_path": "/uapi/domestic-stock/v1/trading/inquire-account-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3670:    "pension_inquire_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3673:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/pension_inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3674:      "method": "pension_inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3675:      "api_path": "/uapi/domestic-stock/v1/trading/pension/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:4441:    "pension_inquire_present_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:4444:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/pension_inquire_present_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:4445:      "method": "pension_inquire_present_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:4446:      "api_path": "/uapi/domestic-stock/v1/trading/pension/inquire-present-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_bond.json:588:    "inquire_balance": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_bond.json:591:      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_bond/inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_bond.json:592:      "method": "inquire_balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/configs/domestic_bond.json:593:      "api_path": "/uapi/domestic-bond/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:362:def inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:397:        >>> df = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:430:    api_url = "/uapi/domestic-bond/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:468:            return inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/backend/routers/account.py:204:@router.get("/balance", response_model=BalanceResponse)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/backend/routers/account.py:205:async def get_balance():
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/lib/api/account.ts:17:  return apiGet<ApiResponse<Balance>>("/api/account/balance");
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/hooks/useAccount.ts:13:  balance: Balance | null;
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/hooks/useAccount.ts:26:  const [balance, setBalance] = useState<Balance | null>(null);
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/hooks/useAccount.ts:34:    balance: 0,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/hooks/useAccount.ts:93:    if (now - lastFetchTimes.current.balance < MIN_FETCH_INTERVAL) {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/hooks/useAccount.ts:104:        lastFetchTimes.current.balance = now;
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/hooks/useAccount.ts:106:        // Set error but DON'T clear existing balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/hooks/useAccount.ts:118:    lastFetchTimes.current = { info: 0, holdings: 0, balance: 0 };
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/hooks/useAccount.ts:142:    balance,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/Kis Trading MCP/tools/base.py:205:        # N개 튜플 반환 함수 처리 (예: inquire_balance는 (df1, df2) 반환)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_examples.py:78:result1, result2 = inquire_balance(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn="01",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_examples.py:87:result1, result2 = inquire_balance_settlement_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_dt="20230906")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_examples.py:95:result1, result2 = inquire_balance_valuation_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn="01",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_examples.py:170:result1, result2 = inquire_ngt_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:360:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:396:def inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:431:        >>> df1, df2 = inquire_balance(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn="01", excc_stat_cd="1")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:468:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:505:            return inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:520:def inquire_balance_settlement_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:551:        >>> df1, df2 = inquire_balance_settlement_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_dt="20230906")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:576:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:612:            return inquire_balance_settlement_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:626:def inquire_balance_valuation_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:660:        >>> df1, df2 = inquire_balance_valuation_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn="01", excc_stat_cd="1")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:688:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:725:            return inquire_balance_valuation_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1273:def inquire_ngt_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1308:        >>> df1, df2 = inquire_ngt_balance("12345678", "01", "01", "1")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1336:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1374:            return inquire_ngt_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/backend/routers/orders.py:20:from core.data_fetcher import get_deposit, get_holdings, get_pending_orders, cancel_order, clear_balance_cache
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/backend/routers/orders.py:105:    clear_balance_cache()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1904:										"value": "VTTC8434R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1906:										"description": "[실전투자]\nTTTC8434R : 주식 잔고 조회\n\n[모의투자]\nVTTC8434R : 주식 잔고 조회"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1919:									"raw": "{{VTS}}/uapi/domestic-stock/v1/trading/inquire-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=01&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=00&CTX_AREA_FK100=&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1928:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2545:									"raw": "{{VTS}}/uapi/domestic-futureoption/v1/trading/inquire-balance?CANO={{CANO_T}}&ACNT_PRDT_CD=03&MGNA_DVSN=01&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2554:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4688:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/inquire-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=TKSE&TR_CRCY_CD=JPY&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4697:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4922:										"value": "VTRP6504R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4924:										"description": "[실전투자]\nCTRP6504R\n\n[모의투자]\nVTRP6504R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4932:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/inquire-present-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&NATN_CD=000&WCRC_FRCR_DVSN_CD=01&TR_MKET_CD=00&INQR_DVSN_CD=00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4941:										"inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/live_trading.py:126:        balance = live.get_balance()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/live_trading.py:127:        print(f"  예수금: {balance.cash:,.0f}원")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/live_trading.py:128:        print(f"  출금가능금액: {balance.available_cash:,.0f}원")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/examples/live_trading.py:129:        print(f"  총평가금액: {balance.total_value:,.0f}원")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api03.py:44:rt_data = kb.get_overseas_inquire_balance(excg_cd="NASD", crcy_cd="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api03.py:50:rt_data = kb.get_overseas_inquire_balance(excg_cd="NASD", crcy_cd="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api03.py:64:rt_data = kb.get_overseas_inquire_present_balance(dv="02", dvsn="01", natn="000", mkt="00", inqr_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api03.py:102:rt_data = kb.get_overseas_inquire_paymt_stdr_balance(dv="03", dt="", dvsn="01", inqr_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/elw/elw_exp_ccnl/chk_elw_exp_ccnl.py:117:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domfuopt.py:260:def get_domfuopt_inquire_ngt_balance_obj(tr_cont="", FK100="", NK100="", dataframe=None):
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domfuopt.py:261:    url = '/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domfuopt.py:295:def get_domfuopt_inquire_ngt_balance_lst(tr_cont="", FK100="", NK100="", dataframe=None):  # 국내주식주문 > 주식잔고조회(현재종목별 잔고)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domfuopt.py:296:    url = '/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domfuopt.py:327:        return get_domfuopt_inquire_ngt_balance_lst("N", FK100, NK100, dataframe)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:292:def get_inquire_balance_obj(tr_cont="", FK100="", NK100="", dataframe=None):  # 국내주식주문 > 주식잔고조회(현재잔고)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:293:    url = '/uapi/domestic-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:294:    tr_id = "TTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:323:def get_inquire_balance_lst(tr_cont="", FK100="", NK100="", dataframe=None):  # 국내주식주문 > 주식잔고조회(현재종목별 잔고)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:324:    url = '/uapi/domestic-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:325:    tr_id = "TTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:360:        return get_inquire_balance_lst("N", FK100, NK100, dataframe)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:628:def get_inquire_balance_rlz_pl_obj(tr_cont="", FK100="", NK100="", dataframe=None):  # [국내주식] 주문/계좌 > 주식잔고조회_실현손익 (잔고조회 Output2)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:629:    url = '/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:659:def get_inquire_balance_rlz_pl_lst(tr_cont="", FK100="", NK100="", dataframe=None):  # [국내주식] 주문/계좌 > 주식잔고조회_실현손익 (보유주식내역 Output2)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:660:    url = '/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_domstk.py:698:        return get_inquire_balance_rlz_pl_lst("N", FK100, NK100, dataframe)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:199:domestic_bond,주문/계좌,장내채권 잔고조회,inquire_balance,[장내채권] 주문/계좌 장내채권 잔고조회[국내주식-198] 장내채권 잔고조회 API를 호출하여 DataFrame으로 반환합니다.,"cano (str): 종합계좌번호
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:209:max_depth (int): 최대 재귀 깊이 (기본값: 10)",Optional[pd.DataFrame]: 장내채권 잔고조회 데이터,"     df = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:228:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_bond/inquire_balance/inquire_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_bond/inquire_balance/chk_inquire_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:858:domestic_futureoption,주문/계좌,(야간)선물옵션 잔고현황,inquire_ngt_balance,(야간)선물옵션 잔고현황 API입니다.,"cano (str): [필수] 종합계좌번호 (ex. 계좌번호 체계(8-2)의 앞 8자리)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:869:max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: (output1 데이터, output2 데이터)","     df1, df2 = inquire_ngt_balance(""12345678"", ""01"", ""01"", ""1"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:922:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_ngt_balance/inquire_ngt_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_ngt_balance/chk_inquire_ngt_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:923:domestic_futureoption,주문/계좌,선물옵션 잔고현황,inquire_balance,"선물옵션 잔고현황 API입니다. 한 번의 호출에 최대 20건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다.","env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:934:max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: (output1, output2) 선물옵션 잔고현황 데이터","     df1, df2 = inquire_balance(env_dv=""real"", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn=""01"", excc_stat_cd=""1"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:984:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_balance/inquire_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_balance/chk_inquire_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1004:domestic_futureoption,주문/계좌,선물옵션 잔고평가손익내역,inquire_balance_valuation_pl,"시장별 투자자매매동향(일별) API입니다. 한국투자 HTS(eFriend Plus) > [0404] 시장별 일별동향 화면의 기능을 API로 개발한 사항으로, 해당 화면을 참고하시면 기능을 이해하기 쉽습니다.","cano (str): [필수] 종합계좌번호 (ex. 계좌번호 체계(8-2)의 앞 8자리)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1014:max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: (output1 데이터프레임, output2 데이터프레임)","     df1, df2 = inquire_balance_valuation_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn=""01"", excc_stat_cd=""1"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1062:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/inquire_balance_valuation_pl.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/chk_inquire_balance_valuation_pl.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1215:domestic_futureoption,주문/계좌,선물옵션 잔고정산손익내역,inquire_balance_settlement_pl,선물옵션 잔고정산손익내역 API입니다.,"cano (str): [필수] 종합계좌번호
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1224:max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: (output1 데이터, output2 데이터)","     df1, df2 = inquire_balance_settlement_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_dt=""20230906"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1251:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/inquire_balance_settlement_pl.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/chk_inquire_balance_settlement_pl.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2526:domestic_stock,주문/계좌,투자계좌자산현황조회,inquire_account_balance,"투자계좌자산현황조회 API입니다. output1은 한국투자 HTS(eFriend Plus) > [0891] 계좌 자산비중(결제기준) 화면 아래 테이블의 기능을 API로 개발한 사항으로, 해당 화면을 참고하시면 기능을 이해하기 쉽습니다.","cano (str): [필수] 종합계좌번호 (ex. 12345678)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2529:bspr_bf_dt_aply_yn (str): 기준가이전일자적용여부","Tuple[pd.DataFrame, pd.DataFrame]: (output1 데이터프레임, output2 데이터프레임)","     df1, df2 = inquire_account_balance(""12345678"", ""21"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2563:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_account_balance/inquire_account_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_account_balance/chk_inquire_account_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2892:domestic_stock,주문/계좌,주식잔고조회,inquire_balance,"주식 잔고조회 API입니다. 실전계좌의 경우, 한 번의 호출에 최대 50건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다. 모의계좌의 경우, 한 번의 호출에 최대 20건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다. * 당일 전량매도한 잔고도 보유수량 0으로 보여질 수 있으나, 해당 보유수량 0인 잔고는 최종 D-2일 이후에는 잔고에서 사라집니다.","env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2907:max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: 주식잔고조회 데이터 (output1, output2)","     df1, df2 = inquire_balance(env_dv=""real"", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, afhr_flpr_yn=""N"", inqr_dvsn=""01"", unpr_dvsn=""01"", fund_sttl_icld_yn=""N"", fncg_amt_auto_rdpt_yn=""N"", prcs_dvsn=""00"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2960:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_balance/chk_inquire_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2961:domestic_stock,주문/계좌,퇴직연금 체결기준잔고,pension_inquire_present_balance,[국내주식] 주문/계좌 > 퇴직연금 체결기준잔고[v1_국내주식-032] ※ 55번 계좌(DC가입자계좌)의 경우 해당 API 이용이 불가합니다. KIS Developers API의 경우 HTS ID에 반드시 연결되어있어야만 API 신청 및 앱정보 발급이 가능한 서비스로 개발되어서 실물계좌가 아닌 55번 계좌는 API 이용이 불가능한 점 양해 부탁드립니다.,"cano (str): [필수] 종합계좌번호 (ex. '12345678')
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2965:NK100 (str): 연속조회키100","Tuple[pd.DataFrame, pd.DataFrame]: (output1, output2) 데이터프레임 튜플","     df1, df2 = pension_inquire_present_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, user_dvsn_cd=""00"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2987:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/pension_inquire_present_balance/pension_inquire_present_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/pension_inquire_present_balance/chk_pension_inquire_present_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3240:domestic_stock,주문/계좌,퇴직연금 잔고조회,pension_inquire_balance,"주식, ETF, ETN만 조회 가능하며 펀드는 조회 불가합니다. ​※ 55번 계좌(DC가입자계좌)의 경우 해당 API 이용이 불가합니다. KIS Developers API의 경우 HTS ID에 반드시 연결되어있어야만 API 신청 및 앱정보 발급이 가능한 서비스로 개발되어서 실물계좌가 아닌 55번 계좌는 API 이용이 불가능한 점 양해 부탁드립니다.","cano (str): [필수] 종합계좌번호 (ex. 12345678)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3250:max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: 퇴직연금 잔고 데이터","     df1, df2 = pension_inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, acca_dvsn_cd=""00"", inqr_dvsn=""00"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3275:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/pension_inquire_balance/pension_inquire_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/pension_inquire_balance/chk_pension_inquire_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3276:domestic_stock,주문/계좌,주식잔고조회_실현손익,inquire_balance_rlz_pl,"주식잔고조회_실현손익 API입니다. 한국투자 HTS(eFriend Plus) [0800] 국내 체결기준잔고 화면을 API로 개발한 사항으로, 해당 화면을 참고하시면 기능을 이해하기 쉽습니다. (참고: 포럼 - 공지사항 - 신규 API 추가 안내(주식잔고조회_실현손익 외 1건))","cano (str): [필수] 종합계좌번호 (계좌번호 체계(8-2)의 앞 8자리)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3292:max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: 주식잔고조회_실현손익 데이터 (output1, output2)","     df1, df2 = inquire_balance_rlz_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, afhr_flpr_yn=""N"", inqr_dvsn=""02"", unpr_dvsn=""01"", fund_sttl_icld_yn=""N"", fncg_amt_auto_rdpt_yn=""N"", prcs_dvsn=""01"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3346:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_balance_rlz_pl/inquire_balance_rlz_pl.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_balance_rlz_pl/chk_inquire_balance_rlz_pl.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:5035:domestic_stock,종목정보,국내주식 대차대조표,finance_balance_sheet,[국내주식] 종목정보 국내주식 대차대조표[v1_국내주식-078] 국내주식 대차대조표 API를 호출하여 DataFrame으로 반환합니다.,"fid_div_cls_code (str): 0: 년, 1: 분기
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:5041:max_depth (int): 최대 재귀 깊이 (기본값: 10)",Optional[pd.DataFrame]: 국내주식 대차대조표 데이터,"     df = finance_balance_sheet(""0"", ""J"", ""000660"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:5054:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/finance_balance_sheet/finance_balance_sheet.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/finance_balance_sheet/chk_finance_balance_sheet.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:5145:domestic_stock,시세분석,국내주식 신용잔고 일별추이,daily_credit_balance,"국내주식 신용잔고 일별추이 API입니다. 한국투자 HTS(eFriend Plus) > [0476] 국내주식 신용잔고 일별추이 화면의 기능을 API로 개발한 사항으로, 해당 화면을 참고하시면 기능을 이해하기 쉽습니다. 한 번의 호출에 최대 30건 확인 가능하며, fid_input_date_1 을 입력하여 다음 조회가 가능합니다. ※ 상환수량은 ""매도상환수량+현금상환수량""의 합계 수치입니다.","fid_cond_mrkt_div_code (str): [필수] 시장 분류 코드 (ex. J: 주식)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:5152:max_depth (int): 최대 재귀 횟수 제한",pd.DataFrame: 국내주식 신용잔고 일별추이 데이터,"     df = daily_credit_balance(""J"", ""20476"", ""005930"", ""20240313"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:5180:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/daily_credit_balance/daily_credit_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/daily_credit_balance/chk_daily_credit_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:5966:domestic_stock,순위분석,국내주식 호가잔량 순위,quote_balance,[국내주식] 순위분석 국내주식 호가잔량 순위[국내주식-089] 국내주식 호가잔량 순위 API를 호출하여 DataFrame으로 반환합니다.,"fid_vol_cnt (str): 입력값 없을때 전체 (거래량 ~)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:5977:dataframe (Optional[pd.DataFrame]): 누적 데이터프레임",Optional[pd.DataFrame]: 국내주식 호가잔량 순위 데이터,"     df = quote_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:6003:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/quote_balance/quote_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/quote_balance/chk_quote_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:6004:domestic_stock,순위분석,국내주식 신용잔고 상위,credit_balance,[국내주식] 순위분석 국내주식 신용잔고 상위[국내주식-109] 국내주식 신용잔고 상위 API를 호출하여 DataFrame으로 반환합니다.,"fid_cond_scr_div_code (str): Unique key(11701)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:6013:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame]: 국내주식 신용잔고 상위 데이터","     df1, df2 = credit_balance('11701', '0000', '2', 'J', '0')
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:6035:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/credit_balance/credit_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/credit_balance/chk_credit_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:6110:domestic_stock,순위분석,국내주식 시간외잔량 순위,after_hour_balance,[국내주식] 순위분석 국내주식 시간외잔량 순위[v1_국내주식-093] 국내주식 시간외잔량 순위 API를 호출하여 DataFrame으로 반환합니다.,"fid_input_price_1 (str): 입력값 없을때 전체 (가격 ~)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:6123:max_depth (int): 최대 재귀 깊이 (기본값: 10)",Optional[pd.DataFrame]: 국내주식 시간외잔량 순위 데이터,"     df = after_hour_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:6147:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/after_hour_balance/after_hour_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/after_hour_balance/chk_after_hour_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10664:overseas_stock,주문/계좌,해외주식 잔고,inquire_balance,[해외주식] 주문/계좌 해외주식 잔고[v1_해외주식-006] 해외주식 잔고 API를 호출하여 DataFrame으로 반환합니다.,"cano (str): 계좌번호 체계(8-2)의 앞 8자리
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10675:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame]: 해외주식 잔고 데이터","     df1, df2 = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10711:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10712:overseas_stock,주문/계좌,해외주식 체결기준현재잔고,inquire_present_balance,[해외주식] 주문/계좌 해외주식 체결기준현재잔고[v1_해외주식-008] 해외주식 체결기준현재잔고 API를 호출하여 DataFrame으로 반환합니다.,"cano (str): 계좌번호 체계(8-2)의 앞 8자리
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10724:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: 해외주식 체결기준현재잔고 데이터","     df1, df2, df3 = inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10795:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11095:overseas_stock,주문/계좌,해외주식 결제기준잔고,inquire_paymt_stdr_balance,[해외주식] 주문/계좌 해외주식 결제기준잔고[해외주식-064] 해외주식 결제기준잔고 API를 호출하여 DataFrame으로 반환합니다.,"cano (str): 종합계좌번호
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11105:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: 해외주식 결제기준잔고 데이터","     df1, df2, df3 = inquire_paymt_stdr_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11152:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_paymt_stdr_balance/inquire_paymt_stdr_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api02.py:44:rt_data = kb.get_domfuopt_inquire_ngt_balance_obj()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api02.py:48:rt_data = kb.get_domfuopt_inquire_ngt_balance_lst()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/components/execute/HoldingsList.tsx:21:  balance?: Balance | null;
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/components/execute/HoldingsList.tsx:32:  balance,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/components/execute/HoldingsList.tsx:67:      {balance && (
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/components/execute/HoldingsList.tsx:79:                {balance.deposit.toLocaleString()}원
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/components/execute/HoldingsList.tsx:85:                {balance.total_eval.toLocaleString()}원
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/inquire_paymt_stdr_balance.py:26:API_URL = "/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/inquire_paymt_stdr_balance.py:28:def inquire_paymt_stdr_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/inquire_paymt_stdr_balance.py:63:        >>> df1, df2, df3 = inquire_paymt_stdr_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/inquire_paymt_stdr_balance.py:176:            return inquire_paymt_stdr_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api01.py:51:rt_data = kb.get_inquire_balance_obj()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api01.py:55:rt_data = kb.get_inquire_balance_lst()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api01.py:86:rt_data = kb.get_inquire_balance_rlz_pl_obj()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_api01.py:88:rt_data = kb.get_inquire_balance_rlz_pl_lst()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:14:from inquire_paymt_stdr_balance import inquire_paymt_stdr_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:93:        >>> df1, df2, df3 = inquire_paymt_stdr_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, bass_dt="20250630", wcrc_frcr_dvsn_cd="01", inqr_dvsn_cd="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:110:        result1, result2, result3 = inquire_paymt_stdr_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:352:def get_overseas_inquire_balance(excg_cd="", crcy_cd="", tr_cont="", FK100="", NK100="", dataframe=None):
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:353:    url = '/uapi/overseas-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:397:def get_overseas_inquire_balance_lst(excg_cd="", crcy_cd="", tr_cont="", FK100="", NK100="", dataframe=None):
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:398:    url = '/uapi/overseas-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:448:        return get_overseas_inquire_balance_lst(excg_cd, crcy_cd, "N", FK100, NK100, dataframe)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:574:def get_overseas_inquire_present_balance(dv="03", dvsn="01", natn="000", mkt="00", inqr_dvsn="00", tr_cont="", FK100="", NK100="", dataframe=None):
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:575:    url = '/uapi/overseas-stock/v1/trading/inquire-present-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:576:    tr_id = "CTRP6504R"   # 모의투자 VTRP6504R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:1062:def get_overseas_inquire_paymt_stdr_balance(dv="03", dt="", dvsn="01", inqr_dvsn="00", tr_cont="", FK100="", NK100="", dataframe=None):
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/Sample01/kis_ovrseastk.py:1063:    url = '/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/server.py:120:ex) 내 주식 잔고 조회해줘. -> subcategory="주문/계좌", function_name="inquire_balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/server.py:159:ex) 내 채권 잔고 조회해줘. -> subcategory="주문/계좌", function_name="inquire_balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/server.py:214:ex) 내 계좌의 해외주식 잔고 알려줘. -> subcategory="주문/계좌", function_name="inquire_balance", api_name="해외주식 잔고"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/MCP/KIS Code Assistant MCP/server.py:215:ex) 해외주식 체결기준 현재잔고 보여줘. -> subcategory="주문/계좌", function_name="inquire_present_balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/elw/elw_asking_price/chk_elw_asking_price.py:140:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_account_balance/inquire_account_balance.py:22:API_URL = "/uapi/domestic-stock/v1/trading/inquire-account-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_account_balance/inquire_account_balance.py:24:def inquire_account_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_account_balance/inquire_account_balance.py:45:        >>> df1, df2 = inquire_account_balance("12345678", "21")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/package-lock.json:1785:        "balanced-match": "^1.0.0"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/package-lock.json:2413:    "node_modules/balanced-match": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/package-lock.json:2415:      "resolved": "https://registry.npmjs.org/balanced-match/-/balanced-match-1.0.2.tgz",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/package-lock.json:2436:        "balanced-match": "^1.0.0",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_account_balance/chk_inquire_account_balance.py:12:from inquire_account_balance import inquire_account_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_account_balance/chk_inquire_account_balance.py:84:        result1, result2 = inquire_account_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/websocket/delphi/MainForm.pas:74:  LogMessage('[TR_ID 예시]');
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/websocket/delphi/MainForm.pas:100:  // TR_ID가 변경되면 URL도 자동 업데이트
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/websocket/delphi/MainForm.pas:128:    ShowMessage('TR_ID를 입력해주세요.');
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/websocket/delphi/MainForm.pas:139:    LogMessage('TR_ID: ' + trId);
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/websocket/delphi/MainForm.pas:264:        LogMessage('TR_ID: ' + trId);
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/websocket/delphi/MainForm.dfm:28:    Caption = 'TR_ID:'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/websocket/delphi/MainForm.dfm:52:    TextHint = 'TR_ID ('#50696': H0STCNT0)'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/legacy/websocket/python/multi_processing_sample_ws.py:257:            print(f"\n[DEBUG parse_stock_code] TR_ID: {trid}")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py:78:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/frontend/package-lock.json:1894:        "balanced-match": "^1.0.0"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/frontend/package-lock.json:2523:    "node_modules/balanced-match": {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/frontend/package-lock.json:2525:      "resolved": "https://registry.npmjs.org/balanced-match/-/balanced-match-1.0.2.tgz",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/frontend/package-lock.json:2546:        "balanced-match": "^1.0.0",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/app/execute/page.tsx:31:  const { holdings, balance, fetchHoldings, fetchBalance, resetThrottle, isLoading: accountLoading } = useAccount();
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/app/execute/page.tsx:67:  // Fetch holdings, balance, and pending orders when authenticated
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/frontend/src/app/execute/page.tsx:289:              balance={balance}
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py:13:from inquire_balance import inquire_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py:74:        >>> df = inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_excg_cd="NASD", tr_crcy_cd="USD")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py:90:        result1, result2 = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:25:API_URL = "/uapi/overseas-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:27:def inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:64:        >>> df1, df2 = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:161:            return inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/__init__.py:81:    RebalanceSimulator,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/__init__.py:82:    RebalanceResult,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/__init__.py:149:    "RebalanceSimulator",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/__init__.py:150:    "RebalanceResult",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:844:    def simulate_rebalance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:868:            RebalanceResult: 시뮬레이션 결과
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:871:            result = client.simulate_rebalance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:879:            print(f"리밸런싱 효과: {result.rebalance_benefit:+.2%}")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:881:        from .portfolio import RebalanceSimulator, RebalanceResult
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:886:        logger.info(f"[Rebalance] 시뮬레이션 시작: period={period}")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:905:        simulator = RebalanceSimulator(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:913:        logger.info(f"[Rebalance] 완료: 효과={result.rebalance_benefit:+.2%}")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:923:        rebalance_result = None,  # Optional[RebalanceResult]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:933:            rebalance_result: 리밸런싱 시뮬레이션 결과 (옵션)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:963:            rebalance_result=rebalance_result,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:1075:    def get_balance(self):
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/client.py:1080:        return self._brokerage.get_balance()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/bond_asking_price/chk_bond_asking_price.py:90:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:15:    from ..portfolio import PortfolioMetrics, RebalanceResult
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:39:            rebalance_result=rebalance_result,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:55:        rebalance_result: Optional["RebalanceResult"] = None,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:65:            rebalance_result: 리밸런싱 시뮬레이션 결과 (옵션)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:102:        if rebalance_result is not None:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:103:            html_parts.append(self._generate_rebalance_section(rebalance_result))
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:287:    def _generate_rebalance_section(self, result: "RebalanceResult") -> str:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:291:        fig = PortfolioVisualizer.rebalance_comparison(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:298:        if result.rebalance_benefit > 0.01:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:300:        elif result.rebalance_benefit > -0.01:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:308:            <div class="rebalance-summary">
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:310:                <div class="rebalance-stats">
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:312:                    <span>Buy & Hold: <strong>{result.no_rebalance_return:+.2%}</strong></span>
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:313:                    <span>효과: <strong class="{'positive' if result.rebalance_benefit > 0 else 'negative'}">{result.rebalance_benefit:+.2%}</strong></span>
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:314:                    <span>리밸런싱 횟수: <strong>{result.rebalance_count}회</strong></span>
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:546:        .rebalance-summary {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:556:        .rebalance-stats {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:562:        .rebalance-stats span {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:566:        .rebalance-stats strong {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:570:        .rebalance-stats strong.positive { color: var(--success); }
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/report/portfolio_report.py:571:        .rebalance-stats strong.negative { color: var(--danger); }
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/providers/base.py:165:    def get_balance(self) -> AccountBalance:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/bond_ccnl/chk_bond_ccnl.py:68:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/providers/kis/brokerage.py:201:        API: /uapi/domestic-stock/v1/trading/inquire-balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/providers/kis/brokerage.py:202:        TR ID: TTTC8434R (실전), VTTC8434R (모의)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/providers/kis/brokerage.py:256:    def get_balance(self) -> AccountBalance:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/providers/kis/constants.py:37:    BALANCE_REAL = "TTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/providers/kis/constants.py:38:    BALANCE_PAPER = "VTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/providers/kis/constants.py:75:    DOMESTIC_BALANCE = "/uapi/domestic-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/order_executor.py:200:            # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:14:from inquire_present_balance import inquire_present_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:122:        >>> df1, df2, df3 = inquire_present_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, wcrc_frcr_dvsn_cd="02", natn_cd="000", tr_mket_cd="00", inqr_dvsn_cd="00", env_dv="real")  # 실전투자
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:146:        result1, result2, result3 = inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:20:    from .rebalance import RebalanceResult
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:250:    def rebalance_comparison(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:251:        result: "RebalanceResult",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:255:        show_rebalance_points: bool = True,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:260:            result: RebalanceResult 객체
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:262:            show_rebalance_points: 리밸런싱 시점 표시 여부
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:279:            x=result.no_rebalance_curve.index,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:280:            y=result.no_rebalance_curve.values,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:282:            name=f"Buy & Hold ({result.no_rebalance_return:+.2%})",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:287:        if show_rebalance_points and result.rebalance_dates:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:288:            for date in result.rebalance_dates:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:297:        benefit_text = f"리밸런싱 효과: {result.rebalance_benefit:+.2%}"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:309:                text=f"{title} (효과: {result.rebalance_benefit:+.2%})",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/visualizer.py:332:            comparison_df: RebalanceSimulator.compare_periods() 결과
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:26:API_URL = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:28:def inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:67:        >>> df1, df2, df3 = inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:108:        tr_id = "VTRP6504R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:189:            return inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:23:# 1. RebalanceResult - 시뮬레이션 결과 모델
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:27:class RebalanceResult:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:32:        no_rebalance_curve: Buy & Hold 자산 곡선
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:34:        no_rebalance_return: Buy & Hold 최종 수익률
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:35:        rebalance_benefit: 리밸런싱 효과 (수익률 차이)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:36:        rebalance_dates: 리밸런싱 실행 날짜 목록
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:38:        rebalance_count: 리밸런싱 횟수
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:43:    no_rebalance_curve: pd.Series
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:47:    no_rebalance_return: float
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:48:    rebalance_benefit: float
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:51:    rebalance_dates: List[datetime]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:52:    rebalance_count: int
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:62:            "BuyHold_수익률": self.no_rebalance_return,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:63:            "리밸런싱_효과": self.rebalance_benefit,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:64:            "리밸런싱_횟수": self.rebalance_count,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:71:            f"RebalanceResult(\n"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:73:            f"  Buy&Hold 수익률={self.no_rebalance_return:.2%},\n"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:74:            f"  리밸런싱 효과={self.rebalance_benefit:+.2%},\n"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:75:            f"  리밸런싱 횟수={self.rebalance_count}\n"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:81:# 2. RebalanceSimulator - 리밸런싱 시뮬레이터
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:84:class RebalanceSimulator:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:90:        simulator = RebalanceSimulator(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:97:        print(f"리밸런싱 효과: {result.rebalance_benefit:+.2%}")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:132:    ) -> RebalanceResult:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:146:            RebalanceResult: 시뮬레이션 결과
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:153:        no_rebalance_equity = self._buy_and_hold(returns)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:156:        rebalance_equity, rebalance_dates, turnover, total_cost = self._with_rebalance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:161:        final_return = (rebalance_equity.iloc[-1] / self.initial_capital) - 1
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:162:        no_rebalance_return = (no_rebalance_equity.iloc[-1] / self.initial_capital) - 1
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:164:        result = RebalanceResult(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:165:            equity_curve=rebalance_equity,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:166:            no_rebalance_curve=no_rebalance_equity,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:168:            no_rebalance_return=no_rebalance_return,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:169:            rebalance_benefit=final_return - no_rebalance_return,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:170:            rebalance_dates=rebalance_dates,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:171:            rebalance_count=len(rebalance_dates),
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:178:            f"B&H={no_rebalance_return:.2%}, "
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:179:            f"효과={result.rebalance_benefit:+.2%}"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:208:    def _with_rebalance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:223:        rebalance_dates = []
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:228:        rebalance_mask = self._get_rebalance_mask(returns.index, period)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:240:            should_rebalance = False
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:246:                    should_rebalance = True
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:247:            elif rebalance_mask[i]:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:248:                should_rebalance = True
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:250:            if should_rebalance:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:263:                rebalance_dates.append(date)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:274:        return equity, rebalance_dates, total_turnover, total_cost
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:276:    def _get_rebalance_mask(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:355:                "rebalance_benefit": result.rebalance_benefit,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:356:                "rebalance_count": result.rebalance_count,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:364:            "final_return": result.no_rebalance_return,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:365:            "rebalance_benefit": 0,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/rebalance.py:366:            "rebalance_count": 0,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:37:_balance_cache_lock = threading.Lock()
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:38:_balance_cache = {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:46:def _fetch_balance_raw(env_dv: str = "real"):
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:52:    tr_id = "TTTC8434R" if is_real else "VTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:69:        "/uapi/domestic-stock/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:80:def _get_balance_cached(env_dv: str = "real"):
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:82:    global _balance_cache
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:84:    with _balance_cache_lock:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:87:            _balance_cache["data"] is not None
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:88:            and _balance_cache["env_dv"] == env_dv
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:89:            and (now - _balance_cache["timestamp"]) < _BALANCE_CACHE_TTL
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:91:            return _balance_cache["data"]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:94:    data = _fetch_balance_raw(env_dv)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:96:    with _balance_cache_lock:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:97:        _balance_cache = {
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:106:def clear_balance_cache():
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:108:    global _balance_cache
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:109:    with _balance_cache_lock:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:110:        _balance_cache = {"data": None, "timestamp": 0.0, "env_dv": None}
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:149:        # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:294:        raw = _get_balance_cached(env_dv)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/strategy_builder/core/data_fetcher.py:424:        raw = _get_balance_cached(env_dv)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/__init__.py:20:from .rebalance import RebalanceSimulator, RebalanceResult
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/__init__.py:26:    "RebalanceSimulator",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/portfolio/__init__.py:27:    "RebalanceResult",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/backtester/kis_backtest/strategies/preset/momentum.py:120:                "rebalance": "monthly",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_balance/chk_inquire_balance.py:15:from inquire_balance import inquire_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_balance/chk_inquire_balance.py:58:        >>> df = inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_cndt="00", pdno="", buy_dt="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_balance/chk_inquire_balance.py:77:        result = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_balance/inquire_balance.py:28:API_URL = "/uapi/domestic-bond/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_balance/inquire_balance.py:30:def inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_balance/inquire_balance.py:65:        >>> df = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_balance/inquire_balance.py:131:            return inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/elw/elw_ccnl/chk_elw_ccnl.py:127:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/bond_index_ccnl/chk_bond_index_ccnl.py:72:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/ccnl_notice/chk_ccnl_notice.py:73:- TR_ID : 등록한 tr_id
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/after_hour_balance/after_hour_balance.py:29:API_URL = "/uapi/domestic-stock/v1/ranking/after-hour-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/after_hour_balance/after_hour_balance.py:31:def after_hour_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/after_hour_balance/after_hour_balance.py:72:        >>> df = after_hour_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/after_hour_balance/after_hour_balance.py:152:            return after_hour_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/after_hour_balance/chk_after_hour_balance.py:14:from after_hour_balance import after_hour_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/after_hour_balance/chk_after_hour_balance.py:64:        >>> df = after_hour_balance(fid_input_price_1="", fid_cond_mrkt_div_code="J", fid_cond_scr_div_code="20176", fid_rank_sort_cls_code="1", fid_div_cls_code="0", fid_input_iscd="0000", fid_trgt_exls_cls_code="0", fid_trgt_cls_code="0", fid_vol_cnt="", fid_input_price_2="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/after_hour_balance/chk_after_hour_balance.py:79:        result = after_hour_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance_rlz_pl/inquire_balance_rlz_pl.py:24:API_URL = "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance_rlz_pl/inquire_balance_rlz_pl.py:26:def inquire_balance_rlz_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance_rlz_pl/inquire_balance_rlz_pl.py:73:        >>> df1, df2 = inquire_balance_rlz_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, afhr_flpr_yn="N", inqr_dvsn="02", unpr_dvsn="01", fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="01")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance_rlz_pl/inquire_balance_rlz_pl.py:152:            return inquire_balance_rlz_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance_rlz_pl/chk_inquire_balance_rlz_pl.py:12:from inquire_balance_rlz_pl import inquire_balance_rlz_pl
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance_rlz_pl/chk_inquire_balance_rlz_pl.py:101:        result1, result2 = inquire_balance_rlz_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/index_exp_ccnl/chk_index_exp_ccnl.py:87:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/index_program_trade/chk_index_program_trade.py:161:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_present_balance/chk_pension_inquire_present_balance.py:12:from pension_inquire_present_balance import pension_inquire_present_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_present_balance/chk_pension_inquire_present_balance.py:71:        result1, result2 = pension_inquire_present_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_present_balance/pension_inquire_present_balance.py:22:API_URL = "/uapi/domestic-stock/v1/trading/pension/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_present_balance/pension_inquire_present_balance.py:25:def pension_inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_present_balance/pension_inquire_present_balance.py:49:        >>> df1, df2 = pension_inquire_present_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, user_dvsn_cd="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/credit_balance/chk_credit_balance.py:14:from credit_balance import credit_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/credit_balance/chk_credit_balance.py:67:        >>> df1, df2 = credit_balance(fid_cond_scr_div_code="11701", fid_input_iscd="0000", fid_option="2", fid_cond_mrkt_div_code="J", fid_rank_sort_cls_code="0")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/credit_balance/chk_credit_balance.py:82:        result1, result2 = credit_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/quote_balance/chk_quote_balance.py:8:from quote_balance import quote_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/quote_balance/chk_quote_balance.py:59:        >>> df = quote_balance(fid_vol_cnt="1000", fid_cond_mrkt_div_code="J", fid_cond_scr_div_code="20172", fid_input_iscd="0001", fid_rank_sort_cls_code="0", fid_div_cls_code="0", fid_trgt_cls_code="0", fid_trgt_exls_cls_code="0", fid_input_price_1="50000", fid_input_price_2="100000")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/quote_balance/chk_quote_balance.py:70:    result = quote_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/quote_balance/quote_balance.py:22:API_URL = "/uapi/domestic-stock/v1/ranking/quote-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/quote_balance/quote_balance.py:24:def quote_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/quote_balance/quote_balance.py:61:        >>> df = quote_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/quote_balance/quote_balance.py:129:            return quote_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/ccnl_krx/chk_ccnl_krx.py:103:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/credit_balance/credit_balance.py:25:API_URL = "/uapi/domestic-stock/v1/ranking/credit-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/credit_balance/credit_balance.py:27:def credit_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/credit_balance/credit_balance.py:60:        >>> df1, df2 = credit_balance('11701', '0000', '2', 'J', '0')
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/credit_balance/credit_balance.py:150:            return credit_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/overtime_exp_ccnl_krx/chk_overtime_exp_ccnl_krx.py:103:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/program_trade_krx/chk_program_trade_krx.py:62:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/member_krx/chk_member_krx.py:137:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/inquire_balance_valuation_pl.py:23:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/inquire_balance_valuation_pl.py:26:def inquire_balance_valuation_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/inquire_balance_valuation_pl.py:60:        >>> df1, df2 = inquire_balance_valuation_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn="01", excc_stat_cd="1")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/inquire_balance_valuation_pl.py:120:            return inquire_balance_valuation_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/market_status_krx/chk_market_status_krx.py:59:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/overtime_ccnl_krx/chk_overtime_ccnl_krx.py:103:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/chk_inquire_balance_valuation_pl.py:12:from inquire_balance_valuation_pl import inquire_balance_valuation_pl
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/chk_inquire_balance_valuation_pl.py:95:        result1, result2 = inquire_balance_valuation_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn="01",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance/chk_inquire_balance.py:12:from inquire_balance import inquire_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance/chk_inquire_balance.py:100:        result1, result2 = inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance/inquire_balance.py:24:API_URL = "/uapi/domestic-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance/inquire_balance.py:26:def inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance/inquire_balance.py:73:        >>> df1, df2 = inquire_balance(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, afhr_flpr_yn="N", inqr_dvsn="01", unpr_dvsn="01", fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance/inquire_balance.py:116:        tr_id = "TTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance/inquire_balance.py:118:        tr_id = "VTTC8434R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_balance/inquire_balance.py:160:            return inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/daily_credit_balance/chk_daily_credit_balance.py:12:from daily_credit_balance import daily_credit_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/daily_credit_balance/chk_daily_credit_balance.py:78:        result1 = daily_credit_balance(fid_cond_mrkt_div_code="J", fid_cond_scr_div_code="20476",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/daily_credit_balance/chk_daily_credit_balance.py:101:        result2 = daily_credit_balance(fid_cond_mrkt_div_code="J", fid_cond_scr_div_code="20476",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_asking_price_exp_ccn/inquire_asking_price_exp_ccn.py:57:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/daily_credit_balance/daily_credit_balance.py:24:API_URL = "/uapi/domestic-stock/v1/quotations/daily-credit-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/daily_credit_balance/daily_credit_balance.py:26:def daily_credit_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/daily_credit_balance/daily_credit_balance.py:57:        >>> df = daily_credit_balance("J", "20476", "005930", "20240313")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/daily_credit_balance/daily_credit_balance.py:104:            return daily_credit_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_time_overtimeconclusion/inquire_time_overtimeconclusion.py:62:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/exp_ccnl_krx/chk_exp_ccnl_krx.py:103:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/asking_price_krx/chk_asking_price_krx.py:114:- TR_ID : 등록한 tr_id
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_daily_overtimeprice/inquire_daily_overtimeprice.py:57:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/finance_balance_sheet/finance_balance_sheet.py:25:API_URL = "/uapi/domestic-stock/v1/finance/balance-sheet"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/finance_balance_sheet/finance_balance_sheet.py:27:def finance_balance_sheet(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/finance_balance_sheet/finance_balance_sheet.py:54:        >>> df = finance_balance_sheet("0", "J", "000660")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/finance_balance_sheet/finance_balance_sheet.py:109:            return finance_balance_sheet(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/finance_balance_sheet/chk_finance_balance_sheet.py:14:from finance_balance_sheet import finance_balance_sheet
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/finance_balance_sheet/chk_finance_balance_sheet.py:56:        >>> df = finance_balance_sheet(fid_div_cls_code="0", fid_cond_mrkt_div_code="J", fid_input_iscd="000660")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/finance_balance_sheet/chk_finance_balance_sheet.py:69:        result = finance_balance_sheet(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_balance/pension_inquire_balance.py:24:API_URL = "/uapi/domestic-stock/v1/trading/pension/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_balance/pension_inquire_balance.py:26:def pension_inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_balance/pension_inquire_balance.py:62:        >>> df1, df2 = pension_inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, acca_dvsn_cd="00", inqr_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_balance/pension_inquire_balance.py:122:            return pension_inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_balance/chk_pension_inquire_balance.py:12:from pension_inquire_balance import pension_inquire_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_balance/chk_pension_inquire_balance.py:91:        result1, result2 = pension_inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, acca_dvsn_cd="00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/overtime_asking_price_krx/chk_overtime_asking_price_krx.py:120:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/index_ccnl/chk_index_ccnl.py:83:- TR_ID : 등록한 tr_id (ex. H0STCNT0)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance/chk_inquire_balance.py:11:from inquire_balance import inquire_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance/chk_inquire_balance.py:96:        result1, result2 = inquire_balance(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn="01",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance/inquire_balance.py:23:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance/inquire_balance.py:25:def inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance/inquire_balance.py:60:        >>> df1, df2 = inquire_balance(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, mgna_dvsn="01", excc_stat_cd="1")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance/inquire_balance.py:129:            return inquire_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_balance/inquire_ngt_balance.py:24:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_balance/inquire_ngt_balance.py:26:def inquire_ngt_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_balance/inquire_ngt_balance.py:61:        >>> df1, df2 = inquire_ngt_balance("12345678", "01", "01", "1")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_balance/inquire_ngt_balance.py:122:            return inquire_ngt_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_asking_price/inquire_asking_price.py:56:    # TR_ID 설정
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_balance/chk_inquire_ngt_balance.py:12:from inquire_ngt_balance import inquire_ngt_balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_balance/chk_inquire_ngt_balance.py:101:        result1, result2 = inquire_ngt_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/chk_inquire_balance_settlement_pl.py:11:from inquire_balance_settlement_pl import inquire_balance_settlement_pl
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/chk_inquire_balance_settlement_pl.py:73:        result1, result2 = inquire_balance_settlement_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_dt="20230906")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/inquire_balance_settlement_pl.py:23:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/inquire_balance_settlement_pl.py:25:def inquire_balance_settlement_pl(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/inquire_balance_settlement_pl.py:56:        >>> df1, df2 = inquire_balance_settlement_pl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_dt="20230906")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/inquire_balance_settlement_pl.py:112:            return inquire_balance_settlement_pl(

exec
/bin/zsh -lc "sed -n '560,700p' /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py && sed -n '3679,3795p' /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py && sed -n '1180,1255p' /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
        return pd.DataFrame(), pd.DataFrame()


##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 잔고 [v1_해외주식-006]
##############################################################################################

def inquire_balance(
        cano: str,  # 종합계좌번호
        acnt_prdt_cd: str,  # 계좌상품코드
        ovrs_excg_cd: str,  # 해외거래소코드
        tr_crcy_cd: str,  # 거래통화코드
        FK200: str = "",  # 연속조회검색조건200
        NK200: str = "",  # 연속조회키200
        env_dv: str = "real",  # 실전모의구분
        dataframe1: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output1)
        dataframe2: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output2)
        tr_cont: str = "",
        depth: int = 0,
        max_depth: int = 10
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    [해외주식] 주문/계좌 
    해외주식 잔고[v1_해외주식-006]
    해외주식 잔고 API를 호출하여 DataFrame으로 반환합니다.
    
    Args:
        cano (str): 계좌번호 체계(8-2)의 앞 8자리
        acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
        ovrs_excg_cd (str): [모의] NASD : 나스닥 NYSE : 뉴욕  AMEX : 아멕스  [실전] NASD : 미국전체 NAS : 나스닥 NYSE : 뉴욕  AMEX : 아멕스  [모의/실전 공통] SEHK : 홍콩 SHAA : 중국상해 SZAA : 중국심천 TKSE : 일본 HASE : 베트남 하노이 VNSE : 베트남 호치민
        tr_crcy_cd (str): USD : 미국달러 HKD : 홍콩달러 CNY : 중국위안화 JPY : 일본엔화 VND : 베트남동
        FK200 (str): 공란 : 최초 조회시 이전 조회 Output CTX_AREA_FK200값 : 다음페이지 조회시(2번째부터)
        NK200 (str): 공란 : 최초 조회시 이전 조회 Output CTX_AREA_NK200값 : 다음페이지 조회시(2번째부터)
        env_dv (str): 실전모의구분 (real:실전, demo:모의)
        dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
        dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)
        tr_cont (str): 연속 거래 여부
        depth (int): 현재 재귀 깊이
        max_depth (int): 최대 재귀 깊이 (기본값: 10)
        
    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 해외주식 잔고 데이터
        
    Example:
        >>> df1, df2 = inquire_balance(
        ...     cano=trenv.my_acct,
        ...     acnt_prdt_cd=trenv.my_prod,
        ...     ovrs_excg_cd="NASD",
        ...     tr_crcy_cd="USD",
        ...     FK200="",
        ...     NK200=""
        ... )
        >>> print(df1)
        >>> print(df2)
    """
    # [필수 파라미터 검증]
    if not cano:
        logger.error("cano is required. (e.g. '810XXXXX')")
        raise ValueError("cano is required. (e.g. '810XXXXX')")
    if not acnt_prdt_cd:
        logger.error("acnt_prdt_cd is required. (e.g. '01')")
        raise ValueError("acnt_prdt_cd is required. (e.g. '01')")
    if not ovrs_excg_cd:
        logger.error("ovrs_excg_cd is required. (e.g. 'NASD')")
        raise ValueError("ovrs_excg_cd is required. (e.g. 'NASD')")
    if not tr_crcy_cd:
        logger.error("tr_crcy_cd is required. (e.g. 'USD')")
        raise ValueError("tr_crcy_cd is required. (e.g. 'USD')")

    # 최대 재귀 깊이 체크
    if depth >= max_depth:
        logger.warning("Maximum recursion depth (%d) reached. Stopping further requests.", max_depth)
        return dataframe1 if dataframe1 is not None else pd.DataFrame(), dataframe2 if dataframe2 is not None else pd.DataFrame()

    # TR ID 설정 (모의투자 지원 로직)
    if env_dv == "real":
        tr_id = "TTTS3012R"  # 실전투자용 TR ID
    elif env_dv == "demo":
        tr_id = "VTTS3012R"  # 모의투자용 TR ID
    else:
        raise ValueError("env_dv can only be 'real' or 'demo'")

    api_url = "/uapi/overseas-stock/v1/trading/inquire-balance"

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": ovrs_excg_cd,
        "TR_CRCY_CD": tr_crcy_cd,
        "CTX_AREA_FK200": FK200,
        "CTX_AREA_NK200": NK200,
    }

    res = ka._url_fetch(api_url=api_url, ptr_id=tr_id, tr_cont=tr_cont, params=params)

    if res.isOK():
        # output1 처리
        if hasattr(res.getBody(), 'output1'):
            output_data = res.getBody().output1
            if output_data:
                # output1은 단일 객체, output2는 배열일 수 있음
                if isinstance(output_data, list):
                    current_data1 = pd.DataFrame(output_data)
                else:
                    # 단일 객체인 경우 리스트로 감싸서 DataFrame 생성
                    current_data1 = pd.DataFrame([output_data])

                if dataframe1 is not None:
                    dataframe1 = pd.concat([dataframe1, current_data1], ignore_index=True)
                else:
                    dataframe1 = current_data1
            else:
                if dataframe1 is None:
                    dataframe1 = pd.DataFrame()
        else:
            if dataframe1 is None:
                dataframe1 = pd.DataFrame()
        # output2 처리
        if hasattr(res.getBody(), 'output2'):
            output_data = res.getBody().output2
            if output_data:
                # output1은 단일 객체, output2는 배열일 수 있음
                if isinstance(output_data, list):
                    current_data2 = pd.DataFrame(output_data)
                else:
                    # 단일 객체인 경우 리스트로 감싸서 DataFrame 생성
                    current_data2 = pd.DataFrame([output_data])

                if dataframe2 is not None:
                    dataframe2 = pd.concat([dataframe2, current_data2], ignore_index=True)
                else:
                    dataframe2 = current_data2
            else:
                if dataframe2 is None:
                    dataframe2 = pd.DataFrame()
        else:
            if dataframe2 is None:
                dataframe2 = pd.DataFrame()
        tr_cont, FK200, NK200 = res.getHeader().tr_cont, res.getBody().ctx_area_fk200, res.getBody().ctx_area_nk200

        if tr_cont in ["M", "F"]:
def inquire_balance(
        env_dv: str,  # 실전모의구분
        cano: str,  # 종합계좌번호
        acnt_prdt_cd: str,  # 계좌상품코드
        afhr_flpr_yn: str,  # 시간외단일가·거래소여부
        inqr_dvsn: str,  # 조회구분
        unpr_dvsn: str,  # 단가구분
        fund_sttl_icld_yn: str,  # 펀드결제분포함여부
        fncg_amt_auto_rdpt_yn: str,  # 융자금액자동상환여부
        prcs_dvsn: str,  # 처리구분
        FK100: str = "",  # 연속조회검색조건100
        NK100: str = "",  # 연속조회키100
        tr_cont: str = "",  # 연속거래여부
        dataframe1: Optional[pd.DataFrame] = None,  # 누적 데이터프레임1
        dataframe2: Optional[pd.DataFrame] = None,  # 누적 데이터프레임2
        depth: int = 0,  # 내부 재귀깊이 (자동관리)
        max_depth: int = 10  # 최대 재귀 횟수 제한
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    주식 잔고조회 API입니다. 
    실전계좌의 경우, 한 번의 호출에 최대 50건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다. 
    모의계좌의 경우, 한 번의 호출에 최대 20건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다. 

    * 당일 전량매도한 잔고도 보유수량 0으로 보여질 수 있으나, 해당 보유수량 0인 잔고는 최종 D-2일 이후에는 잔고에서 사라집니다.
    
    Args:
        env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)
        cano (str): [필수] 종합계좌번호 (ex. 계좌번호 체계(8-2)의 앞 8자리)
        acnt_prdt_cd (str): [필수] 계좌상품코드 (ex. 계좌번호 체계(8-2)의 뒤 2자리)
        afhr_flpr_yn (str): [필수] 시간외단일가·거래소여부 (ex. N:기본값, Y:시간외단일가, X:NXT)
        inqr_dvsn (str): [필수] 조회구분 (ex. 01 – 대출일별 | 02 – 종목별)
        unpr_dvsn (str): [필수] 단가구분 (ex. 01)
        fund_sttl_icld_yn (str): [필수] 펀드결제분포함여부 (ex. N, Y)
        fncg_amt_auto_rdpt_yn (str): [필수] 융자금액자동상환여부 (ex. N)
        prcs_dvsn (str): [필수] 처리구분 (ex. 00: 전일매매포함, 01:전일매매미포함)
        FK100 (str): 연속조회검색조건100
        NK100 (str): 연속조회키100
        tr_cont (str): 연속거래여부
        dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임1
        dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임2
        depth (int): 내부 재귀깊이 (자동관리)
        max_depth (int): 최대 재귀 횟수 제한

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 주식잔고조회 데이터 (output1, output2)
        
    Example:
        >>> df1, df2 = inquire_balance(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, afhr_flpr_yn="N", inqr_dvsn="01", unpr_dvsn="01", fund_sttl_icld_yn="N", fncg_amt_auto_rdpt_yn="N", prcs_dvsn="00")
        >>> print(df1)
        >>> print(df2)
    """
    api_url = "/uapi/domestic-stock/v1/trading/inquire-balance"

    # 필수 파라미터 검증
    if env_dv == "":
        raise ValueError("env_dv is required (e.g. 'real:실전, demo:모의')")

    if cano == "":
        raise ValueError("cano is required (e.g. '계좌번호 체계(8-2)의 앞 8자리')")

    if acnt_prdt_cd == "":
        raise ValueError("acnt_prdt_cd is required (e.g. '계좌번호 체계(8-2)의 뒤 2자리')")

    if afhr_flpr_yn == "":
        raise ValueError("afhr_flpr_yn is required (e.g. 'N:기본값, Y:시간외단일가, X:NXT')")

    if inqr_dvsn == "":
        raise ValueError("inqr_dvsn is required (e.g. '01 – 대출일별 | 02 – 종목별')")

    if unpr_dvsn == "":
        raise ValueError("unpr_dvsn is required (e.g. '01')")

    if fund_sttl_icld_yn == "":
        raise ValueError("fund_sttl_icld_yn is required (e.g. 'N, Y')")

    if fncg_amt_auto_rdpt_yn == "":
        raise ValueError("fncg_amt_auto_rdpt_yn is required (e.g. 'N')")

    if prcs_dvsn == "":
        raise ValueError("prcs_dvsn is required (e.g. '00: 전일매매포함, 01:전일매매미포함')")

    if depth > max_depth:
        logging.warning("Max recursive depth reached.")
        if dataframe1 is None:
            dataframe1 = pd.DataFrame()
        if dataframe2 is None:
            dataframe2 = pd.DataFrame()
        return dataframe1, dataframe2

    # tr_id 설정
    if env_dv == "real":
        tr_id = "TTTC8434R"
    elif env_dv == "demo":
        tr_id = "VTTC8434R"
    else:
        raise ValueError("env_dv is required (e.g. 'real' or 'demo')")

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "AFHR_FLPR_YN": afhr_flpr_yn,
        "OFL_YN": "",
        "INQR_DVSN": inqr_dvsn,
        "UNPR_DVSN": unpr_dvsn,
        "FUND_STTL_ICLD_YN": fund_sttl_icld_yn,
        "FNCG_AMT_AUTO_RDPT_YN": fncg_amt_auto_rdpt_yn,
        "PRCS_DVSN": prcs_dvsn,
        "CTX_AREA_FK100": FK100,
        "CTX_AREA_NK100": NK100
    }

    res = ka._url_fetch(api_url, tr_id, tr_cont, params)

    if res.isOK():
        # output1 처리
        current_data1 = pd.DataFrame(res.getBody().output1)
        if dataframe1 is not None:
        else:
            if dataframe3 is None:
                dataframe3 = pd.DataFrame()
        tr_cont = res.getHeader().tr_cont

        if tr_cont in ["M", "F"]:
            logger.info("Calling next page...")
            ka.smart_sleep()
            return inquire_paymt_stdr_balance(
                cano=cano,
                acnt_prdt_cd=acnt_prdt_cd,
                bass_dt=bass_dt,
                wcrc_frcr_dvsn_cd=wcrc_frcr_dvsn_cd,
                inqr_dvsn_cd=inqr_dvsn_cd,
                dataframe1=dataframe1,
                dataframe2=dataframe2,
                dataframe3=dataframe3,
                tr_cont="N",
                depth=depth + 1,
                max_depth=max_depth
            )
        else:
            logger.info("Data fetch complete.")
            return dataframe1, dataframe2, dataframe3
    else:
        logger.error("API call failed: %s - %s", res.getErrorCode(), res.getErrorMessage())
        res.printError(api_url)
        # 이미 수집된 데이터가 있으면 그것을 반환, 없으면 빈 DataFrame 반환
        if dataframe1 is not None and not dataframe1.empty:
            logger.info("Returning already collected data due to API error.")
            return dataframe1, dataframe2 if dataframe2 is not None else pd.DataFrame(), dataframe3 if dataframe3 is not None else pd.DataFrame()
        else:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 기간손익 [v1_해외주식-032]
##############################################################################################

def inquire_period_profit(
        cano: str,  # 종합계좌번호
        acnt_prdt_cd: str,  # 계좌상품코드
        ovrs_excg_cd: str,  # 해외거래소코드
        natn_cd: str,  # 국가코드
        crcy_cd: str,  # 통화코드
        pdno: str,  # 상품번호
        inqr_strt_dt: str,  # 조회시작일자
        inqr_end_dt: str,  # 조회종료일자
        wcrc_frcr_dvsn_cd: str,  # 원화외화구분코드
        FK200: str,  # 연속조회검색조건200
        NK200: str,  # 연속조회키200
        dataframe1: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output1)
        dataframe2: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output2)
        tr_cont: str = "",
        depth: int = 0,
        max_depth: int = 10
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    [해외주식] 주문/계좌 
    해외주식 기간손익[v1_해외주식-032]
    해외주식 기간손익 API를 호출하여 DataFrame으로 반환합니다.
    
    Args:
        cano (str): 계좌번호 체계(8-2)의 앞 8자리
        acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
        ovrs_excg_cd (str): 공란 : 전체,  NASD : 미국, SEHK : 홍콩, SHAA : 중국, TKSE : 일본, HASE : 베트남
        natn_cd (str): 공란(Default)
        crcy_cd (str): 공란 : 전체 USD : 미국달러, HKD : 홍콩달러, CNY : 중국위안화,  JPY : 일본엔화, VND : 베트남동
        pdno (str): 공란 : 전체
        inqr_strt_dt (str): YYYYMMDD
        inqr_end_dt (str): YYYYMMDD
        wcrc_frcr_dvsn_cd (str): 01 : 외화, 02 : 원화
        FK200 (str): 연속조회검색조건200
        NK200 (str): 연속조회키200
        dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
        dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)

exec
/bin/zsh -lc "rg -n \"def inquire_present_balance|CTRP6504R|VTRP6504R|inquire-present-balance|tr_id = \\\"VTTS3012R\\\"|frcr_dncl_amt_2|ord_psbl_cash\" /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py -S" in /Users/manager/side/makemoney
 succeeded in 0ms:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:98:        tr_id = "VTTS3012R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:26:API_URL = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:28:def inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:106:        tr_id = "CTRP6504R"  # 실전투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:108:        tr_id = "VTRP6504R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:638:        tr_id = "VTTS3012R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1599:def inquire_present_balance(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1677:        tr_id = "CTRP6504R"  # 실전투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1679:        tr_id = "VTRP6504R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1683:    api_url = "/uapi/overseas-stock/v1/trading/inquire-present-balance"

codex
The KIS sample repo confirms two useful overseas balance choices: `VTTS3012R` for overseas stock balance and `VTRP6504R` for present/settlement-style overseas balance. For this engine’s current position map, `VTTS3012R` is the direct fit; `VTRP6504R` is useful if you want settled/current account buckets.
web search: 
web search: https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py
web search: 
web search: https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py
exec
/bin/zsh -lc 'rg -n "nccs|NCCS|미체결|inquire-nccs|3018|0081R|VTTS3018|VTTC0081R" /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user -S' in /Users/manager/side/makemoney
 succeeded in 0ms:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_examples.py:111:            ccld_nccs_dvsn="00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_examples.py:184:                                            end_ord_dt="20250613", sll_buy_dvsn_cd="00", ccld_nccs_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_examples.py:71:df1, df2 = inquire_daily_ccld(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_strt_dt="20250601", inqr_end_dt="20250630", sll_buy_dvsn_cd="%", sort_sqn_dvsn="01", pdno="", nccs_yn="N", ctx_area_nk200="", ctx_area_fk200="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:307:    ccld_nccs_dvsn: str,  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:325:        ccld_nccs_dvsn (str): 01:전체 / 02:체결 / 03:미체결
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:342:        ...     ccld_nccs_dvsn="01",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:357:    if not ccld_nccs_dvsn:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:358:        logger.error("ccld_nccs_dvsn is required. (e.g. '01')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:359:        raise ValueError("ccld_nccs_dvsn is required. (e.g. '01')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:382:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:413:                ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:627:    ccld_nccs_dvsn: str,  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:648:        ccld_nccs_dvsn (str): 체결미체결구분 (01:전체 / 02:체결 / 03:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:668:        ...     ccld_nccs_dvsn="01",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:689:    if not ccld_nccs_dvsn:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:690:        logger.error("ccld_nccs_dvsn is required. (e.g. '01')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:691:        raise ValueError("ccld_nccs_dvsn is required. (e.g. '01')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:717:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py:751:                ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_examples.py:70:                  ord_end_dt="20250131", sll_buy_dvsn="00", ccld_nccs_dvsn="00", ovrs_excg_cd="NASD", sort_sqn="DS",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_examples.py:75:# [해외주식] 주문/계좌 > 해외주식 미체결내역 [v1_해외주식-005]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_examples.py:78:df = inquire_nccs(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_excg_cd="NASD", sort_sqn="DS", FK200="",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:594:        nccs_yn: str,  # 미체결여부
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:616:        nccs_yn (str): 미체결여부 (N(전체), C(체결), Y(미체결))
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:637:        ...     nccs_yn='N',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:663:    if not nccs_yn in ["N", "C", "Y"]:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:664:        logger.error("nccs_yn is required. (e.g. 'N')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:665:        raise ValueError("nccs_yn is required. (e.g. 'N')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:687:        "NCCS_YN": nccs_yn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:752:                nccs_yn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_examples.py:38:df = inquire_ccld(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ccld_nccs_dvsn="01", sll_buy_dvsn_cd="%%", fuop_dvsn="00", ctx_area_fk200="", ctx_area_nk200="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_examples.py:53:df = inquire_daily_order(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, strt_dt="20250601", end_dt="20250703", fm_pdgr_cd="", ccld_nccs_dvsn="01", sll_buy_dvsn_cd="%%", fuop_dvsn="00", ctx_area_fk200="", ctx_area_nk200="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:747:    ccld_nccs_dvsn: str,   # [필수] 체결미체결구분 (ex. 00:전체, 01:체결, 02:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:770:        ccld_nccs_dvsn (str): [필수] 체결미체결구분 (ex. 00:전체, 01:체결, 02:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:787:        >>> df1, df2 = inquire_ccnl(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, strt_ord_dt="20220730", end_ord_dt="20220830", sll_buy_dvsn_cd="00", ccld_nccs_dvsn="00", sort_sqn="DS")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:811:    if not ccld_nccs_dvsn:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:812:        raise ValueError("ccld_nccs_dvsn is required (e.g. '00')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:845:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:881:                sll_buy_dvsn_cd, ccld_nccs_dvsn, sort_sqn, pdno, strt_odno, 
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1395:    ccld_nccs_dvsn: str,                                # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1419:        ccld_nccs_dvsn (str): [필수] 체결미체결구분 (ex. 00:전체, 01:체결, 02:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1438:        >>> df1, df2 = inquire_ngt_ccnl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, strt_ord_dt="20231201", end_ord_dt="20231214", sll_buy_dvsn_cd="00", ccld_nccs_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1459:    if ccld_nccs_dvsn == "" or ccld_nccs_dvsn is None:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1460:        raise ValueError("ccld_nccs_dvsn is required (e.g. '00:전체, 01:체결, 02:미체결')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1483:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:1523:                cano, acnt_prdt_cd, strt_ord_dt, end_ord_dt, sll_buy_dvsn_cd, ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:737:        ccld_nccs_dvsn: str,  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:763:        ccld_nccs_dvsn (str): 00 : 전체  01 : 체결  02 : 미체결 ※ 모의투자계좌의 경우 "00"(전체 조회)만 가능
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:788:        ...     ccld_nccs_dvsn="00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:815:    if not ccld_nccs_dvsn:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:816:        logger.error("ccld_nccs_dvsn is required. (e.g. '00')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:817:        raise ValueError("ccld_nccs_dvsn is required. (e.g. '00')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:844:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:882:                ccld_nccs_dvsn=ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:906:# [해외주식] 주문/계좌 > 해외주식 미체결내역 [v1_해외주식-005]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:909:def inquire_nccs(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:924:    해외주식 미체결내역[v1_해외주식-005]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:925:    해외주식 미체결내역 API를 호출하여 DataFrame으로 반환합니다.
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:931:        sort_sqn (str): DS : 정순 그외 : 역순  [header tr_id: TTTS3018R] ""(공란)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:941:        Optional[pd.DataFrame]: 해외주식 미체결내역 데이터
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:944:        >>> df = inquire_nccs(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:973:    tr_id = "TTTS3018R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:975:    api_url = "/uapi/overseas-stock/v1/trading/inquire-nccs"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1007:            return inquire_nccs(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2367:    - 미국장 마감 후, 미체결주문은 자동취소
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2740:        orgn_odno (str): 정정 또는 취소할 원주문번호 (해외주식_주문 API ouput ODNO  or 해외주식 미체결내역 API output ODNO 참고)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:5117:        fill: str,  # 미체결채움구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:1087:# [국내주식] 주문/계좌 > 퇴직연금 미체결내역[v1_국내주식-033]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_examples.py:1092:                                    ccld_nccs_dvsn="%%", inqr_dvsn_3="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:4128:        ccld_dvsn: str,  # [필수] 체결구분 (00 전체 / 01 체결 / 02 미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:4164:        ccld_dvsn (str): [필수] 체결구분 (ex. 00 전체 / 01 체결 / 02 미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:4217:        raise ValueError("ccld_dvsn is required (e.g. '00 전체 / 01 체결 / 02 미체결')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:4239:            tr_id = "TTTC0081R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:4246:            tr_id = "VTTC0081R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:10413:    - 예약종료일 입력 시 기간예약주문으로 최초 예약주문수량 중 미체결 된 수량에 대해 예약종료일까지 매 영업일 주문이
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11440:# [국내주식] 주문/계좌 > 퇴직연금 미체결내역[v1_국내주식-033]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11448:        ccld_nccs_dvsn: str,  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11458:    [국내주식] 주문/계좌 > 퇴직연금 미체결내역[v1_국내주식-033]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11467:        ccld_nccs_dvsn (str): [필수] 체결미체결구분 (ex. %%: 전체, 01: 체결, 02: 미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11477:        pd.DataFrame: 퇴직연금 미체결내역 데이터
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11480:        >>> df = pension_inquire_daily_ccld(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, user_dvsn_cd="%%", sll_buy_dvsn_cd="00", ccld_nccs_dvsn="%%", inqr_dvsn_3="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11497:    if ccld_nccs_dvsn == "":
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11498:        raise ValueError("ccld_nccs_dvsn is required (e.g. '%%: 전체, 01: 체결, 02: 미체결')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11510:    tr_id = "TTTC2201R"  # 퇴직연금 미체결내역
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11517:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11541:                cano, acnt_prdt_cd, user_dvsn_cd, sll_buy_dvsn_cd, ccld_nccs_dvsn, inqr_dvsn_3, FK100, NK100, "N",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/daytime_order_rvsecncl/chk_daytime_order_rvsecncl.py:47:        - orgn_odno (str): 원주문번호 ('정정 또는 취소할 원주문번호(매매 TR의 주문번호) - 해외주식 주문체결내역api (/uapi/overseas-stock/v1/trading/inquire-nccs)에서 odno(주문번호) 참조')
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_ccnl/inquire_ngt_ccnl.py:32:    ccld_nccs_dvsn: str,                                # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_ccnl/inquire_ngt_ccnl.py:56:        ccld_nccs_dvsn (str): [필수] 체결미체결구분 (ex. 00:전체, 01:체결, 02:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_ccnl/inquire_ngt_ccnl.py:75:        >>> df1, df2 = inquire_ngt_ccnl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, strt_ord_dt="20231201", end_ord_dt="20231214", sll_buy_dvsn_cd="00", ccld_nccs_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_ccnl/inquire_ngt_ccnl.py:96:    if ccld_nccs_dvsn == "" or ccld_nccs_dvsn is None:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_ccnl/inquire_ngt_ccnl.py:97:        raise ValueError("ccld_nccs_dvsn is required (e.g. '00:전체, 01:체결, 02:미체결')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_ccnl/inquire_ngt_ccnl.py:115:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_ccnl/inquire_ngt_ccnl.py:155:                cano, acnt_prdt_cd, strt_ord_dt, end_ord_dt, sll_buy_dvsn_cd, ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ngt_ccnl/chk_inquire_ngt_ccnl.py:84:                                            end_ord_dt="20250613", sll_buy_dvsn_cd="00", ccld_nccs_dvsn="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/inquire_daily_ccld.py:38:        nccs_yn: str,  # 미체결여부
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/inquire_daily_ccld.py:60:        nccs_yn (str): 미체결여부 (N(전체), C(체결), Y(미체결))
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/inquire_daily_ccld.py:81:        ...     nccs_yn='N',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/inquire_daily_ccld.py:107:    if not nccs_yn in ["N", "C", "Y"]:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/inquire_daily_ccld.py:108:        logger.error("nccs_yn is required. (e.g. 'N')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/inquire_daily_ccld.py:109:        raise ValueError("nccs_yn is required. (e.g. 'N')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/inquire_daily_ccld.py:126:        "NCCS_YN": nccs_yn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/inquire_daily_ccld.py:191:                nccs_yn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/chk_inquire_daily_ccld.py:49:    'nccs_qty': '미체결수량',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/chk_inquire_daily_ccld.py:70:        - nccs_yn (str): 미체결여부 (N(전체), C(체결), Y(미체결))
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/chk_inquire_daily_ccld.py:76:        >>> df1, df2 = inquire_daily_ccld(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_strt_dt="20250601", inqr_end_dt="20250630", sll_buy_dvsn_cd="%", sort_sqn_dvsn="01", pdno="", nccs_yn="N", ctx_area_nk200="", ctx_area_fk200="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_bond/inquire_daily_ccld/chk_inquire_daily_ccld.py:102:            nccs_yn="N",  # 미체결여부
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ccnl/inquire_ccnl.py:33:    ccld_nccs_dvsn: str,   # [필수] 체결미체결구분 (ex. 00:전체, 01:체결, 02:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ccnl/inquire_ccnl.py:56:        ccld_nccs_dvsn (str): [필수] 체결미체결구분 (ex. 00:전체, 01:체결, 02:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ccnl/inquire_ccnl.py:73:        >>> df1, df2 = inquire_ccnl(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, strt_ord_dt="20220730", end_ord_dt="20220830", sll_buy_dvsn_cd="00", ccld_nccs_dvsn="00", sort_sqn="DS")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ccnl/inquire_ccnl.py:97:    if not ccld_nccs_dvsn:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ccnl/inquire_ccnl.py:98:        raise ValueError("ccld_nccs_dvsn is required (e.g. '00')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ccnl/inquire_ccnl.py:127:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ccnl/inquire_ccnl.py:163:                sll_buy_dvsn_cd, ccld_nccs_dvsn, sort_sqn, pdno, strt_odno, 
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_futureoption/inquire_ccnl/chk_inquire_ccnl.py:89:            ccld_nccs_dvsn="00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py:49:        orgn_odno (str): 정정 또는 취소할 원주문번호 (해외주식_주문 API ouput ODNO  or 해외주식 미체결내역 API output ODNO 참고)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/chk_inquire_time_itemchartprice.py:64:        - fill (str): 미체결채움구분 ("" 공백으로 입력)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py:35:        ccld_nccs_dvsn: str,  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py:61:        ccld_nccs_dvsn (str): 00 : 전체  01 : 체결  02 : 미체결 ※ 모의투자계좌의 경우 "00"(전체 조회)만 가능
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py:86:        ...     ccld_nccs_dvsn="00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py:115:    if not ccld_nccs_dvsn:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py:116:        logger.error("ccld_nccs_dvsn is required. (e.g. '00')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py:117:        raise ValueError("ccld_nccs_dvsn is required. (e.g. '00')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py:142:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py:180:                ccld_nccs_dvsn=ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/chk_inquire_ccnl.py:40:    'nccs_qty': '미체결수량',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/chk_inquire_ccnl.py:77:        - ccld_nccs_dvsn (str): 체결미체결구분 (00 : 전체  01 : 체결  02 : 미체결 ※ 모의투자계좌의 경우 "00"(전체 조회)만 가능)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/chk_inquire_ccnl.py:91:        >>> df = inquire_ccnl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="%", ord_strt_dt="20250101", ord_end_dt="20250131", sll_buy_dvsn="00", ccld_nccs_dvsn="00", ovrs_excg_cd="NASD", sort_sqn="DS", ord_dt="", ord_gno_brno="", odno="", env_dv="real")  # 실전투자
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_ccnl/chk_inquire_ccnl.py:122:            ccld_nccs_dvsn="00",  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/order_rvsecncl/chk_order_rvsecncl.py:46:        - orgn_odno (str): 원주문번호 (정정 또는 취소할 원주문번호 (해외주식_주문 API ouput ODNO  or 해외주식 미체결내역 API output ODNO 참고))
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:14:from inquire_nccs import inquire_nccs
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:21:# [해외주식] 주문/계좌 > 해외주식 미체결내역 [v1_해외주식-005]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:39:    'nccs_qty': '미체결수량',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:55:    해외주식 미체결내역[v1_해외주식-005]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:57:    해외주식 미체결내역 테스트 함수
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:63:        - sort_sqn (str): 정렬순서 (DS : 정순 그외 : 역순  [header tr_id: TTTS3018R] ""(공란))
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:69:        - DataFrame: 해외주식 미체결내역 결과
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:72:        >>> df = inquire_nccs(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_excg_cd="NASD", sort_sqn="DS", FK200="", NK200="", env_dv="real")  # 실전투자
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:95:        result = inquire_nccs(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py:122:        logger.info("=== 해외주식 미체결내역 결과 ===")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py:36:    fill: str,  # 미체결채움구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:22:# [해외주식] 주문/계좌 > 해외주식 미체결내역 [v1_해외주식-005]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:26:API_URL = "/uapi/overseas-stock/v1/trading/inquire-nccs"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:28:def inquire_nccs(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:43:    해외주식 미체결내역[v1_해외주식-005]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:44:    해외주식 미체결내역 API를 호출하여 DataFrame으로 반환합니다.
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:50:        sort_sqn (str): DS : 정순 그외 : 역순  [header tr_id: TTTS3018R] ""(공란)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:60:        Optional[pd.DataFrame]: 해외주식 미체결내역 데이터
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:63:        >>> df = inquire_nccs(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:92:    tr_id = "TTTS3018R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:124:            return inquire_nccs(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/chk_inquire_daily_order.py:69:        - ccld_nccs_dvsn (str): 체결미체결구분 (01:전체 / 02:체결 / 03:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/chk_inquire_daily_order.py:79:        >>> df = inquire_daily_order(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, strt_dt="20250601", end_dt="20250703", fm_pdgr_cd="", ccld_nccs_dvsn="01", sll_buy_dvsn_cd="%%", fuop_dvsn="00", ctx_area_fk200="", ctx_area_nk200="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/chk_inquire_daily_order.py:101:            ccld_nccs_dvsn="01",          # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/inquire_daily_order.py:34:    ccld_nccs_dvsn: str,  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/inquire_daily_order.py:55:        ccld_nccs_dvsn (str): 체결미체결구분 (01:전체 / 02:체결 / 03:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/inquire_daily_order.py:75:        ...     ccld_nccs_dvsn="01",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/inquire_daily_order.py:96:    if not ccld_nccs_dvsn:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/inquire_daily_order.py:97:        logger.error("ccld_nccs_dvsn is required. (e.g. '01')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/inquire_daily_order.py:98:        raise ValueError("ccld_nccs_dvsn is required. (e.g. '01')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/inquire_daily_order.py:119:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/inquire_daily_order.py:153:                ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_stock/order_resv/order_resv.py:77:    - 미국장 마감 후, 미체결주문은 자동취소
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/chk_inquire_ccld.py:72:        - ccld_nccs_dvsn (str): 체결미체결구분 (01:전체 / 02:체결 / 03:미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/chk_inquire_ccld.py:82:        >>> df = inquire_ccld(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ccld_nccs_dvsn="01", sll_buy_dvsn_cd="%%", fuop_dvsn="00", ctx_area_fk200="", ctx_area_nk200="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/chk_inquire_ccld.py:99:            ccld_nccs_dvsn="01",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/inquire_ccld.py:31:    ccld_nccs_dvsn: str,  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/inquire_ccld.py:49:        ccld_nccs_dvsn (str): 01:전체 / 02:체결 / 03:미체결
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/inquire_ccld.py:66:        ...     ccld_nccs_dvsn="01",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/inquire_ccld.py:81:    if not ccld_nccs_dvsn:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/inquire_ccld.py:82:        logger.error("ccld_nccs_dvsn is required. (e.g. '01')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/inquire_ccld.py:83:        raise ValueError("ccld_nccs_dvsn is required. (e.g. '01')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/inquire_ccld.py:101:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/inquire_ccld.py:132:                ccld_nccs_dvsn,
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py:34:    ccld_dvsn: str,  # [필수] 체결구분 (00 전체 / 01 체결 / 02 미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py:70:        ccld_dvsn (str): [필수] 체결구분 (ex. 00 전체 / 01 체결 / 02 미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py:122:        raise ValueError("ccld_dvsn is required (e.g. '00 전체 / 01 체결 / 02 미체결')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py:143:            tr_id = "TTTC0081R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py:150:            tr_id = "VTTC0081R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/order_resv/order_resv.py:51:    - 예약종료일 입력 시 기간예약주문으로 최초 예약주문수량 중 미체결 된 수량에 대해 예약종료일까지 매 영업일 주문이
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:19:# [국내주식] 주문/계좌 > 퇴직연금 미체결내역[v1_국내주식-033]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:30:    ccld_nccs_dvsn: str,    # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:40:    [국내주식] 주문/계좌 > 퇴직연금 미체결내역[v1_국내주식-033]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:49:        ccld_nccs_dvsn (str): [필수] 체결미체결구분 (ex. %%: 전체, 01: 체결, 02: 미체결)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:59:        pd.DataFrame: 퇴직연금 미체결내역 데이터
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:62:        >>> df = pension_inquire_daily_ccld(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, user_dvsn_cd="%%", sll_buy_dvsn_cd="00", ccld_nccs_dvsn="%%", inqr_dvsn_3="00")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:78:    if ccld_nccs_dvsn == "":
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:79:        raise ValueError("ccld_nccs_dvsn is required (e.g. '%%: 전체, 01: 체결, 02: 미체결')")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:91:    tr_id = "TTTC2201R"  # 퇴직연금 미체결내역
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:98:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,  # 체결미체결구분
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/pension_inquire_daily_ccld.py:122:                cano, acnt_prdt_cd, user_dvsn_cd, sll_buy_dvsn_cd, ccld_nccs_dvsn, inqr_dvsn_3, FK100, NK100, "N", dataframe, depth + 1, max_depth
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/chk_pension_inquire_daily_ccld.py:18:# [국내주식] 주문/계좌 > 퇴직연금 미체결내역[v1_국내주식-033]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/chk_pension_inquire_daily_ccld.py:31:    'nccs_qty': '미체결수량',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/chk_pension_inquire_daily_ccld.py:45:    퇴직연금 미체결내역 조회 테스트 함수
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/chk_pension_inquire_daily_ccld.py:47:    이 함수는 퇴직연금 미체결내역 API를 호출하여 결과를 출력합니다.
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.7JffJOSkgV/open-trading-api/examples_llm/domestic_stock/pension_inquire_daily_ccld/chk_pension_inquire_daily_ccld.py:67:                                            ccld_nccs_dvsn="%%", inqr_dvsn_3="00")

codex
**Model**
Do not run [LiveEngine.run](/Users/manager/side/makemoney/trader/live/engine.py:14) against `KisLiveFeed.events()` for daily live trading. That method is a replay loop. Daily live needs a separate “warm history, act latest bar only” runner.

```python
@dataclass(frozen=True)
class AccountSnapshot:
    asof: datetime
    cash: dict[str, float]              # keep current engine: {"KRW": ...}
    positions: dict[tuple[str, str], int]  # (market, ticker) -> qty
    marks: dict[tuple[str, str], float]
    fx: dict[str, float]                # {"KRW": 1.0, "USD": usdk_rw}
```

**1. Warm-Up vs Act**
Refactor [FusionEngine.on_bar](/Users/manager/side/makemoney/trader/strategy/fusion_engine.py:29) into observe/decide. Warm-up updates deterministic state, but never calls `order_factory`.

```python
class FusionEngine:
    def observe_bar(self, bar: BarEvent) -> list[NormalizedSignal]:
        self.risk.on_bar(bar, self.portfolio)
        return [s for src in self.sources if (s := src.on_bar(bar)) is not None]

    def decide_orders(
        self, bar: BarEvent, signals: list[NormalizedSignal]
    ) -> list[OrderEvent]:
        combined = self._combine(signals)
        if combined >= self.enter_threshold:
            weight = combined
        elif combined <= self.exit_threshold:
            weight = 0.0
        else:
            return []
        target = TargetPosition(bar.symbol, weight, reason=f"combined={combined:.2f}")
        sized = self.risk.size_target(target, self.portfolio, bar)
        return self.order_factory.orders_for_target(
            sized, self.portfolio, price=bar.close, ts=bar.ts
        )

    def warmup_bar(self, bar: BarEvent) -> None:
        self.observe_bar(bar)

    def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
        return self.decide_orders(bar, self.observe_bar(bar))
```

Daily runner:

```python
class DailyActEngine:
    def run(self, trading_date: date) -> list[OrderEvent]:
        snapshot = self.kis.account_snapshot()
        self.portfolio = Portfolio.from_snapshot(snapshot)

        bars = self.feed.daily_history()  # not feed.events()
        act_bars = latest_closed_bars_by_symbol(bars)

        for bar in sorted(b for b in bars if b not in act_bars):
            self.portfolio.mark(bar)
            self.strategy.warmup_bar(bar)

        orders: list[OrderEvent] = []
        for bar in sorted(act_bars, key=lambda b: (b.ts, b.symbol.market.value, b.symbol.ticker)):
            self.portfolio.mark(bar)
            orders.extend(self.strategy.on_bar(bar))

        return self.submit_once(trading_date, orders)
```

Better feed contract:

```python
class DailyHistoryFeed(Protocol):
    def daily_history(self) -> list[BarEvent]: ...
    def latest_closed_date(self, market: Market) -> date: ...
```

Key rule: `warmup_bar()` may update indicators, risk state, caches, and marks. It must not submit, audit as submitted, mutate broker state, or apply synthetic fills.

**2. Portfolio Sync**
Add KIS snapshot before strategy construction or before daily runner starts. Do not use hardcoded `10_000_000`.

KIS paper TR IDs:

```text
Domestic KOSPI balance:
GET /uapi/domestic-stock/v1/trading/inquire-balance
paper tr_id = VTTC8434R
real  tr_id = TTTC8434R

Overseas US stock balance:
GET /uapi/overseas-stock/v1/trading/inquire-balance
paper tr_id = VTTS3012R
real  tr_id = TTTS3012R

Overseas present/settlement-style balance:
GET /uapi/overseas-stock/v1/trading/inquire-present-balance
paper tr_id = VTRP6504R
real  tr_id = CTRP6504R
```

KIS’s official sample repo shows those paths/TR IDs for overseas balance, overseas present balance, and domestic balance respectively: [overseas balance](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py), [overseas present balance](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py), [domestic balance](https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py).

Mapping:

```python
class KisClient:
    def domestic_balance(self) -> BrokerBalance: ...
    def overseas_balance(self, exchange: str = "NASD", ccy: str = "USD") -> BrokerBalance: ...
    def account_snapshot(self) -> AccountSnapshot: ...
```

```python
class Portfolio:
    @classmethod
    def from_snapshot(cls, s: AccountSnapshot) -> "Portfolio":
        p = cls(cash=s.cash, fx=FxRates(s.fx))
        for (market, ticker), qty in s.positions.items():
            sym = Symbol(ticker, Market(market), "USD" if market == "NASDAQ" else "KRW")
            p._pos[(market, ticker)] = qty
            p._sym[(market, ticker)] = sym
            p._mark[(market, ticker)] = s.marks.get((market, ticker), 0.0)
        return p
```

Given current [Portfolio.apply_fill](/Users/manager/side/makemoney/trader/strategy/portfolio.py:29) converts all fills into `cash["KRW"]`, keep the live snapshot KRW-settled too: `cash={"KRW": broker_available_cash_krw}` plus positions keyed by `(market, ticker)`. Do not introduce `USD` cash unless you also change order sizing and fill accounting.

**3. Idempotency / Scheduling**
Use both broker inquiry and a local atomic marker.

```python
@dataclass(frozen=True)
class DailyRunKey:
    env: str              # paper/real
    account: str
    market: Market
    trading_date: date
    strategy_id: str

class RunLedger:
    def acquire(self, key: DailyRunKey) -> bool: ...
    def record_intents(self, key: DailyRunKey, intents: list[OrderIntent]) -> None: ...
    def record_submitted(self, key: DailyRunKey, intent_hash: str, odno: str) -> None: ...
    def complete(self, key: DailyRunKey) -> None: ...
```

Submit flow:

```python
if not ledger.acquire(key):
    return []

existing = kis.today_orders_or_open_orders(key.trading_date)
if has_matching_order(existing, deterministic_intent_hash(order)):
    ledger.complete(key)
    return []

ledger.record_intents(key, intents)
for order in orders:
    odno = execution.submit_order(order)
    ledger.record_submitted(key, hash_order(order), odno)
ledger.complete(key)
```

Relevant order inquiry TRs already in your repo/docs: overseas execution inquiry `VTTS3035R`, domestic daily order/filled inquiry `VTTC0081R`. For overseas open orders, KIS samples show `/uapi/overseas-stock/v1/trading/inquire-nccs`; verify paper support before relying on it.

Scheduling:

```cron
# KRX close 15:30 KST; run after data has settled
40 15 * * 1-5 TZ=Asia/Seoul cd /app && python -m trader.app.run_daily --market KOSPI

# US regular close 16:00 ET; run after close, expressed in New York time
10 16 * * 1-5 TZ=America/New_York cd /app && python -m trader.app.run_daily --market NASDAQ
```

Use an exchange calendar, not weekday-only cron, to skip holidays/early closes.

**4. Daily Order Price**
For US paper, assume regular overseas stock order supports limit only unless live-tested otherwise. Your current code already encodes NASDAQ as `ORD_DVSN="00"` limit.

Recommendation:

```python
def daily_order_price(side: Side, last_close: float, band: float = 0.01) -> tuple[str, float]:
    if side == Side.BUY:
        return "LIMIT", round_tick(last_close * (1 + band))
    return "LIMIT", round_tick(last_close * (1 - band))
```

A limit exactly at last close is deterministic but often misses after a gap. A marketable protective limit is the practical daily model. For KOSPI, market order is acceptable if your risk model tolerates open slippage; otherwise use the same protective-limit approach.

**5. Verify Now vs Market Hours**
Can verify now, read-only:

```text
- token cache
- overseas/domestic daily bars
- domestic balance VTTC8434R
- overseas balance VTTS3012R
- overseas present balance VTRP6504R
- today order/fill inquiries, including empty responses
- local warmup/act determinism tests with MockTransport
- idempotency marker behavior
```

Can partially verify now:

```text
- order endpoint schema/auth/TR_ID with paper order call, expecting market-closed/pre-open business error
```

Needs market/session or supported reservation endpoint:

```text
- actual order acceptance
- fill lifecycle
- cancel/replace
- open-order inquiry after a live accepted order
- whether overseas paper accepts after-close queued orders through the regular order endpoint
```

Bottom line: build a separate daily runner. Historical bars are input for state only; the only broker-mutating path is `act_bars == latest_closed_bar_per_symbol`, guarded by account sync plus idempotency.
tokens used
139,532

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
