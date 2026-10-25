# Eduma BUILD-12 — quality, migration rehearsal and pilot readiness

**Date:** 25 October 2026 · **Status:** from the spec pack, fast mode. **Source:** 05 BUILD-12; 11 cutover sequence;
TST-021, TST-024, TST-025; 10 security and operations.

| ID | Decision |
|---|---|
| S12-01 | **Cross-tenant sweep:** every API route that takes a record id is called by another institution's admin and by one of its students, with one real id of every institution-owned record type, as GET and POST. Every call must be refused, and the victim's audit log must not grow. A positive control proves the same paths find the owner's records. The sweep is a release gate, `pytest -m adversarial`, because it takes minutes. |
| S12-02 | **Static accessibility check** (`npm run check:a11y`) using Angular's template parser: images need alt text, buttons and links need a name, form controls need a label. It checks itself on a known-bad template. The human keyboard and screen-reader review is part of the final browser pass and of UAT. |
| S12-03 | **Security:** `check --deploy` must be clean with production settings (the remaining silences are documented in settings). Logs redact document-verification tokens (TST-021). Risky patterns were reviewed: raw SQL, unsafe HTML, public endpoints. |
| S12-04 | **Workload:** `manage.py measure_workload` runs concurrent personas making their everyday reads and prints p50/p95 against the 800 ms planning target. Results are recorded in `docs/operations.md`. |
| S12-05 | **Cutover rehearsal:** `manage.py cutover_report` gives the pack's reconciliation numbers. A test imports the sample file, reconciles, retries, and checks that nothing moves. |
| S12-06 | **Limitations, provider dependencies and support ownership** are in `docs/limitations.md`. BUILD-13 is recorded as outside web completion. |
