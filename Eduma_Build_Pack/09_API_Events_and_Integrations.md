# Eduma — API, Events and Integrations

**Baseline:** 12 October 2026 · **Status:** proposed interface contract for review. JSON examples are documentation, not an application implementation.

Use [architecture](07_Architecture_and_Decisions.md), [data dictionary](08_Data_Model_and_Dictionary.md), [workflows](03_Workflows_and_Business_Rules.md) and [permissions](02_Roles_Tenancy_and_Permissions.md). The later build must produce machine-readable OpenAPI and event schemas from these reviewed contracts and verify frontend/backend compatibility. Do not claim this route catalog alone is complete production API documentation.

## 1. Contract conventions

| Item | Proposed contract |
|---|---|
| Institutional base | `/api/v1/institutions/{institution_id}`; abbreviated `I` below |
| Platform base | `/api/v1/platform`; abbreviated `P` below; separate platform permissions |
| Self-service/auth base | `/api/v1/session` and `/api/v1/me`; no untrusted institution selection grants access |
| Admission bootstrap | Public form read `/api/v1/public/admissions/{institution_slug}`; authenticated applicant creation `/api/v1/applicant/institutions/{institution_slug}/applications` with server-resolved institution and limited membership |
| Content | UTF-8 JSON; `application/problem+json` for errors; multipart/direct storage workflow for files |
| Identifiers | UUID strings; route ID must match verified institutional membership/context |
| Amount/time | Decimal strings with currency; UTC ISO timestamps; date-only values retain local date meaning |
| Lists | `{items, next_cursor, previous_cursor}`; opaque cursor; default limit 25, maximum 100 proposed |
| Sort/filter | Explicit allowlist; stable `(sort_value,id)` ordering; no arbitrary SQL/field lookup expressions |
| Updates | Integer `version` required for existing mutable resource commands; atomic check and increment |
| Creation | `201` with resource/Location; long work `202` with authorized job resource; never success for unconfigured integration |
| Deletion | Archive action where history exists; hard deletion only defined record types and approved retention flows |
| Compatibility | Additive optional fields within v1; incompatible semantics require migration/deprecation and version review |

Cursor tokens bind institution, query filters, ordering and relevant authorization context. Reject a cursor replayed with different filters or institution; never allow it to override access scope. Total counts are optional separate aggregations because large lists should not require expensive exact counts on every request. Export is a separate asynchronous authorized operation, not `limit=unlimited`.

First-party web uses protected session cookies and CSRF on unsafe methods, including login. Do not place long-lived credentials in localStorage or URLs. DRF session authentication may return 403 for unauthenticated access; normalize its problem `code` to `authentication_required`, distinct from `permission_denied`. Future bearer/OIDC clients may receive 401 with the applicable authentication challenge. Clients handle the machine code, not a guessed redirect from status alone. [DRF authentication behavior](https://www.django-rest-framework.org/api-guide/authentication/)

## 2. Errors, conflict and retry rules

Use RFC 9457 Problem Details plus Eduma extension members. Do not leak stack traces, SQL, provider credentials or existence of inaccessible records. [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html)

```json
{
  "type": "urn:eduma:problem:version_conflict",
  "title": "This record changed",
  "status": 409,
  "detail": "Reload the latest record and review your changes.",
  "instance": "urn:eduma:request:17b5f9e0-4b36-4eeb-97ba-2d0c849885aa",
  "code": "version_conflict",
  "errors": [],
  "trace_id": "17b5f9e04b364eeb97ba2d0c849885aa",
  "current_version": 8
}
```

| Status / code | Meaning and UI behavior |
|---|---|
| 400 / `invalid_request` | Malformed JSON, unsupported filter/cursor; fix request |
| 403 / `authentication_required` | Web session missing/expired; preserve permissible draft and sign in |
| 403 / `permission_denied` | Known context but disallowed action; no retry loop |
| 404 / `not_found` | Missing or deliberately concealed cross-scope resource |
| 409 / `version_conflict`, `invalid_transition`, `capacity_exhausted` | Refresh/review; do not silently overwrite |
| 409 / `idempotency_mismatch`, `integration_not_configured` | Same key/different payload or required setup absent |
| 422 / `validation_failed` | Valid JSON but failed domain rules; `errors` includes field/path/code/message |
| 429 / `rate_limited` | Respect Retry-After; show remaining retry time where useful |
| 503 / `dependency_unavailable` | Temporary provider/dependency failure; preserve uncertain financial state |

A client must not blindly retry non-idempotent writes after a timeout. Every payment/refund, enrollment acceptance, publication, import confirmation and message submission has an idempotency key or equivalent client operation ID. Scope the key to institution, actor/service principal, method and route; persist payload hash, processing status and original response. Identical retries return the original outcome or in-progress operation; a different payload gets conflict. Proposed general replay retention is at least seven days, subject to reviewed workload needs; durable business-source uniqueness remains even after response-cache expiry. Financial/provider event identifiers follow financial retention policy.

## 3. Core route and authority catalog

All reads are scoped; all state-changing commands validate current state, supplied version when applicable and action-specific authority. UUID parameters shown as `{id}` belong to the route institution.

| Routes | Principal action / authority |
|---|---|
| `POST /session/login`, `POST /session/logout`, `GET /me` | Authenticate/logout; list own memberships and permitted context |
| `POST /api/v1/accounts/registration-requests`, `/api/v1/accounts/verification-completions` | Policy-enabled applicant account creation and verified contact; generic responses, single-use expiring challenges and abuse limits; no staff role or institutional directory access |
| `GET/POST P/institutions`, `GET/PATCH P/institutions/{id}` | Authorized platform onboarding and institution metadata |
| `POST P/institutions/{id}/activate`, `/suspend`, `/reactivate` | Reasoned lifecycle transition; session/job/communication effects audited |
| `POST P/institutions/{id}/admin-invitations` | Invite designated Institution Admin; no password sharing |
| `POST P/institutions/{id}/branding/upload-requests`, `/branding/{asset_id}/finalize` | Authorized platform onboarding upload for the named institution; same quarantine/scan/ownership controls as institutional files; no blanket access to learner documents |
| `GET P/health`, `/incidents`, `/usage`, `/audit-events` | Operational metadata only; permission-specific sensitive detail |
| `GET/PATCH I/profile`, `GET/POST I/campuses`, `I/departments` | Institution setup and delegated configuration |
| `GET I/entitlements`, `GET I/module-settings`, `POST I/module-settings/{id}/change` | Enable available features subject to active-record/dependency impact |
| `GET/POST I/configurations/{key}/revisions`, `POST .../{id}/preview`, `/publish` | Draft, validate, impact preview and publish typed settings |
| `GET/POST I/memberships`, `POST I/memberships/{id}/revoke`, `I/role-grants` | Access delegation constrained by grantable authority |
| `GET /api/v1/public/admissions/{institution_slug}` | Sanitized published form/cycles for `/apply/{institution_slug}/...`; no applicant records or internal configuration |
| `POST /api/v1/applicant/institutions/{institution_slug}/applications` | Authenticated `application.own_create` bootstrap; server assigns institution, limited membership and owner |
| `GET/POST I/applications`, `GET/PATCH I/applications/{id}`, `POST .../{id}/submit`, `/accept` | Staff-scoped access or applicable `application.own_view/edit/submit/accept`; own/delegated object and field scope enforced |
| `POST I/applications/{id}/reviews`, `/information-requests`, `/approve`, `/offer` | `application.review`, `application.request_information` and `admission.approve` as applicable; applicant cannot grant its own admission |
| `GET/POST I/students`, `GET/PATCH I/students/{id}`, `I/guardian-links` | Registry and specifically authorized relationships/fields |
| `GET/POST I/enrollments`, `POST I/enrollments/{id}/transfer`, `/withdraw` | Authorized study-track lifecycle; history retained |
| `GET/POST I/academic-years`, `I/terms`, `I/programs`, `I/curricula`, `I/courses` | Academic catalog configuration with published-rule protection |
| `GET/POST I/course-offerings`, `POST I/course-registrations`, `/course-registrations/{id}/withdraw` | Eligibility, capacity and student/registrar permissions |
| `GET/POST I/timetable-slots`, `POST I/timetable/validate` | Room/instructor conflict checks and approved scheduling |
| `GET/POST I/attendance-sessions`, `PUT I/attendance-sessions/{id}/marks`, `POST .../submit`, `/correction-requests` | Assigned teacher; correction approval after lock |
| `GET/POST I/assignments`, `POST I/assignments/{id}/submissions` | Teacher assignment and enrolled student submission |
| `GET/POST I/assessment-batches`, `PUT .../{id}/marks`, `POST .../validate`, `/submit`, `/approve`, `/publish` | Separated marking/review/publication powers |
| `GET I/results`, `POST I/result-corrections`, `GET I/transcripts` | Published results by permitted owner; formal correction/reissue |
| `GET/POST I/outcome-mappings`, `POST I/attainment-runs` | Engineering outcome evidence and versioned method |
| `GET/POST I/affiliation-exchanges`, `POST .../{id}/approve`, `/release` | Explicit university/college exchange contract and both-side scope |
| `GET/POST I/invoices`, `POST I/invoices/{id}/issue`, `I/credit-notes` | Finance creation/approval; issued history immutable |
| `POST I/payment-intents`, `GET I/payments/{id}`, `POST I/cash-collections` | Initiate provider checkout or authorized offline receipt |
| `POST I/allocations`, `POST I/refunds`, `POST I/refunds/{id}/approve` | Ledger rules, dual control and idempotency |
| `GET I/reconciliation-cases`, `POST .../{id}/resolve` | Evidence-backed finance exception resolution |
| `GET/POST I/conversations`, `GET/POST .../{id}/messages`, `POST .../read` | Allowed participants/relationships, durable messages |
| `POST I/call-requests`, `POST .../{id}/accept`, `/decline`, `/end` | Teacher-parent/staff calls within policy |
| `GET/POST I/class-sessions`, `POST .../{id}/start`, `/join`, `/admit`, `/end` | Assigned teacher host; authorized students join only |
| `POST I/files/upload-requests`, `/files/{id}/finalize`, `GET .../download` | Scoped upload quarantine, scan state and authorized retrieval |
| `POST I/imports`, `POST .../{id}/validate`, `/commit`, `GET .../errors` | Dry run and explicit commit; source-key deduplication |
| `POST I/exports`, `GET I/jobs/{id}`, `GET I/reports/{report_code}` | Field/scope restrictions and data freshness |

Platform suspension preserves records and documented obligations. It must not discard confirmed financial callbacks, emergency incident evidence or retention jobs. User-facing access and new external activity are restricted according to the approved lifecycle policy.

## 4. Worked request/response contracts

### 4.1 Institution creation

`POST P/institutions` with `Idempotency-Key`. Platform role must permit onboarding. Body contains no infrastructure secrets; admin invitation is a subsequent command so retries do not send duplicate invitations.

```json
{
  "code": "EDU-SYN-001",
  "legal_name": "Synthetic Institute of Engineering",
  "display_name": "Synthetic Engineering",
  "category": "engineering_college",
  "country_code": "IN",
  "timezone": "Asia/Kolkata",
  "base_currency": "INR"
}
```

```json
{
  "id": "0f33dd82-077d-4ca4-8b73-b9e020010001",
  "code": "EDU-SYN-001",
  "lifecycle_status": "draft",
  "version": 1,
  "onboarding_required": ["institution_admin", "campus", "academic_setup"]
}
```

Activation requires completed mandatory setup and permitted entitlements; an invitation alone does not prove the admin accepted or the institution is ready.

### 4.2 Attendance and concurrent edits

`PUT I/attendance-sessions/{id}/marks` is an atomic batch update of specified learner marks, not replacement/deletion of omitted learners. An assigned teacher supplies:

```json
{
  "version": 4,
  "marks": [
    {"enrollment_id": "cfce04fd-007b-4871-87ac-d1cec0020001", "code": "present"},
    {"enrollment_id": "cfce04fd-007b-4871-87ac-d1cec0020002", "code": "absent", "reason": null}
  ]
}
```

Return session ID, `version: 5`, `state: "draft"`, saved count and remaining unmarked count. Invalid learners cause 422 with indexed field errors and no partial mutation. A stale version causes 409. Submission validates all required marks; later changes use correction requests with reason and approval, not direct edits to locked evidence.

### 4.3 Course registration

`POST I/course-registrations`, with idempotency key, takes `enrollment_id`, `course_offering_id` and `curriculum_version_id`. The service checks active enrollment, prerequisites, allowed workload, registration window, offering capacity and timetable conflicts under the applicable rule revision. Return `201` registration, state, recorded rule revision and attempt number. Concurrent acceptance of the last seat results in one confirmed registration and one 409 `capacity_exhausted`; a displayed cached seat count is not a reservation.

### 4.4 Invoice balance and refund

`GET I/invoices/{id}` returns server-computed amounts:

```json
{
  "id": "b8ebf06b-dd47-4da9-a33c-2a9400030001",
  "currency": "INR",
  "issued_charges": "10000.00",
  "credit_notes": "1000.00",
  "net_charges": "9000.00",
  "net_allocated": "6000.00",
  "outstanding": "3000.00",
  "state": "partially_paid",
  "version": 7
}
```

`POST I/refunds` takes payment ID, amount/currency, reason, selected allocation-reversal amounts and current payment version. The service returns `201` a refund in `requested` state and an impact preview; it does not claim money returned. Approval reserves refundable capacity and queues the provider operation. A completed INR 1,000 refund that reverses INR 1,000 allocation changes `net_allocated` to 5,000 and `outstanding` to 4,000. No credit note is created automatically. Financial state changes occur only after appropriate provider/offline confirmation and balanced posting. Rejection or provider failure releases/reconciles reservations explicitly.

### 4.5 Configuration publishing

`POST I/configurations/assessment_rules/revisions/{id}/preview` returns affected cohorts, incompatible existing records, warnings, blocking validations and a preview token tied to draft version. `/publish` requires version, preview token, effective date and approval evidence if required. A changed draft invalidates the preview. Return new effective revision and unchanged historical revision references; never silently recalculate published results.

### 4.6 Teacher-hosted session admission

`POST I/class-sessions/{id}/join` checks current enrollment/assignment, institution policy, host state and session window. A waiting student receives `202` with `admission_state: "waiting"`; an admitted participant receives short-lived provider connection details bound to attendee role. Tokens never permit an attendee to become host. Missing provider configuration returns 409 `integration_not_configured`, not a fake room URL. Provider outage returns an actionable failure or pending state; persisted schedules remain visible.

### 4.7 Applicant self-service and ownership

The `/apply/{institution_slug}/...` browser routes use `GET /api/v1/public/admissions/{institution_slug}` for allowlisted institution branding, published cycle options, deadlines, field definitions, public requirements and notices. Unpublished, closed or unavailable forms receive an appropriate unavailable state; the endpoint cannot enumerate applicants, internal reviewer configuration or stored documents. Public reads are rate limited. Creating or reading an application requires authentication, CSRF protection for session requests and request-level ownership checks.

`POST /api/v1/applicant/institutions/{institution_slug}/applications` takes `admission_cycle_id`, `form_revision_id`, the allowed applicant `answers`, optional permitted applicant-file references and an idempotency key. It does **not** accept client authority over `institution_id`, `owner_membership_id`, reviewer fields or stage. The server resolves the active published institution/cycle, creates or reuses a limited applicant membership, binds the authenticated actor as owner and creates a draft atomically. Return `201` with application ID, assigned institution ID, `stage: "draft"`, version, applicant-visible values and computed `allowed_actions`. The returned institution ID supports routing; possessing it grants no additional access.

An existing account signs in; a new applicant uses the policy-enabled account verification flow. Before institutional membership exists, the bootstrap service evaluates eligibility against the published intake policy rather than requiring a staff invitation. It can grant only the fixed limited applicant permissions for that intake. If a membership already exists, preserve its valid roles without granting additional staff powers. A client-supplied role or permission list is never accepted. New drafts can be created without attachments; subsequent upload requests bind to that authorized application.

Subsequent `GET/PATCH I/applications/{id}` and `/submit` or `/accept` actions require matching ownership or an active, specifically authorized guardian/delegate grant. A `GET I/applications` by an applicant returns only their permitted applications; it cannot become a staff directory through query parameters. Draft editing requires `application.own_edit` and expected version. After submission, further editing is limited to specifically requested information in the allowed state, preserving the original submission. File finalization/download checks the same application authority and field state. A revoked delegate loses these capabilities, including export/download links requiring authorization.

Guardian/delegate grants record verified authority basis, permitted actions and expiry; creating one is a controlled institution policy workflow, never automatic from a shared phone or client-supplied child UUID. A guardian submitting for a minor is the submitting identity; the learner profile remains separate. Staff can review/request information through their permissions. Applicant `/accept` with `application.own_accept` accepts an existing valid approved offer, but cannot invoke `admission.approve`, change offered track/price or bypass outstanding conditions. Any promised enrollment conversion must follow the approved workflow and transaction rules.

Applicant serializers explicitly exclude internal notes, reviewer-only attachments, hidden scoring, risk/triage fields and staff deliberations; the exclusion applies to list/detail, search, notifications and exports. Unknown/inaccessible application UUIDs return the concealed 404 contract. Test two applicants within the same institution, one owner across two institutions, a guardian delegate with narrowed authority, ownership-field injection and a delegate revoked during file access.

## 5. Full-catalog route boundaries

These routes define planned operational breadth; they require actual implementation and acceptance before being presented as available. L1/L2 is delivery order, not an approved reduction of web scope.

| Domain routes under I | Commands and integration boundary |
|---|---|
| `/library/items`, `/library/copies`, `/library/loans`, `/library/loans/{id}/return`, `/library/reservations` | Barcode uniqueness, borrower eligibility, due/renewal/fine policy; fine posting through finance service |
| `/transport/routes`, `/transport/assignments`, `/transport/trips`, `/transport/trips/{id}/boarding-events` | Authorized route roster, boarding/handover and incident corrections; location provider optional/configured |
| `/hostel/beds`, `/hostel/allocations`, `/hostel/leave-passes`, `/mess/plans` | Capacity and overlap constraints, wardens/guardians per policy |
| `/employees`, `/leave-requests`, `/leave-requests/{id}/approve`, `/payroll-runs`, `/payroll-runs/{id}/export` | Restricted HR, immutable approved payroll snapshot and external accounting adapter; statutory engine scope explicit |
| `/requisitions`, `/purchase-orders`, `/goods-receipts`, `/assets`, `/assets/{id}/custody-events` | Procurement approvals and stock/custody reconciliation |
| `/laboratories`, `/lab-resources`, `/lab-bookings`, `/lab-bookings/{id}/approve`, `/lab-bookings/{id}/cancel` | SCR047: `lab_booking.create/approve` with scoped eligibility, safety policy and atomic capacity/exclusive-resource conflict checks; cancellation follows ownership/delegated state policy |
| `/placement/opportunities`, `/placement/applications`, `/internships` | Eligibility and consented employer access; employer scope never broad directory access |
| `/service-cases`, `/service-cases/{id}`, `/service-cases/{id}/notes`, `/service-cases/{id}/assign`, `/service-cases/{id}/resolve`, `/service-cases/{id}/appeals` | SCR049: generic service/grievance `case_type`; `service_case.create/read/update/assign/resolve/appeal`, case-specific participant/staff scope and audience-filtered notes |
| `/research/scholars`, `/research/milestones`, `/research/grants`, `/research/ethics-approvals` | Supervisor/office scope, valid approvals, evidence and accounting links |
| `/accreditation/evidence`, `/accreditation/review-cycles`, `/accreditation/submissions` | Versioned evidence assembly; export status is not accreditation approval |

`POST I/lab-bookings` accepts laboratory/resource IDs, purpose or offering, start/end times and required participant/safety declarations; the server derives requester and institution. Return a requested booking with version and approval requirements. `/approve` requires current version and `lab_booking.approve`; overlapping exclusive resources/capacity exhaustion returns 409 and no reservation mutation. Requesters cannot self-approve by setting `state` in the creation body. Approval and cancellation generate auditable allocation/release evidence.

`POST I/service-cases` accepts allowlisted `case_type`, subject, requester-visible description and authorized attachment IDs; server-derived requester and policy select routing/classification. A requester cannot set assignee, internal classification, private notes or resolved state. `GET/PATCH I/service-cases/{id}` uses `service_case.read/update` with ownership/participant/case-team scope and field/state restrictions. `/assign`, `/resolve` and `/appeals` require their respective permission and expected version; an appeal preserves the original resolution and enters an explicit review state. Notes have a server-validated audience: requester-visible replies and internal staff notes use separate response projections. Unauthorized staff and requesters never receive internal note text, attachment URLs or excerpts through lists, notification previews, exports or search. This generic route replaces a parallel `/grievances` API; grievance behavior is selected by case type and policy.

## 6. Events, realtime and webhook delivery

Business updates and outbox records commit together. Proposed event envelope:

```json
{
  "event_id": "a0c33377-7bfe-4128-a6f7-fb7d00040001",
  "event_type": "finance.payment.confirmed",
  "schema_version": 1,
  "institution_id": "0f33dd82-077d-4ca4-8b73-b9e020010001",
  "occurred_at": "2026-10-12T09:30:00Z",
  "aggregate_type": "payment",
  "aggregate_id": "7d4df275-e846-4ae4-b7d3-dbd900050001",
  "aggregate_version": 3,
  "correlation_id": "17b5f9e0-4b36-4eeb-97ba-2d0c849885aa",
  "data": {"amount": "6000.00", "currency": "INR"}
}
```

Other event types include `institution.activated`, `membership.revoked`, `enrollment.confirmed`, `attendance.submitted`, `result.published`, `refund.completed`, `configuration.published`, `message.created` and `class.ended`. Event data is minimal; authorized consumers retrieve sensitive detail through scoped services. A global log collector must not receive whole student/message records.

Assume at-least-once delivery, possible duplicates and out-of-order arrival. Each consumer records event ID and processing outcome atomically with its effect. Use aggregate version to detect gaps/stale state; do not discard a necessary older financial fact merely because a newer status event arrived first. Re-read authoritative state or replay ordered source history when needed. Retry transient failures with bounded backoff; permanent validation failures enter an actionable dead-letter state. Authorized replay preserves original event identity.

Realtime endpoint proposal: `/ws/v1/institutions/{institution_id}`. Authenticate session and validate Origin before subscription. Authorize each conversation/session subscription and each event payload; revoke subscriptions when membership or relationship changes. HTTP commands remain canonical writes initially; WebSocket sends event hints with sequence numbers. On reconnect, client fetches missing messages through REST. A network-level send acknowledgment is not a persisted/read acknowledgment. Rate-limit connections and subscriptions; never put long-lived credentials in the WebSocket URL.

Provider webhooks use `/api/v1/integrations/{provider}/webhooks/{connection_id}`. The opaque connection ID resolves the configured provider account and institution; incoming body institution IDs never select tenancy. Verify provider signature over raw bytes, allowed timestamp/replay window and event identifier before durable acceptance. Return success only after durable capture, then process asynchronously. Duplicates are acknowledged without reposting. Preserve enough sanitized evidence for reconciliation; provider payloads follow restricted retention rules.

Outgoing institution webhooks, if enabled, use signed timestamped envelopes, per-connection secrets, event allowlists, retry/delivery records and destination validation against SSRF. Do not allow arbitrary private-network destinations. Delivery failure must not roll back a committed academic/financial action.

## 7. Integration inventory and provider acceptance

| Interface | Eduma responsibility | External responsibility / required evidence |
|---|---|---|
| Payment | Fee obligation, allocation, receipt, refund approval, reconciliation | Authorized account, payment/refund IDs, signed events, settlement reports, refunds, timeout/duplicate semantics |
| Media/WebRTC | Policy, permitted contacts, teacher role, class schedule and admission | Browser/mobile SDKs, room role controls, token expiry, revocation, TURN, region, recording controls, accessibility and billing |
| Email/SMS/push | Recipient authority, templates, preference/quiet-hour policy, notification intent | Delivery IDs/status, authenticated callbacks, template/account requirements, rate limits and cost |
| Accounting/payroll | Approved export snapshot, chart mapping and reconciliation cases | Account mapping, period locks, import acknowledgment, reversals and error report |
| LMS | Authoritative enrollment mapping and approved outcome exchange | Versioned roster/content/grade APIs and explicit source of truth; prevent bidirectional update loops |
| SSO | Institution-domain connection, membership policy and revocation handling | OIDC/SAML metadata as selected, verified issuer/audience, lifecycle and recovery process |
| Government/education systems | Validated identifiers, consent/access workflow, approved export | Official documented and authorized access; portal existence is not an available public API |
| Storage/scan | File metadata, access control, retention and quarantine | Private storage, scoped upload/download, integrity and malware scan outcome |

For India-specific identifiers/reporting, evaluate UDISE+, AISHE, APAAR/ABC, DigiLocker and applicable board/university submissions individually. Do not invent endpoints or state that all are connected. Provide validated manual export/import workflows where officially authorized APIs are unavailable, with clear operator steps and audit evidence. Numeric identifiers remain strings so leading zeros survive.

Each adapter exposes explicit `unconfigured`, `validating`, `ready`, `degraded`, `disabled` and `revoked` states as appropriate, capability flags, connection health time and safe error details. Secrets live in a secret manager; APIs return references/masked status, never secret values. Vendor changes preserve source transaction mapping and replay/reconciliation history.

## 8. Acceptance evidence

Contract tests must cover unknown/mismatched institution IDs, revoked membership during export and WebSocket activity, conflicting updates, duplicate and out-of-order payment/refund events, failed provider calls, upload quarantine, class admission controls, disabled modules and replayed commands. Test the complete request-to-database-to-UI outcome, not only mocked 200 responses. An adapter is complete only after authorized sandbox/live-equivalent evidence verifies the capabilities required for its slice. Unconfigured adapters remain clearly unconfigured and are not counted as delivered integrations.
