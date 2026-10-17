# Eduma — Requirements and Acceptance Traceability

**Version/date:** 1.0 / 12 October 2026  
**Status:** Documentation coverage map. Every application acceptance test is **Not run**. A linked specification is not implementation evidence.

## 1. How to use this map

Requirement families are defined in [01](01_PRD_and_Release_Scope.md); action permissions in [02](02_Roles_Tenancy_and_Permissions.md); workflow IDs in [03](03_Workflows_and_Business_Rules.md); screen IDs in [04](04_Navigation_and_Screen_Catalog.md); test IDs in [11](11_Test_UAT_and_Migration.md); build IDs in [12](12_Delivery_Backlog_and_Build_Readiness.md). Screen details and state behavior are in [06](06_Screen_Specs_and_Prototype_Review.md). Data and interfaces are proposed in [08](08_Data_Model_and_Dictionary.md) and [09](09_API_Events_and_Integrations.md).

The matrix records representative coverage, not an exhaustive endpoint-by-endpoint test inventory. During each build slice, add atomic acceptance cases, actual routes/entities, test files, evidence and unresolved defects. Cross-cutting authorization, accessibility, audit and failure recovery apply to every row even when not repeated. Never mark an entire requirement family complete because one linked test passed.

## 2. Product-to-build coverage

| Requirement | Workflow / rule | Screens | Data and interface boundary | Acceptance examples | Delivery |
|---|---|---|---|---|---|
| REQ-TEN | WF-ACL; institution boundary and explicit exchanges | SCR-002, SCR-015, SCR-031 | Institution, Membership, GroupInstitution, AffiliationAgreement; institution context and exchange routes | TST-002, TST-003, TST-005 | BUILD-01, BUILD-05, BUILD-12 |
| REQ-ONB | WF-ONB; resumable onboarding and lifecycle | SCR-005, SCR-006, SCR-007, SCR-012 | Institution, BrandingAsset, invitations; platform institution commands | TST-001; lifecycle exception in EX-07 | BUILD-02, BUILD-12 |
| REQ-ACL | WF-ACL; action/field/relationship authority | SCR-001, SCR-003, SCR-010, SCR-014, SCR-020 | RoleDefinition, PermissionGrant, RelationshipGrant, SupportAccessGrant; current authorization on every surface | TST-004, TST-006, TST-007, TST-033, TST-034 | BUILD-01, BUILD-03, BUILD-12 |
| REQ-CFG | WF-CFG; effective-dated publication | SCR-009, SCR-012, SCR-013, SCR-021 | SettingDefinition/Revision, InstitutionEntitlement; preview/publish and module dependency checks | TST-008, TST-031 | BUILD-03, BUILD-05 |
| REQ-ADM | WF-ADM; application through enrollment | SCR-016, SCR-017, SCR-018, SCR-019, SCR-020 | Application, Offer, Student, Enrollment; published intake form, own application actions and staff review | TST-009, TST-025, TST-033 | BUILD-04 |
| REQ-ACA | WF-ACA; curricula, capacity, progression | SCR-018, SCR-019, SCR-021, SCR-028, SCR-029, SCR-030, SCR-031 | EnrollmentPeriod, CurriculumVersion, CourseOffering, CourseAttempt; registration, grants and degree audit | TST-010, TST-013, TST-035 | BUILD-05, BUILD-07 |
| REQ-ATT | WF-ATT; assigned rosters and corrections | SCR-022, SCR-023, SCR-024, SCR-025 | TeachingAssignment, TimetableSlot, AttendanceSession/Mark, Assignment; save/submit/correct | TST-011, TST-020; EX-04 | BUILD-06 |
| REQ-EXM | WF-EXM; moderation, publication and revision | SCR-026, SCR-027, SCR-029, SCR-030, SCR-031 | Assessment, ResultVersion, PublicationBatch, Transcript, AttainmentRun; review/publish/correct | TST-012, TST-013, TST-014, TST-031 | BUILD-07 |
| REQ-FIN | WF-FIN; immutable postings and reconciliation | SCR-032, SCR-033, SCR-034, SCR-035, SCR-036 | Invoice, Payment, Allocation, Refund, Journal, Settlement; commands and authenticated provider callbacks | TST-015, TST-016, TST-025 | BUILD-08 |
| REQ-COM | WF-COM; policy-authorized communication | SCR-037, SCR-038, SCR-039, SCR-040 | Conversation, Message, CallRequest, ClassSession; durable REST writes, scoped realtime events and media tokens | TST-017, TST-018, TST-020; later TST-032 | BUILD-09; mobile BUILD-13 |
| REQ-OPS | WF-OPS and platform operating rules | SCR-004, SCR-008, SCR-009, SCR-010, SCR-041, SCR-043–SCR-049 | Operational domain records, AuditEvent, jobs and health/usage signals; scoped module commands | TST-021–TST-024, TST-027–TST-030, TST-034 | BUILD-10, BUILD-11, BUILD-12 |
| REQ-UX | Role-specific journeys and shared screen states | SCR-001–SCR-049; particularly SCR-011, SCR-023, SCR-035, SCR-036 | Permission-aware view models, consistent validation/problem details and honest asynchronous states | TST-019, TST-020; human prototype review | Every slice; BUILD-12 |
| REQ-MIG | Staging, reconciliation, cutover and corrections | SCR-042, relevant domain review screens | ImportJob/Row, ExportJob, source identity/provenance; validate/commit/download authorization | TST-002, TST-022, TST-025 | BUILD-04, BUILD-11, BUILD-12 |
| REQ-INT | Authorized adapters and explicit source of truth | SCR-008, SCR-012, SCR-031, SCR-034, SCR-038, SCR-039, SCR-042 | Integration connections, outbox, consumer receipts, signed callbacks and provider reconciliation | TST-016, TST-018, TST-026; mobile TST-032 | Relevant slices; BUILD-11, BUILD-13 |

Ranges such as SCR-043–SCR-049 mean all intervening IDs; they do not create additional identifiers. The test catalog contains a mixture of scenario families and individual examples; split them into independently executable cases when implementing.

## 3. Coverage of all four institution categories

| Category / fixture | Required representative journey | Documents and evidence |
|---|---|---|
| School / FIX-SCH | Application → grade/section placement → timetable and attendance → report card → guardian fees/communication | WF-ADM, WF-ACA, WF-ATT, WF-EXM, WF-FIN, WF-COM; TST-009, TST-011, TST-012, TST-015, TST-017, TST-035 |
| General college / FIX-COL | Admission → curriculum/semester placement → prerequisite/capacity registration → attempts and credits → transcript | WF-ACA, WF-EXM; TST-010, TST-013, TST-014; adult delegation in TST-006 |
| Engineering college / FIX-ENG | Linked theory/lab registration → practical assessment → backlog/repeat → project/internship and outcome evidence | SCR-028, SCR-030, SCR-047, SCR-048; TST-010, TST-012, TST-013, TST-030; domain acceptance cases added in BUILD-10 |
| University / FIX-UNI | Internal campus context → approved affiliated-college exchange → central review/publication → award/degree evidence | SCR-015, SCR-027, SCR-029, SCR-031, SCR-048; TST-005, TST-014; university authority does not expose ungranted college records |

These journeys are a minimum for checking the architecture. They do not replace the full approved web catalog or actual institutional academic regulations. One institution type's successful demo cannot establish the other three are supported.

## 4. Operational breadth checklist

| Capability | Screen / workflow evidence | Acceptance dependency |
|---|---|---|
| Library | SCR-043; issue, return, renewal, loss and fine history in WF-OPS | TST-027 plus borrower policy and finance integration |
| Transport | SCR-044; routes, capacity, boarding and authorized handover | TST-028 plus safety/incident corrections and permitted location visibility |
| Hostel/mess | SCR-045; bed allocation, leave and meal plan | TST-028 plus date overlaps and warden/guardian scope |
| HR/leave/payroll boundary | SCR-046; employee, approval, snapshot and export | TST-029 plus agreed statutory/accounting scope D-11 |
| Procurement/assets/laboratories | SCR-047; approvals, receipts, custody, maintenance and bookings | TST-030 plus quantity reconciliation and linked equipment availability |
| Placement/internship/alumni | SCR-048; opportunities, consented sharing and evaluations | Add concrete consent, eligibility and export cases in BUILD-10 before claiming delivery |
| Research and accreditation evidence | SCR-048; supervisor milestones, approvals and evidence snapshots | Add grant/ethics validity, restricted reviewer access and reproducibility cases in BUILD-10 |
| Service requests/grievances | SCR-049; own submission, triage, restricted notes, resolution and appeal | TST-034 plus approved escalation rules; not an unrestricted student messaging route |

Shared components may support these modules, but each needs its actual domain rules and role-visible states. The absence of a dedicated test ID for every module action remains an implementation planning task, not permission to omit verification.

## 5. Verification status and maintenance

- Documentation references, catalog identifiers and worked arithmetic are checked during preparation; the performed checks are recorded in [00](00_README.md).
- Application behavior, integrations, rendered UI, accessibility conformance, device calling, tenant recovery and capacity are unverified because the application has not been generated.
- Add evidence links against the smallest applicable case. Separate local synthetic verification from provider sandbox evidence, human UAT and production authorization.
- When a requirement changes, update its workflow, permission, data/API contract, screen states, acceptance cases and backlog together. Record the accepted change in [14](14_Decisions_and_Assumptions.md).
- Preserve stable IDs. Retire superseded cases with a reason and replacement reference rather than silently reusing their identifiers.
