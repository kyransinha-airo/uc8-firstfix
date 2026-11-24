# FirstFix mock data

Main scenario (BRD 14.1) on demo date 2026-12-01, site-local time (-06:00). The dispatch run
starts at 09:30 after both reports are in. Check everything with:

```
python data/mock-data/build_telemetry.py   # regenerates telemetry (deterministic)
python data/mock-data/validate.py          # recomputes all 42 answer-key figures
```

## Rules for everyone writing data

1. **Asset ID is the shared key.** Every file that refers to the unit uses `CU-2` (serial `CX450-20817`).
2. **Neutral names only.** No file name, field or heading may hint at an answer: no "decoy",
   "correct", "trap", "fan_cause". The agents read `01_reports/`, `02_documents/` and `03_structured/`; they must never see `05_answer_key/`.
3. **Answer key first.** Change `05_answer_key/` and the data together, then run the validator.
4. **Keep the mess.** Phase 1 has no clean option and phase 2's verdict rests on two dips. Don't tune it away.

## Layout

| Folder | Read by |
|---|---|
| `01_reports/` | A1 (raw reports per channel) |
| `02_documents/` | Agents via read tools (`.md`, a `--- page N ---` line at each page break) |
| `03_structured/` | Deterministic tools |
| `04_config/parameters.yaml` | Tools and agents (rule values) |
| `05_answer_key/` | Tests and `validate.py` only |

## What's here (Kyran, W-004 + W-006, done)

| File | What it holds |
|---|---|
| `03_structured/install_base.csv`, `sites.csv`, `locations.csv` | CU-2 at site S14, plus decoy assets |
| `03_structured/alarm_map.csv`, `fault_families.csv` | HP-01 → HIGH_SIDE_PRESSURE |
| `03_structured/fault_causes.csv` | CX-450 fault table: 4 causes, priors, procedure ids, likely parts |
| `03_structured/skill_matrix.csv` | Level and certificate per cause |
| `03_structured/technicians.csv`, `certificates.csv`, `bookings.csv` | T1–T4; T2's certificate expired 2026-11-28; T4 locked 10:30–12:30 at S09 |
| `03_structured/van_stock.csv`, `depot_stock.csv`, `parts.csv`, `supersession.csv` | V1 has no FM-220; D1 has none; D2 has one |
| `03_structured/travel_matrix.csv` | B1→S14 70, B1→D2 100, D2→S14 60, S09→S14 50 |
| `03_structured/service_history.csv`, `maintenance_intervals.csv` | Coil last cleaned 2025-09-30 (6-month interval) |
| `03_structured/bulletins.csv` | SB-07 (CX-450, FM-220) and an off-model SB-11 |
| `03_structured/agreement_register.csv` | Pointer table: SA-0412 docs with effective dates and assets mentioned |
| `03_structured/telemetry_series.csv`, `telemetry_readings_pre.csv`, `telemetry_readings_post.csv` | 1-min readings; two fan dips before, two after the visit |
| `01_reports/rpt_a7731.json` | 09:10 HP-01 alarm |
| `05_answer_key/answer_key.csv` | 42 expected figures with rule basis |
| `05_answer_key/agreement_facts.csv` | What each agreement document must say (contract for the documents) |
| `05_answer_key/expected_extractions.csv`, `expected_evidence.csv` | What A1 should extract, what A2 should find |

## Still to write (Prajwal, W-005 + intake schema)

Write documents as `.md` with a `--- page N ---` line at each page break, so citations can point to a page.


| File | Must contain |
|---|---|
| `01_reports/rpt_c2290.txt` | 09:25 call note from site S14: storage room warming, unit keeps tripping. Names the site and the unit in words a caller would use, not "CU-2" necessarily |
| Intake schema | The fault record every channel becomes: asset ref / serial, site, symptom text, reporter, received_at, fault family (closed list), cited spans |
| `02_documents/agreements/` | SA-0412 agreement, schedules A/B/C, amendments 1–3, saying exactly what `agreement_facts.csv` says. The agreement text should point to its schedules and amendments |
| `02_documents/manuals/` | CX-450 extract: HIGH_SIDE_PRESSURE fault table (C1–C4 matching `fault_causes.csv`), procedures PR-108/114/121/123 (gauge connection in 108 and 114), verification step: discharge pressure 200–325 psig and fan current 2.8–3.6 A held for 2 h under load |
| `02_documents/bulletins/` | BUL-07 (SB-07: early capacitor failures on FM-220, CX-450) and BUL-11 (RX-300, FM-310) |
| `02_documents/history/` | HIST-3109, HIST-4410, HIST-4876 notes matching `service_history.csv` |
| `01_reports/closeout_t1.txt` (phase 2) | 14:05 close-out: coil heavily fouled and cleaned, pressure back in range, fan running but noisy, motor not replaced because the site wanted the unit running; parts used: coil cleaner only; marked resolved |
