# Eduma — Predevelopment Decision Register

**Prepared:** 12 October 2026  
**Status:** Initial planning register. Proposed answers are not approvals.  
**Related documents:** `Eduma_Predevelopment_Plan.md` and `Eduma_Enterprise_ERP_Knowledge_Document.md`.

## 1. Confirmed context

These points were provided directly in this conversation:

| ID | Decision | Status |
|---|---|---|
| C-01 | Product name is Eduma | Confirmed |
| C-02 | India first, with international expansion | Confirmed |
| C-03 | Schools, colleges, engineering colleges and universities are initial institution categories | Confirmed |
| C-04 | Support groups, campuses and affiliated colleges | Confirmed |
| C-05 | System Admin handles central onboarding and platform operations; Institution Admin manages institutional operations and features | Confirmed |
| C-06 | Teacher–parent and staff messaging/calling; teacher-conducted student meetings controlled by institutional policy | Confirmed |
| C-07 | Web first, Android/iOS later | Confirmed |
| C-08 | Planning and review precede application generation | Confirmed |
| C-09 | Logo will be provided after clarity | Confirmed |

Angular + Django + PostgreSQL remains the user's proposed stack and the knowledge document's recommendation. Detailed versions, libraries, hosting and mobile framework are not yet approved architecture decisions.

## 2. First decisions to work through

We should discuss these in small groups while drafting the PRD, rather than ask for every answer at once. “Decide by” means the planning stage that needs the answer, not an imposed calendar deadline.

| ID | Decision needed | Proposed starting position | Status | Decide by | Suggested owner |
|---|---|---|---|---|---|
| D-01 | Which concrete school boards, college regulations, engineering programs and university models represent launch? | Use one representative pilot scenario for each category, then expand the matrix | Open | PRD/workflow review | Product owner + academic representatives |
| D-02 | Which modules must be complete at first launch for each category? | Agree complete common workflows plus the necessary sector-specific ones; explicitly list optional modules | Open | Scope review | Product owner |
| D-03 | What is the expected initial and next-stage scale? | Record institutions, enrollments, active/concurrent users and concurrent class participants separately | Open | Architecture/cost review | Product owner + engineering |
| D-04 | Which visual references, tone and information density suit Eduma? | Review calm professional directions with task-focused dashboards and readable data tables | Open | Visual-direction review | Product owner + design |
| D-05 | Which launch languages, devices and accessibility needs matter most? | Responsive English-first draft for discussion; language coverage remains unconfirmed | Open | Screen/design review | Product owner + pilot users |
| D-06 | What team, budget and desired launch window are available? | Estimate delivery only after the first-release scope and key dependencies are known | Open | Delivery planning | Product owner |

## 3. Decisions to resolve as specifications develop

| ID | Decision needed | Proposed starting position | Status | Decide by | Suggested owner |
|---|---|---|---|---|---|
| D-07 | Which group/university units are separate data/contractual tenants? | Independent governance generally implies separate tenancy with explicit affiliation grants | Proposed | Role/tenancy review | Product owner + institution/legal representatives |
| D-08 | How much branding may institutions change? | Institution logo and controlled accent/theme tokens; preserve shared interaction and accessibility rules | Proposed | Design system review | Product owner + design |
| D-09 | One Eduma mobile application or separate branded applications? | One app with secure institution/role switching initially | Proposed | Client architecture review | Product owner + mobile engineering |
| D-10 | Which component library/design approach should Angular use? | Evaluate candidates against approved table/form/navigation needs, accessibility, theming and licensing | Open | Design/technical review | Design + frontend engineering |
| D-11 | Full accounting/payroll engines or integrations? | Fee subledger and reconciliation as core; evaluate specialist integrations for deeper finance/payroll | Proposed | Module/API scope review | Product owner + finance representative |
| D-12 | Which payment, messaging, LMS and media providers are required or already available? | Shortlist using functionality, authorized access, cost, privacy and operational support | Open | Integration review | Product owner + engineering |
| D-13 | What call recording and class recording policy is required? | Recording off unless a purpose-specific approved policy and controls exist | Proposed | Communication/privacy review | Institution policy owner + privacy/design |
| D-14 | What residency, retention and recovery requirements will be promised? | Document by data category and contract; validate backup/restore objectives before commitments | Open | Security/operations review | Product owner + operations/privacy |
| D-15 | What are the safe limits of configurable academic and finance rules? | Typed, versioned rules with preview, approval and preserved historical outcomes | Proposed | Workflow/configuration review | Academic/finance owners + engineering |
| D-16 | Which institution sample documents and legacy data formats need support? | Collect blank/redacted examples and create synthetic migration fixtures | Open | Workflow/migration review | Institution representatives |
| D-17 | What support coverage and service targets are affordable? | Define business hours, escalation, incident ownership and service tier before contracting | Open | Operations/cost review | Product owner + operations |
| D-18 | Will dark mode be included in the first release? | Prioritize one complete accessible theme; include a second theme if explicitly scoped and tested | Proposed | Design scope review | Product owner + design |

## 4. Technical assumptions requiring evidence

| ID | Assumption to verify | Evidence required | Current state |
|---|---|---|---|
| T-01 | Proposed tenancy approach isolates every access path | Architecture review followed by API/job/file/WebSocket isolation tests during implementation | Not validated |
| T-02 | Proposed mobile approach supports reliable incoming calls | SDK compatibility review and later device/network/OS-state prototype | Not validated |
| T-03 | Fee processing tolerates duplicate/out-of-order provider events | Contract/state-machine review and later reconciliation/idempotency tests | Not validated |
| T-04 | Academic model handles all launch pilot rules | Worked school/college/engineering/university cases and independently checked expected results | Not validated |
| T-05 | Government/institution integrations are accessible | Official documentation plus required authorization/provider/institution access | Not validated |
| T-06 | Hosting design meets target capacity and recovery | Sizing assumptions, cost review, later load tests and restore drill | Not validated |
| T-07 | Chosen UI components support Eduma's complex responsive workflows | Representative table, form, timetable and accessibility evaluation | Not validated |

None of these rows means a prototype, test, account or integration already exists. Evidence should state what was actually evaluated, which conditions were used, and any limitations.

## 5. Record format for a resolved decision

For each material decision, record:

- ID and question.
- Options considered and chosen option.
- Reason and tradeoffs.
- Confirming owner and date/evidence.
- Affected requirements, screens, data entities, interfaces and tests.
- Conditions that would justify revisiting it.

Do not mark a proposal approved because time has passed or a draft was generated. When the user changes a decision, preserve the previous entry as superseded and update the affected documents.
