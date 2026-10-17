# Eduma — Product Requirements and Release Scope

**Pack version:** 1.0  
**Prepared:** 12 October 2026  
**Status:** Substantive proposal for review. Confirmed user requirements are distinguished from recommended implementation defaults. No software or visual prototype is claimed complete.

## 1. Product outcome

Eduma lets an education organization run admissions, student records, academics, institutional operations and communication in one governed platform. Eduma's platform team onboards and operates the service; institution teams control their own workflows and data within assigned authority.

Success means that a teacher, parent, registrar, accountant or administrator can complete real work with correct permissions and reliable records. A dashboard containing sample numbers is not sufficient delivery of the underlying function.

## 2. Confirmed scope

| Topic | Confirmed requirement |
|---|---|
| Product and market | Eduma; India first, later international expansion |
| Institution categories | Schools, general colleges, engineering colleges and universities are supported at initial launch |
| Structure | Groups, campuses and affiliated colleges, with central management accounts |
| System Admin | Central onboarding, initial institution images/details and admin invitation, activation/deactivation, technical operations and metrics |
| Institution Admin | Institutional users, academics, feature settings, branding and operations |
| Communication | Teacher–parent and staff messages/calls; students join teacher-conducted classes under institution policy |
| Devices | Responsive web first; Android and iOS later |
| Technology | User proposed Angular, Django and PostgreSQL; the planning recommendation retains them |
| Process | Review the documents and design before generating the application; logo supplied later |

The scope is broader than one school template. Academic registration, curriculum versions, attempts, credits and university authority are first-class requirements.

## 3. Proposed delivery groups

These groups describe dependency order and review priorities. They are **not user-approved exclusions**. The full web catalog remains in the product scope. A smaller commercial launch must be explicitly selected in [the decisions register](14_Decisions_and_Assumptions.md).

- **L1 — operational core across all four categories:** platform setup, identity, institution configuration, student lifecycle, academics, attendance, assessment/results, student fees, communication, reports, audit and required integrations.
- **L2 — institutional operational breadth:** library, transport, hostel/mess, HR/payroll interfaces, purchasing/assets/labs, student services, placements/alumni and quality/research administration as applicable.
- **L3 — later platform/depth:** native mobile applications, more advanced optimization, additional country/regulatory packs, and other explicitly selected advanced capabilities. Native mobile follows the web phase as requested.

An institution can enable only relevant modules. Unconfigured or unavailable features must say so honestly. A disabled menu, mock response, decorative screen or nonfunctional button does not count as a completed module.

## 4. Users and jobs to complete

| User | Principal job | Example completion evidence |
|---|---|---|
| System Admin | Bring an institution into service and keep it operating | Institution provisioned, admin invited, readiness checked, activated and monitored |
| Institution Admin | Configure and delegate institutional work | Academic structure, roles, modules and policies saved with version/audit |
| Group/university manager | Perform authorized shared governance | Aggregate or exchange available only for explicitly granted institutions/fields |
| Teacher/faculty | Teach, record progress and communicate | Assigned attendance/marks saved, parent contacted, class hosted |
| Registrar/exam officer | Maintain authoritative academic records | Curriculum, registration, results and awards follow approved rules |
| Finance officer | Collect and reconcile fees | Provider events, receipts, refunds and settlements match the ledger |
| Parent/guardian | Follow and support authorized children | Correct child selected; relevant notices, fees and contact actions available |
| Student | Complete own academic/service tasks | Appropriate registration, timetable, coursework, published results and class join |
| Domain staff | Operate assigned services | Correct loan, trip, room, leave, requisition or case workflow completed |

Detailed action authority belongs in [02](02_Roles_Tenancy_and_Permissions.md). Job titles do not grant global access.

## 5. Requirement families and observable acceptance

These IDs are the shared traceability keys. Domain documents may define narrower rules or test cases beneath a family.

| ID | Requirement family | Required observable behavior |
|---|---|---|
| REQ-TEN | Organization and isolation | One institution cannot access another's records; group/affiliation rights are explicit and revocable |
| REQ-ONB | Platform onboarding/lifecycle | Create institution, upload approved branding, invite admin, validate readiness, activate, restrict, suspend, reactivate and offboard |
| REQ-ACL | Identity and authorization | Role/action/scope/relationship/state checks work in APIs, exports, files, jobs and realtime channels |
| REQ-CFG | Dynamic configuration | Forms, modules, templates and supported rules are versioned, validated and effective-dated without rewriting history |
| REQ-ADM | Admissions and student lifecycle | Enquiry/application through enrollment, transfers, withdrawal and authorized guardian links |
| REQ-ACA | Academic structure and registration | School grade/section and higher-education curriculum/offering/credit models work for all four categories |
| REQ-ATT | Scheduling, teaching and attendance | Conflict-aware schedules, assigned rosters, attendance corrections and defined eligibility calculations |
| REQ-EXM | Assessment, results and awards | Versioned calculation, moderation, publication, revaluation, progression and reproducible academic records |
| REQ-FIN | Student fees and accounting boundary | Exact amounts, durable payment events, balanced subledger, receipts, refunds and reconciliation |
| REQ-COM | Messages, calls and online classes | Only authorized relationships communicate; teacher supervision and active-session revocation are enforced |
| REQ-OPS | Institutional services and platform operations | Enabled service workflows function; health, usage, audit, support and recovery are actionable |
| REQ-UX | Responsive and accessible experience | Role-specific navigation and critical workflows work on defined devices and in error/restricted states |
| REQ-MIG | Imports, exports and migration | Staged mapping, validation, safe retry, reconciliation and provenance preserve correctness |
| REQ-INT | Integrations and external exchange | Approved provider adapters show real states, retry safely and identify the source of truth |

## 6. Institution-type capability matrix

**Core** means required for that category's operational core. **Applicable** means enabled according to institutional need and reviewed scope; it does not mean deleted from the product backlog.

| Capability | School | College | Engineering college | University |
|---|---|---|---|---|
| Identity, configuration, admissions, people, fees, reporting | Core | Core | Core | Core |
| Grades/sections, school report cards, promotion | Core | Where attached school unit exists | Where attached school unit exists | Where governed school unit exists |
| Guardian links and teacher–parent communication | Core with child/privacy controls | Authorized relationships | Authorized relationships | Authorized relationships |
| Terms, programs, curricula, offerings, course registration | Subject structure as needed | Core | Core | Core |
| Credits, attempts, SGPA/CGPA and degree audit | Where applicable | Core | Core | Core |
| Timetable, attendance and assessment | Core | Core | Core | Core |
| Teacher-led online sessions and staff communication | Core | Core | Core | Core |
| Lab batches, projects and outcome evidence | Applicable | Applicable | Core | Core for applicable programs |
| Constituent campuses, affiliations and central examinations | Group/campus functions | Affiliation participation | Affiliation participation | Core |
| Library, transport, hostel, HR, assets and service cases | Applicable | Applicable | Applicable | Applicable |
| Placements, internships and alumni | Applicable alumni/careers | Applicable | Applicable | Applicable |
| Quality/accreditation evidence and research administration | Applicable | Applicable | Applicable | Applicable |

Every pilot institution must demonstrate an end-to-end journey. Supporting every board, regulation, accreditation route and specialized program is not implied until those rules are supplied and validated.

## 7. Platform and institutional configuration boundaries

System Admin sets supported capabilities, commercial entitlements, quotas, platform templates and operational limits. Institution Admin enables entitled modules, configures permitted rules and delegates authority. Campus/department overrides exist only where delegated.

Effective access is the intersection of deployed capability, entitlement, institution enablement, scope, user permission, relationship and current record state. Frontend visibility is not a security control.

Editable configuration includes typed custom fields, forms, labels, document layouts, workflows, notification templates, grading/attendance schemes and fee policies. It excludes arbitrary executable code, unrestricted SQL, bypass of consent/security controls and silent editing of posted financial or published academic history.

## 8. Communication requirements

- Teacher–parent contact requires an authorized guardian relationship and relevant teacher assignment.
- Staff communication respects institutional and organizational scope.
- Students can join teacher-conducted online classes and institution-approved moderated class interactions. Unrestricted student direct messaging/calling is outside the confirmed initial communication scope.
- Adult-student parent access requires a separate authorized relationship; parent payment does not grant all academic or private information.
- Audio is the proposed default for direct calls; video is supported where approved and needed for online classes.
- Recording remains off under the proposed default. Recording, transcription and their access/retention rules require separate approval.
- A teacher's departure or revoked relationship removes active as well as future access.
- If the final authorized host leaves, student participation pauses or the class ends according to a bounded policy.

## 9. Operational breadth retained in the catalog

| Module | Minimum functional boundary when selected for delivery |
|---|---|
| Library | Catalog/copies, loans, reservations, returns, lost items, policy-driven dues and clearance |
| Transport | Routes/stops, assigned trips and riders, boarding events, safe handover and authorized trip visibility |
| Hostel/mess | Bed allocations, occupancy, leave/out-pass, meal plans, incidents and charges |
| HR/payroll | Employee lifecycle, assignments, leave, attendance, approved payroll inputs, payslips or a reconciled payroll adapter |
| Purchasing/inventory/assets | Requisition, approval, order, receipt, stock movements, custody and maintenance |
| Laboratories | Resource availability, booking, experiment/project evidence and maintenance |
| Student services | Service requests, confidential grievance/counseling referral, case-specific access and deadlines |
| Placement/internship/alumni | Eligible opportunities, applications, outcomes, supervised internship evidence and consented alumni records |
| Quality/research | Approved evidence, outcome calculations, review periods, research supervision and milestone workflows |

Full tax/statutory payroll, general-ledger accounting, biometric integrations and jurisdiction-specific compliance engines are separate fit-and-responsibility decisions. The intended boundary must be visible; an export adapter must not be presented as a full engine.

## 10. Proposed nonfunctional targets

The following are planning targets only: WCAG 2.2 AA for applicable web journeys; reliable behavior at representative phone/tablet/desktop widths; 99.9% monthly core-service availability; p95 ordinary reads below 800 ms and writes below 2 s under a defined workload; proposed disaster RPO 15 minutes/RTO 4 hours.

Targets require measurement definitions, cost validation and evidence before contract commitments. [10](10_Security_Privacy_and_Operations.md) and [11](11_Test_UAT_and_Migration.md) define the validation process. Browser calling cannot imply native locked-phone reliability.

## 11. Explicit exclusions and deferred decisions

Confirmed later scope includes native Android/iOS development. Unsupported initial assumptions include unrestricted student social messaging, platform custody of tuition funds, silent call recording, automatic regulator submission without authorization, and AI deciding admissions, disciplinary outcomes or official grades.

The following remain decisions, not invented facts: first pilot boards/programs, release breadth, real scale, launch languages, budget/team/date, provider accounts, institution legal tenancy, document templates, exact retention, hosting/residency promises and final branding.

Synthetic academic examples in [03](03_Workflows_and_Business_Rules.md) demonstrate calculations only. They must not be labeled real CBSE, UGC or university regulations.

## 12. Product completion and review

A delivered feature has a reachable interface, persisted records, enforced authority, meaningful failure behavior, audit where needed and acceptance evidence. Business flows must work against the actual backend. Development fixtures and provider test doubles are identifiable and cannot report production readiness.

Review the launch matrix and decisions once, record resulting scope, then implement in connected slices. After the core, continue the approved operational modules before declaring the agreed web product complete. [12](12_Delivery_Backlog_and_Build_Readiness.md) governs dependency order; [13](13_Traceability.md) connects requirements to evidence.
