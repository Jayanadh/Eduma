# Eduma — Screen Specifications and Prototype Review

**Version:** 0.1 · **Date:** 12 October 2026 · **Status:** Review-ready written specification.  
**Evidence boundary:** These are task, layout and state specifications. No clickable prototype, rendered design, visual approval or application exists as evidence in this document.  
**Related:** [Screen catalog](04_Navigation_and_Screen_Catalog.md), [design system](05_Design_System_and_Responsive_UX.md), [business rules](03_Workflows_and_Business_Rules.md), [test plan](11_Test_UAT_and_Migration.md).

## 1. Rules shared by all screens

All data and actions use the current authorized institution and scope. Action permissions use the canonical `<resource>.<action>` registry in [02](02_Roles_Tenancy_and_Permissions.md); the representative mappings below must not be replaced with role-name checks or alternate permission names. UI availability never grants access. APIs under `/api/v1/institutions/{institution_id}/...` validate identity, entitlement, scope, relationship and record state independently. Mutating an existing record submits its integer `version`; conflicts require deliberate review.

Every screen supports loading, populated, no records, no matching results, validation failure, server failure, access denied and session expired states. Relevant screens additionally specify read-only, offline, stale data and reconnect states. Preserve recoverable draft input where policy allows, but do not persist sensitive student/financial data in browser storage by default. Field-level errors reference the visible label. Financial, publication and bulk actions include review of their actual effect.

The 15 walkthroughs below cover representative connected tasks. They establish reusable behavior, not a claim that every sector rule or future screen state is finally approved. L1 and L2 denote proposed build order; all listed web areas remain part of the intended complete product until an explicit scope change.

### Representative action-to-permission mapping

Each entry identifies action authority, not blanket read access to every field on the page. All relationships, scopes, separation of duties and state restrictions in [02](02_Roles_Tenancy_and_Permissions.md) still apply. Other screen actions must use their separately registered permission; do not infer them from a nearby allowed action.

| Screen group / action | Canonical permission | Additional boundary |
|---|---|---|
| SCR-006 create; SCR-007 activate/suspend | `institution.create`; `institution.activate`; `institution.suspend` | Platform authority and named-institution lifecycle checks |
| SCR-008 view health | `platform_health.read` | Redacted platform diagnostics |
| SCR-009 change entitlement; SCR-012 branding | `entitlement.update`; `institution_brand.update` | Platform entitlement ownership versus institutional branding authority |
| SCR-014 edit role / assign membership | `role.manage`; `membership.assign` | Grant ceiling; prevent escalation and last-admin removal |
| SCR-015 approve affiliation access | `affiliation_grant.approve` | Named parties, fields, purpose and validity |
| SCR-017 applicant read/edit/submit/accept | `application.own_view`; `application.own_edit`; `application.own_submit`; `application.own_accept` | Authenticated application owner or explicitly authorized applicant guardian; state-specific edits |
| SCR-017 staff final admission approval | `admission.approve` | Assigned campaign/program; separate from the applicant's offer acceptance |
| SCR-018/019 read/update student | `student.read`; `student.update` | Assigned students and allowed fields; own/guardian views also require their relationship scope |
| SCR-024 submit/correct attendance | `attendance.submit`; `attendance.correct` | Assigned session and submission/correction workflow |
| SCR-027/030 enter marks; SCR-027 verify/publish results | `mark.enter`; `result.verify`; `result.publish` | Assigned assessment and separate official publication authority |
| SCR-028 approve registration or override | `course_registration.approve` | Authorized academic role; student course selection does not grant this approval |
| SCR-032 charge; SCR-033 record payment; SCR-034 approve refund | `fee_charge.issue`; `fee_payment.record`; `fee_refund.approve` | Finance authority and maker/checker rules; payer checkout is not manual posting authority |
| SCR-037 send; SCR-038 initiate call | `message.send`; `call.initiate` | Authorized teacher-parent or staff relationship and communication policy |
| SCR-039 host / join | `meeting.host`; `meeting.join` | Assigned host or enrolled/invited participant; no unrestricted student room creation |
| SCR-041/042 export report | `report.export` | Authorized data/fields; recheck at generation and download |
| SCR-049 request/read/update case | `service_case.create`; `service_case.read`; `service_case.update` | Own permitted case or assigned case role; confidential fields independently scoped |
| SCR-049 assign/resolve/appeal | `service_case.assign`; `service_case.resolve`; `service_case.appeal` | Triage/resolution authority or eligible requester appeal; not a general private-message channel |

## 2. Fifteen representative walkthroughs

### 1. Access and institution selection — SCR-001/002

**Task:** A user accepts an institution invitation or signs in and chooses an authorized workspace. Invitation contains institution, invited contact and proposed role; acceptance never grants extra scope from client fields. Inputs are verified identifier, authentication challenge and required security setup. Recovery responses avoid revealing whether an account exists. MFA applies to privileged users under the access policy.

**Layout:** Centered narrow form; institution invitation context above fields; help/recovery below. On phone, controls remain above the keyboard and labels stay visible. After authentication, show only valid memberships, institution name/type and role summary. One membership can open directly; switching context clears incompatible filters and in-memory records.

**States/check:** Expired/revoked/used invitation has a safe recovery path; suspended institution shows its permitted service state. An expired invitation cannot create a membership. Verify a user with two institutions never opens the second institution's last-viewed student in the first context.

### 2. System Admin institution directory — SCR-005

**Task:** An onboarding operator locates institutions needing action. Columns: institution name, type, group, lifecycle state, onboarding progress, last activity and assigned operator. Filters: type, state, group and onboarding exception; default ordering is actionable recent work. Primary action: “Add institution”. Row opens SCR-007; bulk suspension is not an ordinary list shortcut.

**Layout:** Page title/action, search/filter bar, summary of selected scope, table, pagination. Phone cards prioritize name/type/state and a details link. Empty first-use state offers onboarding; no matches offers filter reset. Loading never substitutes zero institutions for unknown count.

**Validation/check:** Search and pagination retain scope; returned counts obey operator grants. Institution names are not unique identifiers. Verify long names, duplicate display names, a failed onboarding job and revoked operator access.

### 3. Institution onboarding and activation — SCR-006/007

**Task:** System Admin creates the tenant, uploads initial branding, provides Institution Admin details and invites the admin. Steps: identity/type and location; campuses/group relationship; initial images; entitled modules; admin invitation; review. Fields include legal/display name, institution type, country, timezone, primary campus, contact email, admin name/contact and applicable identifiers. Show board/UDISE/AISHE or affiliation identifiers only where relevant; do not require all identifiers for all types.

**Layout:** Step list with saved status and main form; on phone use current step/total and forward/back controls. Review displays all effects and unresolved requirements. Save draft differs from creating an active institution. Images show uploaded, scanning, accepted or rejected states.

**Validation/check:** Duplicate checks use institution identifiers and a human review path; email verification is not a personal identity guarantee. Invitation retry does not create another tenant. Activation requires the agreed checklist. Suspension requires reason, impact preview and authorized reauthentication, without deleting records or silently dropping pending financial reconciliation.

### 4. Platform health and incident detail — SCR-008

**Task:** Operations staff distinguish an actionable incident from missing telemetry. Show API availability/latency/error rate, database connectivity/replication/storage, worker/queue age, object storage, media provider and integration health. Each tile contains observation time, environment, threshold and source. An incident detail shows timeline, affected services/tenants, owner and runbook reference.

**Layout:** Incident banner, service table, selected time window, detail panel. Phone prioritizes active incidents and key readings, with graphs behind detail. Actions are acknowledge, assign and permitted remediation workflow; no arbitrary shell command box or database browser.

**States/check:** Unknown telemetry is gray “Unknown”, not healthy green. Partial failure leaves independent metrics usable. Stale metrics show their age. Secret values, raw student data and message bodies never enter this UI. Test dependency outage, recovery, missing heartbeat and insufficient operator privilege.

### 5. Institution home and configuration — SCR-011/012/013

**Task:** Institution Admin completes setup and changes available features. Home shows setup progress, pending approvals, academic deadlines and domain exceptions with links. Configuration shows entitlement, enabled state, inherited source, effective value and change history. Inputs include institutional branding, calendar, academic labels, feature settings and notification rules.

**Layout:** Task-focused home; configuration has category navigation, editor and effective-value preview. Phone uses sections and a final review page. Actions: save draft, validate, preview impact, request approval where required, publish version and inspect history.

**Validation/check:** Validate typed values, dependencies, allowed override scope and effective dates. Disabling fees cannot erase receipts; changing grading rules cannot rewrite published results. Concurrent edits show a version conflict. A failed publish retains the previous effective configuration and a recoverable draft. Verify inherited settings, locked entitlement, invalid color contrast and a scheduled future change.

### 6. Roles, campuses and cross-institution grants — SCR-014/015

**Task:** Institution Admin invites staff and delegates scope; authorized group management receives explicit cross-institution grants. Inputs: verified user, role template, campus/department/record relationship, start/end time and reason. Grant review lists actions and data categories actually exposed, including export separately. Affiliation is displayed as a relationship independent from its grants.

**Layout:** User list and assignment detail; readable permission categories with current/proposed comparison. Phone reviews one assignment at a time instead of shrinking a permission matrix. Actions include invite, assign, revoke and access review.

**Validation/check:** Prevent self-escalation, removal of the last viable Institution Admin and prohibited duty conflicts. A school-wide assignment cannot be inferred from a teaching role. Expired grants show inactive status. Save conflict requires refreshed comparison. Test an affiliated college with result-submission permission but no access to the university's private messages or unrelated student details.

### 7. Student directory, record and guardian links — SCR-018/019/020

**Task:** Authorized staff finds a student and manages permitted identity/enrollment fields. Filters include campus, academic period, grade/program, cohort and enrollment state. Detail separates identity from each enrollment, with tabs/sections for academic history, attendance, fees and documents according to access. Sensitive categories are separate restricted areas.

**Layout:** Searchable directory, then record heading with enrollment context and relevant actions. Phone shows identity and current enrollment before historical sections. Guardian editing records relationship, verification state and specific allowed access; paying fees does not automatically authorize academic or communication access.

**Validation/check:** Detect possible duplicates without auto-merging people. Required fields vary through approved templates; birth date is not a timezone timestamp. Revoked guardian access immediately removes related content. Adult-student access follows an explicitly approved authorization rule. Failures preserve authorized edits; audit shows changes without exposing restricted former values to an unauthorized viewer.

### 8. Teacher attendance — SCR-024

**Task:** Assigned teacher records attendance for a scheduled session. Header: offering/section, date/time, campus and roster version. Rows: roll/identifier, name, status and permitted short note. Configured statuses have explicit meanings; unmarked is not absent. Actions: mark selected/all present, edit exceptions, save draft, review and submit; correction follows the lock policy.

**Layout:** Roster list with visible counts and keyboard-friendly status controls. Phone provides large per-student actions and search; a sticky summary must not obscure the last row. Bulk defaulting requires review of remaining exceptions.

**Validation/check:** Reject unassigned sessions, duplicate submission and invalid dates. New roster changes require reconciliation. Offline UI indicates unsent work; no promise of durable offline storage unless separately implemented and approved. Test two teachers editing, network loss after submission and locked-session correction without duplicate attendance rows.

### 9. Collection and reconciliation — SCR-033/034

**Task:** Finance officer or authorized payer settles valid dues; finance reviews provider exceptions. Collection fields: student/account, invoice lines, amounts, currency, mode and reference. Show allocation and remaining balance before commitment. Online provider handling may use approved hosted payment UI; Eduma does not ask users to type card credentials into custom ERP fields.

**Layout:** Outstanding items, allocation panel and review summary. Phone shows one clear amount/action; after return, display authoritative status and a “Check status” action for uncertain cases. Reconciliation table compares expected payment, provider event and bank settlement separately. Refund is a request/review workflow with reason and remaining refundable amount.

**Validation/check:** Decimal currency precision, allocation limits, concessions and refund totals follow approved rules. Pending is not success. Do not encourage immediate repay after a timeout. Duplicate/out-of-order events must not issue duplicate receipts; posted receipts use correction/reversal history. Confirm the user initiating a refund cannot approve it when separation of duties applies.

### 10. Assessment, moderation and publication — SCR-026/027

**Task:** Evaluator enters assigned marks; moderator reviews exceptions; exam authority publishes. Inputs: assessment component, maximum mark, attempt, grade/rubric and authorized absence/exemption code. Display approved scheme/version and lock state. School reports and higher-education results use the appropriate academic rules rather than a universal averaging formula.

**Layout:** Desktop marks grid with keyboard navigation and sticky identifiers; phone individual-student editor. Review page lists missing marks, invalid ranges, rule version, expected publication audience and sign-off. Actions are save draft, submit, return for correction, approve and publish according to role.

**Validation/check:** Missing differs from zero and absent. Marks cannot exceed allowed bounds. Weights/rounding follow the approved scheme; published versions remain immutable with explicit amendment process. Submission never equals publication. Test stale edits, partial import failure, embargo, revaluation and publication retry without duplicate records or notices.

### 11. College registration and degree progress — SCR-028/029

**Task:** Student chooses term offerings against the applicable regulation; academic adviser handles permitted exceptions. Display course code/name, credits, prerequisites, schedule, capacity, requirement category and prior attempts. Review shows selected load, conflicts and effect on degree requirements. Degree progress distinguishes completed, in progress, planned and unmet credits.

**Layout:** Course finder beside selection summary on desktop; phone alternates finder/selection with persistent count. Confirm is explicit and returns a registration record; a visual selection alone reserves no seat.

**Validation/check:** Server checks current capacity and timetable conflict at commit, plus prerequisites and limits. Override requests carry reason and authorized approval; no hidden bypass checkbox. Repeat courses show the applicable counting rule. A failed confirmation retains candidate choices but labels them unconfirmed. Test last-seat race, repeated course, dropped course and academic hold.

### 12. Engineering lab/project and outcome evidence — SCR-030

**Task:** Faculty records lab/project assessment; coordinator reviews outcome evidence. Inputs: offering, student/team, rubric criterion, score, assessor, evidence file and mapped course/program outcome. Display regulation, approved weights and calculation method. Team membership and each student's contribution remain explicit.

**Layout:** Rubric/evidence entry with side summary; phone supports one criterion at a time and file capture/upload subject to policy. Aggregate view offers table drill-down to underlying assessments. Actions: draft, submit, review, return and publish authorized evidence/report.

**Validation/check:** Prevent invalid weight totals, unmapped required criteria and missing required evidence. Distinguish no assessment evidence from zero attainment. Failed upload does not count as evidence. An outcome graph is not proof of accreditation compliance. Review a shared project with individual marks, repeat assessment and a changed rubric version without altering historical outcomes.

### 13. University affiliation exchange — SCR-031

**Task:** Affiliated college submits an approved batch for central examination or award; university reviewer validates and accepts/returns it. Show source/destination institutions, governing relationship, grant expiry, purpose, permitted fields, regulation and submission version. Preview shows exactly what will cross the tenant boundary.

**Layout:** Submission work queue, batch summary and validation error table. Phone supports status/review decisions and record detail; extensive batch mapping is a desktop task. Actions: validate, submit, receive, reject with reasons, correct and resubmit.

**Validation/check:** Recheck grants on submit and download; affiliation alone is insufficient. Partial rejection produces row-level correction guidance without replacing accepted records silently. Retries preserve batch identity. Test expired grant, wrong curriculum version, duplicate batch, revoked access after submission and a corrected award record with history.

### 14. Parent home — SCR-035

**Task:** Guardian sees relevant actions for an explicitly linked child. Header shows selected child and institution; cards summarize attendance exceptions, pending dues, upcoming classes/meetings and published progress. Prioritize due actions over charts. Contact options list only authorized teachers and current availability.

**Layout:** Phone-first chronological tasks and compact service links; desktop adds secondary progress and notices. Switching child across institutions changes the full context and clears previous child's sensitive content. Payment, teacher contact and acknowledgment are separate named actions.

**Validation/check:** Hide inaccessible categories without showing suggestive counts. A removed relationship produces a neutral access update. Adult-student restrictions are enforced independently from fee-payer status. Test two children in different institutions, one disabled communication entitlement, overdue but disputed fee and delayed progress data.

### 15. Messages, calls and teacher-led classes — SCR-037/038/039

**Task:** Authorized teacher-parent and staff participants communicate; students join assigned teacher-led classes under policy. Composer has recipient context, message, attachment and send status. Calls show recipient, media permissions, availability and explicit accept/decline/end. Classes show host, offering, schedule/timezone, roster and policy. Students cannot create open calling rooms or initiate unrestricted direct calls in this baseline.

**Layout:** Desktop inbox has list/thread; phone a single focused thread with keyboard-safe composer. Call controls remain labelled and reachable. Class UI provides waiting room, roster, raise hand, captions where supported, permitted chat and distinct “Leave”/“End for everyone” actions for the host.

**Validation/check:** Messages distinguish queued, accepted, failed and optional read states. Retry preserves message identity. Recheck participant membership and policy when joining/reconnecting. Quiet hours show next permitted contact action. Recording is off by default and never hidden; enabling requires the separately approved policy. Test blocked microphone, teacher disconnect, connection loss, revoked membership, rejected attachment and call missed/declined/busy states. Provider/browser mobile limits remain to be validated; a web mockup proves no native incoming-call reliability.

## 3. Applicant self-service and operational screen patterns

### Applicant self-service mode — SCR-017

The public route `/apply/{institution_slug}/...` displays only published admission-cycle information, available programs/grades, deadlines and help. The institution slug is a locator, never an access credential. Creating/saving a draft or opening `/apply/{institution_slug}/applications/{application_id}` authenticates the applicant and checks ownership or an explicitly verified applicant-guardian relationship for that UUID. Applicants can exist before enrollment and receive no ordinary student/staff authority through this flow.

Inputs are the approved cycle-specific form fields, selected program/grade/campus, required documents, applicant contact and acknowledgments. A sectioned form shows draft/submitted state, saved time, missing items and next action; phone uses one column and resumable sections. Actions are save draft, upload/replace permitted documents, review, submit, respond to a specific information request and accept a valid offer. Admission-payment status links to the authorized payment workflow; a successful browser redirect alone does not enroll the applicant or confirm funds.

Validation checks cycle/deadline, eligibility fields, document processing, permitted edits and current offer version/expiry. Submitted versions remain preserved; staff-requested corrections affect only reopened fields and create a new revision. No applications shows “Start application”; no active cycle shows its real availability. Expired offer, rejected document, stale update and pending payment each explain a valid next action. Session recovery retains only a safe server-side draft. Test another applicant's UUID, a guardian with revoked authority, repeated submission and concurrent offer acceptance. Staff review uses its own institution/campaign permissions, with final admission authority `admission.approve`; applicant `application.own_accept` must never perform staff approval.

These are substantive first patterns for later build-order areas, not permission to replace them with empty pages. Each needs domain-owner examples before production acceptance.

| Screen | Inputs and primary actions | Validation and difficult states |
|---|---|---|
| SCR-043 Library | Title/edition, copy barcode, borrower, due date; accession, issue, return, renew, reserve, assess/waive authorized fine | Unique copy; borrower eligibility; concurrent issue; lost/damaged copy; empty catalog offers import; scanning failure permits authorized manual lookup; fines link to finance without duplicate charge |
| SCR-044 Transport | Route, stop, vehicle, capacity, driver, trip and assigned student roster; allocate, start trip, board, hand over, report incident | Capacity/time conflicts; authorized pickup; unavailable GPS clearly labelled; no trip data differs from “not boarded”; outage queues only supported safe tasks; student location access is purpose-scoped |
| SCR-045 Hostel/mess | Building/room/bed, resident, allocation period, leave permission and meal plan; allocate, transfer, check out, approve leave | Prevent overlapping occupied-bed allocations; apply eligibility rules; pending leave differs from approved exit; no rooms offers setup; failed allocation preserves uncommitted draft and rechecks bed availability |
| SCR-046 HR/payroll | Employee, appointment, department, contract, leave, attendance and pay components; onboard, approve leave, prepare payroll handoff | Restricted salary/bank fields; overlapping leave/contract rules; payroll period lock; no employee data offers scoped import; integration failure gives retry/reconciliation without repeated payment instruction |
| SCR-047 Assets/procurement/laboratories | Item, asset tag, location, custodian, requisition, supplier, quantities and budget; request, approve, purchase, receive, assign, maintain. Lab mode adds resource, time interval, session, supervisor and prerequisite evidence; request, approve, cancel and record use | Unique asset tag; receiving cannot exceed permitted order; approval thresholds; stock correction reason; no stock differs from failed lookup; partial receipt remains explicit. Lab booking rejects overlapping reservations, exceeded capacity, maintenance blocks and unmet prerequisites; unavailable calendar differs from no bookings; recheck availability when committing a retry |
| SCR-048 Institutional development | Placement opportunity/eligibility/application; alumni consent; accreditation criterion/evidence; research project/supervision/milestone | Separate subworkspaces and permissions; deadline/eligibility checks; verified evidence version; restricted research/case data; no matching opportunity offers filters; failed evidence upload cannot mark criterion complete; do not claim regulatory submission until verified |
| SCR-049 Student services/restricted cases | Category, requester relationship, subject, permitted narrative/files, urgency and preferred safe contact; create, read, update permitted details, triage/assign, resolve and appeal | Own-case access does not include internal safeguarding/counseling notes; staff needs case-specific assignment and field authority. Validate state transitions, safe assignment, deadlines and appeal eligibility. Empty own list offers a new request; an empty staff queue means no assigned visible cases, not no institutional incidents. Failed submit preserves safe draft; duplicate retry creates one case; revoked access removes detail and attachments |

SCR-049 separates ordinary service requests from counseling, health, grievance and safeguarding cases through case types, participant grants and field restrictions. The requester sees only their permitted submissions, safe status, disclosed response and appeal action; assignment does not expose every internal note to them. The officer sees assigned work, due/escalation time and authorized actions. Confidential cases are absent from general student search, ordinary administrator dashboards and unrestricted exports. Case updates go through this controlled workflow, not unrestricted student direct messaging. Review the institution's case-specific fields, retention and urgent-contact guidance before live use; the application must not imply that an ordinary asynchronous case queue is continuously monitored. Vendor/recruiter or guest access opens only the assigned transaction, not the full staff workspace.

## 4. Prototype review plan

| Review batch | Connected path and fixture | Review question | Current evidence |
|---|---|---|---|
| A | Onboarding → invitation → setup; long university name, two campuses | Can both admin levels understand ownership and activation? | Written specification only |
| B | Teacher today → attendance → parent contact; roster correction | Can a teacher finish safely on a phone? | Written specification only |
| C | Account → pending payment → reconciliation/refund | Are uncertainty and posted-versus-settled states unmistakable? | Written specification only |
| D | School result + college registration + engineering evidence + affiliation exchange | Does each academic model retain its own rules and authority? | Written specification only |
| E | Parent child switch → call; class waiting room → reconnect | Are identity, privacy and media controls clear during interruptions? | Written specification only |
| F | Library issue, transport handover, hostel transfer, payroll exception, asset receipt | Can operational staff resolve the common exception without data loss? | Written specification only |
| G | Applicant draft → document correction → offer acceptance; own case → assigned response → appeal; laboratory booking conflict | Are self-service authority, private case fields and reserved resources correctly distinguished? | Written specification only |

Create the actual wireframes/prototype in a later expressly requested design step; do not substitute this text for visual review. Use synthetic fixtures, including 60-student class, duplicate names, 120-character institution name, multi-campus staff, adult student with limited guardian access, low connectivity and expired grant. Review 390 and 1440 CSS px first, then the full responsive matrix. Apply the actual supplied logo before final brand review.

Record task completion, wrong turns, misunderstood labels and severe errors; a task is not “passed” solely because a reviewer liked its appearance. Capture issue ID, screen/state, fixture, viewport, expected/observed behavior, severity, owner and disposition. Test keyboard order, focus restoration, announcement behavior, captions and meaningful reflow against the [W3C accessibility reference](https://www.w3.org/WAI/WCAG22/quickref/). These are future review criteria, not results.

## 5. Design handoff evidence

A screen is implementation-ready when its applicable fields, action permission, state transition, validation, responsive layout, empty/error behavior and acceptance scenario are resolved. Shared components must be referenced consistently. Record outstanding provider or regulation dependencies explicitly and identify which task they block. Do not require a new approval for every spacing change; escalate material scope, authority, academic/financial rule and branding decisions.

Before calling the visual baseline approved, attach real design/prototype references and dated user decisions. Before calling the product complete, test the implemented journeys with actual APIs, database, authorization, persistence, provider callbacks and responsive UI. The planning pack cannot supply that evidence in advance.
