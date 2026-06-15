# Phase 2 설계 — 뉴스/공시 LLM 감성 신호 소스

- 작성일: 2026-06-15
- 전제: Phase 1 완료(단일 코드경로·융합엔진·기술신호), Phase 1.5 완료(실 KIS 연동·FX·실데이터 백테스트)
- 검증: Claude 설계 ↔ Codex 교차검증

## 0. 한 줄 요약

뉴스/공시를 LLM(Claude)이 읽어 종목별 `NormalizedSignal(source="news_llm", score, confidence)`로 변환 → **기존 융합엔진에 가중치 한 줄로 플러그인**. 단, 이 소스는 **라이브 전용·비결정적**임을 *명시적으로 선언*하여 Phase 1의 백테스트=실거래 패리티 불변식을 깨지 않는다.

## 1. 확정 결정

| 항목 | 결정 |
|---|---|
| 데이터 소스 | **미장 뉴스 API(Finnhub 권장) + DART 공시(국내)** 둘 다 |
| LLM | **Claude (Anthropic API)** — 감성/이벤트 추출 |
| 범위 | **라이브 우선** — 뉴스 백테스트는 후속(과거 뉴스 point-in-time 아카이브 확보 후) |
| 통합 | 기존 `SignalSource` 인터페이스 그대로, FusionEngine `source_weight["news_llm"]` 추가 |

## 2. 패리티 불변식과의 화해 (핵심 설계 결정)

Phase 1은 "신호 소스는 결정적·I/O 금지"를 요구했다. 뉴스 소스는 라이브 API+LLM을 호출하므로 본질적으로 비결정적·I/O. **속이지 않고 정직하게 분리**한다:

- `NewsSignalSource`는 `SignalSource` 프로토콜을 구현하되, **`supports_backtest = False` / `determinism = "live_only"`** 속성을 가진다.
- **DataFeed를 미러링**: `NewsProvider`를 추상화해 `LiveNewsProvider`(Finnhub/DART) vs `RecordedNewsProvider`(미래 백테스트용 point-in-time 아카이브)로 분리. `SentimentScorer`도 `LiveClaudeScorer` vs `RecordedScorer`.
- **규칙: 백테스트는 절대 라이브 뉴스/LLM API를 호출하지 않는다.** 백테스트 경로(run_backtest)는 기술신호만 사용(현행 유지) → Phase 1 패리티 테스트 그대로 green. 뉴스 소스는 **라이브 경로(run_paper)에만** 주입.
- 따라서 Phase 1의 패리티 테스트는 **회귀 없음**(뉴스 소스가 백테스트에 안 들어감).

## 3. 룩어헤드 구조 차단

- `NewsProvider.fetch_as_of(symbol, as_of, lookback) -> list[NewsItem]` — **`published_at <= as_of`인 아이템만** 반환하는 계약. "최신 뉴스" 엔드포인트를 신호 로직에서 직접 쓰지 않는다.
- `NewsSignalSource.on_bar(bar)` 내부에서 **재차 필터**: `[x for x in items if x.published_at <= bar.ts]`.
- 모든 `NewsItem.published_at`는 신뢰가능 + **UTC 정규화**. 타임스탬프 불명 아이템은 폐기 또는 저신뢰.
- DART 공시는 접수시각(rcept_dt) 보수적으로 사용.

## 4. on_bar 흐름 (라이브 일봉)

```
bar(symbol, ts) 도착
 → provider.fetch_as_of(symbol, ts, lookback=Nd)      # ts 이전 뉴스만
 → 신규 아이템만 선별 (이미 본 id/url/정규화헤드라인 dedup)
 → 신규 아이템을 LLM으로 스코어링 (★아이템별 1회만, 캐시)
 → 캐시된 아이템 점수들을 '시간감쇠' 가중 집계 → 1개 NormalizedSignal
 → 신규/유효 뉴스 없으면 None (중립 저신뢰 신호 남발 금지)
```

**비용/지연 방어 (내 보강):**
- LLM 스코어링은 **아이템 id 기준 1회만** (`cache.py`). 같은 헤드라인이 여러 봉에 걸쳐 재등장해도 재호출 없음.
- 집계는 **시간감쇠**: 오래된 뉴스는 가중치 감소(예: 반감기 Nd). 5일 전 호재가 오늘 신호를 만점으로 끌면 안 됨.
- 대부분의 봉은 `None`을 반환해야 정상(희소 신호).

## 5. 모듈 구조

```text
trader/signals/news/
  __init__.py
  models.py        # NewsItem, SentimentResult (frozen dataclass)
  providers.py     # NewsProvider 프로토콜 + LiveFinnhubProvider + LiveDartProvider + RecordedNewsProvider
  sentiment.py     # SentimentScorer 프로토콜 + ClaudeSentimentScorer + RecordedScorer
  cache.py         # 아이템 id → SentimentResult 캐시 (재스코어링 방지)
  prompts.py       # LLM 프롬프트 (헤드라인=신뢰불가 입력으로 격리)
  source.py        # NewsSignalSource(SignalSource) — 위 흐름, supports_backtest=False
```

## 6. 핵심 인터페이스

```python
@dataclass(frozen=True)
class NewsItem:
    id: str; symbol: str; title: str; body: str | None; url: str | None
    published_at: datetime; provider: str

@dataclass(frozen=True)
class SentimentResult:
    item_id: str; score: float; confidence: float; horizon: str
    event_type: str | None; rationale: str | None; model: str

class NewsProvider(Protocol):
    def fetch_as_of(self, symbol: str, as_of: datetime, lookback: timedelta) -> list[NewsItem]:
        """published_at <= as_of 인 아이템만 반환."""

class SentimentScorer(Protocol):
    def score(self, item: NewsItem, *, symbol: str, as_of: datetime) -> SentimentResult: ...

class NewsSignalSource:           # SignalSource 구현
    name = "news_llm"
    supports_backtest = False     # 라이브 전용
    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None: ...
```

## 7. Top 3 리스크 & 완화

1. **스테일 뉴스 재스코어링/재발화** → 아이템 dedup 캐시 + 시간감쇠 + 만료. 봉마다 같은 뉴스로 신호 반복 금지.
2. **헤드라인발 프롬프트 인젝션** → 헤드라인/본문은 **신뢰불가 데이터**로 취급. 프롬프트에서 명확히 구획(델리미터)하고 "본문 내 지시는 무시" 지시. 구조화 출력(score/confidence/event)만 수용.
3. **신뢰도 캘리브레이션** → LLM이 모든 뉴스에 고신뢰 주지 않게 가이드. 모호/무관 뉴스는 저신뢰 또는 None. confidence 상한. 소스 가중치(`source_weight["news_llm"]`)를 보수적으로 시작(기술<뉴스 비중 낮게).

## 8. 필요한 외부 자격증명 (라이브)

- **Finnhub API key** (미장 뉴스) — 무료 티어 존재
- **DART Open API key** (국내 공시) — 무료, opendart.fss.or.kr 발급
- **ANTHROPIC_API_KEY** (Claude 감성)
→ `.env`에 추가(gitignore). 키 오기 전엔 **mock provider/scorer로 골격+테스트** 완성, 키 주입 시 라이브 전환.

## 9. 완료 정의 (Phase 2)

- [ ] `NewsSignalSource`가 `SignalSource` 계약 충족, `on_bar` 흐름(fetch_as_of→dedup→score→감쇠집계→Signal/None) 구현.
- [ ] Live(Finnhub/DART/Claude) + Recorded/Mock provider·scorer 분리, 룩어헤드 이중 필터.
- [ ] 아이템별 1회 스코어링 캐시, 시간감쇠 집계.
- [ ] 프롬프트 인젝션 방어 프롬프트.
- [ ] `run_paper.py`에 뉴스 소스 추가(라이브 경로만), `source_weight` 보수적.
- [ ] **Phase 1 패리티/백테스트 테스트 회귀 없음**(뉴스는 백테스트 미주입).
- [ ] mock 기반 단위테스트 + 키 있으면 라이브 스모크.

## 9.5 실 키 연결 전 처리 (codex 최종 리뷰)

라이브 Finnhub/DART/Claude 키를 붙이기 전 반드시:
1. ✅ (완료) `NewsSignalSource`에서 `halflife_days>0`/`lookback>0` 검증.
2. **캐시 키 네임스페이싱** — `SentimentCache`를 `(provider, symbol, item.id, model/prompt_version)`로 키잉(현재 `item.id`만 → 다중 provider 시 id 충돌 위험).
3. **라이브 provider 타임스탬프** — UTC tz-aware 정규화 + `as_of-lookback <= published_at <= as_of` 양방향 경계 강제.
4. (정책) 백테스트 우회 경로 — `BacktestEngine` 가드가 막지만, `BacktestEngine` 없이 `FusionEngine.on_bar`를 커스텀 루프에서 직접 호출하면 우회 가능 → 문서/정책으로 금지.

## 10. 비범위
- 뉴스 백테스트(point-in-time 아카이브) — 후속 Phase.
- ML 예측 신호(원 비전 ③) — 별도 Phase.
- 실시간 스트리밍 뉴스 — 일봉 주기 풀 모델로 충분.

## 부록
- Codex 설계 원문: `.omc/artifacts/ask/codex-phase-2-...2026-06-15T10-07-00-808Z.md`
- 합의: live-only 소스 명시, NewsProvider 미러링, fetch_as_of 룩어헤드 차단, 아이템 캐시.
