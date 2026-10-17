# 02 — Roles, Tenancy and Permissions

**Product:** Eduma  
**Prepared:** 12 October 2026  
**Status:** Draft specification for review; no permissions or infrastructure have been implemented.  
**Requirement families:** REQ-TEN, REQ-ONB, REQ-ACL, REQ-CFG, REQ-COM.  
**Related:** [PRD](01_PRD_and_Release_Scope.md), [workflows](03_Workflows_and_Business_Rules.md), [data model](08_Data_Model_and_Dictionary.md), [security](10_Security_Privacy_and_Operations.md), [decisions](14_Decisions_and_Assumptions.md).

## 1. Boundary and vocabulary

Eduma supports schools, colleges, engineering colleges and universities from the initial product scope. An institution is the operational tenant: every tenant-owned record carries an immutable `institution_id` UUID. The institution owns its configuration, academic records, users' memberships, financial records and communication policies. A user's global identity may have several institution memberships, but personal records and permissions are not automatically merged between them.

| Object | Meaning | Access consequence |
|---|---|---|
| Platform | Eduma service and control plane | Operates provisioning, entitlements, health and service administration |
| Customer/group | Commercial or governance grouping | Group association alone grants no tenant data access |
| Institution | School, college, engineering college or university tenant | Primary isolation boundary; independently authorized membership |
| Campus | Operational location within an institution | Optional narrower scope; not automatically a separate tenant |
| Department/program | Academic ownership and enrollment structures | Narrows staff responsibilities and academic authority |
| Affiliation | Time-bound relationship between institutions | Allows only explicitly granted academic exchanges or reporting |
| Account / institution person | Account is global sign-in identity; Person is institution-owned biographic data | Neither implies student, guardian or employee status everywhere; do not merge institutional Person records globally |
| Membership/role assignment | Account's effective institutional authority | Includes role version, scope, start/end, status and assigning actor |

An independently governed affiliated college remains a separate institution tenant even when a university controls an examination scheme. University affiliation does not expose college payroll, health records, unrelated parent conversations or bank reconciliation. Conversely, a multi-campus university can be one tenant if the agreed governance and contractual model supports it. This is a proposed model to confirm with representative institutions; legal ownership must not be inferred from organization names.

## 2. Authorization decision

Permission names use `<resource>.<action>`, such as `attendance.submit`, `result.publish` and `fee_refund.approve`. A permission is necessary but insufficient: the server also checks scope, relationship, record state, policy and effective time.

For every request, worker, export, download and real-time subscription:

1. Authenticate the actor; validate session and account status.
2. Resolve the requested institution and its service state server-side.
3. Resolve active memberships or an explicit, unexpired exchange/support grant.
4. Check the action permission against the current role/policy revision.
5. Check institution, campus, department and record boundaries.
6. Check relevant relationship: assigned teacher, enrolled student, verified guardian, nominated reviewer or granted recipient.
7. Check workflow state, feature entitlement, legal/policy restrictions and separation of duties.
8. Return only permitted fields; record security-relevant access or mutations.

Default is deny. Explicit restrictive policy and protected-record rules take precedence over the union of ordinary role permissions. The browser may hide buttons for usability but never supplies the authorization decision. Changing `institution_id` in `/api/v1/institutions/{institution_id}/…` must not change the caller's authority. UUIDs reduce guessability; they are not an access control.

Campus-limited users cannot widen access through reports, counts, autocomplete, global search, CSV files or aggregate drill-down. Errors must not reveal another institution's record existence. A scheduled report must revalidate recipient authority when generated and again when delivered/downloaded.

## 3. Role templates

Templates are editable within protected platform boundaries. Institutions create named roles from allowed permissions, then assign narrow scopes. Role names are labels; code must check permissions and relationships.

| Template | Primary authority | Default limits |
|---|---|---|
| System Admin | Provision institutions, invite initial admins, manage lifecycle and entitlements | No routine institution record browsing or academic/financial editing |
| Platform Operations | Health, alerts, capacity, recovery and deployments | Redacted diagnostics; no student records by default |
| Platform Support | Handle cases and approved diagnostic sessions | Time-bound read access to named records; no implicit impersonation |
| Group Administrator | Manage authorized cross-institution governance | Only separately granted institutions and data categories |
| Institution Admin | Setup, staff membership, configuration and institutional operations | Cannot weaken platform security or silently bypass approvals |
| Principal/Director | Institutional oversight and delegated approvals | No automatic payment gateway secrets or confidential case access |
| Registrar/Academic Administrator | Enrollment, term setup, registration and academic records | Finance and result-publication permissions separately granted |
| Dean/Head of Department | Department planning, workload and academic approvals | Assigned departments and programs only |
| Teacher/Faculty | Assigned teaching, attendance, assessment and authorized communication | No unrelated classes, mass finance exports or peer employee records |
| Examination Officer | Exam setup, scrutiny and result publication | Maker/reviewer/publisher authority separated where configured |
| Admissions Officer | Applications, documents, verification and admission preparation | Sensitive document fields restricted; concessions separately approved |
| Applicant / authorized application guardian | Create and manage specifically owned applications | Application-only membership; no enrollment, student directory or staff access; adult applicant delegation verified separately |
| Accountant/Cashier | Charges, collections, reconciliation and fee reporting | Refund approval and reversal authority separately assigned |
| HR/Payroll Officer | Employee and payroll workflows | Student academic/health records unavailable by default |
| Librarian/Transport/Hostel/Asset Officer | Their operational module | Minimum student contact or assignment data required for service |
| Service / Grievance / Safeguarding Officer | Assigned case triage, action and resolution | Case confidentiality and explicit assignment; institution-wide admin role alone does not disclose private case notes |
| Student | Own enrollment, learning, published results, dues and permitted meetings | Cannot host unrestricted calls or access peers' private records |
| Parent/Guardian | Permitted records of explicitly linked learners | Per-child and per-purpose scope; no inherited whole-family access |
| Auditor | Approved record categories and audit trails | Read/export only where granted, with expiry and purpose |

A person may hold multiple roles. A teacher who is also a parent switches context clearly; employment authority must not expand parent access. Emergency contacts, fee payers and pickup nominees are separate relationships from academic guardians.

## 4. Action matrix

This is the starting permission contract. “Scoped” always includes the authorization checks above. “Separate grant” means the capability is not inherent in that role. Institutional permissions can be delegated without transferring ownership of the whole tenant.

| Action permission | Default eligible role | Scope / relationship | Required constraint |
|---|---|---|---|
| `institution.create` | System Admin | Platform | Idempotent provisioning; verified organization request |
| `institution.activate` / `institution.suspend` | System Admin | Named institution | Reason, impact preview, audit; suspension is not deletion |
| `institution_brand.update` | Institution Admin; System Admin during setup | Own institution | Scan assets; version published branding |
| `platform_health.read` | System Admin, Operations | Platform | Redacted diagnostics and secret filtering |
| `entitlement.update` | System Admin | Named institution | Cannot grant prohibited processing or overwrite historical records |
| `role.manage` / `membership.assign` | Institution Admin | Own institution; assigned campus if delegated | Grant ceiling; cannot award platform authority or exceed own delegated authority |
| `affiliation_grant.approve` | Authorized institution owners | Named sender, receiver and purpose | Acceptance, expiry, allowed fields and revocation rules |
| `student.read` / `student.update` | Registrar; assigned administrative roles | Own institution and assigned students | Field rules; changes to identity/enrollment history audited |
| `admission.approve` | Admissions approver/Registrar | Assigned campaign/program | Required checks complete; prevent own approval if policy requires |
| `application.review` / `application.request_information` | Admissions Officer | Assigned cycle/program/applications | Restricted documents and field access; review is distinct from admission approval |
| `application.own_create` / `application.own_view` / `application.own_edit` | Applicant / authorized application guardian | Published admission cycle and explicitly owned application | Backend creates only a limited applicant membership; edit only draft or returned fields, never other applicants |
| `application.own_submit` / `application.own_accept` | Applicant / authorized application guardian | Own verified application/offer | Required fields/documents complete; offer valid; admission payment status comes from verified finance events |
| `course_registration.approve` | Registrar/academic approver | Program/term | Versioned prerequisites and authorized override reason |
| `attendance.submit` | Assigned teacher/substitute | Teaching session and roster | Submission window; enrollment effective dates |
| `attendance.correct` | Authorized academic approver | Submitted session | Reason, prior value and approval history retained |
| `mark.enter` | Assigned evaluator | Component/course/term | Allowed mark range and missing/absent statuses |
| `result.verify` / `result.publish` | Examiner / publisher | Approved exam cycle | No silent self-approval; locked rule version and reconciled cohort |
| `fee_charge.issue` / `fee_payment.record` | Accountant/Cashier | Institution/campus ledger | Decimal money, approved schedule and immutable posting history |
| `fee_concession.approve` / `fee_refund.approve` | Named finance approver | Allowed amount/category threshold | Independent maker/checker where required; step-up authentication |
| `message.send` / `call.initiate` | Teacher, guardian, authorized staff | Institution-approved relationship | Availability, recipient policy, abuse controls and restrictions |
| `meeting.host` | Assigned teacher/authorized staff | Scheduled class or approved audience | Policy-controlled invitation, waiting room and removal |
| `meeting.join` | Enrolled invited student; authorized participants | Meeting roster | Short-lived token; recheck revoked invitation |
| `report.export` | Role with explicit export grant | Authorized dataset and fields | Purpose, size limits, audited delivery and expiry |
| `privacy_request.manage` | Designated privacy owner | Named institution/request | Identity verification and separate legal-hold decision |
| `support_access.request` | Platform Support | Named ticket/institution | Institution approval or recorded emergency procedure |
| `configuration.edit` / `configuration.publish` | Institution Admin or designated configuration approver | Permitted settings and effective scope | Publication authority separated for high-impact rules; locked constraints cannot be weakened |
| `academic_structure.manage` / `timetable.publish` | Registrar / academic coordinator | Assigned institution/campus/program | Rule and conflict checks; versioned publication |
| `library.manage` / `library.issue` / `library.return` | Librarian | Assigned library and authorized borrower | Atomic copy allocation and controlled fine corrections |
| `transport.manage` / `transport.record_boarding` | Transport manager / assigned attendant | Assigned routes/trips/riders | Active trip and pickup authority; no broad location-history access |
| `hostel.allocate` / `hostel.approve_leave` | Authorized warden | Assigned hostel/building | Occupancy constraints and approved handover/leave policy |
| `employee.manage` / `leave.approve` / `payroll.process` | HR / designated leave or payroll officer | Assigned employees and employment period | Salary fields protected; independent payroll approval as configured |
| `procurement.approve` / `inventory.move` / `asset.manage` | Authorized purchasing/store/asset officer | Assigned budget/store/resources | Approval thresholds, atomic stock movements and custody history |
| `lab_booking.create` / `lab_booking.approve` | Authorized requester / lab manager | Assigned lab/resources and permitted booking audience | Capacity/conflict/safety/maintenance checks |
| `service_case.create` / `service_case.read` | Authorized requester / assigned case officer | Own or explicitly assigned case | Own read excludes confidential internal notes; third-party details protected |
| `service_case.update` / `service_case.assign` / `service_case.resolve` | Assigned officer / case supervisor | Case and confidentiality scope | State, delegation and separation rules; never institution-wide implicit access |
| `service_case.appeal` | Eligible requester or authorized representative | Own closed/resolved case within permitted window | Preserve original decision and appeal authority |
| `placement.manage` / `research.manage` / `quality_evidence.manage` | Assigned placement / research / quality officer | Approved programs/projects/evidence periods | Data-purpose consent, committee authority and official publication boundaries |

Read-only access never implicitly includes export. Financial approval limits use currency-specific decimal values. A UI role editor shows permission descriptions, dependencies and a before/after impact preview; it must warn on conflicting duties and reject protected combinations rather than relying on a warning alone.

## 5. Guardian and adult student relationships

Store relationship type, learner, institution, permitted record categories, verification method/reference, effective dates, restrictions and review status. Do not expose custody or safeguarding notes to ordinary teachers or other guardians. A shared phone number or surname cannot establish a guardian link. Invitation acceptance proves control of an account, not legal authority.

For minor learners, access follows verified authority and the applicable purpose/policy. Record restrictions independently for multiple guardians. A guardian may be allowed to pay fees without receiving confidential wellbeing records. Changes require an authorized institutional review, with evidence minimization.

Adult students require a separately justified relationship and access policy; do not automatically extend parental access into college. Provide student-authorized delegation where appropriate, per category and time period, with revocation. Turning 18 triggers a review workflow using verified date of birth and policy jurisdiction; it must not silently broaden access or delete records. Under-18 college students still require the relevant child-related handling.

## 6. Groups and affiliated institutions

An exchange grant names granting institution, receiving institution/group principal, purpose, data categories, filters, permitted actions, effective dates and approval evidence. Financial, safeguarding and communications records require separate consideration from academic exchange. A group dashboard queries only active grants and shows reporting freshness and scope.

Submitted affiliation snapshots preserve who supplied them and their revision; the receiver cannot change the source college's student record. Corrections create new versions and reconcile accepted submissions. Revocation stops new access, future jobs and live sessions; retained lawful submissions follow their documented retention and correction rules, not a false promise that every recipient copy disappears immediately.

## 7. Provisioning, delegation and suspension

System Admin creates the institutional profile, verified contact, initial image assets, institution category and entitlements, then sends a single-use expiring invitation to Institution Admin. The invite is bound to institution and intended authority; no shared default password. Institution Admin completes academics, memberships, policy and feature setup. Activation must show unresolved readiness checks and record any authorized exceptions.

Delegated admins cannot grant beyond their own grant ceiling, move records into another tenant, or approve their own privilege escalation. Removing the last active Institution Admin requires a replacement or approved recovery process. Departure revokes sessions, service tokens, assignments and queued exports as appropriate while preserving record authorship.

Restriction and suspension follow the distinct lifecycle states in 03. Billing restrictions may preserve approved read/export continuity; a security suspension revokes affected interactive sessions and media access. Provider payment callbacks still require controlled processing and reconciliation so money is not lost. An institution cannot reactivate itself by changing configuration. Archive/offboarding is a separate workflow with export, retention and deletion review.

## 8. Support and emergency access

Normal support starts with redacted telemetry. If tenant data is necessary, use a ticket-bound grant with institution approval, named support actor, purpose, records/actions, expiry and visible session banner. Default grant is read-only. Export, impersonation and mutations require explicit additional authority; ordinary support must not edit financial postings or issued results.

Emergency access uses named privileged accounts, strong authentication, a recorded incident, restricted duration and independent review. A proposed 60-minute maximum session is a configurable operational policy, not a legal standard. Capture actor, effective identity, grant, institution, accessed records, action, reason, timestamp and outcome. Notify the designated institution contact according to the incident policy. Approval authority and reviewer cannot be the same person acting alone. Group membership is independent of support access and cannot bypass its controls.

## 9. Mandatory denial cases and acceptance

The implementation must deny and test: swapped institution IDs; another tenant's attachment URL; expired affiliation grants; teacher access to an unassigned class; guardian access to an unlinked learner; revoked adult delegation; publishing a result with only mark-entry rights; approving one's own refund where separation is required; stale-role access after removal; permission escalation through custom role JSON; export continuation after revocation; and joining a class with a forwarded token.

Evidence must include API, worker, database connection reuse, object storage, cache, search and WebSocket paths. Database row-level security is defense in depth, not a replacement for these checks. Review the matrix with one representative of each launch institution type and reconcile every action to [UAT tests](11_Test_UAT_and_Migration.md). Approval remains pending; this document is not an access-control audit or proof of isolation.
