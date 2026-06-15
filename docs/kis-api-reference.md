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
