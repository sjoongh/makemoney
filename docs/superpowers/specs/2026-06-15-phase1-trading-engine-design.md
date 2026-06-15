# Phase 1 설계 — 신호 융합 자동매매 엔진 (백테스트=실거래 단일 코드경로)

- 작성일: 2026-06-15
- 프로젝트: `makemoney/` (Python 주식 자동매매)
- 설계 검증: Claude(설계) ↔ Codex(독립 설계) 교차검증 후 합의안 + Claude 보강 3건

---

## 0. 한 줄 요약

**전략(`FusionEngine`)은 자기가 백테스트 중인지 실거래 중인지 절대 모른다.** 불변 이벤트(`BarEvent`)만 받아 주문(`OrderEvent`)을 내고 체결(`FillEvent`)을 돌려받는다. 백테스트와 모의투자(KIS 페이퍼)의 차이는 **오직 두 어댑터** — `DataFeed`와 `ExecutionHandler` — 의 교체뿐이다. 그 사이의 신호·판단·리스크·주문 코드는 한 줄도 갈리지 않는다.

```
백테스트:  HistoricalDataFeed + SimulatedExecutionHandler
모의투자:  LiveKisDataFeed    + KisPaperExecutionHandler
            └────────────── 그 사이는 100% 동일 ──────────────┘
```

---

## 1. 확정된 결정 사항 (Locked Decisions)

| 항목 | 결정 | 근거 |
|---|---|---|
| 시장 / 브로커 | 미국 NASDAQ(메인) + 한국 KOSPI(보조), **KIS 단일 API** | KIS 한 계좌로 국내+해외 모두 커버 → 브로커 2개보다 단순 |
| 전략 비전 | **신호 융합 엔진** (① 기술지표 ② 뉴스/공시 LLM ③ ML 예측) | Phase 1은 ①만, ②③는 동일 인터페이스로 후속 플러그인 |
| Phase 1 범위 | 융합엔진 뼈대 + 기술지표 소스 + 경량 자체 이벤트 백테스트 + KIS 모의투자 | 작동하는 자동매매를 먼저 완성 |
| **#1 원칙** | 백테스트와 실거래가 **정확히 같은 신호·판단 코드경로** | 알고 트레이딩 최대 함정 차단. "관습"이 아니라 "구조적으로 위반 불가"하게 |
| 봉 주기 | **일봉(daily)** | 룩어헤드·타임존 함정 최소, KIS 호출 적음, 검증 후 분봉 확장 |
| 포지션 방향 | **롱/현금만** (공매도 없음) | KIS 모의 체결·리스크 단순, 공매도 비용/규제/마진콜 회피 |
| 과거 데이터 | **KIS 과거데이터 → parquet 적재** | 실거래와 동일 소스라 패리티 최상. yfinance는 리서치 스크래치용만 |
| 기준통화 | **KRW** | KIS 계좌 기준, USD 자산은 일별 환율로 KRW 환산 |

---

## 2. 핵심 불변식 (The Invariant)

이 한 문장이 시스템 전체를 지배한다:

> **시장 데이터에 대한 모든 외부 I/O는 `DataFeed` 뒤에, 모든 주문 I/O는 `ExecutionHandler` 뒤에 숨는다. `FusionEngine`과 신호 소스는 브로커/DB/파일/시계에 직접 접근하지 못한다.**

이게 지켜지면 같은 이벤트 스트림 → 같은 주문이 수학적으로 보장된다.

### 결정성 봉인 (Claude 보강 #3)
- 전략·신호 소스 내부에서 `datetime.now()`, `random`, 전역 상태, 네트워크 호출 **금지**.
- 시간이 필요하면 **주입된 `Clock`**만 사용 (백테스트=데이터 타임스탬프, 라이브=벽시계).
- 신호 소스는 **롤링/증분 상태**만 유지 — 미래 행이 든 DataFrame을 받지 않는다.

---

## 3. 모듈 구조 (Phase 1)

`[NOW]` = Phase 1에서 실제 구현, `[STUB]` = 인터페이스만/최소, `[LATER]` = Phase 2+ 자리만 확보.

```text
makemoney/
  pyproject.toml
  trader/
    app/
      run_backtest.py        # [NOW] 과거피드 + 시뮬실행 + 엔진 조립
      run_paper.py           # [NOW] KIS라이브피드 + KIS페이퍼실행 + 엔진 조립
      config.py              # [NOW] env/설정 로딩(pydantic), 시장/세션 설정

    core/
      events.py              # [NOW] 불변 이벤트: Bar/Signal/Order/Fill + Enum
      types.py               # [NOW] Symbol, Market, Side, OrderType, Money
      clock.py               # [NOW] 백테스트/라이브 시계 추상화 (결정성 봉인)

    data/
      interfaces.py          # [NOW] DataFeed 프로토콜
      historical_feed.py     # [NOW] parquet에서 일봉 재생 (시간순 1개씩)
      kis_live_feed.py       # [NOW] KIS 일봉 폴링 → 블로킹 이터레이터로 변환
      calendar.py            # [NOW] US/KR 세션·휴장·타임존
      storage.py             # [NOW] OHLCV parquet 적재/조회
      recorder.py            # [NOW] 라이브 세션을 이벤트 로그로 녹화 (패리티 보강 #1)

    signals/
      interfaces.py          # [NOW] SignalSource 프로토콜 + NormalizedSignal
      technical.py           # [NOW] MA/RSI/MACD/Bollinger 소스 (롤링/증분)
      registry.py            # [LATER] 다중 소스 등록/조합 (Phase 1은 리스트 직접 주입)

    strategy/
      fusion_engine.py       # [NOW] 신호 결합 → 목표 의도 (모드 무지)
      risk.py                # [NOW] 사이징·노출한도·킬스위치
      portfolio.py           # [NOW] 포지션·현금(통화별)·평가액·PnL·FX환산
      order_factory.py       # [NOW] 목표비중 델타 → 주문

    execution/
      interfaces.py          # [NOW] ExecutionHandler 프로토콜
      simulated.py           # [NOW] 백테스트 체결/슬리피지/수수료 (다음 봉 시가)
      kis_paper.py           # [NOW] KIS 모의 주문 제출 + 체결 대사(reconcile)
      kis_client.py          # [NOW] 인증된 KIS REST 래퍼 (국내/해외 차이 흡수)
      costs.py               # [NOW] US/KR 수수료·세금·슬리피지 모델

    backtest/
      engine.py              # [NOW] 과거 시뮬 이벤트 루프
      metrics.py             # [NOW] 수익률·MDD·턴오버·노출·승률
      report.py              # [NOW] 결과 직렬화/요약 출력

    live/
      engine.py              # [NOW] 라이브 이벤트 루프 (+ 녹화 훅)

    observability/
      logging.py             # [NOW] structlog 구조화 로그
      audit.py               # [NOW] 모든 event/order/fill 감사 추적

  tests/
    test_backtest_live_parity.py  # [NOW] 같은 이벤트 → 같은 주문 (핵심 테스트)
    test_replay_parity.py         # [NOW] 녹화된 라이브 세션 재생 = 동일 결과 (보강 #1)
    test_no_lookahead.py          # [NOW] 지표가 미래/당일종가 체결 안 함
    test_risk.py                  # [NOW] 한도·킬스위치
    test_execution_sim.py         # [NOW] 시뮬 체결 정확성
    test_fx_portfolio.py          # [NOW] KRW 환산 평가액 (보강 #2)
```

YAGNI 적용: 틱→봉 `bar_builder`, `telemetry`, signal `registry` 본격 구현은 Phase 1에서 제외(일봉·단일 소스라 불필요).

---

## 4. 핵심 인터페이스 계약

### 4.1 이벤트 (불변)
```python
# trader/core/events.py — frozen dataclasses
class Market(str, Enum): NASDAQ="NASDAQ"; KOSPI="KOSPI"
class Side(str, Enum):   BUY="BUY"; SELL="SELL"

@dataclass(frozen=True)
class Symbol:    ticker: str; market: Market; currency: str

@dataclass(frozen=True)
class BarEvent:               # 닫힌 봉만. ts=봉 종료시각(tz-aware)
    symbol: Symbol; ts: datetime
    open: float; high: float; low: float; close: float; volume: int
    timeframe: str = "1d"; is_closed: bool = True

@dataclass(frozen=True)
class NormalizedSignal:       # ★ #2/#3 소스가 동일 형태로 플러그인되는 계약
    source: str               # "technical" | "news_llm" | "ml_forecast"
    symbol: Symbol; ts: datetime
    score: float              # [-1, +1] 약세↔강세 방향 확신
    confidence: float         # [0, 1] 신뢰도/데이터품질
    horizon: str              # "1d","5d"...
    features: Mapping[str, float]

@dataclass(frozen=True)
class OrderEvent:
    order_id: UUID; symbol: Symbol; ts: datetime
    side: Side; quantity: int; order_type: str
    limit_price: float | None; reason: str

@dataclass(frozen=True)
class FillEvent:
    order_id: UUID; symbol: Symbol; ts: datetime
    side: Side; quantity: int; price: float
    commission: float; currency: str
```

### 4.2 4대 프로토콜
```python
class DataFeed(Protocol):
    def events(self) -> Iterator[BarEvent]: ...
    # 시간순 증가하는 '닫힌' BarEvent를 1개씩 yield. 과거/라이브 동일 계약.

class SignalSource(Protocol):
    name: str
    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None: ...
    # 닫힌 봉 1개 소비 → 정규화 신호 0/1개. 내부 롤링 상태만. 미래 데이터 금지.

class ExecutionHandler(Protocol):
    def submit_order(self, order: OrderEvent) -> list[FillEvent]: ...
    # 백테스트=시뮬 체결 / 페이퍼=KIS 제출 후 '확인된' 체결만 반환

class FusionEngine:           # 전략 = 모드 무지
    def on_bar(self, bar) -> list[OrderEvent]: ...
    def on_fill(self, fill) -> None: ...   # 포트폴리오는 '체결'에만 갱신
```

### 4.3 동일 전략, 다른 배선
```python
# 두 경우 FusionEngine 생성이 글자 그대로 동일. 어댑터만 교체.
strategy = FusionEngine([TechnicalSignalSource(...)], portfolio, risk, order_factory)

BacktestEngine(HistoricalDataFeed(...), strategy, SimulatedExecutionHandler(...)).run()
LiveEngine(LiveKisDataFeed(...),       strategy, KisPaperExecutionHandler(...)).run()
```

---

## 5. 이벤트 루프 & 룩어헤드 방지

```python
for bar in data_feed.events():          # 닫힌 봉만, 시간순 1개씩
    assert bar.is_closed
    orders = strategy.on_bar(bar)        # 신호→융합→리스크→주문팩토리
    for order in orders:
        for fill in execution.submit_order(order):
            strategy.on_fill(fill)        # 포트폴리오는 체결로만 변함
            audit.write(fill)
```

**체결 타이밍 (룩어헤드 차단의 핵심):**
```
봉 N 종료 → 전략이 봉 N을 봄 → 주문 발생 → 시뮬 체결은 봉 N+1 '시가'
```
당일 종가로 만든 신호를 당일 종가에 체결하지 않는다. 라이브도 동형: 봉 N 종료 → 주문 → KIS 페이퍼 계좌 체결.

---

## 6. 신호 정규화 & 융합 (확장성의 핵심)

모든 소스는 `score×confidence×source_weight`로 합산되는 동일 통화로 말한다 — 원시 지표값이 아니라.

```python
combined = weighted_mean(s.score, weight=s.confidence * source_weight[s.source]
                         for s in signals)
# Phase 1: source_weight = {"technical": 1.0}
# Phase 2+: {"technical": .., "news_llm": .., "ml_forecast": ..} 만 추가하면 끝
```
결정 임계치 (롱/현금): `combined >= +0.35 → 롱 목표`, `<= -0.35 → 청산/현금`, 그 외 홀드.

---

## 7. 리스크 & 포지션 사이징 위치

```
BarEvent → SignalSource(s) → FusionEngine(융합=목표의도)
        → RiskManager(사이징·클램프) → OrderFactory(주문델타)
        → ExecutionHandler → FillEvent → Portfolio
```
리스크는 **융합 후 / 주문 생성 전.** 책임: 종목별 최대비중, 시장별(NASDAQ/KOSPI) 노출한도, 현금버퍼, 최소주문, 통화인지 사이징, 일일손실한도, **킬스위치**, 종목 화이트/블랙리스트.

---

## 8. FX / 포트폴리오 (Claude 보강 #2)

- 현금은 **통화별 버킷**(KRW, USD)으로 보유.
- 총평가액·PnL은 **KRW 기준**, USD 자산은 **일별 환율**로 환산.
- 환율은 외부 입력(또는 KIS)으로 받아 `Clock`/이벤트와 동일하게 결정적으로 주입 → 백테스트 재현 가능.

---

## 9. 패리티 보강 — 녹화/재생 (Claude 보강 #1)

단순 "같은 이벤트→같은 주문" 테스트는 *결정성*만 검증한다. 진짜 위험은 **라이브 피드가 과거 피드와 다른 봉을 만드는 것.** 따라서:

1. 두 피드 모두 **동일 `Calendar`+정규화**를 통과 → 봉 모양/타이밍 일치 보장.
2. `recorder.py`가 **라이브 세션의 BarEvent 스트림을 그대로 로그로 녹화**.
3. `test_replay_parity.py`가 그 녹화 로그를 백테스트 엔진으로 재생 → 라이브에서 났던 주문과 **비트 단위로 동일**한지 검증.

이게 "백테스트는 됐는데 실거래는 다름"을 사후가 아니라 사전에 잡는 안전망.

---

## 10. Top 5 함정 & 회피

1. **백테스트/실거래 전략 분기** → `FusionEngine` 모드 무지 + 어댑터만 교체 + 패리티/재생 테스트.
2. **DataFrame 지표 룩어헤드** → 롤링/증분 지표만, 다음 봉 시가 체결.
3. **US/KR 타임존·휴장 실수** → 전부 tz-aware, 명시적 `Calendar`, naive datetime 금지.
4. **KIS 국내/해외 API 차이**(엔드포인트·호가단위·시간·통화) → `KisClient`/`KisPaperExecutionHandler` 내부로 격리, 외부는 표준 `OrderEvent`/`FillEvent`만.
5. **체결 미대사** → 주문 제출 ≠ 체결. 확인된 체결만 `FillEvent`로, 포트폴리오는 체결로만 갱신.

---

## 11. 라이브러리

**사용:** numpy(지표 수학), pandas(리서치/오프라인 검증), pydantic v2(설정·KIS 응답 검증), pyarrow+parquet(OHLCV/이벤트 저장), httpx(KIS REST), websockets(KIS 스트리밍, 후속), exchange-calendars(세션/휴장), pytest(패리티/룩어헤드 테스트), structlog(구조 로그), rich(CLI).

**주의:** TA-Lib(설치 까다로움 → 일단 자체 구현 또는 `ta`/`pandas-ta`).

**금지:** backtrader/zipline/vectorbt(자체 전략 라이프사이클 강제 → 제2의 코드경로 = #1원칙 파괴), ccxt(암호화폐용, KIS 무관), yfinance(프로덕션/패리티 데이터로는 금지, 리서치 스크래치만), 전역 DataFrame 전략 함수(룩어헤드·불일치의 최대 원인).

---

## 12. Phase 1 완료 정의 (Definition of Done)

- [ ] `run_backtest.py`로 KIS 과거 일봉(parquet) 기반 백테스트가 돌고 수익률/MDD 리포트 출력.
- [ ] `run_paper.py`로 KIS 모의투자 계좌에 실제 주문이 나가고 체결이 포트폴리오에 반영.
- [ ] 동일 `FusionEngine` 인스턴스 구성이 두 경로에서 글자 그대로 동일.
- [ ] `test_backtest_live_parity` + `test_replay_parity` + `test_no_lookahead` 통과.
- [ ] 기술지표 소스(MA/RSI/MACD/Bollinger)가 `NormalizedSignal` 방출.
- [ ] KRW 기준 통화별 포트폴리오 평가 + 킬스위치 동작.

## 13. Phase 1 비범위 (Out of Scope)
- 뉴스/공시 LLM 신호(②), ML 예측 신호(③) — 자리만 확보.
- 분봉/틱, 공매도, 실계좌(실거래) 주문, 멀티프로세스/분산.
- 학습형 융합 가중치 — Phase 1은 고정 가중.

---

## 부록: 설계 출처
- Codex(gpt-5.5) 독립 설계 원문: `.omc/artifacts/ask/codex-you-are-a-senior-quant-...-2026-06-15T06-05-27-137Z.md`
- 합의: 이벤트 드리븐·모드 무지 전략·정규화 신호·다음봉 체결·프레임워크 금지.
- Claude 보강 3건: ①녹화/재생 패리티, ②FX/기준통화, ③결정성 봉인(Clock).
