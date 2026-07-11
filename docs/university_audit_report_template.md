# University Audit Report

## Metadata

- University:
- Campaign:
- Role: `primary_pilot` / `secondary_pilot` / `monitor_only` / `deferred`
- Audit date:
- Reviewer:
- Grade: `A` / `B` / `C` / `reject`

## Evidence Register

| Claim | Value | Confidence | Official URL | Archive URL | Observed at | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |

## Source And Access

- Official admissions URL:
- Competition-list URL:
- Format: `html` / `xlsx` / `pdf` / `js` / other
- Public without authentication:
- Cookies, credentials or personal-account access required:
- Browser required:
- Stable URL:
- Campaign/version embedded in URL or payload:
- Raw snapshot feasible:
- Terms/robots/access risks:

## Groups Audited

| Group label | Official URL | Archive URL | Funding/category | Snapshot time | Rows aggregate | Hash |
|---|---|---|---|---|---:|---|
| | | | | | | |

Do not put UIDs, names, URLs containing applicant identifiers, or row payloads
in this report.

## Field Inventory

| Field label | Normalized field | Present | Semantics confidence | Evidence | Notes |
|---|---|---:|---|---|---|
| UID | applicant_uid_hmac | | | | |
| Consent | consent | | | | |
| Priority | enrollment_priority | | | | |
| Places | seats | | | | |
| Scores | score fields | | | | |
| Status | application_status | | | | |

## Identity Namespace

- Exact namespace:
- Namespace scope:
- Namespace confidence:
- Normalization rule:
- HMAC rule:
- Within-university repeatability aggregate:
- Cross-university repeatability aggregate:
- Cross-year validation:
- Prohibited assumptions:

Use this form only:

```text
HMAC-SHA256(secret, f"{identity_namespace}:{normalized_uid}")
```

## Priority Semantics

- Source label:
- `priority_kind`:
- `priority_confidence`:
- Official rule evidence:
- Can it be used as global priority: no unless explicitly verified
- Unknowns:

## Consent And Occupancy

- Source consent label:
- Consent scope: group / university / campaign / unknown
- Consent confidence:
- Final-order evidence:
- Occupancy probability interpretation:
- Absolute occupancy classes allowed: no

Every forecast state must become an occupancy probability interval for the
specific competition group. No state implies probability 0 or 1.

## Seats And Effective Capacity

- Gross capacity:
- Quota capacities:
- BVI treatment:
- Effective ordinary-competition capacity:
- Transfer/reallocation evidence:
- Capacity confidence:
- Forecast restriction:

## Updates And Snapshots

- Observed update timestamps:
- Claimed update frequency:
- Snapshot hash method:
- Immutable raw storage location:
- Parser version:
- Snapshot validation status:
- Empty/corrupt response protection:

## Coverage And Forecast Confidence

- Groups observed:
- Expected groups:
- Alternative applications visible:
- `coverage_score` low:
- `coverage_score` high:
- Coverage basis:
- Coverage limitations:
- `forecast_confidence` ceiling:

Coverage is not the probability of admission. Forecast confidence describes
the completeness and reliability of the evidence.

## Final Decision

- Grade:
- MVP role:
- Forecast enabled:
- Cross-university matching enabled:
- Conditions for promotion:
- Re-audit trigger:

## Raw Storage And Privacy Review

- Raw retention: 120 days
- Storage: restricted local volume/MinIO, S3-compatible interface
- Raw UID retained outside primary DB: no
- Raw fixture committed to Git: no
- UID in logs/API/public tests: no
- Deletion/retention hold:

## Open Questions

1.
2.
3.
