# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-06-15T14:55:25.752Z

## Original task

KIS overseas balance inquiry (paper, tr_id VTTS3012R, /uapi/overseas-stock/v1/trading/inquire-balance) — I need to fold the USD cash + USD position values into a KRW-base account snapshot. My account_snapshot() currently takes cash_krw ONLY from domestic balance (VTTC8434R dnca_tot_amt) and positions from both, but after a USD stock buy the USD cash debit isn't reflected (cash_krw stayed unchanged). 

Tersely: (1) Which fields in VTTS3012R output2 (summary) give the USD cash balance / available foreign currency (e.g. frcr_dncl_amt1, frcr_buy_amt_smtl1, ord_psbl_frcr_amt)? (2) Is there a cleaner combined endpoint — VTRP6504R present-balance output2/output3 — that gives BOTH foreign cash per currency AND a KRW-converted total (e.g. tot_evlu_pfls_amt, frcr_evlu_tota, evlu_amt_smtl)? (3) Recommend: for a KRW-base portfolio, should account_snapshot use VTRP6504R as the single source of truth (it has FX + foreign cash + positions + KRW totals) instead of stitching VTTC8434R+VTTS3012R? Give the exact field names to read for: KRW cash, USD cash (→ convert via the bass_exrt we already read), total KRW equity. Flag any field name you're unsure of. Senior, terse.

## Final prompt

KIS overseas balance inquiry (paper, tr_id VTTS3012R, /uapi/overseas-stock/v1/trading/inquire-balance) — I need to fold the USD cash + USD position values into a KRW-base account snapshot. My account_snapshot() currently takes cash_krw ONLY from domestic balance (VTTC8434R dnca_tot_amt) and positions from both, but after a USD stock buy the USD cash debit isn't reflected (cash_krw stayed unchanged). 

Tersely: (1) Which fields in VTTS3012R output2 (summary) give the USD cash balance / available foreign currency (e.g. frcr_dncl_amt1, frcr_buy_amt_smtl1, ord_psbl_frcr_amt)? (2) Is there a cleaner combined endpoint — VTRP6504R present-balance output2/output3 — that gives BOTH foreign cash per currency AND a KRW-converted total (e.g. tot_evlu_pfls_amt, frcr_evlu_tota, evlu_amt_smtl)? (3) Recommend: for a KRW-base portfolio, should account_snapshot use VTRP6504R as the single source of truth (it has FX + foreign cash + positions + KRW totals) instead of stitching VTTC8434R+VTTS3012R? Give the exact field names to read for: KRW cash, USD cash (→ convert via the bass_exrt we already read), total KRW equity. Flag any field name you're unsure of. Senior, terse.

## Raw output

```text
**Short Answer**

1. `VTTS3012R / inquire-balance`
   - Positions: `output1`
   - Summary/P&L: `output2`
   - Useful `output2` fields:
     - `tot_evlu_pfls_amt`: total valuation P/L
     - `tot_pftrt`: total return %
     - `frcr_buy_amt_smtl1`: foreign buy amount sum 1
     - `frcr_buy_amt_smtl2`: foreign buy amount sum 2
   - Not clean USD cash. `frcr_dncl_amt1` is **not** `VTTS3012R`; it appears under `foreign-margin` (`TTTC2101R`) as foreign deposit amount.
   - `ord_psbl_frcr_amt` is **not** `VTTS3012R`; it is from `inquire-psamount` (`VTTS3007R`) and means orderable foreign currency amount.

2. `VTRP6504R / inquire-present-balance`
   - Yes, cleaner for snapshot.
   - `output1`: overseas positions, includes:
     - `pdno`
     - `cblc_qty13`
     - `ovrs_now_pric1`
     - `frcr_evlu_amt2`
     - `bass_exrt`
     - `crcy_cd`
   - `output2`: per-currency cash/FX block, includes:
     - `crcy_cd`
     - `frcr_dncl_amt_2`: foreign cash/deposit amount
     - `frcr_drwg_psbl_amt_1`: withdrawable foreign cash
     - `nxdy_frcr_drwg_psbl_amt`
     - `frst_bltn_exrt`
   - `output3`: aggregate KRW/account totals, includes:
     - `dncl_amt`: deposit amount
     - `tot_dncl_amt`: total deposit amount
     - `evlu_amt_smtl`: valuation amount sum
     - `frcr_evlu_tota`: foreign valuation total
     - `evlu_amt_smtl_amt`: valuation amount sum amount
     - `tot_evlu_pfls_amt`: total valuation P/L
     - `tot_asst_amt`: total asset amount

3. Recommendation: use `VTRP6504R` as the snapshot source of truth for overseas/FX-aware account equity. Keep `VTTC8434R` only if you need domestic stock detail not represented there.

For KRW-base snapshot fields:

- KRW cash: `output3[0].tot_dncl_amt` or `output3[0].dncl_amt`
  - I’d use `tot_dncl_amt` for total cash/deposit; fall back to `dncl_amt`.
- USD cash: `output2` row where `crcy_cd == "USD"`:
  - use `frcr_dncl_amt_2`
  - conservative available-cash variant: `frcr_drwg_psbl_amt_1`
  - convert with `bass_exrt` from matching `output1`/USD row or `frst_bltn_exrt` from `output2`.
- Total KRW equity:
  - use `output3[0].tot_asst_amt` if present.
  - fallback: `output3[0].evlu_amt_smtl_amt`.
  - `tot_evlu_pfls_amt` is P/L, not equity.

Unsure/needs live confirmation: whether `tot_dncl_amt` includes KRW-only cash or all deposits converted to KRW in your paper account. Field name suggests total deposit amount, but KIS naming is inconsistent; validate once against a known cash balance.


OpenAI Codex v0.139.0
--------
workdir: /Users/manager/side/makemoney
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019ecbc5-9e2f-7f20-aba0-c9c22f49473f
--------
user
KIS overseas balance inquiry (paper, tr_id VTTS3012R, /uapi/overseas-stock/v1/trading/inquire-balance) — I need to fold the USD cash + USD position values into a KRW-base account snapshot. My account_snapshot() currently takes cash_krw ONLY from domestic balance (VTTC8434R dnca_tot_amt) and positions from both, but after a USD stock buy the USD cash debit isn't reflected (cash_krw stayed unchanged). 

Tersely: (1) Which fields in VTTS3012R output2 (summary) give the USD cash balance / available foreign currency (e.g. frcr_dncl_amt1, frcr_buy_amt_smtl1, ord_psbl_frcr_amt)? (2) Is there a cleaner combined endpoint — VTRP6504R present-balance output2/output3 — that gives BOTH foreign cash per currency AND a KRW-converted total (e.g. tot_evlu_pfls_amt, frcr_evlu_tota, evlu_amt_smtl)? (3) Recommend: for a KRW-base portfolio, should account_snapshot use VTRP6504R as the single source of truth (it has FX + foreign cash + positions + KRW totals) instead of stitching VTTC8434R+VTTS3012R? Give the exact field names to read for: KRW cash, USD cash (→ convert via the bass_exrt we already read), total KRW equity. Flag any field name you're unsure of. Senior, terse.
codex
I’ll verify this against KIS docs/examples rather than rely on memory, because these TR field names are easy to mix up.
web search: 
web search: VTTS3012R frcr_dncl_amt1 ord_psbl_frcr_amt output2
web search: 
web search: site:github.com VTTS3012R frcr_dncl_amt1
web search: 
web search: "frcr_dncl_amt1" "frcr_buy_amt_smtl1"
web search: 
web search: https://raw.githubusercontent.com/naraeit77/stockmaru-real-main/main/stockmaru_real_main.md
web search: 
web search: 'frcr_dncl_amt1' in https://raw.githubusercontent.com/naraeit77/stockmaru-real-main/main/stockmaru_real_main.md
web search: 
web search: KoreaInvestment open-trading-api inquire-present-balance output3
codex
I found KIS’s official sample-code repo and the endpoint/TR mapping. I’m going one level deeper for the actual response schema names now, since endpoint names alone won’t settle the cash/equity fields.
exec
/bin/zsh -lc 'rg --files . | head -80 && rg -n "VTTS3012R|VTRP6504R|inquire-present-balance|frcr_dncl_amt|ord_psbl_frcr_amt|tot_evlu_pfls_amt|frcr_evlu_tota|evlu_amt_smtl|dnca_tot_amt" .' in /Users/manager/side/makemoney
 succeeded in 0ms:
./scripts/run_daily.sh
./MORNING_REPORT.md
./docs/kis-api-reference.md
./docs/operations.md
./pyproject.toml
./docs/superpowers/specs/2026-06-15-phase1-trading-engine-design.md
./docs/superpowers/specs/2026-06-15-phase2-news-llm-signal-design.md
./tests/test_news_models.py
./tests/test_technical_indicators.py
./tests/test_portfolio_helpers.py
./tests/test_news_providers.py
./tests/test_fx_portfolio.py
./tests/test_kis_live_feed.py
./tests/test_news_prompts.py
./tests/test_no_lookahead.py
./tests/test_technical_indicator_source.py
./tests/test_clock.py
./tests/test_interfaces.py
./tests/test_technical_signal.py
./tests/test_events.py
./tests/test_backtest_engine.py
./tests/test_news_cache.py
./tests/test_fetch_data.py
./tests/test_indicators.py
./tests/test_kis_orders.py
./tests/test_backtest_live_parity.py
./tests/test_audit.py
./tests/test_sleeve.py
./tests/test_daily_act.py
./tests/test_evaluate.py
./tests/test_kis_client.py
./tests/test_risk.py
./tests/test_phase2_integration.py
./tests/test_kis_paper.py
./tests/test_execution_sim.py
./tests/__init__.py
./tests/test_historical_feed.py
./tests/test_kis_live_integration.py
./tests/test_run_ledger.py
./tests/test_news_sentiment.py
./tests/test_metrics.py
./tests/test_fusion_engine.py
./tests/test_news_source.py
./tests/test_diversified_fusion.py
./tests/test_costs.py
./tests/test_kis_fx.py
./tests/test_replay_parity.py
./tests/test_order_factory.py
./tests/test_kis_history.py
./tests/test_kis_balance.py
./tests/test_journal.py
./docs/superpowers/plans/2026-06-15-paper-forward-signal-journal.md
./docs/superpowers/plans/2026-06-15-evaluation-metrics-fix.md
./docs/superpowers/plans/2026-06-15-phase2-news-llm-signal.md
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md
./trader/observability/__init__.py
./trader/observability/audit.py
./trader/observability/logging.py
./trader/strategy/portfolio.py
./trader/strategy/risk.py
./trader/strategy/__init__.py
./trader/strategy/order_factory.py
./trader/strategy/sleeve.py
./trader/strategy/fusion_engine.py
./trader/__init__.py
./trader/execution/kis_paper.py
./trader/execution/costs.py
./trader/execution/__init__.py
./trader/execution/kis_client.py
./trader/execution/simulated.py
./trader/execution/interfaces.py
./trader/data/historical_feed.py
./trader/data/kis_live_feed.py
./trader/data/storage.py
./trader/data/calendar.py
./trader/data/__init__.py
./trader/data/recorder.py
./trader/data/interfaces.py
./trader/backtest/report.py
./trader/backtest/evaluate.py
./docs/kis-api-reference.md:33:| 현재잔고/환율 | `GET /uapi/overseas-stock/v1/trading/inquire-present-balance` | `VTRP6504R` | ✅ 라이브 검증 — `output2[].frst_bltn_exrt` USD/KRW=1520.40 수신 확인 (2026-06-15) |
./docs/kis-api-reference.md:35:### VTRP6504R 파라미터 메모
./docs/kis-api-reference.md:36:- **현재잔고/환율** (`VTRP6504R`): query `CANO`, `ACNT_PRDT_CD="01"`, `WCRC_FRCR_DVSN_CD="01"`, `NATN_CD="000"`, `TR_MKET_CD="00"`, `INQR_DVSN_CD="00"`. 응답 `output1[].bass_exrt`(기준환율, 통화코드=`crcy_cd`), `output2[].frst_bltn_exrt`(최초고시환율). USD/KRW 환율: `crcy_cd=="USD"` 행 우선 `bass_exrt` → 없으면 `frst_bltn_exrt` → 없으면 fallback 1380.0. 문자열→float 변환 필수; 0/empty는 fallback 처리.
./trader/execution/kis_client.py:649:          output2: list with one summary row (dnca_tot_amt = 예수금총금액,
./trader/execution/kis_client.py:650:                   prvs_rcdl_excc_amt = 전일매도정산금 — we use dnca_tot_amt
./trader/execution/kis_client.py:683:        """GET /uapi/overseas-stock/v1/trading/inquire-balance (VTTS3012R paper).
./trader/execution/kis_client.py:698:            headers=self._headers("VTTS3012R"),
./trader/execution/kis_client.py:717:        """GET /uapi/overseas-stock/v1/trading/inquire-present-balance (VTRP6504R).
./trader/execution/kis_client.py:728:            "/uapi/overseas-stock/v1/trading/inquire-present-balance",
./trader/execution/kis_client.py:729:            headers=self._headers("VTRP6504R"),
./trader/execution/kis_client.py:748:        """Return today's USD/KRW exchange rate from present_balance (VTRP6504R).
./trader/execution/kis_client.py:784:                "cash_krw": float,            # KRW available cash (dnca_tot_amt from domestic output2)
./trader/execution/kis_client.py:789:        Cash note: we use `dnca_tot_amt` (예수금총금액 — total deposit amount) from
./trader/execution/kis_client.py:802:        cash_krw = _safe_float(summary_row.get("dnca_tot_amt", "0"))
./trader/app/run_daily.py:109:    # Fetch live USD/KRW rate via VTRP6504R; falls back to 1380.0 if unavailable.
./trader/app/run_daily.py:112:    print(f"FX rate: 1 USD = {usd_rate:,.2f} KRW (live via VTRP6504R, fallback=1380.0)")
./tests/test_kis_fx.py:2:"""Mock tests for KisClient.present_balance and usd_krw_rate (VTRP6504R)."""
./tests/test_kis_fx.py:34:        if "inquire-present-balance" in p:
./tests/test_kis_balance.py:27:            "dnca_tot_amt": "5000000",
./tests/test_kis_balance.py:79:    assert body["output2"][0]["dnca_tot_amt"] == "5000000"
./tests/test_kis_balance.py:114:    # dnca_tot_amt = "5000000"
./tests/test_kis_balance.py:154:                "output2": [{"dnca_tot_amt": "1000000"}],

codex
Your repo already has a local KIS reference note and `KisClient.account_snapshot()` comments around these fields. I’m reading those with the implementation so the recommendation matches your current code shape.
exec
/bin/zsh -lc "sed -n '620,850p' trader/execution/kis_client.py" in /Users/manager/side/makemoney
exec
/bin/zsh -lc "sed -n '1,120p' docs/kis-api-reference.md" in /Users/manager/side/makemoney
 succeeded in 0ms:
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
| 해외 주문 | `POST /uapi/overseas-stock/v1/trading/order` | 매수 `VTTT1002U` / 매도 `VTTT1001U` | ✅✅ **장중 실체결 검증**(2026-06-15) — AAPL 1주 매수 $295.85 체결→매도 flat 완료. ⚠️ 매도는 `VTTT1006U` 아님(모의 거부 "해당업무 미제공") → **`VTTT1001U` + body `SLL_TYPE="00"`** 필수. |
| 국내 주문 | `POST /uapi/domestic-stock/v1/trading/order-cash` | 매수 `VTTC0012U` / 매도 `VTTC0011U` | ⬜ 미검증 (단위테스트만) |
| 해외 체결조회 | `GET /uapi/overseas-stock/v1/trading/inquire-ccnl` | `VTTS3035R` | ✅ rt_cd=0, 빈 리스트 반환 (정상 수락) |
| 국내 체결조회 | `GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld` | 3개월내 `VTTC0081R` | ⬜ 미검증 (TODO) |
| 현재잔고/환율 | `GET /uapi/overseas-stock/v1/trading/inquire-present-balance` | `VTRP6504R` | ✅ 라이브 검증 — `output2[].frst_bltn_exrt` USD/KRW=1520.40 수신 확인 (2026-06-15) |

### VTRP6504R 파라미터 메모
- **현재잔고/환율** (`VTRP6504R`): query `CANO`, `ACNT_PRDT_CD="01"`, `WCRC_FRCR_DVSN_CD="01"`, `NATN_CD="000"`, `TR_MKET_CD="00"`, `INQR_DVSN_CD="00"`. 응답 `output1[].bass_exrt`(기준환율, 통화코드=`crcy_cd`), `output2[].frst_bltn_exrt`(최초고시환율). USD/KRW 환율: `crcy_cd=="USD"` 행 우선 `bass_exrt` → 없으면 `frst_bltn_exrt` → 없으면 fallback 1380.0. 문자열→float 변환 필수; 0/empty는 fallback 처리.

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

 succeeded in 0ms:

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

    # ------------------------------------------------------------------
    # Balance inquiry
    # ------------------------------------------------------------------

    def domestic_balance(self) -> dict:
        """GET /uapi/domestic-stock/v1/trading/inquire-balance (VTTC8434R paper).

        Returns the parsed JSON body with:
          output1: list of position rows (pdno, hldg_qty, prpr, ...)
          output2: list with one summary row (dnca_tot_amt = 예수금총금액,
                   prvs_rcdl_excc_amt = 전일매도정산금 — we use dnca_tot_amt
                   as available KRW cash; see account_snapshot docstring).

        Raises RuntimeError if rt_cd != "0".
        """
        cano = self.account
        self._throttle()
        resp = self._c.get(
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=self._headers("VTTC8434R"),
            params={
                "CANO": cano,
                "ACNT_PRDT_CD": "01",
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS domestic_balance error [{body.get('rt_cd')}]: {body.get('msg1', body)}"
            )
        return body

    def overseas_balance(self, exchange: str = "NASD", ccy: str = "USD") -> dict:
        """GET /uapi/overseas-stock/v1/trading/inquire-balance (VTTS3012R paper).

        Args:
            exchange: KIS exchange code e.g. "NASD" (NASDAQ).
            ccy: Currency code e.g. "USD".

        Returns the parsed JSON body with:
          output1: list of position rows (ovrs_pdno, ovrs_cblc_qty, now_pric2, ...)

        Raises RuntimeError if rt_cd != "0".
        """
        cano = self.account
        self._throttle()
        resp = self._c.get(
            "/uapi/overseas-stock/v1/trading/inquire-balance",
            headers=self._headers("VTTS3012R"),
            params={
                "CANO": cano,
                "ACNT_PRDT_CD": "01",
                "OVRS_EXCG_CD": exchange,
                "TR_CRCY_CD": ccy,
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS overseas_balance error [{body.get('rt_cd')}]: {body.get('msg1', body)}"
            )
        return body

    def present_balance(self, exchange: str = "NASD", ccy: str = "USD") -> dict:
        """GET /uapi/overseas-stock/v1/trading/inquire-present-balance (VTRP6504R).

        Returns the parsed JSON body containing current overseas balance with FX rates.
        Key fields used for USD/KRW rate:
          output1[*].bass_exrt  — base exchange rate where the row's currency matches.
          output2[*].frst_bltn_exrt — first posted exchange rate (fallback).

        Raises RuntimeError if rt_cd != "0".
        """
        self._throttle()
        resp = self._c.get(
            "/uapi/overseas-stock/v1/trading/inquire-present-balance",
            headers=self._headers("VTRP6504R"),
            params={
                "CANO": self.account,
                "ACNT_PRDT_CD": "01",
                "WCRC_FRCR_DVSN_CD": "01",
                "NATN_CD": "000",
                "TR_MKET_CD": "00",
                "INQR_DVSN_CD": "00",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS present_balance error [{body.get('rt_cd')}]: {body.get('msg1', body)}"
            )
        return body

    def usd_krw_rate(self, default: float = 1380.0) -> float:
        """Return today's USD/KRW exchange rate from present_balance (VTRP6504R).

        Lookup priority:
          1. output1[*].bass_exrt  where the row's currency code is "USD".
          2. output2[*].frst_bltn_exrt where the row's currency code is "USD".
          3. Returns `default` (1380.0) if the API returns nothing usable.

        All string→float conversions are defensive; zero/empty values fall through
        to the next source or the default.
        """
        try:
            body = self.present_balance()
        except Exception:
            return default

        # --- Priority 1: output1 bass_exrt ---
        for row in body.get("output1", []):
            if row.get("crcy_cd", "").upper() == "USD":
                val = _safe_float(row.get("bass_exrt", ""), 0.0)
                if val > 0:
                    return val

        # --- Priority 2: output2 frst_bltn_exrt ---
        for row in body.get("output2", []):
            if row.get("crcy_cd", "").upper() == "USD":
                val = _safe_float(row.get("frst_bltn_exrt", ""), 0.0)
                if val > 0:
                    return val

        return default

    def account_snapshot(self) -> dict:
        """Return a normalized account snapshot combining domestic + overseas balances.

        Structure:
            {
                "cash_krw": float,            # KRW available cash (dnca_tot_amt from domestic output2)
                "positions": {(market, ticker): qty},   # int qty; market is "KOSPI" or "NASDAQ"
                "marks":     {(market, ticker): price}, # float last price in native currency
            }

        Cash note: we use `dnca_tot_amt` (예수금총금액 — total deposit amount) from
        domestic output2[0] as the base KRW cash figure.  This is the gross available
        cash before settlement netting; it is the most reliably present field across
        KIS paper accounts.  Overseas USD cash is a TODO (folded later via FX).

        Defensively casts all string fields to float/int; skips zero-qty rows.
        """
        dom = self.domestic_balance()
        ovr = self.overseas_balance()

        # --- KRW cash ---
        dom_summary = dom.get("output2", [{}])
        summary_row = dom_summary[0] if dom_summary else {}
        cash_krw = _safe_float(summary_row.get("dnca_tot_amt", "0"))

        positions: dict[tuple[str, str], int] = {}
        marks: dict[tuple[str, str], float] = {}

        # --- Domestic positions (KOSPI) ---
        for row in dom.get("output1", []):
            ticker = row.get("pdno", "").strip()
            qty = _safe_int(row.get("hldg_qty", "0"))
            price = _safe_float(row.get("prpr", "0"))
            if not ticker or qty == 0:
                continue
            key = ("KOSPI", ticker)
            positions[key] = qty
            marks[key] = price

        # --- Overseas positions (NASDAQ) ---
        for row in ovr.get("output1", []):
            ticker = row.get("ovrs_pdno", "").strip()
            qty = _safe_int(row.get("ovrs_cblc_qty", "0"))
            price = _safe_float(row.get("now_pric2", "0"))
            if not ticker or qty == 0:
                continue
            key = ("NASDAQ", ticker)
            positions[key] = qty
            marks[key] = price

        return {
            "cash_krw": cash_krw,
            "positions": positions,
            "marks": marks,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val, default: float = 0.0) -> float:
    """Cast string/number to float; return default on failure."""
    try:
        return float(val) if val not in (None, "", "-") else default
    except (ValueError, TypeError):
        return default


def _safe_int(val, default: int = 0) -> int:
    """Cast string/number to int; return default on failure."""
    try:

exec
/bin/zsh -lc "sed -n '1,220p' tests/test_kis_balance.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
"""Unit tests for KisClient balance inquiry + account_snapshot — MockTransport, no network."""
from __future__ import annotations

import httpx
import pytest

from trader.execution.kis_client import KisClient

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_DOM_BALANCE_RESP = {
    "rt_cd": "0",
    "msg1": "정상처리 되었습니다.",
    "output1": [
        {
            "pdno": "005930",
            "prdt_name": "삼성전자",
            "hldg_qty": "10",
            "prpr": "75000",
            "evlu_amt": "750000",
        }
    ],
    "output2": [
        {
            "dnca_tot_amt": "5000000",
            "prvs_rcdl_excc_amt": "4800000",
            "tot_evlu_amt": "5750000",
        }
    ],
}

_OVR_BALANCE_RESP = {
    "rt_cd": "0",
    "msg1": "정상처리 되었습니다.",
    "output1": [
        {
            "ovrs_pdno": "AAPL",
            "ovrs_item_name": "APPLE",
            "ovrs_cblc_qty": "5",
            "now_pric2": "195.50",
            "evlu_pfls_amt": "50.00",
        }
    ],
    "output2": [{}],
}


def _handler(req: httpx.Request) -> httpx.Response:
    p = str(req.url.path)
    if p.endswith("/oauth2/tokenP"):
        return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
    if "inquire-balance" in p and "domestic-stock" in p:
        return httpx.Response(200, json=_DOM_BALANCE_RESP)
    if "inquire-balance" in p and "overseas-stock" in p:
        return httpx.Response(200, json=_OVR_BALANCE_RESP)
    return httpx.Response(404, json={"error": f"unmatched: {p}"})


def _client(tmp_path) -> KisClient:
    c = httpx.Client(transport=httpx.MockTransport(_handler), base_url="https://mock")
    return KisClient(
        c, "k", "s", "50193330", paper=True, min_interval=0,
        token_cache_path=str(tmp_path / "tok.json"),
    )


# ---------------------------------------------------------------------------
# domestic_balance
# ---------------------------------------------------------------------------

def test_domestic_balance_returns_parsed_body(tmp_path):
    body = _client(tmp_path).domestic_balance()
    assert body["rt_cd"] == "0"
    assert len(body["output1"]) == 1
    assert body["output1"][0]["pdno"] == "005930"
    assert len(body["output2"]) == 1
    assert body["output2"][0]["dnca_tot_amt"] == "5000000"


def test_domestic_balance_raises_on_error(tmp_path):
    def handler_err(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
        return httpx.Response(200, json={"rt_cd": "1", "msg1": "잔고조회 오류"})

    c = httpx.Client(transport=httpx.MockTransport(handler_err), base_url="https://mock")
    kis = KisClient(c, "k", "s", "50193330", paper=True, min_interval=0,
                    token_cache_path=str(tmp_path / "tok.json"))
    with pytest.raises(RuntimeError, match="잔고조회 오류"):
        kis.domestic_balance()


# ---------------------------------------------------------------------------
# overseas_balance
# ---------------------------------------------------------------------------

def test_overseas_balance_returns_parsed_body(tmp_path):
    body = _client(tmp_path).overseas_balance()
    assert body["rt_cd"] == "0"
    assert len(body["output1"]) == 1
    assert body["output1"][0]["ovrs_pdno"] == "AAPL"
    assert body["output1"][0]["ovrs_cblc_qty"] == "5"


# ---------------------------------------------------------------------------
# account_snapshot
# ---------------------------------------------------------------------------

def test_account_snapshot_cash_krw(tmp_path):
    snap = _client(tmp_path).account_snapshot()
    # dnca_tot_amt = "5000000"
    assert snap["cash_krw"] == 5_000_000.0


def test_account_snapshot_domestic_position(tmp_path):
    snap = _client(tmp_path).account_snapshot()
    key = ("KOSPI", "005930")
    assert key in snap["positions"]
    assert snap["positions"][key] == 10
    assert snap["marks"][key] == 75_000.0


def test_account_snapshot_overseas_position(tmp_path):
    snap = _client(tmp_path).account_snapshot()
    key = ("NASDAQ", "AAPL")
    assert key in snap["positions"]
    assert snap["positions"][key] == 5
    assert snap["marks"][key] == 195.50


def test_account_snapshot_shape(tmp_path):
    snap = _client(tmp_path).account_snapshot()
    assert "cash_krw" in snap
    assert "positions" in snap
    assert "marks" in snap
    assert isinstance(snap["cash_krw"], float)
    assert isinstance(snap["positions"], dict)
    assert isinstance(snap["marks"], dict)


def test_account_snapshot_skips_zero_qty_rows(tmp_path):
    """Rows with qty=0 must be excluded from positions."""
    def handler_zero(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
        if "domestic-stock" in p:
            return httpx.Response(200, json={
                "rt_cd": "0", "msg1": "ok",
                "output1": [{"pdno": "005930", "hldg_qty": "0", "prpr": "75000"}],
                "output2": [{"dnca_tot_amt": "1000000"}],
            })
        if "overseas-stock" in p:
            return httpx.Response(200, json={
                "rt_cd": "0", "msg1": "ok",
                "output1": [{"ovrs_pdno": "AAPL", "ovrs_cblc_qty": "0", "now_pric2": "195"}],
                "output2": [{}],
            })
        return httpx.Response(404, json={})

    c = httpx.Client(transport=httpx.MockTransport(handler_zero), base_url="https://mock")
    kis = KisClient(c, "k", "s", "50193330", paper=True, min_interval=0,
                    token_cache_path=str(tmp_path / "tok.json"))
    snap = kis.account_snapshot()
    assert snap["positions"] == {}
    assert snap["marks"] == {}
    assert snap["cash_krw"] == 1_000_000.0

exec
/bin/zsh -lc "sed -n '1,140p' tests/test_kis_fx.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
# tests/test_kis_fx.py
"""Mock tests for KisClient.present_balance and usd_krw_rate (VTRP6504R)."""
from __future__ import annotations

import httpx
import pytest

from trader.execution.kis_client import KisClient


# ---------------------------------------------------------------------------
# Mock transport helpers
# ---------------------------------------------------------------------------

def _token_resp():
    return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})


def _make_client(handler, tmp_path) -> KisClient:
    c = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://mock")
    return KisClient(
        c, "k", "s", "50193330",
        paper=True, min_interval=0,
        token_cache_path=str(tmp_path / "tok.json"),
    )


def _present_balance_handler(output1=None, output2=None, rt_cd="0"):
    """Build a mock handler that returns a present_balance response."""
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_resp()
        if "inquire-present-balance" in p:
            return httpx.Response(200, json={
                "rt_cd": rt_cd,
                "msg1": "ok" if rt_cd == "0" else "error",
                "output1": output1 or [],
                "output2": output2 or [],
            })
        return httpx.Response(404, json={})
    return handler


# ---------------------------------------------------------------------------
# Tests: present_balance
# ---------------------------------------------------------------------------

class TestPresentBalance:
    def test_returns_parsed_json(self, tmp_path):
        """present_balance returns the parsed JSON body on rt_cd=0."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": "1375.50"}]
        )
        kis = _make_client(handler, tmp_path)
        result = kis.present_balance()
        assert result["rt_cd"] == "0"
        assert result["output2"][0]["crcy_cd"] == "USD"

    def test_raises_on_nonzero_rt_cd(self, tmp_path):
        """present_balance raises RuntimeError when rt_cd != 0."""
        handler = _present_balance_handler(rt_cd="1")
        kis = _make_client(handler, tmp_path)
        with pytest.raises(RuntimeError, match="present_balance error"):
            kis.present_balance()


# ---------------------------------------------------------------------------
# Tests: usd_krw_rate
# ---------------------------------------------------------------------------

class TestUsdKrwRate:
    def test_reads_from_output2_frst_bltn_exrt(self, tmp_path):
        """usd_krw_rate reads frst_bltn_exrt from output2 when output1 has no USD row."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": "1375.50"}]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate()
        assert rate == 1375.50

    def test_reads_from_output1_bass_exrt_first(self, tmp_path):
        """usd_krw_rate prefers output1.bass_exrt over output2."""
        handler = _present_balance_handler(
            output1=[{"crcy_cd": "USD", "bass_exrt": "1390.00"}],
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": "1375.50"}],
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate()
        assert rate == 1390.00

    def test_skips_non_usd_rows_in_output2(self, tmp_path):
        """Non-USD rows are ignored; only USD row is used."""
        handler = _present_balance_handler(
            output2=[
                {"crcy_cd": "JPY", "frst_bltn_exrt": "0.0065"},
                {"crcy_cd": "USD", "frst_bltn_exrt": "1375.50"},
            ]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate()
        assert rate == 1375.50

    def test_returns_default_when_output_empty(self, tmp_path):
        """Returns default=1380.0 when both output1 and output2 are empty."""
        handler = _present_balance_handler(output1=[], output2=[])
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1380.0)
        assert rate == 1380.0

    def test_returns_default_when_no_usd_row(self, tmp_path):
        """Returns default when no USD currency row exists."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "JPY", "frst_bltn_exrt": "0.0065"}]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1380.0)
        assert rate == 1380.0

    def test_returns_default_when_rate_is_zero(self, tmp_path):
        """Zero exchange rate falls through to default."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": "0"}]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1380.0)
        assert rate == 1380.0

    def test_returns_default_when_rate_is_empty_string(self, tmp_path):
        """Empty string exchange rate falls through to default."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": ""}]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1380.0)
        assert rate == 1380.0

    def test_returns_default_when_api_raises(self, tmp_path):
        """If present_balance raises, usd_krw_rate catches and returns default."""
        handler = _present_balance_handler(rt_cd="1")

codex
The local note confirms `VTRP6504R` has been live-verified for FX in this repo, but it doesn’t document the cash/equity summary fields. I’m pulling the official sample repo metadata next; if it’s absent there too, I’ll label the uncertain fields explicitly.
exec
/bin/zsh -lc 'tmp=$(mktemp -d); git clone --depth 1 https://github.com/koreainvestment/open-trading-api "$tmp/repo" >/dev/null 2>&1 && rg -n "VTTS3012R|VTRP6504R|frcr_dncl_amt|frcr_buy_amt_smtl|ord_psbl_frcr_amt|tot_evlu_pfls_amt|frcr_evlu_tota|evlu_amt_smtl|inquire-present-balance|inquire-balance" "$tmp/repo"' in /Users/manager/side/makemoney
 succeeded in 4363ms:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:890:    'frcr_dncl_amt': '외화예수금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:921:    'evlu_amt_smtl': '평가금액합계'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:954:    'frcr_dncl_amt': '외화예수금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:983:    'evlu_amt_smtl': '평가금액합계'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:1034:    'frcr_dncl_amt': '외화예수금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:2542:    'evlu_amt_smtl': '평가금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:2551:    'frcr_evlu_tota': '외화평가총액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:2611:    'ord_psbl_frcr_amt_wcrc': '주문가능외화금액원화'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:2954:    'evlu_amt_smtl_amt': '평가금액합계금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:2982:    'evlu_amt_smtl_amt': '평가금액합계금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:3008:    'ord_psbl_frcr_amt_wcrc': '주문가능외화금액원화'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:3336:    'evlu_amt_smtl_amt': '평가금액합계금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10706:    'tot_evlu_pfls_amt': '총평가손익금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10708:    'frcr_buy_amt_smtl1': '외화매수금액합계1',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10710:    'frcr_buy_amt_smtl2': '외화매수금액합계2'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10763:    'frcr_buy_amt_smtl': '외화매수금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10765:    'frcr_dncl_amt_2': '외화예수금액2',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10775:    'evlu_amt_smtl': '평가금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10782:    'frcr_evlu_tota': '외화평가총액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10785:    'evlu_amt_smtl_amt': '평가금액합계금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10786:    'tot_evlu_pfls_amt': '총평가손익금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:10897:    'ord_psbl_frcr_amt': '주문가능외화금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:11140:    'frcr_dncl_amt_2': '외화예수금액2',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:11144:    'tot_evlu_pfls_amt': '총평가손익금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:11147:    'wcrc_evlu_amt_smtl': '원화평가금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:11149:    'frcr_cblc_wcrc_evlu_amt_smtl': '외화잔고원화평가금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:11204:    'frcr_buy_amt_smtl': '외화매수금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/KIS Code Assistant MCP/data.csv:11344:    'frcr_dncl_amt1': '외화예수금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/rest/kis_api.py:271:    url = '/uapi/domestic-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_bond/inquire_balance/inquire_balance.py:28:API_URL = "/uapi/domestic-bond/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample02/CSharp/KIS_OverseaStk.cs:402:            string url = "/uapi/overseas-stock/v1/trading/inquire-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample02/CSharp/KIS_OverseaStk.cs:403:            string trID = "TTTS3012R"; // 모의투자 VTTS3012R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample02/CSharp/KIS_OverseaStk.cs:435:            string url = "/uapi/overseas-stock/v1/trading/inquire-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample02/CSharp/KIS_OverseaStk.cs:436:            string trID = "TTTS3012R"; // 모의투자 VTTS3012R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample02/CSharp/KIS_OverseaStk.cs:633:            string url = "/uapi/overseas-stock/v1/trading/inquire-present-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample02/CSharp/KIS_OverseaStk.cs:634:            string trID = "CTRP6504R"; // 모의투자 VTRP6504R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_period_trans/chk_inquire_period_trans.py:49:    'frcr_buy_amt_smtl': '외화매수금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_period_trans/chk_inquire_period_trans.py:59:    'dmst_wcrc_fee', 'ovrs_wcrc_fee', 'erlm_exrt', 'frcr_buy_amt_smtl', 'frcr_sll_amt_smtl',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/overseas_stock.json:1396:      "api_path": "/uapi/overseas-stock/v1/trading/inquire-present-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/overseas_stock.json:1496:      "api_path": "/uapi/overseas-stock/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/domestic_futureoption.json:277:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1010:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1100:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1056:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=01&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=00&CTX_AREA_FK100&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1065:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1778:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/pension/inquire-present-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=29&USER_DVSN_CD=00&CTX_AREA_FK100=&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1788:										"inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2256:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/pension/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=29&ACCA_DVSN_CD=00&INQR_DVSN=00&CTX_AREA_FK100&CTX_AREA_NK100",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2266:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2342:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=02&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=01&COST_ICLD_YN=N&CTX_AREA_FK100=&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2351:										"inquire-balance-rlz-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16072:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-balance?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&MGNA_DVSN=01&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16081:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16725:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&INQR_DT=20230906&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16734:										"inquire-balance-settlement-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16942:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&MGNA_DVSN=02&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16951:										"inquire-balance-valuation-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19858:										"description": "[실전투자]\nTTTS3012R\n\n[모의투자]\nVTTS3012R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19867:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=NASD&TR_CRCY_CD=USD&CTX_AREA_FK200=&CTX_AREA_NK200",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19876:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20102:										"description": "[실전투자]\nCTRP6504R\n\n[모의투자]\nVTRP6504R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20111:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-present-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&NATN_CD=000&WCRC_FRCR_DVSN_CD=01&TR_MKET_CD=00&INQR_DVSN_CD=00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20120:										"inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:25929:									"raw": "{{PROD}}/uapi/domestic-bond/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&INQR_CNDT=00&PDNO=&BUY_DT=&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:25938:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1919:									"raw": "{{VTS}}/uapi/domestic-stock/v1/trading/inquire-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=01&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=00&CTX_AREA_FK100=&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1928:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2545:									"raw": "{{VTS}}/uapi/domestic-futureoption/v1/trading/inquire-balance?CANO={{CANO_T}}&ACNT_PRDT_CD=03&MGNA_DVSN=01&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2554:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4678:										"value": "VTTS3012R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4680:										"description": "[실전투자]\nTTTS3012R\n\n[모의투자]\nVTTS3012R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4688:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/inquire-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=TKSE&TR_CRCY_CD=JPY&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4697:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4922:										"value": "VTRP6504R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4924:										"description": "[실전투자]\nCTRP6504R\n\n[모의투자]\nVTRP6504R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4932:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/inquire-present-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&NATN_CD=000&WCRC_FRCR_DVSN_CD=01&TR_MKET_CD=00&INQR_DVSN_CD=00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4941:										"inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/domestic_stock.json:2694:      "api_path": "/uapi/domestic-stock/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/domestic_stock.json:3160:      "api_path": "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/domestic_stock.json:3675:      "api_path": "/uapi/domestic-stock/v1/trading/pension/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/domestic_stock.json:4446:      "api_path": "/uapi/domestic-stock/v1/trading/pension/inquire-present-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:52:    'frcr_dncl_amt_2': '외화예수금액2',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:56:    'tot_evlu_pfls_amt': '총평가손익금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:59:    'wcrc_evlu_amt_smtl': '원화평가금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:61:    'frcr_cblc_wcrc_evlu_amt_smtl': '외화잔고원화평가금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/MCP/Kis Trading MCP/configs/domestic_bond.json:593:      "api_path": "/uapi/domestic-bond/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_domstk.py:293:    url = '/uapi/domestic-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_domstk.py:324:    url = '/uapi/domestic-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_domstk.py:392:        #cf1 = ['ord_psbl_cash', 'ruse_psbl_amt', 'fund_rpch_chgs', 'psbl_qty_calc_unpr', 'nrcvb_buy_amt', 'nrcvb_buy_qty', 'max_buy_amt', 'max_buy_qty', 'cma_evlu_amt', 'ovrs_re_use_amt_wcrc', 'ord_psbl_frcr_amt_wcrc']
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_domstk.py:629:    url = '/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_domstk.py:660:    url = '/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_psamount/chk_inquire_psamount.py:27:    'ord_psbl_frcr_amt': '주문가능외화금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_ovrseastk.py:353:    url = '/uapi/overseas-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_ovrseastk.py:354:    tr_id = "TTTS3012R"   # 모의투자 VTTS3012R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_ovrseastk.py:398:    url = '/uapi/overseas-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_ovrseastk.py:399:    tr_id = "TTTS3012R"   # 모의투자 VTTS3012R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_ovrseastk.py:575:    url = '/uapi/overseas-stock/v1/trading/inquire-present-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/legacy/Sample01/kis_ovrseastk.py:576:    tr_id = "CTRP6504R"   # 모의투자 VTRP6504R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/foreign_margin/chk_foreign_margin.py:26:    'frcr_dncl_amt1': '외화예수금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py:45:    'tot_evlu_pfls_amt': '총평가손익금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py:47:    'frcr_buy_amt_smtl1': '외화매수금액합계1',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py:49:    'frcr_buy_amt_smtl2': '외화매수금액합계2'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:25:API_URL = "/uapi/overseas-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:98:        tr_id = "VTTS3012R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/inquire_balance_valuation_pl.py:23:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/chk_inquire_balance_valuation_pl.py:39:    'frcr_dncl_amt': '외화예수금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_futureoption/inquire_ngt_balance/chk_inquire_ngt_balance.py:41:    'frcr_dncl_amt': '외화예수금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_futureoption/inquire_ngt_balance/chk_inquire_ngt_balance.py:72:    'evlu_amt_smtl': '평가금액합계'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/strategy_builder/core/data_fetcher.py:69:        "/uapi/domestic-stock/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/strategy_builder/core/data_fetcher.py:445:            "eval_amount": int(summary.get("evlu_amt_smtl_amt", 0)),
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/inquire_account_balance/chk_inquire_account_balance.py:32:    'evlu_amt_smtl': '평가금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/inquire_account_balance/chk_inquire_account_balance.py:41:    'frcr_evlu_tota': '외화평가총액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_futureoption/inquire_balance/chk_inquire_balance.py:38:    'frcr_dncl_amt': '외화예수금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_futureoption/inquire_balance/chk_inquire_balance.py:67:    'evlu_amt_smtl': '평가금액합계'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_futureoption/inquire_balance/inquire_balance.py:23:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:54:    'frcr_buy_amt_smtl': '외화매수금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:56:    'frcr_dncl_amt_2': '외화예수금액2',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:66:    'evlu_amt_smtl': '평가금액합계',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:73:    'frcr_evlu_tota': '외화평가총액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:76:    'evlu_amt_smtl_amt': '평가금액합계금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:77:    'tot_evlu_pfls_amt': '총평가손익금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:93:    'unit_amt', 'loan_rmnd', 'frcr_buy_amt_smtl', 'frcr_sll_amt_smtl', 'frcr_dncl_amt_2',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:95:    'nxdy_frcr_drwg_psbl_amt', 'pchs_amt_smtl', 'evlu_amt_smtl', 'evlu_pfls_amt_smtl', 'dncl_amt',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:96:    'cma_evlu_amt', 'tot_dncl_amt', 'etc_mgna', 'wdrw_psbl_tot_amt', 'frcr_evlu_tota',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:97:    'evlu_erng_rt1', 'pchs_amt_smtl_amt', 'evlu_amt_smtl_amt', 'tot_evlu_pfls_amt', 'tot_asst_amt',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/inquire_balance_settlement_pl.py:23:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:26:API_URL = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:108:        tr_id = "VTRP6504R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/pension_inquire_present_balance/chk_pension_inquire_present_balance.py:36:    'evlu_amt_smtl_amt': '평가금액합계금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/domestic_stock/domestic_stock_functions.py:3730:    api_url = "/uapi/domestic-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/domestic_stock/domestic_stock_functions.py:3882:    api_url = "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/domestic_stock/domestic_stock_functions.py:11370:    api_url = "/uapi/domestic-stock/v1/trading/pension/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/domestic_stock/domestic_stock_functions.py:11638:    api_url = "/uapi/domestic-stock/v1/trading/pension/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/pension_inquire_present_balance/pension_inquire_present_balance.py:22:API_URL = "/uapi/domestic-stock/v1/trading/pension/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/overseas_stock/overseas_stock_functions.py:638:        tr_id = "VTTS3012R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/overseas_stock/overseas_stock_functions.py:642:    api_url = "/uapi/overseas-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/overseas_stock/overseas_stock_functions.py:1679:        tr_id = "VTRP6504R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/overseas_stock/overseas_stock_functions.py:1683:    api_url = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/domestic_bond/domestic_bond_functions.py:430:    api_url = "/uapi/domestic-bond/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/domestic_futureoption/domestic_futureoption_functions.py:468:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/domestic_futureoption/domestic_futureoption_functions.py:576:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_user/domestic_futureoption/domestic_futureoption_functions.py:688:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/inquire_psbl_order/chk_inquire_psbl_order.py:34:    'ord_psbl_frcr_amt_wcrc': '주문가능외화금액원화'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/inquire_balance_rlz_pl/inquire_balance_rlz_pl.py:24:API_URL = "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/inquire_balance_rlz_pl/chk_inquire_balance_rlz_pl.py:63:    'evlu_amt_smtl_amt': '평가금액합계금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/backtester/kis_backtest/providers/kis/brokerage.py:201:        API: /uapi/domestic-stock/v1/trading/inquire-balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/backtester/kis_backtest/providers/kis/constants.py:75:    DOMESTIC_BALANCE = "/uapi/domestic-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/inquire_balance/chk_inquire_balance.py:66:    'evlu_amt_smtl_amt': '평가금액합계금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/inquire_credit_psamount/chk_inquire_credit_psamount.py:33:    'ord_psbl_frcr_amt_wcrc': '주문가능외화금액원화'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/inquire_balance/inquire_balance.py:24:API_URL = "/uapi/domestic-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.TmCm26LNjK/repo/examples_llm/domestic_stock/pension_inquire_balance/pension_inquire_balance.py:24:API_URL = "/uapi/domestic-stock/v1/trading/pension/inquire-balance"

exec
/bin/zsh -lc 'base=$(find /var/folders -path '"'*open-trading-api' -type d 2>/dev/null | head -1); sed -n '1,140p' \""'$base/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py"; sed -n '"'1,130p' \""'$base/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py"; sed -n '"'1,55p' \""'$base/examples_llm/overseas_stock/inquire_psamount/chk_inquire_psamount.py"; sed -n '"'1,45p' \""'$base/examples_llm/overseas_stock/foreign_margin/chk_foreign_margin.py"' in /Users/manager/side/makemoney
 succeeded in 113ms:
"""
Created on 2025-06-30

"""

import sys
import logging

import pandas as pd

sys.path.extend(['../..', '.'])  # kis_auth 파일 경로 추가
import kis_auth as ka
from inquire_balance import inquire_balance

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 잔고 [v1_해외주식-006]
##############################################################################################

COLUMN_MAPPING = {
    'cano': '종합계좌번호',
    'acnt_prdt_cd': '계좌상품코드',
    'prdt_type_cd': '상품유형코드',
    'ovrs_pdno': '해외상품번호',
    'frcr_evlu_pfls_amt': '외화평가손익금액',
    'evlu_pfls_rt': '평가손익율',
    'pchs_avg_pric': '매입평균가격',
    'ovrs_cblc_qty': '해외잔고수량',
    'ord_psbl_qty': '주문가능수량',
    'frcr_pchs_amt1': '외화매입금액1',
    'ovrs_stck_evlu_amt': '해외주식평가금액',
    'now_pric2': '현재가격2',
    'tr_crcy_cd': '거래통화코드',
    'ovrs_excg_cd': '해외거래소코드',
    'loan_type_cd': '대출유형코드',
    'loan_dt': '대출일자',
    'expd_dt': '만기일자',
    'frcr_pchs_amt1': '외화매입금액1',
    'ovrs_rlzt_pfls_amt': '해외실현손익금액',
    'ovrs_tot_pfls': '해외총손익',
    'rlzt_erng_rt': '실현수익율',
    'tot_evlu_pfls_amt': '총평가손익금액',
    'tot_pftrt': '총수익률',
    'frcr_buy_amt_smtl1': '외화매수금액합계1',
    'ovrs_rlzt_pfls_amt2': '해외실현손익금액2',
    'frcr_buy_amt_smtl2': '외화매수금액합계2'
}

# 숫자형 컬럼 정의
NUMERIC_COLUMNS = []

def main():
    """
    [해외주식] 주문/계좌
    해외주식 잔고[해외주식-006]

    해외주식 잔고 테스트 함수
    
    Parameters:
        - cano (str): 종합계좌번호 ()
        - acnt_prdt_cd (str): 계좌상품코드 ()
        - ovrs_excg_cd (str): 해외거래소코드 ()
        - tr_crcy_cd (str): 거래통화코드 ()
        - FK200 (str): 연속조회검색조건200 ()
        - NK200 (str): 연속조회키200 ()

    Returns:
        - DataFrame: 해외주식 잔고 결과
    
    Example:
        >>> df = inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_excg_cd="NASD", tr_crcy_cd="USD")
    """
    try:
        # pandas 출력 옵션 설정
        pd.set_option('display.max_columns', None)  # 모든 컬럼 표시
        pd.set_option('display.width', None)  # 출력 너비 제한 해제
        pd.set_option('display.max_rows', None)  # 모든 행 표시

        # 토큰 발급
        logger.info("토큰 발급 중...")
        ka.auth()
        logger.info("토큰 발급 완료")
        trenv = ka.getTREnv()

        # API 호출
        logger.info("API 호출")
        result1, result2 = inquire_balance(
            cano=trenv.my_acct,  # 종합계좌번호
            acnt_prdt_cd=trenv.my_prod,  # 계좌상품코드
            ovrs_excg_cd="NASD",  # 해외거래소코드
            tr_crcy_cd="USD",  # 거래통화코드
            FK200="",  # 연속조회검색조건200
            NK200="",  # 연속조회키200
        )
        
        # output1 결과 처리
        logging.info("=== output1 결과 ===")
        logging.info("사용 가능한 컬럼: %s", result1.columns.tolist())
        
        # 한글 컬럼명으로 변환
        result1 = result1.rename(columns=COLUMN_MAPPING)
        
        # 숫자형 컬럼 소수점 둘째자리까지 표시
        for col in NUMERIC_COLUMNS:
            if col in result1.columns:
                result1[col] = pd.to_numeric(result1[col], errors='coerce').round(2)
        
        logging.info("결과:")
        print(result1)
        
        # output3 결과 처리
        logging.info("=== output2 결과 ===")
        logging.info("사용 가능한 컬럼: %s", result2.columns.tolist())
        
        # 한글 컬럼명으로 변환
        result2 = result2.rename(columns=COLUMN_MAPPING)
        
        # 숫자형 컬럼 소수점 둘째자리까지 표시
        for col in NUMERIC_COLUMNS:
            if col in result2.columns:
                result2[col] = pd.to_numeric(result2[col], errors='coerce').round(2)
        
        logging.info("결과(output2):")
        print(result2)
        
    except Exception as e:
        logger.error("에러 발생: %s", str(e))
        raise

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
Created on 2025-06-30

"""

import sys
import logging

import pandas as pd

sys.path.extend(['../..', '.'])  # kis_auth 파일 경로 추가
import kis_auth as ka
from inquire_present_balance import inquire_present_balance

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 체결기준현재잔고 [v1_해외주식-008]
##############################################################################################

# 컬럼명 매핑 (한글 변환용)
COLUMN_MAPPING = {
    'cblc_qty13': '잔고수량13',
    'thdt_buy_ccld_qty1': '당일매수체결수량1',
    'thdt_sll_ccld_qty1': '당일매도체결수량1',
    'ccld_qty_smtl1': '체결수량합계1',
    'ord_psbl_qty1': '주문가능수량1',
    'frcr_pchs_amt': '외화매입금액',
    'frcr_evlu_amt2': '외화평가금액2',
    'evlu_pfls_amt2': '평가손익금액2',
    'evlu_pfls_rt1': '평가손익율1',
    'pdno': '상품번호',
    'bass_exrt': '기준환율',
    'buy_crcy_cd': '매수통화코드',
    'ovrs_now_pric1': '해외현재가격1',
    'avg_unpr3': '평균단가3',
    'tr_mket_name': '거래시장명',
    'natn_kor_name': '국가한글명',
    'pchs_rmnd_wcrc_amt': '매입잔액원화금액',
    'thdt_buy_ccld_frcr_amt': '당일매수체결외화금액',
    'thdt_sll_ccld_frcr_amt': '당일매도체결외화금액',
    'unit_amt': '단위금액',
    'std_pdno': '표준상품번호',
    'prdt_type_cd': '상품유형코드',
    'loan_rmnd': '대출잔액',
    'loan_dt': '대출일자',
    'loan_expd_dt': '대출만기일자',
    'ovrs_excg_cd': '해외거래소코드',
    'item_lnkg_excg_cd': '종목연동거래소코드',
    'crcy_cd': '통화코드',
    'frcr_buy_amt_smtl': '외화매수금액합계',
    'frcr_sll_amt_smtl': '외화매도금액합계',
    'frcr_dncl_amt_2': '외화예수금액2',
    'frst_bltn_exrt': '최초고시환율',
    'frcr_buy_mgn_amt': '외화매수증거금액',
    'frcr_etc_mgna': '외화기타증거금',
    'frcr_drwg_psbl_amt_1': '외화출금가능금액1',
    'frcr_evlu_amt2': '출금가능원화금액',
    'acpl_cstd_crcy_yn': '현지보관통화여부',
    'nxdy_frcr_drwg_psbl_amt': '익일외화출금가능금액',
    'output3': '응답상세3',
    'pchs_amt_smtl': '매입금액합계',
    'evlu_amt_smtl': '평가금액합계',
    'evlu_pfls_amt_smtl': '평가손익금액합계',
    'dncl_amt': '예수금액',
    'cma_evlu_amt': 'CMA평가금액',
    'tot_dncl_amt': '총예수금액',
    'etc_mgna': '기타증거금',
    'wdrw_psbl_tot_amt': '인출가능총금액',
    'frcr_evlu_tota': '외화평가총액',
    'evlu_erng_rt1': '평가수익율1',
    'pchs_amt_smtl_amt': '매입금액합계금액',
    'evlu_amt_smtl_amt': '평가금액합계금액',
    'tot_evlu_pfls_amt': '총평가손익금액',
    'tot_asst_amt': '총자산금액',
    'buy_mgn_amt': '매수증거금액',
    'mgna_tota': '증거금총액',
    'frcr_use_psbl_amt': '외화사용가능금액',
    'ustl_sll_amt_smtl': '미결제매도금액합계',
    'ustl_buy_amt_smtl': '미결제매수금액합계',
    'tot_frcr_cblc_smtl': '총외화잔고합계',
    'tot_loan_amt': '총대출금액'
}

# 숫자형 컬럼 정의 (소수점 처리용)
NUMERIC_COLUMNS = [
    'cblc_qty13', 'thdt_buy_ccld_qty1', 'thdt_sll_ccld_qty1', 'ccld_qty_smtl1', 'ord_psbl_qty1',
    'frcr_pchs_amt', 'frcr_evlu_amt2', 'evlu_pfls_amt2', 'evlu_pfls_rt1', 'bass_exrt',
    'ovrs_now_pric1', 'avg_unpr3', 'pchs_rmnd_wcrc_amt', 'thdt_buy_ccld_frcr_amt', 'thdt_sll_ccld_frcr_amt',
    'unit_amt', 'loan_rmnd', 'frcr_buy_amt_smtl', 'frcr_sll_amt_smtl', 'frcr_dncl_amt_2',
    'frst_bltn_exrt', 'frcr_buy_mgn_amt', 'frcr_etc_mgna', 'frcr_drwg_psbl_amt_1', 'frcr_evlu_amt2',
    'nxdy_frcr_drwg_psbl_amt', 'pchs_amt_smtl', 'evlu_amt_smtl', 'evlu_pfls_amt_smtl', 'dncl_amt',
    'cma_evlu_amt', 'tot_dncl_amt', 'etc_mgna', 'wdrw_psbl_tot_amt', 'frcr_evlu_tota',
    'evlu_erng_rt1', 'pchs_amt_smtl_amt', 'evlu_amt_smtl_amt', 'tot_evlu_pfls_amt', 'tot_asst_amt',
    'buy_mgn_amt', 'mgna_tota', 'frcr_use_psbl_amt', 'ustl_sll_amt_smtl', 'ustl_buy_amt_smtl',
    'tot_frcr_cblc_smtl', 'tot_loan_amt'
]

def main():
    """
    [해외주식] 주문/계좌
    해외주식 체결기준현재잔고[v1_해외주식-008]

    해외주식 체결기준현재잔고 테스트 함수
    
    Parameters:
        - cano (str): 종합계좌번호 (계좌번호 체계(8-2)의 앞 8자리)
        - acnt_prdt_cd (str): 계좌상품코드 (계좌번호 체계(8-2)의 뒤 2자리)
        - wcrc_frcr_dvsn_cd (str): 원화외화구분코드 (01 : 원화  02 : 외화)
        - natn_cd (str): 국가코드 (000 전체 840 미국 344 홍콩 156 중국 392 일본 704 베트남)
        - tr_mket_cd (str): 거래시장코드 ([Request body NATN_CD 000 설정] 00 : 전체  [Request body NATN_CD 840 설정] 00 : 전체 01 : 나스닥(NASD) 02 : 뉴욕거래소(NYSE) 03 : 미국(PINK SHEETS) 04 : 미국(OTCBB) 05 : 아멕스(AMEX)  [Request body NATN_CD 156 설정] 00 : 전체 01 : 상해B 02 : 심천B 03 : 상해A 04 : 심천A  [Request body NATN_CD 392 설정] 01 : 일본  [Request body NATN_CD 704 설정] 01 : 하노이거래 02 : 호치민거래소  [Request body NATN_CD 344 설정] 01 : 홍콩 02 : 홍콩CNY 03 : 홍콩USD)
        - inqr_dvsn_cd (str): 조회구분코드 (00 : 전체  01 : 일반해외주식  02 : 미니스탁)
        - env_dv (str): 실전모의구분 (real:실전, demo:모의)

    Returns:
        - DataFrame: 해외주식 체결기준현재잔고 결과
    
    Example:
        >>> df1, df2, df3 = inquire_present_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, wcrc_frcr_dvsn_cd="02", natn_cd="000", tr_mket_cd="00", inqr_dvsn_cd="00", env_dv="real")  # 실전투자
    """
    try:
        # pandas 출력 옵션 설정
        pd.set_option('display.max_columns', None)  # 모든 컬럼 표시
        pd.set_option('display.width', None)  # 출력 너비 제한 해제
        pd.set_option('display.max_rows', None)  # 모든 행 표시

        # 실전/모의투자 선택 (모의투자 지원 로직)
# -*- coding: utf-8 -*-
"""
Created on 2025-06-30

"""

import sys
import logging

import pandas as pd

sys.path.extend(['../..', '.'])  # kis_auth 파일 경로 추가
import kis_auth as ka
from inquire_psamount import inquire_psamount

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 매수가능금액조회 [v1_해외주식-014]
##############################################################################################

# 컬럼명 매핑 (한글 변환용)
COLUMN_MAPPING = {
    'tr_crcy_cd': '거래통화코드',
    'ord_psbl_frcr_amt': '주문가능외화금액',
    'sll_ruse_psbl_amt': '매도재사용가능금액',
    'ovrs_ord_psbl_amt': '해외주문가능금액',
    'max_ord_psbl_qty': '최대주문가능수량',
    'echm_af_ord_psbl_amt': '환전이후주문가능금액',
    'echm_af_ord_psbl_qty': '환전이후주문가능수량',
    'ord_psbl_qty': '주문가능수량',
    'exrt': '환율',
    'frcr_ord_psbl_amt1': '외화주문가능금액1',
    'ovrs_max_ord_psbl_qty': '해외최대주문가능수량'
}

# 숫자형 컬럼 정의 (소수점 처리용)
NUMERIC_COLUMNS = []

def main():
    """
    [해외주식] 주문/계좌
    해외주식 매수가능금액조회[v1_해외주식-014]

    해외주식 매수가능금액조회 테스트 함수
    
    Parameters:
        - cano (str): 종합계좌번호 (계좌번호 체계(8-2)의 앞 8자리)
        - acnt_prdt_cd (str): 계좌상품코드 (계좌번호 체계(8-2)의 뒤 2자리)
        - ovrs_excg_cd (str): 해외거래소코드 (NASD : 나스닥 / NYSE : 뉴욕 / AMEX : 아멕스 SEHK : 홍콩 / SHAA : 중국상해 / SZAA : 중국심천 TKSE : 일본 / HASE : 하노이거래소 / VNSE : 호치민거래소)
        - ovrs_ord_unpr (str): 해외주문단가 (해외주문단가 (23.8) 정수부분 23자리, 소수부분 8자리)
        - item_cd (str): 종목코드 (종목코드)
        - env_dv (str): 실전모의구분 (real:실전, demo:모의)
"""
Created on 2025-06-26

"""

import sys
import logging

import pandas as pd

sys.path.extend(['../..', '.'])  # kis_auth 파일 경로 추가
import kis_auth as ka
from foreign_margin import foreign_margin

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 - 해외증거금 통화별조회 [해외주식-035]
##############################################################################################

# 컬럼명 매핑 (한글 변환용)
COLUMN_MAPPING = {
    'natn_name': '국가명',
    'frcr_dncl_amt1': '외화예수금액',
    'ustl_buy_amt': '미결제매수금액',
    'ustl_sll_amt': '미결제매도금액',
    'frcr_rcvb_amt': '외화미수금액',
    'frcr_mgn_amt': '외화증거금액',
    'frcr_gnrl_ord_psbl_amt': '외화일반주문가능금액',
    'frcr_ord_psbl_amt1': '외화주문가능금액',
    'itgr_ord_psbl_amt': '통합주문가능금액',
    'bass_exrt': '기준환율'
}

# 숫자형 컬럼 정의 (소수점 처리용)
NUMERIC_COLUMNS = [
    '외화예수금액', '미결제매수금액', '미결제매도금액', '외화미수금액', '외화증거금액',
    '외화일반주문가능금액', '외화주문가능금액', '통합주문가능금액', '기준환율'
]

def main():
    """
    [해외주식] 주문/계좌

exec
/bin/zsh -lc 'base=$(find /var/folders -path '"'*open-trading-api' -type d 2>/dev/null | head -1); sed -n '1,190p' \""'$base/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py"; sed -n '"'1,140p' \""'$base/examples_llm/overseas_stock/inquire_balance/inquire_balance.py"' in /Users/manager/side/makemoney
 succeeded in 0ms:
# -*- coding: utf-8 -*-
"""
Created on 2025-06-30

"""

import logging
import time
from typing import Optional, Tuple
import sys

import pandas as pd

sys.path.extend(['../..', '.'])
import kis_auth as ka

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 체결기준현재잔고 [v1_해외주식-008]
##############################################################################################

# 상수 정의
API_URL = "/uapi/overseas-stock/v1/trading/inquire-present-balance"

def inquire_present_balance(
    cano: str,  # 종합계좌번호
    acnt_prdt_cd: str,  # 계좌상품코드
    wcrc_frcr_dvsn_cd: str,  # 원화외화구분코드
    natn_cd: str,  # 국가코드
    tr_mket_cd: str,  # 거래시장코드
    inqr_dvsn_cd: str,  # 조회구분코드
    env_dv: str = "real",  # 실전모의구분
    dataframe1: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output1)
    dataframe2: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output2)
    dataframe3: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output3)
    tr_cont: str = "",
    depth: int = 0,
    max_depth: int = 10
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    [해외주식] 주문/계좌 
    해외주식 체결기준현재잔고[v1_해외주식-008]
    해외주식 체결기준현재잔고 API를 호출하여 DataFrame으로 반환합니다.
    
    Args:
        cano (str): 계좌번호 체계(8-2)의 앞 8자리
        acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
        wcrc_frcr_dvsn_cd (str): 01 : 원화  02 : 외화
        natn_cd (str): 000 전체 840 미국 344 홍콩 156 중국 392 일본 704 베트남
        tr_mket_cd (str): [Request body NATN_CD 000 설정] 00 : 전체  [Request body NATN_CD 840 설정] 00 : 전체 01 : 나스닥(NASD) 02 : 뉴욕거래소(NYSE) 03 : 미국(PINK SHEETS) 04 : 미국(OTCBB) 05 : 아멕스(AMEX)  [Request body NATN_CD 156 설정] 00 : 전체 01 : 상해B 02 : 심천B 03 : 상해A 04 : 심천A  [Request body NATN_CD 392 설정] 01 : 일본  [Request body NATN_CD 704 설정] 01 : 하노이거래 02 : 호치민거래소  [Request body NATN_CD 344 설정] 01 : 홍콩 02 : 홍콩CNY 03 : 홍콩USD
        inqr_dvsn_cd (str): 00 : 전체  01 : 일반해외주식  02 : 미니스탁
        env_dv (str): 실전모의구분 (real:실전, demo:모의)
        dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
        dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)
        dataframe3 (Optional[pd.DataFrame]): 누적 데이터프레임 (output3)
        tr_cont (str): 연속 거래 여부
        depth (int): 현재 재귀 깊이
        max_depth (int): 최대 재귀 깊이 (기본값: 10)
        
    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: 해외주식 체결기준현재잔고 데이터
        
    Example:
        >>> df1, df2, df3 = inquire_present_balance(
        ...     cano=trenv.my_acct,
        ...     acnt_prdt_cd=trenv.my_prod,
        ...     wcrc_frcr_dvsn_cd="01",
        ...     natn_cd="000",
        ...     tr_mket_cd="00",
        ...     inqr_dvsn_cd="00"
        ... )
        >>> print(df1)
        >>> print(df2)
        >>> print(df3)
    """
    # [필수 파라미터 검증]
    if not cano:
        logger.error("cano is required. (e.g. '810XXXXX')")
        raise ValueError("cano is required. (e.g. '810XXXXX')")
    if not acnt_prdt_cd:
        logger.error("acnt_prdt_cd is required. (e.g. '01')")
        raise ValueError("acnt_prdt_cd is required. (e.g. '01')")
    if not wcrc_frcr_dvsn_cd:
        logger.error("wcrc_frcr_dvsn_cd is required. (e.g. '01')")
        raise ValueError("wcrc_frcr_dvsn_cd is required. (e.g. '01')")
    if not natn_cd:
        logger.error("natn_cd is required. (e.g. '000')")
        raise ValueError("natn_cd is required. (e.g. '000')")
    if not tr_mket_cd:
        logger.error("tr_mket_cd is required. (e.g. '00')")
        raise ValueError("tr_mket_cd is required. (e.g. '00')")
    if not inqr_dvsn_cd:
        logger.error("inqr_dvsn_cd is required. (e.g. '00')")
        raise ValueError("inqr_dvsn_cd is required. (e.g. '00')")

    # 최대 재귀 깊이 체크
    if depth >= max_depth:
        logger.warning("Maximum recursion depth (%d) reached. Stopping further requests.", max_depth)
        return dataframe1 if dataframe1 is not None else pd.DataFrame(), dataframe2 if dataframe2 is not None else pd.DataFrame(), dataframe3 if dataframe3 is not None else pd.DataFrame()
    
    # TR ID 설정 (모의투자 지원 로직)
    if env_dv == "real":
        tr_id = "CTRP6504R"  # 실전투자용 TR ID
    elif env_dv == "demo":
        tr_id = "VTRP6504R"  # 모의투자용 TR ID
    else:
        raise ValueError("env_dv can only be 'real' or 'demo'")

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "WCRC_FRCR_DVSN_CD": wcrc_frcr_dvsn_cd,
        "NATN_CD": natn_cd,
        "TR_MKET_CD": tr_mket_cd,
        "INQR_DVSN_CD": inqr_dvsn_cd,
    }

    res = ka._url_fetch(api_url=API_URL, ptr_id=tr_id, tr_cont=tr_cont, params=params)

    if res.isOK():
        # output1 처리
        if hasattr(res.getBody(), 'output1'):
            output_data = res.getBody().output1
            if output_data:
                if isinstance(output_data, list):
                    current_data1 = pd.DataFrame(output_data)
                else:
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
                if isinstance(output_data, list):
                    current_data2 = pd.DataFrame(output_data)
                else:
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
        
        # output3 처리
        if hasattr(res.getBody(), 'output3'):
            output_data = res.getBody().output3
            if output_data:
                if isinstance(output_data, list):
                    current_data3 = pd.DataFrame(output_data)
                else:
                    current_data3 = pd.DataFrame([output_data])
                
                if dataframe3 is not None:
                    dataframe3 = pd.concat([dataframe3, current_data3], ignore_index=True)
                else:
                    dataframe3 = current_data3
            else:
                if dataframe3 is None:
                    dataframe3 = pd.DataFrame()
        else:
            if dataframe3 is None:
                dataframe3 = pd.DataFrame()
        
        tr_cont = res.getHeader().tr_cont
        
        if tr_cont in ["M", "F"]:
            logger.info("Calling next page...")
            ka.smart_sleep()
            return inquire_present_balance(
                cano=cano,
"""
Created on 2025-06-30

"""

import logging
import time
from typing import Optional, Tuple
import sys

import pandas as pd

sys.path.extend(['../..', '.'])
import kis_auth as ka

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 잔고 [v1_해외주식-006]
##############################################################################################

# 상수 정의
API_URL = "/uapi/overseas-stock/v1/trading/inquire-balance"

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

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": ovrs_excg_cd,
        "TR_CRCY_CD": tr_crcy_cd,
        "CTX_AREA_FK200": FK200,
        "CTX_AREA_NK200": NK200,
    }

    res = ka._url_fetch(api_url=API_URL, ptr_id=tr_id, tr_cont=tr_cont, params=params)

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

exec
/bin/zsh -lc 'base=$(find /var/folders -path '"'*open-trading-api' -type d 2>/dev/null | head -1); python - <<'PY'
import json, glob, os
base=glob.glob('/var/folders/**/open-trading-api', recursive=True)[0]
path=os.path.join(base,'MCP/Kis Trading MCP/configs/overseas_stock.json')
data=json.load(open(path))
for item in data:
    if item.get('api_path') in ['/uapi/overseas-stock/v1/trading/inquire-present-balance','/uapi/overseas-stock/v1/trading/inquire-balance']:
        print('TITLE', item.get('title') or item.get('api_name'), item.keys())
        print(json.dumps(item, ensure_ascii=False, indent=2)[:12000])
PY" in /Users/manager/side/makemoney
 exited 127 in 0ms:
zsh:1: command not found: python

exec
/bin/zsh -lc 'base=$(find /var/folders -path '"'*open-trading-api' -type d 2>/dev/null | head -1); python3 - <<'PY'
import json, glob, os
base=glob.glob('/var/folders/**/open-trading-api', recursive=True)[0]
path=os.path.join(base,'MCP/Kis Trading MCP/configs/overseas_stock.json')
data=json.load(open(path))
for item in data:
    if item.get('api_path') in ['/uapi/overseas-stock/v1/trading/inquire-present-balance','/uapi/overseas-stock/v1/trading/inquire-balance']:
        print('TITLE', item.get('title') or item.get('api_name'), item.keys())
        print(json.dumps(item, ensure_ascii=False, indent=2)[:18000])
PY" in /Users/manager/side/makemoney
 exited 1 in 434ms:
Traceback (most recent call last):
  File "<stdin>", line 6, in <module>
AttributeError: 'str' object has no attribute 'get'

exec
/bin/zsh -lc 'base=$(find /var/folders -path '"'*open-trading-api' -type d 2>/dev/null | head -1); python3 - <<'PY'
import json, glob, os
base=glob.glob('/var/folders/**/open-trading-api', recursive=True)[0]
path=os.path.join(base,'MCP/Kis Trading MCP/configs/overseas_stock.json')
data=json.load(open(path))
print(type(data), data.keys() if isinstance(data,dict) else '')
items=[]
if isinstance(data,dict):
    for k,v in data.items():
        if isinstance(v,list): items+=v
        elif isinstance(v,dict): items.append(v)
else: items=data
for item in items:
    if isinstance(item,dict) and item.get('api_path') in ['/uapi/overseas-stock/v1/trading/inquire-present-balance','/uapi/overseas-stock/v1/trading/inquire-balance']:
        print('TITLE', item.get('title') or item.get('api_name'), item.keys())
        print(json.dumps(item, ensure_ascii=False, indent=2)[:20000])
PY" in /Users/manager/side/makemoney
 succeeded in 231ms:
<class 'dict'> dict_keys(['tool_info', 'apis'])

exec
/bin/zsh -lc 'base=$(find /var/folders -path '"'*open-trading-api' -type d 2>/dev/null | head -1); python3 - <<'PY'
import json, glob, os
base=glob.glob('/var/folders/**/open-trading-api', recursive=True)[0]
path=os.path.join(base,'MCP/Kis Trading MCP/configs/overseas_stock.json')
data=json.load(open(path))
apis=data['apis']
print(type(apis), len(apis))
if isinstance(apis,dict): iterable=apis.values()
else: iterable=apis
for item in iterable:
    if isinstance(item,dict) and item.get('api_path') in ['/uapi/overseas-stock/v1/trading/inquire-present-balance','/uapi/overseas-stock/v1/trading/inquire-balance']:
        print('TITLE', item.get('title') or item.get('api_name'), item.keys())
        print(json.dumps(item, ensure_ascii=False, indent=2)[:22000])
PY" in /Users/manager/side/makemoney
 succeeded in 223ms:
<class 'dict'> 34
TITLE None dict_keys(['category', 'name', 'github_url', 'method', 'api_path', 'params'])
{
  "category": "[해외주식] 주문/계좌",
  "name": "해외주식 체결기준현재잔고",
  "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance",
  "method": "inquire_present_balance",
  "api_path": "/uapi/overseas-stock/v1/trading/inquire-present-balance",
  "params": {
    "cano": {
      "name": "cano",
      "type": "str",
      "required": false,
      "default_value": null,
      "description": "계좌번호 (시스템 자동 설정, 제공 불필요)"
    },
    "acnt_prdt_cd": {
      "name": "acnt_prdt_cd",
      "type": "str",
      "required": false,
      "default_value": null,
      "description": "계좌상품코드 (시스템 자동 설정, 제공 불필요)"
    },
    "wcrc_frcr_dvsn_cd": {
      "name": "wcrc_frcr_dvsn_cd",
      "type": "str",
      "required": true,
      "default_value": null,
      "description": "01 : 원화  02 : 외화"
    },
    "natn_cd": {
      "name": "natn_cd",
      "type": "str",
      "required": true,
      "default_value": null,
      "description": "000 전체 840 미국 344 홍콩 156 중국 392 일본 704 베트남"
    },
    "tr_mket_cd": {
      "name": "tr_mket_cd",
      "type": "str",
      "required": true,
      "default_value": null,
      "description": "[Request body NATN_CD 000 설정] 00 : 전체  [Request body NATN_CD 840 설정] 00 : 전체 01 : 나스닥(NASD) 02 : 뉴욕거래소(NYSE) 03 : 미국(PINK SHEETS) 04 : 미국(OTCBB) 05 : 아멕스(AMEX)  [Request body NATN_CD 156 설정] 00 : 전체 01 : 상해B 02 : 심천B 03 : 상해A 04 : 심천A  [Request body NATN_CD 392 설정] 01 : 일본  [Request body NATN_CD 704 설정] 01 : 하노이거래 02 : 호치민거래소  [Request body NATN_CD 344 설정] 01 : 홍콩 02 : 홍콩CNY 03 : 홍콩USD"
    },
    "inqr_dvsn_cd": {
      "name": "inqr_dvsn_cd",
      "type": "str",
      "required": true,
      "default_value": null,
      "description": "00 : 전체  01 : 일반해외주식  02 : 미니스탁"
    },
    "env_dv": {
      "name": "env_dv",
      "type": "str",
      "required": true,
      "default_value": "real",
      "description": "실전모의구분 (real:실전, demo:모의)"
    },
    "dataframe1": {
      "name": "dataframe1",
      "type": "pd.DataFrame",
      "required": false,
      "default_value": null,
      "description": "누적 데이터프레임 (output1)"
    },
    "dataframe2": {
      "name": "dataframe2",
      "type": "pd.DataFrame",
      "required": false,
      "default_value": null,
      "description": "누적 데이터프레임 (output2)"
    },
    "dataframe3": {
      "name": "dataframe3",
      "type": "pd.DataFrame",
      "required": false,
      "default_value": null,
      "description": "누적 데이터프레임 (output3)"
    },
    "tr_cont": {
      "name": "tr_cont",
      "type": "str",
      "required": true,
      "default_value": "",
      "description": "연속 거래 여부"
    },
    "depth": {
      "name": "depth",
      "type": "int",
      "required": true,
      "default_value": 0,
      "description": "현재 재귀 깊이"
    },
    "max_depth": {
      "name": "max_depth",
      "type": "int",
      "required": true,
      "default_value": 10,
      "description": "최대 재귀 깊이 (기본값: 10)"
    }
  }
}
TITLE None dict_keys(['category', 'name', 'github_url', 'method', 'api_path', 'params'])
{
  "category": "[해외주식] 주문/계좌",
  "name": "해외주식 잔고",
  "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_balance",
  "method": "inquire_balance",
  "api_path": "/uapi/overseas-stock/v1/trading/inquire-balance",
  "params": {
    "cano": {
      "name": "cano",
      "type": "str",
      "required": false,
      "default_value": null,
      "description": "계좌번호 (시스템 자동 설정, 제공 불필요)"
    },
    "acnt_prdt_cd": {
      "name": "acnt_prdt_cd",
      "type": "str",
      "required": false,
      "default_value": null,
      "description": "계좌상품코드 (시스템 자동 설정, 제공 불필요)"
    },
    "ovrs_excg_cd": {
      "name": "ovrs_excg_cd",
      "type": "str",
      "required": true,
      "default_value": null,
      "description": "[모의] NASD : 나스닥 NYSE : 뉴욕  AMEX : 아멕스  [실전] NASD : 미국전체 NAS : 나스닥 NYSE : 뉴욕  AMEX : 아멕스  [모의/실전 공통] SEHK : 홍콩 SHAA : 중국상해 SZAA : 중국심천 TKSE : 일본 HASE : 베트남 하노이 VNSE : 베트남 호치민"
    },
    "tr_crcy_cd": {
      "name": "tr_crcy_cd",
      "type": "str",
      "required": true,
      "default_value": null,
      "description": "USD : 미국달러 HKD : 홍콩달러 CNY : 중국위안화 JPY : 일본엔화 VND : 베트남동"
    },
    "env_dv": {
      "name": "env_dv",
      "type": "str",
      "required": true,
      "default_value": "real"
    },
    "dataframe1": {
      "name": "dataframe1",
      "type": "pd.DataFrame",
      "required": false,
      "default_value": null
    },
    "dataframe2": {
      "name": "dataframe2",
      "type": "pd.DataFrame",
      "required": false,
      "default_value": null
    },
    "tr_cont": {
      "name": "tr_cont",
      "type": "str",
      "required": true,
      "default_value": ""
    },
    "depth": {
      "name": "depth",
      "type": "int",
      "required": true,
      "default_value": 0
    },
    "max_depth": {
      "name": "max_depth",
      "type": "int",
      "required": true,
      "default_value": 10
    }
  }
}

codex
The official repo has the response column mappings. Important distinction: `frcr_dncl_amt1` is not from `VTTS3012R`; it belongs to the foreign-margin currency endpoint. For `VTTS3012R`, the balance summary fields are narrower.
exec
/bin/zsh -lc 'base=$(find /var/folders -path '"'*open-trading-api' -type d 2>/dev/null | head -1); nl -ba \""'$base/MCP/KIS Code Assistant MCP/data.csv" | sed -n '"'10700,10810p'; nl -ba \""'$base/MCP/KIS Code Assistant MCP/data.csv" | sed -n '"'10885,10905p'; nl -ba \""'$base/MCP/KIS Code Assistant MCP/data.csv" | sed -n '"'11338,11350p'" in /Users/manager/side/makemoney
 succeeded in 0ms:
 10700	    'loan_dt': '대출일자',
 10701	    'expd_dt': '만기일자',
 10702	    'frcr_pchs_amt1': '외화매입금액1',
 10703	    'ovrs_rlzt_pfls_amt': '해외실현손익금액',
 10704	    'ovrs_tot_pfls': '해외총손익',
 10705	    'rlzt_erng_rt': '실현수익율',
 10706	    'tot_evlu_pfls_amt': '총평가손익금액',
 10707	    'tot_pftrt': '총수익률',
 10708	    'frcr_buy_amt_smtl1': '외화매수금액합계1',
 10709	    'ovrs_rlzt_pfls_amt2': '해외실현손익금액2',
 10710	    'frcr_buy_amt_smtl2': '외화매수금액합계2'
 10711	}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py
 10712	overseas_stock,주문/계좌,해외주식 체결기준현재잔고,inquire_present_balance,[해외주식] 주문/계좌 해외주식 체결기준현재잔고[v1_해외주식-008] 해외주식 체결기준현재잔고 API를 호출하여 DataFrame으로 반환합니다.,"cano (str): 계좌번호 체계(8-2)의 앞 8자리
 10713	acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
 10714	wcrc_frcr_dvsn_cd (str): 01 : 원화  02 : 외화
 10715	natn_cd (str): 000 전체 840 미국 344 홍콩 156 중국 392 일본 704 베트남
 10716	tr_mket_cd (str): [Request body NATN_CD 000 설정] 00 : 전체  [Request body NATN_CD 840 설정] 00 : 전체 01 : 나스닥(NASD) 02 : 뉴욕거래소(NYSE) 03 : 미국(PINK SHEETS) 04 : 미국(OTCBB) 05 : 아멕스(AMEX)  [Request body NATN_CD 156 설정] 00 : 전체 01 : 상해B 02 : 심천B 03 : 상해A 04 : 심천A  [Request body NATN_CD 392 설정] 01 : 일본  [Request body NATN_CD 704 설정] 01 : 하노이거래 02 : 호치민거래소  [Request body NATN_CD 344 설정] 01 : 홍콩 02 : 홍콩CNY 03 : 홍콩USD
 10717	inqr_dvsn_cd (str): 00 : 전체  01 : 일반해외주식  02 : 미니스탁
 10718	env_dv (str): 실전모의구분 (real:실전, demo:모의)
 10719	dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
 10720	dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)
 10721	dataframe3 (Optional[pd.DataFrame]): 누적 데이터프레임 (output3)
 10722	tr_cont (str): 연속 거래 여부
 10723	depth (int): 현재 재귀 깊이
 10724	max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: 해외주식 체결기준현재잔고 데이터","     df1, df2, df3 = inquire_present_balance(
 10725	    ...     cano=trenv.my_acct,
 10726	    ...     acnt_prdt_cd=trenv.my_prod,
 10727	    ...     wcrc_frcr_dvsn_cd=""01"",
 10728	    ...     natn_cd=""000"",
 10729	    ...     tr_mket_cd=""00"",
 10730	    ...     inqr_dvsn_cd=""00""
 10731	    ... )
 10732	     print(df1)
 10733	     print(df2)
 10734	     print(df3)","{
 10735	    'cblc_qty13': '잔고수량13',
 10736	    'thdt_buy_ccld_qty1': '당일매수체결수량1',
 10737	    'thdt_sll_ccld_qty1': '당일매도체결수량1',
 10738	    'ccld_qty_smtl1': '체결수량합계1',
 10739	    'ord_psbl_qty1': '주문가능수량1',
 10740	    'frcr_pchs_amt': '외화매입금액',
 10741	    'frcr_evlu_amt2': '외화평가금액2',
 10742	    'evlu_pfls_amt2': '평가손익금액2',
 10743	    'evlu_pfls_rt1': '평가손익율1',
 10744	    'pdno': '상품번호',
 10745	    'bass_exrt': '기준환율',
 10746	    'buy_crcy_cd': '매수통화코드',
 10747	    'ovrs_now_pric1': '해외현재가격1',
 10748	    'avg_unpr3': '평균단가3',
 10749	    'tr_mket_name': '거래시장명',
 10750	    'natn_kor_name': '국가한글명',
 10751	    'pchs_rmnd_wcrc_amt': '매입잔액원화금액',
 10752	    'thdt_buy_ccld_frcr_amt': '당일매수체결외화금액',
 10753	    'thdt_sll_ccld_frcr_amt': '당일매도체결외화금액',
 10754	    'unit_amt': '단위금액',
 10755	    'std_pdno': '표준상품번호',
 10756	    'prdt_type_cd': '상품유형코드',
 10757	    'loan_rmnd': '대출잔액',
 10758	    'loan_dt': '대출일자',
 10759	    'loan_expd_dt': '대출만기일자',
 10760	    'ovrs_excg_cd': '해외거래소코드',
 10761	    'item_lnkg_excg_cd': '종목연동거래소코드',
 10762	    'crcy_cd': '통화코드',
 10763	    'frcr_buy_amt_smtl': '외화매수금액합계',
 10764	    'frcr_sll_amt_smtl': '외화매도금액합계',
 10765	    'frcr_dncl_amt_2': '외화예수금액2',
 10766	    'frst_bltn_exrt': '최초고시환율',
 10767	    'frcr_buy_mgn_amt': '외화매수증거금액',
 10768	    'frcr_etc_mgna': '외화기타증거금',
 10769	    'frcr_drwg_psbl_amt_1': '외화출금가능금액1',
 10770	    'frcr_evlu_amt2': '출금가능원화금액',
 10771	    'acpl_cstd_crcy_yn': '현지보관통화여부',
 10772	    'nxdy_frcr_drwg_psbl_amt': '익일외화출금가능금액',
 10773	    'output3': '응답상세3',
 10774	    'pchs_amt_smtl': '매입금액합계',
 10775	    'evlu_amt_smtl': '평가금액합계',
 10776	    'evlu_pfls_amt_smtl': '평가손익금액합계',
 10777	    'dncl_amt': '예수금액',
 10778	    'cma_evlu_amt': 'CMA평가금액',
 10779	    'tot_dncl_amt': '총예수금액',
 10780	    'etc_mgna': '기타증거금',
 10781	    'wdrw_psbl_tot_amt': '인출가능총금액',
 10782	    'frcr_evlu_tota': '외화평가총액',
 10783	    'evlu_erng_rt1': '평가수익율1',
 10784	    'pchs_amt_smtl_amt': '매입금액합계금액',
 10785	    'evlu_amt_smtl_amt': '평가금액합계금액',
 10786	    'tot_evlu_pfls_amt': '총평가손익금액',
 10787	    'tot_asst_amt': '총자산금액',
 10788	    'buy_mgn_amt': '매수증거금액',
 10789	    'mgna_tota': '증거금총액',
 10790	    'frcr_use_psbl_amt': '외화사용가능금액',
 10791	    'ustl_sll_amt_smtl': '미결제매도금액합계',
 10792	    'ustl_buy_amt_smtl': '미결제매수금액합계',
 10793	    'tot_frcr_cblc_smtl': '총외화잔고합계',
 10794	    'tot_loan_amt': '총대출금액'
 10795	}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py
 10796	overseas_stock,주문/계좌,해외주식 지정가체결내역조회,inquire_algo_ccnl,"해외주식 TWAP, VWAP 주문에 대한 체결내역 조회 API로 지정가 주문번호조회 API를 수행 후 조회해야합니다","cano (str): [필수] 계좌번호
 10797	acnt_prdt_cd (str): [필수] 계좌상품코드 (ex. 01)
 10798	ord_dt (str): 주문일자
 10799	ord_gno_brno (str): 주문채번지점번호
 10800	odno (str): 주문번호 (ex. 지정가주문번호 TTTC6058R에서 조회된 주문번호 입력)
 10801	ttlz_icld_yn (str): 집계포함여부
 10802	NK200 (str): 연속조회키200
 10803	FK200 (str): 연속조회조건200
 10804	tr_cont (str): 연속거래여부
 10805	dataframe (Optional[pd.DataFrame]): 누적 데이터프레임
 10806	dataframe3 (Optional[pd.DataFrame]): 누적 데이터프레임3
 10807	depth (int): 내부 재귀깊이 (자동관리)
 10808	max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: (output, output3) 체결내역 데이터","     result, result3 = inquire_algo_ccnl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod)
 10809	     print(result)
 10810	     print(result3)","{
 10885	tr_cont (str): 연속 거래 여부
 10886	dataframe (Optional[pd.DataFrame]): 누적 데이터프레임
 10887	depth (int): 현재 재귀 깊이
 10888	max_depth (int): 최대 재귀 깊이 (기본값: 10)",Optional[pd.DataFrame]: 해외주식 매수가능금액조회 데이터,"     df = inquire_psamount(
 10889	    ...     cano=trenv.my_acct,
 10890	    ...     acnt_prdt_cd=trenv.my_prod,
 10891	    ...     ovrs_excg_cd=""NASD"",
 10892	    ...     ovrs_ord_unpr=""1.4"",
 10893	    ...     item_cd=""QQQ""
 10894	    ... )
 10895	     print(df)","{
 10896	    'tr_crcy_cd': '거래통화코드',
 10897	    'ord_psbl_frcr_amt': '주문가능외화금액',
 10898	    'sll_ruse_psbl_amt': '매도재사용가능금액',
 10899	    'ovrs_ord_psbl_amt': '해외주문가능금액',
 10900	    'max_ord_psbl_qty': '최대주문가능수량',
 10901	    'echm_af_ord_psbl_amt': '환전이후주문가능금액',
 10902	    'echm_af_ord_psbl_qty': '환전이후주문가능수량',
 10903	    'ord_psbl_qty': '주문가능수량',
 10904	    'exrt': '환율',
 10905	    'frcr_ord_psbl_amt1': '외화주문가능금액1',
 11338	tr_cont (str): 연속 거래 여부 (기본값: """")
 11339	dataframe (Optional[pd.DataFrame]): 누적 데이터프레임
 11340	depth (int): 현재 재귀 깊이
 11341	max_depth (int): 최대 재귀 깊이 (기본값: 10)",Optional[pd.DataFrame]: 해외증거금 통화별조회 데이터,"     df = foreign_margin(""12345678"", ""01"")
 11342	     print(df)","{
 11343	    'natn_name': '국가명',
 11344	    'frcr_dncl_amt1': '외화예수금액',
 11345	    'ustl_buy_amt': '미결제매수금액',
 11346	    'ustl_sll_amt': '미결제매도금액',
 11347	    'frcr_rcvb_amt': '외화미수금액',
 11348	    'frcr_mgn_amt': '외화증거금액',
 11349	    'frcr_gnrl_ord_psbl_amt': '외화일반주문가능금액',
 11350	    'frcr_ord_psbl_amt1': '외화주문가능금액',

codex
I have enough to answer: `VTTS3012R` is fine for positions and P/L summary, but not the clean cash source you want. `VTRP6504R` exposes the per-currency cash block plus aggregate KRW valuation fields, so I’ll recommend anchoring snapshots on it.
codex
**Short Answer**

1. `VTTS3012R / inquire-balance`
   - Positions: `output1`
   - Summary/P&L: `output2`
   - Useful `output2` fields:
     - `tot_evlu_pfls_amt`: total valuation P/L
     - `tot_pftrt`: total return %
     - `frcr_buy_amt_smtl1`: foreign buy amount sum 1
     - `frcr_buy_amt_smtl2`: foreign buy amount sum 2
   - Not clean USD cash. `frcr_dncl_amt1` is **not** `VTTS3012R`; it appears under `foreign-margin` (`TTTC2101R`) as foreign deposit amount.
   - `ord_psbl_frcr_amt` is **not** `VTTS3012R`; it is from `inquire-psamount` (`VTTS3007R`) and means orderable foreign currency amount.

2. `VTRP6504R / inquire-present-balance`
   - Yes, cleaner for snapshot.
   - `output1`: overseas positions, includes:
     - `pdno`
     - `cblc_qty13`
     - `ovrs_now_pric1`
     - `frcr_evlu_amt2`
     - `bass_exrt`
     - `crcy_cd`
   - `output2`: per-currency cash/FX block, includes:
     - `crcy_cd`
     - `frcr_dncl_amt_2`: foreign cash/deposit amount
     - `frcr_drwg_psbl_amt_1`: withdrawable foreign cash
     - `nxdy_frcr_drwg_psbl_amt`
     - `frst_bltn_exrt`
   - `output3`: aggregate KRW/account totals, includes:
     - `dncl_amt`: deposit amount
     - `tot_dncl_amt`: total deposit amount
     - `evlu_amt_smtl`: valuation amount sum
     - `frcr_evlu_tota`: foreign valuation total
     - `evlu_amt_smtl_amt`: valuation amount sum amount
     - `tot_evlu_pfls_amt`: total valuation P/L
     - `tot_asst_amt`: total asset amount

3. Recommendation: use `VTRP6504R` as the snapshot source of truth for overseas/FX-aware account equity. Keep `VTTC8434R` only if you need domestic stock detail not represented there.

For KRW-base snapshot fields:

- KRW cash: `output3[0].tot_dncl_amt` or `output3[0].dncl_amt`
  - I’d use `tot_dncl_amt` for total cash/deposit; fall back to `dncl_amt`.
- USD cash: `output2` row where `crcy_cd == "USD"`:
  - use `frcr_dncl_amt_2`
  - conservative available-cash variant: `frcr_drwg_psbl_amt_1`
  - convert with `bass_exrt` from matching `output1`/USD row or `frst_bltn_exrt` from `output2`.
- Total KRW equity:
  - use `output3[0].tot_asst_amt` if present.
  - fallback: `output3[0].evlu_amt_smtl_amt`.
  - `tot_evlu_pfls_amt` is P/L, not equity.

Unsure/needs live confirmation: whether `tot_dncl_amt` includes KRW-only cash or all deposits converted to KRW in your paper account. Field name suggests total deposit amount, but KIS naming is inconsistent; validate once against a known cash balance.
tokens used
184,309

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
