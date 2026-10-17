# Eduma — Workflows and Business Rules

**Version/date:** 1.0 / 12 October 2026  
**Status:** Proposed rules for review. Worked examples are synthetic and do not represent any board, regulator or university's official regulations.

## 1. Contract used by every workflow

Each operation has an actor, institution context, permission, relevant relationship, permitted source state, input validation, resulting state, audit requirement and failure behavior. The server is authoritative. UI, imports, jobs and API consumers use the same business rules.

- An identifier alone never authorizes access.
- Atomic database changes either all commit or all fail.
- External notifications occur from committed events, not before the transaction succeeds.
- Duplicate submissions are recognized with business uniqueness and idempotency keys.
- `version` is an integer changed on update. A stale edit fails with a conflict and current-version context; it does not overwrite newer data silently.
- Dates, timestamps and academic periods have distinct meanings. Store instants in UTC, render institutional timezone, and preserve date-only values.
- A rejected request returns a stable error code and actionable field/detail information without disclosing another institution's records.
- Audit actor, institutional scope, operation, record, before/after or safe diff, reason, timestamp and request trace. Do not log passwords, secrets or full private-message content in operational logs.

Concrete endpoint/error contracts are in [09](09_API_Events_and_Integrations.md); permissions are in [02](02_Roles_Tenancy_and_Permissions.md).

## 2. WF-ONB — institution onboarding and lifecycle

**Actor:** authorized platform onboarding/admin role. Institution setup subsequently belongs to the invited Institution Admin.

1. Enter customer/group relationship, institution legal/display names, category, contacts, campuses, country/timezone and applicable identifiers.
2. Check duplicates and authorized group relationship; allocate immutable institution UUID.
3. Save `draft`; provision storage/configuration/invitation resources through resumable steps.
4. Move to `provisioning`, then `setup` when required resources exist. On failure, preserve diagnostics and retry missing steps without duplicate tenants/invitations.
5. Upload initial branding through validated/scanned files; private and public variants are separate.
6. Send expiring single-use admin invitation. Verification and account recovery never rely on a shared permanent password.
7. Institution Admin sets academic structure, roles, communication policy, templates and enabled entitled modules; imports staged data.
8. Readiness review checks required setup, at least one valid admin, permissions, import reconciliation and applicable configured integrations.
9. Authorized activation changes state to `active` and records actor/time/configuration version.

| Transition | Additional rule |
|---|---|
| `active` → `restricted` | Name restricted capabilities and show reason/remediation; preserve essential authorized retrieval according to policy |
| `active/restricted` → `suspended` | Record reason and scope; revoke affected sessions, realtime subscriptions and media membership |
| `restricted/suspended` → `active` | Revalidate administrator, memberships, integration credentials and outstanding work |
| `active/restricted/suspended` → `archived` | Stop new operations according to closure policy; preserve lawful access/retention |
| `archived` → `deletion_pending` | Verify export, obligations, holds, contractual authority and deletion scope |
| `deletion_pending` → `deleted` | Execute documented data/processor/backup policy; retain only authorized minimal evidence |

Maintenance is a separate bounded operational condition. Suspension does not erase academic or financial history, and valid in-flight payment confirmations still need reconciliation.

## 3. WF-ACL — membership, guardian and affiliation changes

Identity may be shared across authorized memberships; academic records remain institution-scoped. A user selects an institution only from verified active memberships.

**Invitation:** create → delivered/failed → accepted or expired/revoked. Acceptance verifies the intended recipient and applies only the permissions in the invitation. Reinvitation invalidates older active tokens if policy requires it.

**Guardian relationship:** proposed → verified → active → expired/revoked. Record learner, adult, institution, relationship, permitted categories, effective dates, verification evidence and restrictions. An adult student relationship requires appropriate authorization. Custody restrictions cannot be removed through an ordinary contact edit.

**Role/grant change:** validate grantor's authority → preview changed permissions → approve sensitive changes → publish → revoke stale access → audit. Prevent self-escalation and removal of the last active Institution Admin without an approved replacement/recovery path.

**Affiliation exchange:** record parties, academic authority, scope/fields, period, purpose and approving parties. An affiliation record alone grants no read access. Revocation stops future exchange and applies retention/access policy to already received authorized records.

## 4. WF-CFG — configuration publication

Configuration objects move through `draft` → `validated` → `approved` where required → `published` → `superseded`. Keep institution/campus scope, parent template, version, effective interval and allowed override rules.

Before publication:

- Validate types, references, formula constraints and dependency compatibility.
- Show a diff and affected scopes/records.
- Simulate affected academic/financial examples.
- Require designated approval for high-impact changes.
- Prevent overlapping incompatible effective intervals.

Published instances reference the rule version that produced them. Rollback publishes a safe replacement or changes future applicability; it does not erase audit history or blindly recalculate past results. New behavior requiring unsupported expressions is a product change, not arbitrary code entered by an admin.

**Example:** a grading rule introduced for the 2027 cohort must not recalculate a 2026 transcript. A correction for 2026 requires the result-revision workflow and an authorized rule decision.

## 5. WF-ADM — admissions and enrollment

**States:** `draft` → `submitted` → `under_review` → `needs_information` / `eligible` / `rejected` → `offered` → `accepted` → `enrolled`; `withdrawn` may apply at approved points.

The application stores cycle, institution/program/grade choice, required documents, eligibility evidence, seat/category data where applicable and responsible reviewer. Applicants can change only permitted fields during permitted states.

Before enrollment, confirm offer validity, required verification and the applicable admission-payment policy. Use an atomic seat allocation/uniqueness check so parallel admissions do not exceed an approved capacity. A verified payment event may satisfy payment conditions; a browser redirect alone cannot.

Create the student/person link, institution enrollment, academic placement and approved guardian relationships without losing applicant provenance. Keep enrollment number uniqueness scoped to its declared institution/year/program rule. Names, dates of birth or phone numbers alone must not trigger automatic person merges.

Withdrawal after enrollment records effective date, academic consequences, clearance and fee/refund decision separately. Cancellation of enrollment is not automatically a refund and does not delete receipts.

## 6. WF-ACA — curriculum, registration and progression

### 6.1 School model

An academic-year `EnrollmentPeriod` is assigned to grade/section and subject groups inside the enduring `Enrollment` study episode. Teacher assignments determine teaching access. Promotion uses the approved scheme, attendance treatment, review decisions and permitted exceptions. Rollover creates a new `EnrollmentPeriod` within that episode while preserving the previous year's section, results and attendance history. A real new study episode or transfer is modeled separately.

### 6.2 Higher-education model

The learner has an active program enrollment and pinned curriculum/regulation version. A course offering identifies term, section, instructors, capacity and any linked lecture/lab/tutorial requirements.

Registration checks active membership/enrollment, registration window, holds, prerequisites/corequisites, eligible elective group, credit limits, timetable conflicts and available seats. Each failed condition has a separate code and authorized override rule.

**Registration states:** `requested` → `pending_approval` / `waitlisted` / `registered` / `rejected`; registered records can become `dropped` or `withdrawn` only under approved windows/policies.

Seat claims and linked-section registration occur transactionally. Two simultaneous requests for the final seat cannot both succeed. Waitlist promotion rechecks current eligibility before consuming a seat. Duplicate submissions do not create duplicate active registration.

### 6.3 Attempts, equivalence and degree audit

Every assessed course attempt remains identifiable. A repeat may replace the grade contribution according to the pinned rule but does not erase the previous attempt. Credit is counted once unless the applicable approved curriculum explicitly allows multiple distinct credit awards.

Store transfer source, equivalence decision, evidence, approved credits, classification and awarding authority. Separate earned credits from credits accepted toward a particular award. Apply credit categories, substitutions/waivers, transfer/residency limits and minimum performance rules.

Multiple entry/exit, intermediate awards and re-entry apply only where the program's approved regulations permit them. Advisory degree progress and hypothetical program-switch calculations never constitute an issued award.

### 6.4 Rollover

Preview destination year/term/program, eligible students, retained students, withdrawals, pending results, carried balances and staff assignments. An authorized user resolves exceptions before publication. Idempotent batch execution creates no duplicate enrollment and leaves a reconciliation report.

## 7. WF-ATT — timetable, attendance and corrections

Timetable publication checks instructor, room, cohort, resource and accessibility constraints. Draft conflicts are visible; no schedule becomes authoritative merely because an automated solver produced it. Changes create a new published version and notify affected authorized users.

Attendance references the session and roster context, not an arbitrary student list. A teacher can submit only assigned sessions during the allowed window. Student/session uniqueness prevents duplicate marks. Status options must declare whether they contribute to the denominator and numerator.

**States:** `draft` → `submitted` → `locked`. Corrections to submitted/locked records follow a reasoned, authorized amendment; preserve original values and actor.

Offline capture uses a client operation ID and last-known roster/version. Reconnection revalidates authority, session state and roster; a stale conflict is shown for resolution. Display pending local work separately from server-confirmed attendance.

Online-class join events provide supporting evidence. Reconnect events must not double-count time, and room presence is not proof of engagement. The teacher remains responsible for approved academic attendance.

## 8. WF-EXM — assessment to published award

1. Create a scheme tied to curriculum/cohort/period; define components, maxima, weights, pass conditions, grade bands and rounding.
2. Validate scheme completeness and publication authority.
3. Create assessment/exam attempts and approved roster/eligibility snapshots.
4. Assigned evaluators enter/import marks with range, absence and state validation.
5. Submit for moderation; reviewers resolve missing marks and exceptions.
6. Compute results using the pinned rule and record inputs, formula version and rounding behavior.
7. Preview aggregate and individual outputs; an authorized publication action freezes an issued result version.
8. Generate report cards/transcripts/awards with template and signing authority versions.

Mark/result states distinguish draft, submitted, moderated, published, withheld, absent and invalidated outcomes where applicable. An absent mark is not silently stored as a numeric zero. Missing components block publication unless the approved scheme has an explicit alternative.

Recount/revaluation/correction creates a case, records authority, recomputes an approved revision and supersedes the issued result. Preserve old issued versions and their verification status. QR/public verification reveals minimal necessary information and indicates superseded/revoked documents.

## 9. WF-FIN — fee accounting and payment lifecycle

### 9.1 Charge and receipt principles

A fee plan generates identified charges/invoice lines with institution, payer/student account, academic period, due date, amount, currency and applicable rule version. Draft estimates can change; posted charges are corrected by an authorized adjustment or credit note.

Concessions and scholarships have approved eligibility, amount/percentage, period and funding/account mapping. Deposit liabilities remain separate from earned fees. Store exact decimal values and currency; do not use binary floating point.

Use a balanced accounting subledger or equivalent rigorously reconciled journal. The full institution general ledger remains a separately selected boundary. Unallocated money is visible as credit rather than silently attached to an arbitrary fee.

### 9.2 Online payment

`created` → provider order pending → `pending` → `succeeded` / `failed` / `expired`; later refund/dispute states are separate records/events, not destructive edits of the payment.

The backend creates the order. A verified provider callback/event or reconciliation query establishes authoritative payment status. Persist the inbound event and deduplicate by provider/merchant/event identifier before financial effects. Apply payment and issue receipt in a controlled transaction; create notifications after commit.

A payment may succeed after a browser timeout. Show “confirmation pending” and reconcile rather than prompting a blind second payment. Verify amount, currency, merchant and institution mapping. Quarantine mismatches; never post them to a guessed student.

### 9.3 Refunds, reversals and settlement

- A refund returns money. It does not automatically reduce the amount owed.
- A credit note or approved charge reduction changes what is owed.
- Receipt void/reversal retains reason, authority, original reference and accounting reversal.
- Gateway transaction success and bank settlement are separate states.
- Refund request, independent approval where required, provider execution and reconciliation are distinct steps.
- Failed or duplicate refund events must not return/post funds twice.
- Chargebacks/disputes have evidence and accounting treatment; do not silently mark the student unpaid without the approved policy.

Receipt numbering is issued atomically under a defined institution/series/period policy. Never reuse a canceled number. Changes to bank destination require independent verification and approval.

## 10. WF-COM — conversations, calls and classes

Conversations have an institution, purpose, permitted participants and membership history. Teacher-parent threads link the authorized child/assignment. New participants receive only the history allowed by policy. Durable messages are saved before delivery events; a provider acknowledgment is not a read receipt.

**Call sequence:** authorize relationship/policy → create expiring session → notify registered devices → accept/decline → recheck access → issue short-lived room credentials → connect → reconcile end state and usage. States include requested, ringing, accepted, connecting, connected, reconnecting, declined, canceled, missed, failed and ended.

One accepted device cancels ringing on other devices. Stale pushes cannot reopen a completed session. Device denial, unavailable recipient, provider failure and network loss have distinct user messages. Personal phone numbers remain private by default.

Teacher-led classes require an assigned host, enrolled/approved participants and institutional enablement. Students cannot self-start an unsupervised room. Host controls include admission, removal, microphone/camera policy, screen sharing and ending for everyone. After the final host disconnects, pause participation; apply a bounded configured grace period before closing. The proposed initial grace is 60 seconds, subject to review and provider capability.

Revoke active sockets/media membership on suspension or relevant relationship removal. Recording is disabled until an approved policy, explicit visible recording flow, purpose/access/retention settings and provider support exist. Microphone permission alone is not recording consent.

## 11. WF-OPS — operational service workflows

These contracts retain the web catalog's breadth. Enable only applicable modules and record exact institution rules before live use.

| Module | Main transition | Validation and exception behavior |
|---|---|---|
| Library | available → reserved/issued → returned; lost/damaged alternative | Atomic copy allocation, borrower eligibility, due-date calendar, renewal limits; return twice has no duplicate effect; fines use approved finance posting |
| Transport | planned trip → dispatched → in_progress → completed/canceled | Assigned driver/attendant/riders, vehicle capacity, duplicate boarding detection, approved pickup identity; tracking scoped to relevant active trip |
| Hostel | requested → approved → allocated → checked_out | No overlapping active bed allocation; authorized transfer/out-pass; occupancy and deposit reconciled at exit |
| Mess | plan assigned → meal entitlement → attendance/consumption record → period reconciliation | Prevent duplicate entitlements; institution policy determines missed-meal adjustments and sensitive dietary-data access |
| HR leave | draft → submitted → approved/rejected → canceled | Leave balance and overlap checks, delegated approver, employment validity; cancellation reverses balance effects once |
| Payroll | inputs prepared → validated → approved → exported/processed → reconciled | Restricted salary access; calculation/version evidence; adapter output is not proof of bank payment; posted cycles use approved correction |
| Procurement | requisition → approved → ordered → partially_received/received → reconciled | Budget/authority and supplier checks; receipt cannot exceed approved tolerance; returns preserve stock/journal history |
| Inventory/assets | receive → issue/transfer → return/maintenance → dispose | Stock movements atomic, negative stock only under explicit approved policy, custodian and disposal authority recorded |
| Lab booking | requested → confirmed → used/canceled | Resource/instructor availability, equipment limits, safety prerequisites and maintenance blocks |
| Student service case | submitted → triaged → assigned → actioned → resolved/appealed | Case-specific visibility; confidential content not visible to all admins; escalation clock and decision reason |
| Placement | opportunity → approved → applications → shortlist → offer → accepted/declined | Eligibility snapshot, applicant consent, employer scope, placement reports distinguish offers from accepted placements |
| Internship | proposal → approved → active → evidence_review → completed | Assigned supervisor, duration/evidence, rubric and academic-credit approval are separate |
| Alumni | eligible record → consented contact profile → activity | Contact permissions and withdrawal; no perpetual student portal access by default |
| Research | scholar/project created → supervisor assigned → milestones → review → award/closure | Committee authority, evidence and confidentiality; award follows approved university process |
| Accreditation/quality | evidence requested → submitted → reviewed → frozen/exported | Evidence owner, academic period, framework version and traceable calculations; export is not automatic accreditation |

## 12. Synthetic worked examples and expected outcomes

Use these fixtures in development/tests only. Show a “Synthetic demonstration policy” label if they appear in an interface. Replace them with approved institution rules before live academic use.

### EX-01 — fee balance and refund

Currency INR, exact two-decimal display:

1. Posted tuition charge `10000.00`.
2. Approved concession/credit note `1000.00`; net receivable `9000.00`.
3. Successful applied payment `6000.00`; outstanding `3000.00`.
4. Return `1000.00` of that payment without changing the charge; net applied cash `5000.00`, outstanding `4000.00`.
5. A separate approved credit note `1000.00` after that refund reduces outstanding to `3000.00`.

Do not subtract the refund from debt as if it were another payment. Repeat delivery of the same payment/refund event changes none of these totals.

Illustrative net balanced effects before step 5: debit receivable 10000 / credit fee income 10000; debit concession 1000 / credit receivable 1000; debit cash/provider clearing 6000 / credit receivable 6000; debit receivable 1000 / credit cash/provider clearing 1000. File 08 specifies the actual two-stage journal: receipt first creates unapplied student-funds liability, allocation reduces receivable, and a refund reverses the relevant allocation before returning funds. The net effects shown here combine those stages; do not post both the combined and detailed journals. Actual chart/tax/accounting policy needs institution approval.

### EX-02 — weighted assessment

Synthetic scheme: internal maximum 40 contributes 40%; final maximum 60 contributes 60%. Marks 32/40 and 45/60 yield `(32/40 × 40) + (45/60 × 60) = 77.00/100`.

Validate maxima and weights separately. If an institution instead has internal maximum 50 but weight 40%, a raw mark of 40 contributes 32 points. Do not round intermediate contributions unless the scheme explicitly requires it. Pass conditions and grade bands remain separate configured rules; 77 alone does not establish pass status if component minimums apply.

### EX-03 — SGPA and repeated attempts

Synthetic courses: course A has 4 credits at grade point 8; course B has 3 credits at grade point 7. The weighted total is 53 and denominator is 7; the exact result is 53/7 = 7.571428…; configured two-decimal rounding gives 7.57.

If course B is repeated under a replacement policy and the new grade point is 9, its contribution becomes 27 and the result is 59/7 = 8.428571… → 8.43. Retain the old attempt and count course B's credits once. Other institutions may require a different policy; do not assume replacement universally.

### EX-04 — attendance denominator

Synthetic policy: 20 scheduled sessions, 2 canceled sessions removed, 1 approved excused session excluded. The eligible denominator is 17. Attending 15 gives 15/17 × 100 = 88.235294… → 88.24%. If excused absence instead remains eligible, the denominator would be 18 and the result 83.33%; the chosen rule must be visible and versioned.

### EX-05 — final seat

An offering has capacity 30 and 29 active registrations. Two eligible users submit concurrently. Exactly one receives a registered seat; the other receives a waitlist/full outcome according to policy. Replaying either accepted request creates no additional registration or capacity consumption.

### EX-06 — cross-institution guardian

A guardian has one child in schoolA and one in schoolB. Switching child changes authorized institution context. SchoolA's teacher cannot open schoolB's child record or start a conversation about that child merely because the guardian identity is shared.

### EX-07 — suspended institution and pending payment

An institution is suspended after a payment was initiated. New prohibited actions are blocked and active affected sessions revoked. A genuine signed success event for the in-flight order is processed into a restricted reconciliation path without reopening general institution access.

## 13. Exception inventory and publication gates

| Condition | Required outcome |
|---|---|
| Missing authority or another institution's ID | Deny without leaking record details; audit suspicious attempts appropriately |
| Stale record version | Conflict response; preserve draft and provide reload/review path |
| External provider unavailable | Honest unavailable/pending state; bounded retry; no invented success |
| Duplicate submission/event | Return prior result or equivalent no-additional-effect outcome |
| Invalid academic formula | Prevent publication; identify invalid input/rule |
| Conflicting configuration versions | Prevent ambiguous effective applicability |
| Unauthorized historical change | Route to correction/revision process; no direct overwrite |
| Large bulk change | Preview affected counts and errors; resumable batches with per-record status |
| Partial import failure | Preserve validated/failed row accounting and authorized rollback boundaries |

Before adopting real institution policy, an academic or finance owner must review sample calculations and exception outcomes. The acceptance matrix in [11](11_Test_UAT_and_Migration.md) turns these examples into test evidence; the existence of this document does not mean those tests have run.
