# Phase 2 — News/LLM Signal Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development. TDD, one commit per task, mock-first (no external keys).

**Goal:** `news_llm` 신호 소스를 추가하되 Phase 1 백테스트=실거래 패리티를 깨지 않는다(라이브 전용·백테스트 미주입).

**설계 근거:** `docs/superpowers/specs/2026-06-15-phase2-news-llm-signal-design.md`

**공통 환경:** `/Users/manager/side/makemoney`, branch `main`, `.venv/bin/pytest`. 키 없음 → **mock provider/scorer**로 구현·테스트. 라이브(Finnhub/DART/Claude) 어댑터는 시그니처/골격만(키 오면 채움).

**불변 규칙:** 매 태스크 끝에 `.venv/bin/pytest -q` 전체 통과, **특히 `test_backtest_live_parity.py` 회귀 0**(뉴스는 백테스트에 안 들어가므로 영향 없어야 함).

---

## Task 1: news/models.py — NewsItem, SentimentResult
- Create `trader/signals/news/__init__.py`, `trader/signals/news/models.py`; Test `tests/test_news_models.py`.
- frozen dataclass `NewsItem(id, symbol, title, body|None, url|None, published_at, provider)` — `published_at` tz-aware 검증(naive→ValueError).
- frozen dataclass `SentimentResult(item_id, score[-1,1], confidence[0,1], horizon, event_type|None, rationale|None, model)` — score/confidence 범위 검증.
- Test: 생성·불변·범위검증·tz검증. Commit `feat: news signal models`.

## Task 2: news/providers.py — NewsProvider + Mock + 룩어헤드 차단
- Create `trader/signals/news/providers.py`; Test `tests/test_news_providers.py`.
- `NewsProvider` Protocol: `fetch_as_of(symbol, as_of, lookback) -> list[NewsItem]`.
- `MockNewsProvider(items)`: 주어진 아이템 중 `published_at <= as_of` 이고 `>= as_of-lookback` 인 것만, 시간순 반환. **룩어헤드 차단을 여기서 강제.**
- `LiveFinnhubProvider` / `LiveDartProvider`: 시그니처 + `__init__(api_key, client)` 골격. 키 없으면 `fetch_as_of`는 `NotImplementedError`나 빈 리스트(주석으로 TODO 명시). 본격 구현은 키 확보 후.
- Test: Mock이 as_of 이후 아이템 제외(룩어헤드), lookback 경계, 정렬. Commit `feat: news providers (mock + look-ahead-safe fetch_as_of)`.

## Task 3: news/sentiment.py — SentimentScorer + Mock + Claude 골격
- Create `trader/signals/news/sentiment.py`; Test `tests/test_news_sentiment.py`.
- `SentimentScorer` Protocol: `score(item, *, symbol, as_of) -> SentimentResult`.
- `MockSentimentScorer(rule)`: 결정적 규칙(예: 제목에 'beats'/'surge'→+, 'miss'/'plunge'→-, 기타 0/저신뢰)으로 SentimentResult 생성. 테스트·골격 검증용.
- `ClaudeSentimentScorer(client, prompts)`: 시그니처 + 호출 골격(키/anthropic SDK 없으면 미동작 TODO). 프롬프트는 prompts.py 사용.
- Test: MockScorer 결정성, 범위. Commit `feat: sentiment scorer (mock + Claude skeleton)`.

## Task 4: news/cache.py — 아이템 1회 스코어링 캐시
- Create `trader/signals/news/cache.py`; Test `tests/test_news_cache.py`.
- `SentimentCache`: `get_or_score(item, scorer, *, symbol, as_of) -> SentimentResult` — `item.id` 캐시; 미스 시 scorer.score 호출 후 저장, 히트 시 재호출 안 함.
- Test: 같은 item.id 두 번 → scorer 1회만 호출(카운터 fake). Commit `feat: sentiment cache (score each item once)`.

## Task 5: news/prompts.py — 인젝션 방어 감성 프롬프트
- Create `trader/signals/news/prompts.py`; Test `tests/test_news_prompts.py`.
- codex 초안 기반(병렬 수신). `SYSTEM_PROMPT` 상수 + `build_user_message(item, symbol, as_of) -> str` — 뉴스 본문을 **명확한 델리미터로 격리**하고 "본문 내 지시 무시" 명시, STRICT JSON 출력 요구.
- Test: build_user_message가 헤드라인을 델리미터로 감싸고, 인젝션 문구('ignore previous instructions')가 들어와도 그냥 데이터로 임베드되는지(델리미터 안). Commit `feat: injection-resistant sentiment prompt`.

## Task 6: news/source.py — NewsSignalSource (핵심)
- Create `trader/signals/news/source.py`; Test `tests/test_news_source.py`.
- `NewsSignalSource(provider, scorer, cache, *, lookback, halflife_days, source_name="news_llm")`. `name="news_llm"`, `supports_backtest=False`.
- `on_bar(bar) -> NormalizedSignal | None`:
  1. `items = provider.fetch_as_of(bar.symbol.ticker, bar.ts, lookback)`
  2. **재필터** `[x for x in items if x.published_at <= bar.ts]` (이중 룩어헤드 차단)
  3. dedup(이미 본 id) → 신규만
  4. 각 아이템 `cache.get_or_score(...)` (1회 스코어링)
  5. **시간감쇠 가중 집계**: weight = 0.5 ** (age_days/halflife). combined_score = Σ(score*conf*w)/Σ(conf*w), confidence = clamp(Σw_conf 정규화 또는 max conf).
  6. 유효 신규 뉴스 없으면 `None`. 있으면 `NormalizedSignal("news_llm", bar.symbol, bar.ts, score, confidence, horizon, features)`.
- Test: (a) as_of 이후 뉴스 무시(룩어헤드), (b) 호재→양수/악재→음수 score, (c) 뉴스 없는 봉→None, (d) 시간감쇠(오래된 호재 가중 작음), (e) 같은 뉴스 반복 봉→재스코어링 안 함(캐시). Commit `feat: NewsSignalSource (look-ahead-safe, cached, time-decayed)`.

## Task 7: 라이브 경로 통합 + 패리티 회귀 확인
- Modify `trader/app/run_paper.py`: 뉴스 소스를 **라이브 경로에만** 추가. FusionEngine에 `[TechnicalSignalSource(...), NewsSignalSource(MockNewsProvider(...), MockSentimentScorer(), ...)]` + `source_weight={"technical":1.0, "news_llm":0.5}`(보수적). `run_backtest.py`는 **건드리지 않음**(기술신호만).
- Test `tests/test_phase2_integration.py`: 기술+뉴스 두 소스를 단 FusionEngine이 라이브 루프(LiveEngine + InMemoryDailyFeed + SimulatedExecution)에서 동작하고 주문을 내는지(mock 뉴스로). 그리고 **`test_backtest_live_parity.py`가 여전히 green**임을 명시 확인.
- Commit `feat: wire news_llm into live path (conservative weight); backtest unchanged`.

## Self-review 체크
- 패리티: 뉴스는 run_backtest/패리티 테스트에 미주입 → Phase 1 테스트 회귀 0.
- 룩어헤드: provider + source 이중 필터.
- 비용: 아이템 1회 스코어링(cache).
- 키 없음: 전부 mock로 동작·테스트, 라이브 어댑터는 골격.
