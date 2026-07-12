# Data Feasibility Audit

## Status

Fast Pilot Audit 0A.1 is complete for three universities. Full Audit 0A.2
for the remaining twelve universities is background work and does not block
the MVP.

Audit date: 2026-07-11
Campaign audited: 2025, completed campaign
Supplemental campaign: 2026 public structure only

No source UID was stored in this repository or included in this document.
UID comparisons were aggregate-only and performed with an ephemeral
HMAC-SHA256 key.

## MVP Decisions

| University | Role | Grade | Allowed MVP capabilities |
|---|---|---|---|
| ITMO | primary pilot source | B | snapshots, change detection, forecast v1, notifications, real fixture parser |
| HSE | secondary pilot source | B | snapshots and cross-university matching; forecast with conservative seat uncertainty |
| MIPT | monitor-only | C for 2025 backfill | no user forecasts until prospective 2026 audit |

No category A source was identified. The MVP is explicitly allowed to start
with two category B sources.

## Production Identity Policy

The accepted observed namespace for the 2025 pilot is:

```text
admissions_uid:observed_cross_university:2025
```

It is not federal, global, official, or a legal-person identity namespace.
It is an empirical namespace for the audited public sources and campaign.

The stored identifier is always:

```text
HMAC-SHA256(secret, f"{identity_namespace}:{normalized_uid}")
```

The raw UID is not stored in the primary database, logs, API responses,
fixtures committed to Git, or public test data.

For campaign 2026, a new namespace must be created and revalidated before
cross-university matching or cross-university forecasting is enabled.

## 2025 Aggregate UID Evidence

The exact selected competition-list sources produced these aggregate values:

| Source | Rows observed | Distinct identifiers |
|---|---:|---:|
| HSE KS_OM, 3 groups | 3,815 | 3,217 |
| ITMO, groups 2190/2198/2199 | 5,409 | 3,220 |
| MIPT, 3 budget groups | 1,710 | 1,387 |

Aggregate intersections:

| Pair or set | Intersection |
|---|---:|
| HSE and ITMO | 416 |
| HSE and MIPT | 324 |
| ITMO and MIPT | 78 |
| All three | 40 |

All observed values were seven ASCII decimal characters. This supports the
observed campaign namespace, but does not establish persistence across years,
universities not audited, or a one-to-one natural-person identity.

## ITMO Pilot Audit

### Sources

- Campaign news: https://news.itmo.ru/ru/education/official/news/14366/
- 2025 rules archive: https://web.archive.org/web/20250621185610id_/https://abit.itmo.ru/page/66
- 2025 discovery API archive: https://web.archive.org/web/20250730080044id_/https://abitlk.itmo.ru/api/v1/rating/directions?degree=bachelor
- Group 2190 archive: https://web.archive.org/web/20250801140454id_/https://abit.itmo.ru/rating/bachelor/budget/2190
- Group 2198 archive: https://web.archive.org/web/20250801140723id_/https://abit.itmo.ru/rating/bachelor/budget/2198
- Group 2199 archive: https://web.archive.org/web/20250801140330id_/https://abit.itmo.ru/rating/bachelor/budget/2199
- Orders archive: https://web.archive.org/web/20251016062008id_/https://abit.itmo.ru/orders/bachelor
- Current configuration: https://abitlk.itmo.ru/api/v1/configurations

### Findings

- Public unauthenticated SSR HTML with embedded `__NEXT_DATA__`.
- No browser is required for the archived group pages.
- The selected pages contain UID, consent, priority, scores, statuses and
  highest-priority indicators.
- The official rules define numeric priority semantics and state that lists
  are updated at least five times daily when changed.
- The displayed highest-passing-priority count matched displayed capacity for
  groups 2190, 2198 and 2199 in the audited snapshot.
- Consent applies across budget competition groups and is not a commitment to
  the inspected group alone.
- The 2025 live routes are now gone; the current discovery API serves 2026.
- The campaign-wide budget aggregate differed from the campaign news by five
  places, and group 2190 had a final-order count exceeding its displayed
  capacity. Effective seat semantics therefore remain conservative.

### Pilot grade and role

Grade: **B**.

ITMO is the primary pilot source. It may be used for snapshots, change
detection, forecast v1, notifications and the first real parser fixture.
Forecast explanations must distinguish consent, highest-passing-priority and
final-order evidence. The model must not treat any single flag as occupancy
probability 0 or 1.

### Selected fixture

The first real closed fixture is ITMO bachelor budget group 2199:

```text
Official URL:
https://abit.itmo.ru/rating/bachelor/budget/2199

Archive URL:
https://web.archive.org/web/20250801140330id_/https://abit.itmo.ru/rating/bachelor/budget/2199
```

It is a 2025 SSR HTML snapshot with structured `__NEXT_DATA__`, five
admission-condition sections, and a displayed capacity of 93. The raw file
must be stored only in restricted local/object storage during Stage 3. It is
not a Git fixture, public test asset, log payload, or API response.

## HSE Pilot Audit

### Sources

- Official announcement: https://ba.hse.ru/news/1071270782.html
- Archived final manifest: https://web.archive.org/web/20250810163633/https://ba.hse.ru/finlist
- Archived 2025 places: https://web.archive.org/web/20250809150451/https://ba.hse.ru/kolmest
- Mathematics XLSX: https://enrol.hse.ru/storage/public_report_2025/moscow/Bachelors/KS_OM_moscow_B_Math_O.xlsx
- Software Engineering XLSX: https://enrol.hse.ru/storage/public_report_2025/moscow/Bachelors/KS_OM_moscow_B_SE_O.xlsx
- Computer Security XLSX: https://enrol.hse.ru/storage/public_report_2025/moscow/Bachelors/KS_OM_moscow_B_KB_O.xlsx
- Enrollment information: https://ba.hse.ru/enrolled
- 2025 results: https://ba.hse.ru/result2025

### Findings

- Public unauthenticated OOXML XLSX files remain downloadable.
- The official 2025 discovery manifest is now 404 and requires archive
  provenance.
- The `KS_OM` family is the main budget competition list; `BD` is a separate
  registered-applicant report and must not be substituted.
- The selected workbooks have one worksheet (`TDSheet`), a stable header and
  fields for identifier, consent, scores, preferential rights and priorities.
- Gross KCP capacities are confirmed, but effective ordinary-competition
  capacity is dynamic because quota and BVI places are included in KCP.
- The source URLs are mutable and not content-versioned.

### Pilot grade and role

Grade: **B / controlled pilot-ready**.

HSE is the secondary source for controlled regular ingestion. Every applicant
request must resolve `competitiveGroupId`, `setOfCompetitiveGroupId`,
`placeType`, and `level` from a fresh discovery response in memory. Selection
values must not be persisted or reused as defaults; unresolved discovery falls
back to monitor-only. Registration and competition list modes remain explicit.
`placeCount` is the only accepted seat field. Quota-specific forecasting stays
disabled until a non-empty quota response is validated. Raw HSE response bodies
and source identifiers are never persisted; applicant identity is HMAC-only.

## MIPT Monitor Audit

### Sources

- 2025 discovery: https://pk.mipt.ru/bachelor/2025_list/
- 2025 places: https://pk.mipt.ru/bachelor/2025_places/
- 2025 rules: https://pk.mipt.ru/bachelor/2025_rules/
- 2025 Biotechnology archive: https://web.archive.org/web/20250812101908id_/https://priem.mipt.ru/applications_v2/YmFjaGVsb3IvQmlvdGVraG5vbG9naXlhX0J5dWR6ZXRfTmEgb2JzaGNoaWtoIG9zbm92YW5peWFraC5odG1s
- 2025 Mathematics archive: https://web.archive.org/web/20250812102025id_/https://priem.mipt.ru/applications_v2/YmFjaGVsb3IvRnVuZGFtZW50YWxuYXlhIG1hdGVtYXRpa2FfQnl1ZHpoZXRfTmEgb2JzaGNoaWtoIG9zbm92YW5peWFraC5odG1s
- 2025 Physics archive: https://web.archive.org/web/20250812102009id_/https://priem.mipt.ru/applications_v2/YmFjaGVsb3IvRml6aWthIHBlcnNwZWt0aXZueWtoIHRla2hub2xvZ2l5X0J5dWR6ZXRfTmEgb2JzaGNoaWtoIG9zbm92YW5peWFraC5odG1s

### Findings

MIPT has rich server-rendered public tables with UID, consent, priority,
scores and status, plus official places and orders. However, the same
unversioned URLs now return 2026 data. The completed 2025 rows are available
only through incomplete third-party archive captures.

Grade: **C / monitor-only**.

MIPT must not be used for user forecasts. A prospective 2026 audit may promote
it only after contemporaneous snapshots, namespace revalidation, seat joins,
and final-order reconciliation.

## 2026 Unconfirmed Assumptions

These are explicit open assumptions and are not production facts:

1. The 2026 UID namespace may differ from 2025 and must be independently
   validated.
2. Cross-university matching must remain disabled until the new namespace is
   validated.
3. ITMO and HSE 2026 group IDs and URLs may change or be campaign-bound.
4. A visible priority field may have different semantics by university and
   cannot be globally interpreted.
5. Consent may have university-wide or campaign-wide scope rather than
   group-specific scope.
6. Effective seats may differ from gross KCP after quotas, BVI and transfers.
7. A source update timestamp is not an atomic snapshot boundary.
8. Final-order identifiers may not be safely joinable until separately tested.
9. Current frontend APIs and build IDs may change without notice.
10. Coverage of alternative applications is incomplete unless all relevant
    groups and sources are observed.

## Raw Storage Policy

- Stage 3 starts with a restricted local volume or MinIO-compatible storage.
- The storage interface must remain S3-compatible for later migration.
- Raw snapshots are immutable and content-addressed by SHA-256.
- Raw retention is 120 days, except snapshots under audit hold or incident
  investigation.
- Normalized applications and change events are retained separately from raw.
- Raw files contain public but sensitive applicant data and must never be
  returned by API, logged, committed to Git, or included in public fixtures.

## 0A.2 Deferred Audit

The remaining twelve universities are deferred and may be audited in parallel
with Stages 1–3. They do not block MVP infrastructure or the ITMO fixture
parser. Their eventual onboarding requires the same namespace, source,
priority, consent, effective-seat and raw-retention checks.
