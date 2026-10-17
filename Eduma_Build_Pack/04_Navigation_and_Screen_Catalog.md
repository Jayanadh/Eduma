# Eduma — Navigation and Screen Catalog

**Version:** 0.1 · **Date:** 12 October 2026 · **Status:** Review-ready proposal, not approved design.  
**Purpose:** Define reachable workspaces and stable screen identifiers before UI implementation.  
**Related:** [Design system](05_Design_System_and_Responsive_UX.md), [representative screen specifications](06_Screen_Specs_and_Prototype_Review.md), [authority model](02_Roles_Tenancy_and_Permissions.md).

## 1. Navigation contract

Eduma is one product with distinct workspaces. A user with several assignments chooses an active institution and workspace; combining roles must not silently combine permissions across institutions. The header always identifies the active institution and, when relevant, campus, academic period and selected child. Group views display their reporting scope and explicitly granted institutions.

`institution_id` is the initial tenant boundary. Campus is a scope inside an institution. Group membership or affiliation is not permission to open another institution's records. An institution-context route is proposed as `/i/:institutionId/...`; its API counterpart uses `/api/v1/institutions/{institution_id}/...`. UUID identifiers in a URL must be authorized server-side. Platform screens use `/platform/...`; group screens use `/groups/:groupId/...` with explicit grants. Routes below are UI proposals, not implemented endpoints.

The applicant entry route `/apply/{institution_slug}/...` identifies an institution's published admissions information. The slug grants no access to application data. Saving, submitting or opening `/apply/{institution_slug}/applications/{application_id}` requires an authenticated applicant or specifically authorized applicant guardian linked to that application UUID. This applicant relationship does not require an enrolled Student record or grant ordinary staff/student membership rights. Staff review remains a distinct authorized mode of SCR-017.

Navigation exposes entitled modules and allowed tasks. An invisible menu is only a usability behavior: authorization still governs direct routes, requests, exports and downloads. If a user once had access and follows an old bookmark, show a neutral unavailable/access-denied page without disclosing confidential record names. If access changes during editing, preserve only a safe recoverable draft under the retention policy and block submission.

Use six or fewer top-level menu groups in most role workspaces. Secondary pages appear under the selected group. A contextual page title and breadcrumb explain location; a single clearly named primary action explains the main task. Favorites and recent items are optional personal conveniences and obey current access checks.

## 2. Workspace menus

| Workspace | Proposed main navigation | Landing priority |
|---|---|---|
| System Admin | Overview; Institutions; Operations; Usage & Plans; Support; Audit & Access | Onboarding exceptions and actionable platform incidents |
| Institution Admin | Home; People; Academics; Finance; Communication; Administration | Setup gaps, approvals, deadlines and failed jobs |
| Group/university management | Overview; Institutions; Academic Exchange; Reports; Approvals; Access | Scope-specific consolidated figures and pending submissions |
| Teacher/faculty | Today; Teaching; Attendance; Assessments; Messages; Classes | Next session, unsubmitted attendance, marking deadlines |
| Parent/guardian | Home; Progress; Fees; Messages; Services | Tasks for selected authorized child, then information |
| Student | Home; Learning; Timetable; Academics; Fees; Services | Own deadlines, published records and teacher-led classes |
| Finance | Collection; Accounts; Reconciliation; Approvals; Reports | Exceptions, pending settlement and approved collections |
| Examination office | Exams; Evaluation; Moderation; Publication; Records | Controlled preparation and publication work queues |
| Applicant | Application; Documents; Status; Payments; Help | Next application task and explicit submission state |
| Service/case officer | Queue; Assigned Cases; Escalations; Reports | Assigned cases and policy-governed deadlines, with confidential fields restricted |

Labels follow institution terminology without redefining entities: a school sees grade/section while a college sees program/course offering. Administrator-configured labels are length-limited and previewed in menus; they cannot rename a dangerous action to hide its meaning. A teacher's workspace may include a mentor task only for assigned cohorts. Student messaging has no general peer directory or self-created calling rooms in the proposed launch scope.

Parent/student notices remain reachable from Home and its notification center. Services opens the user's permitted requests in SCR-049. Institution staff reach case queues under People/Administration; an Institution Admin title alone does not open confidential cases.

## 3. Screen inventory

The catalog contains **49 screen areas**, several with list/detail/create modes. It is not an estimate of component count. **L1** is the proposed first implementation sequence for common and sector-specific core workflows. **L2** follows with operational breadth; these labels are build order, not approved exclusions from the complete web product. A narrower launch requires the user's explicit scope decision. **L3** denotes later native mobile work. **P** means phone-first task; **R** means responsive; **W** means complex desktop workspace with a useful phone summary and necessary approval/detail actions. W does not excuse inaccessible forms or prevent phone users from viewing their own records.

| ID | Screen / route after context prefix | Audience and primary task | Device | Stage / requirement family |
|---|---|---|---|---|
| SCR-001 | Access `/auth/...` | Sign in, accept invitation, MFA, recovery | R | L1 · REQ-ACL |
| SCR-002 | Context chooser `/select-context` | Choose authorized institution/workspace | P | L1 · REQ-TEN |
| SCR-003 | Profile `/me` | Sessions, preferences, contact verification | P | L1 · REQ-ACL |
| SCR-004 | Platform overview `/platform/overview` | System Admin identifies urgent work | W | L1 · REQ-OPS |
| SCR-005 | Institution directory `/platform/institutions` | Find institution and onboarding status | R | L1 · REQ-ONB |
| SCR-006 | Onboarding `/platform/institutions/new` | System Admin creates institution and invites admin | R | L1 · REQ-ONB |
| SCR-007 | Institution lifecycle `/platform/institutions/:id` | Review, activate, suspend or restore with reason | R | L1 · REQ-ONB |
| SCR-008 | Health `/platform/operations` | Investigate API, database, queue and storage signals | W | L1 · REQ-OPS |
| SCR-009 | Usage/plans `/platform/usage` | Review quotas, subscriptions and entitlement changes | W | L1 · REQ-CFG |
| SCR-010 | Support/audit `/platform/support` | Open approved support session and inspect scoped events | W | L1 · REQ-ACL + REQ-OPS |
| SCR-011 | Institution home `/home` | Prioritize institution setup and operations | R | L1 · REQ-UX |
| SCR-012 | Setup `/settings/setup` | Institution Admin completes profile, branding and academic period | R | L1 · REQ-CFG |
| SCR-013 | Features/configuration `/settings/features` | Preview, publish and inspect effective settings | W | L1 · REQ-CFG |
| SCR-014 | Users/roles `/settings/access` | Invite users and assign allowed scoped roles | W | L1 · REQ-ACL |
| SCR-015 | Organization/grants `/settings/organization` | Manage campuses and explicit group/affiliation grants | W | L1 · REQ-TEN |
| SCR-016 | Admissions `/admissions` | Monitor intake, applications and available seats | R | L1 · REQ-ADM |
| SCR-017 | Applicant self-service `/apply/{institution_slug}/...`; staff review `/admissions/:applicationId` | Applicant manages own draft/documents/submission/offer; staff independently verifies and approves admission | R | L1 · REQ-ADM |
| SCR-018 | Student directory `/students` | Search and filter authorized student records | R | L1 · REQ-ACA |
| SCR-019 | Student record `/students/:studentId` | View permitted identity, enrollments and history | R | L1 · REQ-ACA |
| SCR-020 | Guardian links `/students/:studentId/guardians` | Verify relationships and separately grant access | R | L1 · REQ-ACL |
| SCR-021 | Academic setup `/academics/structure` | Define periods, curricula, grades/programs and offerings | W | L1 · REQ-ACA |
| SCR-022 | Timetable `/academics/timetable` | Allocate sessions, rooms and substitutions | W | L1 · REQ-ACA |
| SCR-023 | Teacher home `/teaching/today` | Open assigned sessions and pending work | P | L1 · REQ-UX |
| SCR-024 | Attendance `/attendance/:sessionId` | Mark, submit and request corrections | P | L1 · REQ-ATT |
| SCR-025 | Learning `/learning/:offeringId` | Publish materials/assignments, submit work | R | L1 core · REQ-ACA |
| SCR-026 | Examination setup `/exams` | Define assessment, eligibility and schedules | W | L1 · REQ-EXM |
| SCR-027 | Marks/results `/exams/:examId/results` | Enter, moderate, approve and publish results | W | L1 · REQ-EXM |
| SCR-028 | Course registration `/academics/registration` | Select eligible offerings and confirm registration | R | L1 HE · REQ-ACA |
| SCR-029 | Degree/progression `/academics/progression` | Review credits, attempts, promotion and award eligibility | R | L1 · REQ-ACA |
| SCR-030 | Engineering outcomes `/academics/outcomes` | Record lab/project rubrics and inspect outcome evidence | W | L1 engineering · REQ-ACA + REQ-EXM |
| SCR-031 | Affiliation exchange `/academics/exchanges` | Submit/review approved central-exam and award data | W | L1 university · REQ-TEN + REQ-EXM |
| SCR-032 | Fee plans/accounts `/finance/accounts` | Define charges and review student balances | W | L1 · REQ-FIN |
| SCR-033 | Collection `/finance/collect/:accountId` | Collect against valid dues and issue confirmed receipt | R | L1 · REQ-FIN |
| SCR-034 | Reconciliation/refunds `/finance/reconciliation` | Resolve unmatched events and approve corrections | W | L1 · REQ-FIN |
| SCR-035 | Parent home `/family/home` | Select child, review tasks and contact assigned teacher | P | L1 · REQ-UX + REQ-COM |
| SCR-036 | Student home `/student/home` | See own classes, tasks, dues and published results | P | L1 · REQ-UX |
| SCR-037 | Inbox `/communication/messages` | Teacher-parent/staff conversation and scoped attachments | P | L1 · REQ-COM |
| SCR-038 | Call `/communication/calls/:callId` | Request/receive authorized call and handle reconnect | P | L1 · REQ-COM |
| SCR-039 | Live classes `/communication/classes` | Teacher schedules/hosts; students join assigned class | P | L1 · REQ-COM |
| SCR-040 | Notices `/communication/notices` | Compose approved announcement and review delivery | R | L1 · REQ-COM |
| SCR-041 | Reports `/reports` | View scoped reports with filters and provenance | W | L1 core · REQ-OPS |
| SCR-042 | Data transfer `/settings/data` | Map imports, review dry run and retrieve permitted exports | W | L1 · REQ-MIG |
| SCR-043 | Library `/library` | Catalog, circulation, reservations and fines | R | L2 · REQ-OPS |
| SCR-044 | Transport `/transport` | Routes, roster, trips and authorized handover | R | L2 · REQ-OPS |
| SCR-045 | Hostel/mess `/residence` | Allocation, leave, meals and issues | R | L2 · REQ-OPS |
| SCR-046 | HR/payroll `/people/employees` | Employee lifecycle, leave and payroll handoff | W | L2 · REQ-OPS |
| SCR-047 | Assets/procurement `/operations/assets`; laboratory booking `/operations/labs/bookings` | Assets, stores, purchasing, maintenance and authorized laboratory-resource bookings | W | L2 · REQ-OPS |
| SCR-048 | Institutional development `/institutional-development` | Placement, alumni, accreditation and research work queues | W | L2 · REQ-OPS |
| SCR-049 | Service requests and restricted cases `/services/cases` | Requester sees own authorized cases; assigned staff triage, resolve and process appeals | R | L2 · REQ-OPS + REQ-ACL |

Do not show unimplemented modules as working features. A module in progress may appear in a clearly labelled availability/settings area, never as a populated fake operational dashboard. L2 task patterns are specified in the companion screen document; institution-specific details must be resolved before their implementation. Their placement later in build order does not remove them from the requested complete product.

## 4. Connected journey coverage

| Journey | Screen sequence | Required exception |
|---|---|---|
| Platform onboarding | 005 → 006 → 007 → 001 → 012 → 011 | Duplicate institution; expired invitation; incomplete activation |
| School daily work | 023 → 022 → 024 → 019 → 037 | Absent child; correction after attendance lock |
| Admissions to fees | 016 → 017 → 019 → 032 → 033 | Duplicate applicant; waitlist; pending payment |
| Applicant self-service | 017 public information → 001 → 017 own application → 017 staff review | Unauthorized application UUID; missing document; expired offer |
| College registration | 036 → 028 → 022 → 029 | Prerequisite, capacity or timetable conflict |
| Engineering evidence | 025 → 030 → 027 → 029 | Missing rubric evidence; repeat attempt; invalid weight total |
| University examination | 015 → 031 → 026 → 027 → 029 | Grant expiry; rejected batch; corrected award submission |
| Parent contact | 035 → 037 → 038 | Restricted relationship; quiet hours; recipient unavailable |
| Teacher-led online class | 023 → 039 → 024 | Waiting room; teacher disconnect; attendance review |
| Finance exception | 033 → 034 → 041 | Duplicate callback; uncertain status; refund approval conflict |
| Student service request | 036/035 → 049 own request → 049 assigned queue → 049 outcome/appeal | Restricted case note; reassignment; expired appeal window |
| Laboratory booking | 047 resource availability → 047 request/review → 022 scheduled session | Concurrent reservation; maintenance block; unmet safety prerequisite |

Numbers in this table abbreviate the stable `SCR-` identifiers. Preserve origin context when returning from details. A notification opens a current authorized state, not an obsolete action taken directly from notification text. The browser Back action restores safe filters and scroll location; it must not resubmit a payment, publication or configuration change.

## 5. Search, notifications and work queues

Institution search remains within the active institution by default. A separately granted group search labels every result's institution and requires a deliberate context switch before editing. Do not expose counseling notes, private message content or hidden academic results through generic search. Display scope, result count and applied filters; empty results distinguish “no matching records” from “no records yet” without leaking restricted counts.

Notifications have read state, event time, institution, subject and safe destination. Batch similar routine notifications where useful; urgent notices require clear purpose and an accessible text label. A notification read receipt is not legal consent or evidence that an academic instruction was understood. Separate announcements from personal messages and approval queues.

Work queues explain why an item needs attention, the permitted next action, due date and owner. Counts are scoped and timestamped; unavailable data shows “Unavailable” rather than zero. A financial total states currency, period and whether it measures assessed, received or settled amounts.

## 6. Review and handoff conditions

Before UI implementation, check every L1 requirement against a screen or justified background process. Review at least one connected journey per institution type with a representative user. Check a parent with children in different institutions, a faculty member with multiple roles, revoked group access and an inactive institution. Confirm that active academic period and institution are visible during sensitive actions.

The catalog is ready for review when all L1 routes have a defined audience, permission scope, primary task, responsive pattern and state owner. It becomes accepted only when review evidence records actual decisions. These Markdown descriptions are not rendered wireframes or proof that users can complete the tasks.

For focus behavior and native semantic elements, implementation should follow the [Angular accessibility guidance](https://angular.dev/best-practices/a11y), verified 12 October 2026. Route transitions must update title and focus deliberately; accessibility still requires testing of the assembled application.
