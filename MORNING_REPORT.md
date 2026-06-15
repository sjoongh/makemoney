# 🌙 야간 자율 작업 보고서 (Claude + Codex)

**시작:** 2026-06-15 23:50 KST · 사용자 취침 중 · 아침 보고용
**원칙:** 모든 변경 TDD + 전체 테스트 통과 + 백테스트=실거래 패리티 불변식 유지. 증분마다 commit+push. 무감독 실주문 금지(KRX 개장 시 1주 bounded 검증만 허용).

## 셋업 완료
- `caffeinate -ims -t 36000` — 맥 잠들지 않게(야간작업/cron 동작용, ~10h)
- cron 설치(dry-run only): KRX 16:00 KST / US 06:00 KST / 주간 reconcile 토 07:00 KST → 페이퍼-포워드 로그 자동 축적
- ⚠️ 맥이 잠들면 cron·야간작업 모두 멈춤. caffeinate로 방지했으나 뚜껑 닫으면 clamshell sleep 가능.

## 야간 백로그 (안전·코드 중심, codex 교차검증)
- [ ] B1. account_snapshot 해외 USD 현금 → KRW 환산 반영 (라이브 테스트서 USD매수 후 cash_krw 미반영 발견)
- [ ] B2. 국내 체결조회 VTTC0081R 구현 (현재 TODO 스텁)
- [ ] B3. KOSPI 주문 라이브 검증 — KRX 개장(~09:00 KST) 시 1주 라운드트립 (NASDAQ과 동일 bounded)
- [ ] B4. KOSPI 거래세율/FX 스프레드 비용모델 정밀화 (APPROX 플래그 해소)
- [ ] B5. AvgHold 등 평가지표 정의 정직성 점검·보강
- [ ] B6. 추가 테스트·엣지케이스 하드닝

## 작업 로그
| 시각(KST) | 항목 | 결과 | 커밋 |
|---|---|---|---|
| 23:50 | 셋업 | caffeinate+cron+보고서 | 921e966 |
| 23:58 | B1 조사 | ⚠️ **보류(사람 판단 필요)** — VTRP6504R 라이브 probe서 `tot_asst_amt=383M` vs 국내현금 100M 불일치, output2 USD현금/포지션 0. KIS 페이퍼 외화총액 의미 불명. 돈처리 코드 무감독 변경 위험 → account_snapshot 현행 유지, 아침에 KIS 문서/고객센터로 확인 권장 | — |

| 00:03 | B2 ✅ | 국내 체결조회 VTTC0081R 구현+병합, 라이브 rt_cd=0, 9테스트, 전체 green | 838789a |

| 01:20 | B5 ✅ | AvgHold/노출 정의 단일·정직화(단일·sleeve 경로 일치), 테스트 추가, 패리티 green | 5aac68e |

| 02:30 | B4 ✅ | 비용모델 정밀화 — KOSPI STT 20bps 2026확정, NASDAQ 자동환전 10bps(APPROX) 반영, KOSDAQ 주석화. 패리티 green | aca98e1 |

### ⚠️ 사람 확인 필요 (B1 상세)
VTRP6504R `output3`: `tot_asst_amt=382,983,974`, `frcr_evlu_tota=382,983,974` (포지션 0·외화현금 0인데 383M). `output2`는 5개 통화(CNY/HKD/USD/JPY/EUR) 행, 전부 `frcr_dncl_amt_2=0`. 국내 VTTC8434R는 100M KRW. **이 383M의 정체를 확인하기 전엔 account_snapshot을 VTRP6504R 기반으로 바꾸지 않음.** 현재는 국내 KRW현금만 사용(보수적·안전).
