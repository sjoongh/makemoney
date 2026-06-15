# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-06-15T17:14:15.352Z

## Original task

Precise 2026 KOSPI cost rates for a trading cost model. My current default: KOSPI commission ~1.405 bps both sides + SELL securities transaction tax (STT) 20.0 bps (0.20%). I flagged STT as APPROX because Korea has been PHASING DOWN the transaction tax.

Tersely and precisely:
1. What is the ACTUAL 2026 KOSPI total sell-side tax (증권거래세 + 농어촌특별세)? The KR STT has been cut in stages: 2023 0.20%, 2024 0.18%, 2025 0.15%, 2026 ? — give the 2026 KOSPI figure split into 거래세 portion + 농특세 0.15%. (KOSPI 농특세 0.15% applies; the 거래세 portion on KOSPI was scheduled toward 0%.) State the best-known 2026 number and flag if uncertain.
2. KOSDAQ differs (no 농특세, different rate) — give 2026 KOSDAQ for completeness.
3. For KRW-funded auto-FX overseas (our model auto-converts KRW→USD per fill), a realistic FX spread per conversion in bps for a retail KIS account — give a defensible default and range, flag as estimate.
Just the numbers + a one-line recommendation on what to set as the configurable defaults (keep APPROX flags). Senior, terse, cite if known. If you cannot be certain of the exact 2026 figure, say so and give the most recent confirmed rate.

## Final prompt

Precise 2026 KOSPI cost rates for a trading cost model. My current default: KOSPI commission ~1.405 bps both sides + SELL securities transaction tax (STT) 20.0 bps (0.20%). I flagged STT as APPROX because Korea has been PHASING DOWN the transaction tax.

Tersely and precisely:
1. What is the ACTUAL 2026 KOSPI total sell-side tax (증권거래세 + 농어촌특별세)? The KR STT has been cut in stages: 2023 0.20%, 2024 0.18%, 2025 0.15%, 2026 ? — give the 2026 KOSPI figure split into 거래세 portion + 농특세 0.15%. (KOSPI 농특세 0.15% applies; the 거래세 portion on KOSPI was scheduled toward 0%.) State the best-known 2026 number and flag if uncertain.
2. KOSDAQ differs (no 농특세, different rate) — give 2026 KOSDAQ for completeness.
3. For KRW-funded auto-FX overseas (our model auto-converts KRW→USD per fill), a realistic FX spread per conversion in bps for a retail KIS account — give a defensible default and range, flag as estimate.
Just the numbers + a one-line recommendation on what to set as the configurable defaults (keep APPROX flags). Senior, terse, cite if known. If you cannot be certain of the exact 2026 figure, say so and give the most recent confirmed rate.

## Raw output

```text
1. **2026 KOSPI sell-side tax:** **20.0 bps total = 증권거래세 5.0 bps + 농어촌특별세 15.0 bps**. Confirmed for transfers on/after **2026-01-01**. Source: Korean gov “달라지는 정책” says KOSPI **0% → 0.05%**, 농특세 **0.15% 유지**. [MOFE](https://whatsnew.mofe.go.kr/mec/ots/dif/view.do?comBaseCd=DIFTYPCD&difField1=DIFFIELD05&difSer=17abfef1-f815-4dee-bd34-90020f1df5ce&temp=2026&temp2=HALF001)

2. **2026 KOSDAQ sell-side tax:** **20.0 bps total = 증권거래세 20.0 bps + 농특세 0.0 bps**. Same source: KOSDAQ/K-OTC **0.15% → 0.20%**, no 농특세.

3. **KRW→USD auto-FX spread, retail KIS:** **estimate: default 10 bps per conversion**, defensible range **5-40 bps** depending on account/event/FX 우대. KIS official FX guide says USD reservation buy/sell gap around **2-3 KRW**, real-time securities FX gap **2-20 KRW** by firm, so account-specific. [KIS](https://m.koreainvestment.com/main/bond/foreign/_static/TF03de000020.jsp)

**Config recommendation:** keep commission **1.40527 bps each side**, set **KOSPI sell tax = 20.0 bps APPROX? no, confirmed**, **KOSDAQ sell tax = 20.0 bps confirmed**, and **auto-FX = 10 bps per conversion APPROX** with configurable range/override.


OpenAI Codex v0.139.0
--------
workdir: /Users/manager/side/makemoney
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019ecc46-4c74-7be0-8ac1-5a397a4d2d10
--------
user
Precise 2026 KOSPI cost rates for a trading cost model. My current default: KOSPI commission ~1.405 bps both sides + SELL securities transaction tax (STT) 20.0 bps (0.20%). I flagged STT as APPROX because Korea has been PHASING DOWN the transaction tax.

Tersely and precisely:
1. What is the ACTUAL 2026 KOSPI total sell-side tax (증권거래세 + 농어촌특별세)? The KR STT has been cut in stages: 2023 0.20%, 2024 0.18%, 2025 0.15%, 2026 ? — give the 2026 KOSPI figure split into 거래세 portion + 농특세 0.15%. (KOSPI 농특세 0.15% applies; the 거래세 portion on KOSPI was scheduled toward 0%.) State the best-known 2026 number and flag if uncertain.
2. KOSDAQ differs (no 농특세, different rate) — give 2026 KOSDAQ for completeness.
3. For KRW-funded auto-FX overseas (our model auto-converts KRW→USD per fill), a realistic FX spread per conversion in bps for a retail KIS account — give a defensible default and range, flag as estimate.
Just the numbers + a one-line recommendation on what to set as the configurable defaults (keep APPROX flags). Senior, terse, cite if known. If you cannot be certain of the exact 2026 figure, say so and give the most recent confirmed rate.
codex
I’ll verify this against current Korean exchange/tax sources because the 2026 rate is exactly the kind of staged policy detail that can drift.
web search: 
web search: 2026 KOSPI securities transaction tax agricultural special tax 0.15 2026
web search: 
web search: Korea Investment Securities overseas stock FX spread USD retail 환전 우대 스프레드 bps
web search: 
web search: site:moef.go.kr 2026 증권거래세율 코스피 0.05 코스닥 0.20 농어촌특별세
codex
1. **2026 KOSPI sell-side tax:** **20.0 bps total = 증권거래세 5.0 bps + 농어촌특별세 15.0 bps**. Confirmed for transfers on/after **2026-01-01**. Source: Korean gov “달라지는 정책” says KOSPI **0% → 0.05%**, 농특세 **0.15% 유지**. [MOFE](https://whatsnew.mofe.go.kr/mec/ots/dif/view.do?comBaseCd=DIFTYPCD&difField1=DIFFIELD05&difSer=17abfef1-f815-4dee-bd34-90020f1df5ce&temp=2026&temp2=HALF001)

2. **2026 KOSDAQ sell-side tax:** **20.0 bps total = 증권거래세 20.0 bps + 농특세 0.0 bps**. Same source: KOSDAQ/K-OTC **0.15% → 0.20%**, no 농특세.

3. **KRW→USD auto-FX spread, retail KIS:** **estimate: default 10 bps per conversion**, defensible range **5-40 bps** depending on account/event/FX 우대. KIS official FX guide says USD reservation buy/sell gap around **2-3 KRW**, real-time securities FX gap **2-20 KRW** by firm, so account-specific. [KIS](https://m.koreainvestment.com/main/bond/foreign/_static/TF03de000020.jsp)

**Config recommendation:** keep commission **1.40527 bps each side**, set **KOSPI sell tax = 20.0 bps APPROX? no, confirmed**, **KOSDAQ sell tax = 20.0 bps confirmed**, and **auto-FX = 10 bps per conversion APPROX** with configurable range/override.
tokens used
19,851

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
