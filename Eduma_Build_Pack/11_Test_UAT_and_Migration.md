# 11 — Testing, UAT and Migration

**Prepared:** 12 October 2026  
**Status:** Test specification only. No application, tests, migrations, device prototype or restore drill have been executed.  
**Requirement families:** All REQ families, especially REQ-TEN, REQ-ACL, REQ-FIN, REQ-EXM, REQ-COM, REQ-UX, REQ-MIG and REQ-OPS.  
**Related:** [scope](01_PRD_and_Release_Scope.md), [workflows](03_Workflows_and_Business_Rules.md), [permissions](02_Roles_Tenancy_and_Permissions.md), [security/operations](10_Security_Privacy_and_Operations.md), [delivery](12_Delivery_Backlog_and_Build_Readiness.md).

## 1. Verification strategy

L1, L2 and L3 describe proposed implementation order, not approval to remove modules. L1 must include representative usable workflows for schools, colleges, engineering colleges and universities; L2 expands the web operational modules; L3 covers mobile and advanced capabilities. Track acceptance at requirement and release level. Passing foundation tests cannot mean the whole ERP is complete.

Use deterministic unit tests for business calculations, database/integration tests for transactions and tenancy, contract tests for provider adapters, and end-to-end tests for critical user journeys. Add accessibility, visual, performance, recovery and human UAT evidence. Tests must exercise outcomes and invariants, not simply repeat implementation details. External sandbox results must identify provider, account mode and limitations; a fake adapter cannot prove a live integration.

Each evidence record contains test ID, requirement family, build/commit, environment/configuration, fixture version, performer, timestamp, expected/actual result, artifact link, status and defect reference. Status values are Not run, Pass, Fail, Blocked and Not applicable with rationale. Begin every entry as Not run. An accepted exception needs owner, risk, containment and review date; tenant leaks or silent financial corruption are release blockers.

## 2. Synthetic fixture set

All names and identities below are fictional. Generate deterministic UUIDs during implementation and maintain a fixture manifest; never use real children's data in shared demos. Reserved example email domains and provider sandbox accounts should be used without sending real notifications.

| Fixture | Institution and academic model | Required records and relationships |
|---|---|---|
| FIX-SCH | Aster School; annual grades, sections and report cards | Grade 8 A/B, two teachers, 12 learners, verified guardian with two children, a restricted guardian, new mid-year enrollment |
| FIX-COL | Meridian College; semester/credit programs | Two departments, elective capacity, prerequisite failure, adult student with revocable parent delegation, under-18 learner |
| FIX-ENG | Vector Engineering College; theory/lab and attempt history | Four-credit and three-credit courses, internal/external components, practical component failure, backlog and repeated course |
| FIX-UNI | Summit University; departments plus affiliated college | Two internal campuses; explicit academic grant from FIX-ENG; grant excludes college finance, HR and messages |

Include a second unrelated school tenant to test similar record names and local admission numbers. A teacher also acts as a guardian under separate context. One account belongs to two institutions with different permissions. Seed active, suspended, invited, expired and revoked memberships; valid/expired support grants; different time zones; long names; Unicode text; missing optional fields; files awaiting scan; and disabled features.

Keep small correctness fixtures separate from large generated load datasets. Reset provider state, storage, queue messages and event deduplication records between tests. Scenario assertions must not depend on test order.

## 3. Authoritative worked results

### 3.1 Fees and payments

For INR, use decimal money with explicit currency and no binary floating-point arithmetic. Fixture fee charge is ₹10,000. An approved concession of ₹1,000 makes net charge ₹9,000. A provider-confirmed successful payment of ₹6,000, allocated to the charge, leaves **₹3,000 outstanding**. A ₹1,000 refund of that payment, without reducing the charge, makes net allocated payment ₹5,000 and **₹4,000 outstanding**. A separate approved credit note reducing the charge would be a distinct transaction and a different expected balance.

Assert charge, concession, payment, allocation, refund and reversal histories separately. Repeated provider events must not create extra receipts. A success screen without trusted provider confirmation cannot mark payment `succeeded`. Bank settlement is independently reconciled and is not required to redefine a captured payment as a second collection. Pending/refunded/failed states and settlement reconciliation must match the approved state machine. Fee rates, concessions and rounding policies are versioned; changing a schedule must not rewrite issued charges.

### 3.2 Marks and credit calculations

For components whose maximums are already weighted 40 and 60, marks 32/40 and 45/60 total **77/100**. Do not multiply by 40%/60% again. If a different scheme stores raw percentages, specify the conversion separately. Passing overall does not override a scheme's mandatory component pass minimum: an external failure may still fail the course.

For grade points 8 on a 4-credit course and 7 on a 3-credit course, the weighted result is `(4×8 + 3×7) / 7 = 53/7 = 7.571428…`, displayed as **7.57** under the fixture's two-decimal display policy. Store sufficient precision; do not average already rounded semester results. Repeats preserve every attempt and apply the approved replacement/inclusion rule without double-counting earned credits. Absent, missing, withheld, exempt and failed are distinct states, not interchangeable zeroes.

## 4. Acceptance test catalog

These tests specify Given/When/Then outcomes. Expand each into automated and/or reviewed cases during implementation; the IDs remain stable.

| ID / family | Given / When / Then |
|---|---|
| TST-001 / REQ-ONB | Given a valid onboarding request, when provisioning is retried with the same operation identity, then exactly one institution, initial invitation and owned asset set exist; interrupted steps can resume. |
| TST-002 / REQ-TEN | Given a FIX-SCH member, when another tenant UUID is substituted in read/write/search/export/file requests, then access is denied without disclosing that tenant's data or counts. |
| TST-003 / REQ-TEN | Given concurrent worker/API requests and pooled database connections, when tenant context changes or a transaction fails, then subsequent queries cannot inherit the previous tenant and missing context fails closed. |
| TST-004 / REQ-ACL | Given a revoked role and existing session/export/socket, when the user retries or the job delivers, then current authorization prevents further disallowed access and a changed role cannot self-escalate. |
| TST-005 / REQ-TEN | Given FIX-UNI's academic grant from FIX-ENG, when it requests approved results, then only granted fields appear; finance/messages are denied, and grant expiry prevents new delivery. |
| TST-006 / REQ-ACL | Given two guardians and an adult learner's delegation, when one relationship is restricted/revoked, then only that authorized scope changes; unrelated sibling data and confidential records remain protected. |
| TST-007 / REQ-ACL | Given a support ticket, when a read-only grant expires or support tries a write/export, then the action is denied; emergency access has independent approval/review and complete audit identity. |
| TST-008 / REQ-CFG | Given a new academic/fee policy version, when previewed and approved for a future period, then affected cohorts are shown and published results/issued charges retain their original rule versions. |
| TST-009 / REQ-ADM | Given a verified application, when admission is approved twice or required verification is incomplete, then only one enrollment is created or the incomplete transition is rejected with an actionable reason. |
| TST-010 / REQ-ACA | Given prerequisite failure or a full elective, registration is blocked/waitlisted; a permitted academic-rule override records reason, authority and version and does not bypass capacity. Given two concurrent claims for the final seat, exactly one registers; linked lecture/lab claims commit atomically. |
| TST-011 / REQ-ATT | Given FIX-SCH and a mid-year enrollment, when attendance is submitted, then only eligible roster dates count; teacher scope is enforced and approved corrections preserve original values. |
| TST-012 / REQ-EXM | Given the 32/40 and 45/60 fixture, when results are calculated, then 77 is produced, component failure policy is honored, and missing/absent/withheld values are not silently converted. |
| TST-013 / REQ-EXM | Given the seven-credit fixture and a later repeated attempt, when GPA/credits are recalculated, then display is 7.57 for the original case, all attempts remain and credits follow the approved repeat rule. |
| TST-014 / REQ-EXM | Given entered marks, when an unauthorized maker publishes or a published mark is edited, then denied; an authorized correction creates an approved revision with reproducible prior results. |
| TST-015 / REQ-FIN | Given the ₹10,000 charge, ₹1,000 concession and ₹6,000 provider-confirmed successful payment/allocation, when ₹1,000 is refunded without reducing charges, then outstanding changes from ₹3,000 to ₹4,000 and all ledger entries reconcile. Bank settlement remains separately tracked. |
| TST-016 / REQ-FIN | Given duplicate/out-of-order payment events and a transient failure, when callbacks retry, then one economic posting exists, invalid signatures are rejected and final provider/ledger totals reconcile. |
| TST-017 / REQ-COM | Given an assigned teacher and linked guardian, when messaging/calling is initiated, then institution policy and availability apply; unrelated parents and unauthorized student-initiated calling are blocked. |
| TST-018 / REQ-COM | Given a teacher-led meeting, when a participant is revoked or the final authorized host disconnects, then revoked active media access ends and reused tokens fail; student participation pauses immediately and closes after the bounded configured grace (proposed 60 seconds) unless an authorized host returns. Recording remains off unless authorized. |
| TST-019 / REQ-UX | Given 360-pixel, tablet and desktop viewports, when critical journeys run with keyboard/screen reader/zoom, then labels, focus, contrast, errors and reflow remain usable without losing essential actions. |
| TST-020 / REQ-UX | Given slow/offline/reconnected network, empty lists and provider failure, when a user submits or retries, then honest status appears, duplicate mutation is prevented and draft/conflict behavior is clear. |
| TST-021 / REQ-OPS | Given a malicious attachment and redaction-sensitive request, when processed, then quarantined content cannot be downloaded and logs exclude tokens, secrets and unnecessary personal data. |
| TST-022 / REQ-OPS | Given an approved deletion plus a held record, when retention runs and a backup is restored, then permitted data is removed, holds remain and deletion records are reapplied before access. |
| TST-023 / REQ-OPS | Given the agreed disaster and separate single-tenant recovery scenarios, when restore is rehearsed, then measured recovery, objects/keys, financial reconciliation and unaffected tenants meet approved objectives. |
| TST-024 / REQ-OPS | Given mixed-tenant peak traffic, when one tenant imports heavily, then interactive budgets and fair processing meet agreed thresholds and stale/missing telemetry reports unknown rather than healthy. |
| TST-025 / REQ-MIG | Given valid and invalid staged imports, when previewed, committed and retried, then row errors, provenance and reconciliation are deterministic with no duplicate learner or financial posting. |
| TST-026 / REQ-INT | Given unavailable government/provider credentials, when the integration screen is used, then it reports unconfigured/unsupported honestly, preserves manual authorized workflows and never displays fabricated synchronization. |
| TST-027 / REQ-OPS | Given two users requesting the last library copy, when both issue it, then only one active loan succeeds; return/fine corrections retain history and lost-book status is distinct. |
| TST-028 / REQ-OPS | Given transport/hostel assignments with date ranges, when seats/beds conflict or pickup authority changes, then capacity and overlap rules hold and restricted contact/location access stays scoped. |
| TST-029 / REQ-OPS + REQ-ACL | Given HR leave and payroll/finance roles, when leave is approved or payroll exported, then employee scope, approval separation and protected compensation fields are enforced. |
| TST-030 / REQ-OPS | Given a laboratory asset booking and procurement request, when conflicts or approval thresholds arise, then unavailable assets cannot be double-booked and purchase approval follows the configured rule version. |
| TST-031 / REQ-CFG | Given a document approval workflow and final issued certificate, when template or branding changes, then pending rules are versioned and previously issued document content remains reproducible. |
| TST-032 / REQ-COM | Given the later mobile client on supported Android/iOS devices, when incoming calls arrive across foreground/background/terminated states, then measured OS/provider behavior meets the selected mobile promise or its limitation is explicitly documented. |
| TST-033 / REQ-ADM + REQ-ACL | Given a published intake and two authenticated applicants, when either creates, edits, uploads, submits or accepts an offer, then only their owned or explicitly delegated application is accessible; spoofed institution/owner IDs, staff-only fields and another applicant's file UUID are rejected. Duplicate acceptance creates one enrollment, and limited applicant membership exposes no student directory. |
| TST-034 / REQ-OPS + REQ-ACL | Given a service/grievance case with internal notes, when the requester, an assigned officer and an unrelated staff member list/search/read/export/receive notifications, then each sees only permitted fields; confidential notes never reach requester views and reassignment/revocation removes obsolete access. Eligible appeals preserve resolution history and do not create unrestricted student messaging. |
| TST-035 / REQ-ACA | Given an existing school study episode and a new academic year, when progression or repeat-year placement is approved and retried, then one new EnrollmentPeriod is created within the existing Enrollment; previous placement, attendance and results remain reproducible and no duplicate student or active episode appears. |

## 5. Performance and usability evaluation

Illustrative sizing scenario only: 20 institutions, 50,000 active enrollment records, 500 simultaneous signed-in users, an 80-request/second API burst, 20 concurrent 40-participant classes, a 50,000-row import and a 10,000-row export. These are planning inputs, not promised capacity or the user's approved forecast. Media participant load is measured separately from Django request traffic.

Agree infrastructure size, data distribution, query mix, p95/p99 latency, error rate, queue age and duration before running. Test warm/cold caches, burst attendance, result publication and retries. Track per-tenant fairness, database connections, locking, memory, storage and provider quotas. State device/network conditions for browser performance; a fast API does not establish good mobile usability.

Perform automated accessibility scans plus manual keyboard, screen-reader and contrast checks on onboarding, attendance, fee payment, result reading and meeting entry. Include 200% zoom, narrow reflow, text expansion, reduced motion and large table navigation. Review representative screens with actual role representatives; screenshots alone do not prove a task can be completed.

## 6. Import contracts and cutover

Imports use private staging, schema/version identification, preview, validation, approval and a committed batch manifest. Never import arbitrary CSV directly into production tables. Every row includes `source_system`, `source_record_id` and `batch_id`; uniqueness is institution + source system + entity type + source record ID. A checksum detects changed content on retry. Source IDs are provenance, not trusted Eduma UUIDs.

| Contract | Required fields | Key validation |
|---|---|---|
| Learner | source identity, legal/display name, institution mapping, date of birth or explicit unknown status | Valid dates, identity duplicate review; do not merge by name/phone alone |
| Enrollment | learner source ID, academic year/term, program/grade, section/campus, start date, status | Resolved references, non-overlapping incompatible enrollments, valid institution |
| Guardian link | learner/account source IDs, relationship, scope, verification status/reference | Quarantine unverified links; no invitations until relationship review |
| Fee opening position | learner source ID, currency, charge/debit, credit/concession, receipts/refunds or approved opening balance, as-of date | Balanced source totals; never count both full history and opening balance twice |
| Academic history | learner, course/subject, term, attempt, component marks/status, rule/version reference, credits/grade | Range, status and weighting checks; preserve unknown legacy rule status |
| Staff assignment | employee source ID, role template, campus/department/course, start/end dates | Grant ceiling, no platform role imports, effective-date validation |

All money is a decimal string plus ISO currency; dates use an agreed unambiguous ISO form; timestamps identify timezone. Document rows carry source filename/checksum and authorized ownership mapping. Error exports neutralize spreadsheet formula interpretation and avoid unnecessary sensitive fields. Report row number, field, error code, safe explanation and corrective action. Reference/domain failures block related commits; approved independent batches can commit separately.

Cutover sequence: inventory and source-owner sign-off; mapping/dry run; resolve exceptions; source freeze or defined delta window; final private backup/export; commit approved batches; reconcile; user/role verification; institution acceptance; release notifications. Record source counts by status, net fee totals, receipt/refund totals, academic course/attempt counts, document checksums and unresolved exceptions. No readiness claim without zero unexplained discrepancies in critical counts and money.

Before general use, an imported batch may be reversed only if dependencies permit and the source is preserved. After users transact, rollback becomes controlled corrections with finance/academic approvals; do not delete legitimate subsequent activity. Roll back application versions separately from data. Preserve import provenance, mapping revision and reconciliation evidence through the approved retention period.

## 7. UAT and release decision

Nominate institution owner, administrator, teacher, finance officer, registrar/examination officer, guardian/student representatives and platform operations. Each institution type completes its applicable end-to-end scenario with agreed expected documents and balances. Users review desktop and phone flows, error recovery, permissions and real terminology, not only dashboard appearance.

Release evidence must identify completed scope, untested paths, open defects, provider limitations, migration reconciliation, security checks, recovery drill and agreed operating support. Logo/brand review and a clickable prototype remain separate design evidence; this test plan does not create or approve them. The product owner accepts the specific release scope only after reviewing evidence. Keep uncompleted L2/L3 capabilities visible in delivery tracking rather than presenting empty screens as finished modules.
