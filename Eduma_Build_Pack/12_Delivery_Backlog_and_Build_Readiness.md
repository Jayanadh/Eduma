# Eduma — Delivery Backlog and Build Readiness

**Version/date:** 1.0 / 12 October 2026  
**Status:** Proposed implementation sequence and acceptance contract. No task below is implemented or verified. This is a delivery specification, not an already approved executable Superpowers implementation plan.

## 1. Delivery principle

Deliver working slices connecting UI, APIs, database, authorization, audit, failures and tests. Keep all four institution categories in the core design. L1/L2 identify dependency order; they do not authorize abandoning operational modules. Native mobile comes later as requested.

Before code, reconcile [01](01_PRD_and_Release_Scope.md), [14](14_Decisions_and_Assumptions.md), logo/design status and the current user's explicit direction. After the design is reviewed, convert the current subsystem into a detailed implementation plan with exact paths, dependencies and runnable verification commands. Superpowers `writing-plans` can support that step if available. It does not replace the agreed product scope.

## 2. Readiness categories

| State | Meaning | Evidence |
|---|---|---|
| Draft specification | A proposed behavior exists | Current Markdown pack |
| Reviewed specification | Relevant owner accepted scope/design/rules | Dated decision and reviewed version |
| Implemented | Real connected code exists | Changed files and working persistence/API/UI |
| Locally verified | Relevant automated/manual checks ran | Commands, results, browser evidence and known limits |
| External integration validated | Required provider/authority connection tested | Sandbox/live authorization and reconciled evidence, accurately labeled |
| Pilot approved | Institution users completed acceptance | Signed/recorded UAT against its actual rules |
| Production ready | Operational and release gates met | Security, accessibility, recovery, migration and support evidence |

Do not equate a successful build command with business completion, or a local development provider with a validated payment/calling integration.

## 3. Proposed repository organization for later creation

The following paths describe responsibilities; they are not files created by this planning task. Adapt exact structure during implementation planning while preserving separation of concerns.

| Proposed area | Responsibility |
|---|---|
| `apps/web/` | Angular application, shared design primitives and feature areas |
| `apps/api/` | Django project, domain modules, HTTP/realtime entry points and workers |
| `docs/specs/` | Reviewed copy of this pack with decision history |
| `docs/plans/` | Small executable subsystem plans after design review |
| `docs/runbooks/` | Local development, operations, incidents and recovery |
| `contracts/` | Machine-readable OpenAPI/event schemas generated from reviewed contracts |
| `infra/` | Local service setup and approved deployment definitions |
| `tests/e2e/` | Role/institution business journeys and browser checks |
| `tests/fixtures/` | Synthetic institution scenarios and deterministic expected outcomes |

The architecture document is authoritative for domain boundaries. Keep UI logic, domain decisions and provider adapters distinct. Do not add a second frontend framework to implement unrelated screens.

## 4. Dependency-ordered backlog

Every slice includes developer documentation and meaningful regression tests. Checks shown are work to be performed later, not completed checkboxes.

### BUILD-01 — foundation, identity and tenant context

**Depends on:** reviewed scope, roles, primary stack and initial architecture.

- [ ] Establish reproducible local setup, pinned compatible toolchain, example environment variables without secrets and health endpoints.
- [ ] Create domain foundations, custom identity/memberships and institution context with server authorization.
- [ ] Apply database/runtime isolation controls and safe tenant context in jobs/connections.
- [ ] Build login/invitation/recovery/context selection and the shared responsive shell.
- [ ] Verify cross-institution denial, permitted context switching, session revocation and accessible navigation.

**Completion evidence:** a named user can access only allowed institution context; backend and file/job access checks cannot be bypassed by changing an ID.

### BUILD-02 — platform onboarding and lifecycle

**Depends on:** BUILD-01.

- [ ] Implement institution directory, onboarding wizard, branding upload, administrator invitation and setup state.
- [ ] Provision resources idempotently; show partial failure and resumable progress.
- [ ] Implement activation/restriction/suspension/reactivation/archive with reason and audit.
- [ ] Verify suspension revokes active access while preserving authorized reconciliation/retention paths.

**Completion evidence:** System Admin creates an institution; its invited Institution Admin signs in and completes setup without manual database edits.

### BUILD-03 — configuration and delegated administration

**Depends on:** BUILD-02.

- [ ] Implement role assignments, scope, guardian/grant administration and approval restrictions.
- [ ] Implement module entitlement/enablement, inherited settings, typed fields and template versions.
- [ ] Add draft validation, impact preview, approval, scheduled effective period and rollback/supersession.
- [ ] Verify historical outcomes do not change when future configuration changes.

**Completion evidence:** institution administrators can configure supported behavior safely; disabled UI actions are also denied by the backend.

### BUILD-04 — admissions, people and imports

**Depends on:** BUILD-03.

- [ ] Implement applicant/student/employee records, document handling and authorized guardian relationships.
- [ ] Complete enquiry/application/review/offer/enrollment/withdrawal states.
- [ ] Add staged CSV/import mapping, row errors, duplicate review, provenance and reconciliation.
- [ ] Verify real student detail screens reflect persisted changes and retain history.

**Completion evidence:** synthetic pilot records for all four categories are admitted/enrolled with correct authority and traceable source data.

### BUILD-05 — academic structures for all four categories

**Depends on:** BUILD-04.

- [ ] Implement grades/sections and higher-education departments/programs/curricula/course offerings.
- [ ] Add registration windows, seats/waitlists, prerequisites, linked sections and overrides.
- [ ] Implement regulation versions, course attempts, credit equivalence and advisory degree progress.
- [ ] Add university affiliation grants and scoped academic exchange.
- [ ] Verify concurrent final-seat allocation and distinct school/college/university record behavior.

**Completion evidence:** all four academic scenarios work; university support is not merely a renamed school interface.

### BUILD-06 — timetable, teaching and attendance

**Depends on:** BUILD-05.

- [ ] Implement room/resource/instructor schedule checks, publication and substitutions.
- [ ] Implement teacher day view, assigned rosters, attendance and approved corrections.
- [ ] Implement planned offline draft/sync behavior only if selected and tested.
- [ ] Add teaching resources/assignments or an explicitly scoped LMS adapter.
- [ ] Verify attendance denominator/roster rules and institution-specific visibility.

**Completion evidence:** an assigned teacher completes attendance and a permitted guardian/student sees the correct result with clear sync state.

### BUILD-07 — assessments, results and awards

**Depends on:** BUILD-05 and relevant BUILD-06 rules.

- [ ] Implement schemes, attempts, marks entry/import, moderation and publication.
- [ ] Add school report card/promotion, college SGPA/transcript, engineering project/lab outcomes and university examination/award flow.
- [ ] Add revaluation/revision, pinned calculations, document version and public verification limits.
- [ ] Verify synthetic calculations and preservation of prior published versions.

**Completion evidence:** report cards/transcripts can be reproduced from recorded input/rule versions and revisions are auditable.

### BUILD-08 — fees, payments and reconciliation

**Depends on:** BUILD-04; can progress beside academic slices after shared identity/data contracts stabilize.

- [ ] Implement fee plans, charges, concessions, subledger, payment allocation and receipt generation.
- [ ] Implement approved provider interface, webhook validation, deduplication and reconciliation.
- [ ] Add refund/credit-note separation, manual collection, settlement exceptions and accounting export boundaries.
- [ ] Verify exact finance examples, duplicate/out-of-order events and concurrency.

**Completion evidence:** balances, receipts, refunds and settlement reports agree; an unconfigured provider produces no fake success.

### BUILD-09 — communication and teacher-led classes

**Depends on:** BUILD-03/04/05 relationships; media feasibility decision for its integration.

- [ ] Implement persistent conversations, participants, messages, attachments and notification preferences.
- [ ] Enforce teacher–guardian/staff permissions and institutional communication policy.
- [ ] Implement call invitation/state machine, device cancellation, provider tokens and revocation.
- [ ] Implement teacher-led class scheduling, admission/host controls and attendance evidence.
- [ ] Verify quiet hours, blocked/removed participants, stale pushes, provider failure and final-host departure.

**Completion evidence:** authorized users can conduct the confirmed interactions; students cannot turn a class into an unsupervised room.

### BUILD-10 — institutional operational breadth

**Depends on:** shared people, workflow, document and finance foundations.

- [ ] Library catalog/loans/returns/reservations and fines/clearance.
- [ ] Transport routes/trips/boarding/safe handover and authorized GPS adapter if selected.
- [ ] Hostel/mess allocations, leave/out-pass, occupancy and charges.
- [ ] Employee leave/attendance and the reviewed payroll engine or adapter boundary.
- [ ] Procurement, stock movements, assets, laboratory booking and maintenance.
- [ ] Student service/grievance cases, placement/internship/alumni and selected research/quality workflows.

Split this slice into separate executable subsystem plans. Each selected module needs its own end-to-end demonstration and error/permission tests. A module may be unavailable while work continues, but must not be called delivered.

### BUILD-11 — reporting, platform operations and automation

**Depends on:** operational domains; instrumentation starts earlier in each slice.

- [ ] Implement permission-aware reports, approved group aggregates, exports and scheduled jobs.
- [ ] Add database/service/queue/storage/media/integration metrics, incidents, support and quota views.
- [ ] Add actionable alerts, diagnostics, usage metering and bounded remediation workflows.
- [ ] Implement backup/restore procedures and run recovery drills in the chosen environment.

**Completion evidence:** service failure produces a useful alert; reports cannot bypass record permissions; recovery has measured evidence.

### BUILD-12 — quality, migration rehearsal and pilot readiness

**Depends on:** the reviewed first-release scope, not merely all code compiling.

- [ ] Run requirement-linked backend/API/browser tests and cross-tenant adversarial cases.
- [ ] Review representative desktop/mobile screens, keyboard/focus behavior and accessibility.
- [ ] Perform defined workload tests, security review and failure/retry/recovery exercises.
- [ ] Rehearse imports/cutover and reconcile academic/finance counts and values.
- [ ] Conduct UAT for all four institution categories using approved real rules and safe data.
- [ ] Record remaining limitations, provider dependencies and support ownership.

**Completion evidence:** the accepted scope has evidence, no concealed placeholder implementations and a controlled release plan.

### BUILD-13 — later native mobile and international expansion

**Depends on:** reviewed separate mobile/country scope and native provider feasibility.

Use the existing backend contracts and design system as inputs, not a promise of automatic frontend conversion. Validate push, locked/background calling, secure storage, permissions, low-bandwidth behavior, app-store requirements and country-specific rules. This slice is not part of web completion unless explicitly re-scoped.

## 5. Definition of done for a slice

- Scope and affected requirements are recorded.
- Real UI actions reach the backend and persist data; data shown belongs to the current authorized context.
- Role, field, object and record-state rules are enforced server-side.
- Failure, empty, loading, conflict and relevant offline/reconnect states exist.
- Audit, idempotency and history preservation are implemented where required.
- Applicable tests execute successfully, with commands/output summarized truthfully.
- Responsive behavior is checked at target and intermediate widths.
- Secrets are excluded and integration state is accurately represented.
- Setup and operator documentation are updated.
- Open external dependencies are explicit and prevent false production claims.

## 6. Build-readiness checklist

- [ ] Scope/release breadth in 01 and decision D-02 are accepted, including treatment of L2.
- [ ] Institution/affiliation boundaries and privileged authority are understood.
- [ ] Pilot academic rules are supplied or synthetic development rules are explicitly accepted for nonproduction work.
- [ ] Representative screens/design direction are reviewed; logo is supplied or a provisional wordmark is explicitly allowed.
- [ ] Stack and component defaults are accepted or replaced by a recorded choice.
- [ ] Initial data/API/permission contracts agree.
- [ ] Media/integration risks have a planned validation path; real provider capability is not assumed.
- [ ] Team/budget/capacity assumptions are recorded to the extent needed for the next slice.
- [ ] The user has asked to begin code generation against the reviewed baseline.

Missing production credentials do not necessarily prevent independent local development. Use unconfigured integrations and isolated test adapters, label their limits, and validate real services before claiming them complete.

## 7. Handoff and continuation protocol

Use [prompt.md](prompt.md) with the entire pack or the merged attachment. The receiving build session should read the manifest, identify current user direction and inspect an existing workspace before creating files.

After implementation begins, maintain a progress record with completed slice/test evidence, current files, remaining work and decisions. On a new session, read that record and repository state rather than regenerating the application. Do not declare the full project finished after a scaffold, a single attractive dashboard or a subset of the agreed scope.
