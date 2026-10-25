# Eduma — decision register

Successor to `Eduma_Build_Pack/14_Decisions_and_Assumptions.md` for the implementation. Earlier entries in the pack
stay as they were; anything here that differs supersedes them. Never record an approval that was not given.

## Slice 1 decisions (17 October 2026)

Evidence: the user's answers in the build session of 17 Oct 2026 ("approved", "native, go ahead") and the approved
spec `docs/superpowers/specs/2026-10-17-foundation-onboarding-branding-design.md`.

| ID | Decision | Supersedes |
|---|---|---|
| S1-01 | Stack as AP Police Student Connect: Angular 22 (zoneless, signals, Vitest), Django 6.1 + DRF 3.18, PostgreSQL 17 in Docker, hand-written SCSS, fonts bundled with `@fontsource` (OFL only, no CDN). Layout `backend/`, `frontend/`, `docs/`. | D-10 (Angular Material/CDK); pack 12 repository layout |
| S1-02 | `/` on the main domain always shows the Eduma landing page, with no sign-in link. | — |
| S1-03 | `/login` on the main domain is unlinked and admits only platform (System Admin) accounts; everyone else gets "Invalid login ID or password." | — |
| S1-04 | Each institution has a subdomain: `<slug>.eduma.app` (locally `<slug>.localhost:4201`). Its page links to its own `/login`, for its members only. | Route prefix `/i/:institutionId` (04) |
| S1-05 | The API takes the institution from the request host. Platform routes stay under `/api/v1/platform/`. | 09 §1 institutional base |
| S1-06 | First sign-in uses a first password set by whoever creates the login, with a forced change before anything else. | 02 §7 and 03 WF-ONB step 6 (invitations) |
| S1-07 | Branding (logo, colours, fonts, public page) is the Institution Admin's alone; the System Admin only onboards the institution and activates it once its checklist is done. *Changed by the user on 18 Oct 2026; was: the System Admin could edit any institution's branding.* | 02 `institution_brand.update` ("System Admin during setup") |
| S1-08 | Creating an institution is one atomic, idempotent request (institution, admin login, membership, starter page). | 03 WF-ONB `draft`/`provisioning` steps |
| S1-09 | Lifecycle states now: `setup`, `active`, `suspended`, `archived`. `restricted` comes with module entitlements; `deletion_pending`/`deleted` with offboarding. | 03 WF-ONB (in part) |
| S1-10 | Public pages are a fixed set of section types that can be edited, hidden and reordered (not a free-form builder). The Eduma page uses the same renderer with its content kept in code. | — |
| S1-11 | Lists use page-number pagination, as in Student Connect, 5 rows a page (the user's rule: any list over 5 records gets pages). | 09 §1 cursors |
| S1-12 | An institution may have its own domain (e.g. `www.dps.edu.in`) as well as `<slug>.<base host>`, set by the System Admin in its details at any time. Its links use the own domain; the Eduma address keeps working. On a server `DJANGO_ALLOWED_HOSTS=*`, since Eduma serves only its base host, its subdomains and recorded domains. | — |
| S1-13 | Country, time zone and currency are chosen from lists taken from the browser's Intl data (ISO countries, current ISO 4217 currencies, IANA zones). | — |

## Slice 2 (organization, staff roles, modules, restricted state)

Full table and reasons: `docs/superpowers/specs/2026-10-18-slice2-organization-staff-modules-design.md` §2.

| ID | Decision |
|---|---|
| S2-01 | Authority comes from role assignments (role + whole institution, campus or department + start/end dates), not a single role on the membership. |
| S2-02, S2-03 | Built-in roles and the permission registry live in code; institutions add custom roles from the registry. Only permissions for built features are registered. |
| S2-04 | Seeing the institution's home comes with membership itself. |
| S2-05 | Staff logins get a first password with a forced change; a login ID is never reused across institutions. |
| S2-06, S2-07 | Grant ceiling: nobody gives what they don't hold, changes their own roles, or removes the last Institution Admin. |
| S2-08 | Role changes take effect at once, audited; approval routing comes with the configuration engine. |
| S2-09 | The platform records each institution's modules; none is built yet, so each says it arrives in a later release. |
| S2-10 | `restricted`: members can sign in and read; every change is refused with the reason. |
| S2-11 | Every institution has a Main campus. |
| S2-12 | Deferred: typed configuration engine, groups and affiliation grants, guardian grants, invitations, support access, approvals. |
| S2-13 | New permission names `organization.manage` and `membership.read`. |

## Pack defaults accepted for local development

Accepted by the user for local development on 12 Oct 2026 (pack 14 §3) and used in slice 1: D-02 (full catalogue kept,
built in order), D-07 (one institution = one tenant, `institution_id` boundary), D-08 (institution logo and validated
theme colours; semantic colours fixed), D-13 (recording off), D-15 (typed, versioned configuration with history),
D-18 (one complete theme first; no dark mode yet).

## Still open (carried forward, unchanged)

D-01 pilot boards and regulations · D-03 capacity targets · D-05 launch languages · D-06 team, budget and dates ·
D-12 providers (payment, email/SMS, storage, media) · D-14 residency, retention and recovery commitments ·
D-16 import formats · D-17 support coverage · D-21 hosting and region · D-22 mobile framework.

## Slice 3 (configuration engine, module enablement, approvals)

Full table and reasons: `docs/superpowers/specs/2026-10-19-slice3-configuration-approvals-design.md` §2.

| ID | Decision |
|---|---|
| S3-01, S3-02 | Settings are defined in code; institutions hold revisions: draft → waiting for approval → published → replaced, or returned / withdrawn. Published revisions are never edited. |
| S3-03 | A change starts on a chosen day (today or later); the value on any day is the latest published one that has started; a newer change cancels a not-yet-started one; restore puts an old value in a new draft. |
| S3-04, S3-05 | Changes that need approval are approved by someone else holding `configuration.publish`; `configuration.edit` drafts and sends. |
| S3-06, S3-07 | First settings: modules switched on (within the plan), approval for powerful roles (needs two whole-institution assigners), academic year start month. Modules in force = plan ∩ switched on. |
| S3-08 | While approval is on, a role beyond "see staff" waits until someone else who could give it approves. |
| S3-09 | No campus overrides yet. |
| S3-10 | Workspace menu grouped: Home · People · Administration. |
| S3-11 | Support access → BUILD-11; groups and affiliation grants → BUILD-05; guardian grants → BUILD-04; invitations and recovery wait for D-12. |

## Slice 4a (admissions to enrollment, student records)

Full table and reasons: `docs/superpowers/specs/2026-10-19-slice4a-admissions-students-design.md` §2.

| ID | Decision |
|---|---|
| S4-01 | Memberships have a kind: staff, applicant or student. Only staff get the `/app` workspace; applicants land on `/apply/applications`, students on `/student`. |
| S4-02 | Applicants make their own account on the institution's address; no email/SMS check yet (D-12 open). |
| S4-03 | An admission cycle holds its places (with seats), questions and required documents; editable while draft, frozen when published. |
| S4-04 | Applications have fixed core fields plus the cycle's questions; every submission keeps a snapshot. Stages run draft → submitted → under review ⇄ more information → eligible / not offered → offered → accepted → enrolled, with withdrawn and offer expired. |
| S4-05 | Reviewers (`application.review`) check and decide eligibility; approvers (`admission.approve`) offer and enroll; scope follows the place's campus. |
| S4-06 | Offers, acceptances and enrollments use seats; an offer locks the place and is refused when full. |
| S4-07 | Enrolling makes a Person, a Student (`<year>-NNNN`), an Enrollment and a student login `<slug>.<number>` with a first password, once only. |
| S4-08 | No admission payment until Fees (BUILD-08). |
| S4-09 | Documents are private PDF/JPEG/PNG files ≤ 5 MB, checked by content, served only to the family and to staff who may review. |
| S4-10 | Admissions and Students routes need their module switched on; otherwise 404. |
| S4-11 | New permissions `admission_cycle.manage`, `application.review`, `admission.approve`, `student.read`, `student.update`, given to Registrar, Admissions Officer and Principal as listed in the spec. |
| S4-12 | Applicant routes live under `/api/v1/applicant/` on the institution's own host. |

## Slice 4b (guardian links, family portal, withdrawal, staff records, history)

Full table and reasons: `docs/superpowers/specs/2026-10-19-slice4b-guardians-withdrawal-design.md` §2.

| ID | Decision |
|---|---|
| S4B-01 | A guardian link joins a student to an adult: proposed → active (verified) → revoked; expiry is computed from its end date; one live link per student and adult. |
| S4B-02 | Links come only from enrollment (to the application's owner) or from staff. Matching names or phones never make one. |
| S4B-03 | Verifying records the authority, how it was checked, a reference, dates and access; revoking needs a reason and takes effect at once. |
| S4B-04 | Access is per link: record (used now), fees and messages (stored for later modules). Paying fees never implies record access. |
| S4B-05 | A link for a student aged 18 or over needs the student's own consent; links made before the 18th birthday are flagged for review. |
| S4B-06 | Verified adults get a guardian login (or keep their applicant login, which becomes one). Staff and student logins cannot be guardians at the same school. |
| S4B-07 | New permission `guardian_link.manage` (Registrar, Institution Admin); `student.read` sees links without notes or evidence. |
| S4B-08 | Family portal `/family`: only children with an active, in-effect link, and only what it shares. |
| S4B-09 | Withdrawal (`student.update`) on or before today and not before the enrollment starts (or, for one that has not started, not before the admission); ends the enrollment and the student's login; reinstate undoes it. Fees untouched. |
| S4B-10 | Employee number (unique per school) and joining/leaving dates on staff. |
| S4B-11 | Every student record shows its own history, without guardian notes or evidence. |
| S4B-12 | Applications show possible duplicate students (same name and date of birth) as a warning; enrolling never merges. |

## Slice 4c (enquiries and staged student imports)

Full table and reasons: `docs/superpowers/specs/2026-10-19-slice4c-enquiries-imports-design.md` §2.

| ID | Decision |
|---|---|
| S4C-01 | Enquiries `E<year>-NNNN` with contact, child, place, message and source; open → following up → applied or closed; follow-ups with a next date. |
| S4C-02 | Families ask from the Apply page without an account; throttled (10 an hour per address) with a hidden honeypot field. |
| S4C-03 | New permission `enquiry.manage` (Registrar, Admissions Officer, Institution Admin), scoped by the place's campus. |
| S4C-04 | An enquiry is linked to an application by its number (final) or closed with a reason (can be reopened). |
| S4C-05 | Imports (`data.import`, Institution Admin): CSV UTF-8, ≤2 MB, ≤2,000 rows (until imports move to the job queue); checked in a dry run, imported only on commit, all or nothing. Synchronous for now. |
| S4C-06 | Contract `students-v1` (16 columns; template downloadable). |
| S4C-07 | Provenance per student (source system + source id + row checksum); a re-run never creates twice; changed rows are listed, not applied. |
| S4C-08 | Possible duplicates (same name and birth date, existing or earlier row) must be decided — create or skip; never merged. |
| S4C-09 | A commit makes Person, Student (`<year>-NNNN` from the academic year), Enrollment, provenance and a proposed guardian link; no logins. |
| S4C-10 | The error file lists row, column, code, message and source id only, with formula-like cells neutralised. |
| S4C-11 | A committed import can be undone while nothing it created has changed; a discarded file is deleted. |
| S4C-12 | Staff can give a student without a login one (`<school>.<number>`, first password). |

## Slice 5a (academic calendar, grades, sections, class placement, teaching assignments)

Full table and reasons: `docs/superpowers/specs/2026-10-23-slice5a-school-structure-design.md` §2.

| ID | Decision |
|---|---|
| S5A-01 | Academic years (no overlaps, one current) with terms inside them that don't overlap. |
| S5A-02 | Grades and subjects are institution-wide lists; school grades are not college programs (5b). |
| S5A-03 | Sections per year, grade and campus, with capacity and a class teacher; closed years are read-only. |
| S5A-04 | One placement per study episode per year (EnrollmentPeriod); full sections refuse; moves within a year are audited. |
| S5A-05 | Teaching assignments open a teacher's own class lists (number, name, status) — a relationship, not a campus permission. |
| S5A-06 | Move up / repeat into a later year's section: preview, then one transaction, idempotent; last year's placement stays. |
| S5A-07 | New permission `academic_structure.manage` (Registrar, Institution Admin), campus-scoped for sections. |
| S5A-08 | A placement can't be earlier than the year the student is enrolled for. |
| S5A-09 | Records, the student's page and the family portal show this year's class; staff see the history. |
| S5A-10 | Module `academics` gates every route. |

## Slice 5b (programs, regulations, courses, offerings, college batches)

Full table and reasons: `docs/superpowers/specs/2026-10-23-slice5b-programs-curricula-design.md` §2.

| ID | Decision |
|---|---|
| S5B-01 | Programs: code unique per institution, qualification, optional department, 1–16 terms. |
| S5B-02 | Regulations (curriculum versions) go draft → published → retired; only a draft changes; New revision copies a published one into a draft n+1; publishing needs a course. |
| S5B-03 | Courses: code unique per institution, credits 0–30 in halves, a kind, optional department. |
| S5B-04 | A regulation lists each course once, with category, term within the program's length, elective group and prerequisites from the same regulation, never in a loop. |
| S5B-05 | Offerings: course, term, campus, section code, seats; planned → open → closed (or cancelled); a link to another offering of the same term; teachers are teaching assignments of the offering. |
| S5B-06 | College batches are sections naming a program instead of a grade (exactly one); placement, class lists and move-up are shared. |
| S5B-07 | Enrolling into a place with a program pins the program and the latest published regulation for that cohort; staff with `student.update` change it, only to a published regulation of the chosen program. |
| S5B-08 | Programs and courses are managed at their department (none: the whole institution); regulations follow their program; offerings follow the course's department, else their campus. |
| S5B-09 | The menu follows the category (colleges and universities get Programs, Courses, Offerings); the API allows both everywhere. |
| S5B-10 | Demo regulation content is labelled synthetic, for development. |

## Slices 5c–5e (registration, attempts and progress, affiliation)

Full table and reasons: `docs/superpowers/specs/2026-10-24-slice5c-registration-progress-affiliation-design.md` §2.

| ID | Decision |
|---|---|
| S5C-01 | A registration window per term: opens, closes, drop deadline, credit limit, adviser approval. |
| S5C-02 | Each failed rule has its own code; six are overridable, enrollment, regulation, offering status, links and capacity never are; timetable conflicts wait for BUILD-06. |
| S5C-03 | One confirmation covers several offerings that commit together; a lecture with labs needs exactly one lab; seats are claimed under locks; full → 409 `capacity_exhausted` or waitlisted on request (single unlinked offerings). |
| S5C-04 | States pending approval (holds a seat), waitlisted, registered, rejected, dropped (attempt removed), withdrawn (attempt kept); one active registration per student and offering. |
| S5C-05 | Waitlist promotion rechecks eligibility; whoever no longer qualifies is rejected with the rule. |
| S5C-06 | Overrides name student, offering and rule, with reason, expiry, grantor and the regulation and window versions; used once. |
| S5C-07 | Holds (academic or administrative) block registration until lifted. |
| S5C-08 | Students register themselves; staff with `registration.manage` for them; new role Academic Adviser. |
| S5D-01 | A registered registration creates the attempt; outcomes are recorded and never deleted. |
| S5D-02 | The regulation's repeat rule (replace, best, all) decides which attempts count; credits count once. |
| S5D-03 | SGPA/CGPA are computed exactly from attempts and shown to two decimals; absent, withheld and exempt are not zeroes. |
| S5D-04 | Transfer credit records source, evidence, decision, approved credits, equivalent course and awarding authority. |
| S5D-05 | Degree progress is advisory and labelled so: earned vs accepted toward the award, in progress, planned, unmet. |
| S5E-01 | Affiliation grants (college → university) are proposed by the platform, approved by the college, revocable by either; in effect only while approved and in dates. |
| S5E-02 | Result batches snapshot each student's identity, program, regulation and the term's attempts; rows with problems block submitting. |
| S5E-03 | The university reviews row by row while the grant is in effect, with a reason for each returned row. |
| S5E-04 | Corrections are new revisions of the same batch; the latest accepted row is the current record; history stays; the university never changes the college's records. |

## Slice 6 (timetable, teaching and attendance)

Full table: `docs/superpowers/specs/2026-10-24-slice6-timetable-attendance-design.md`.

| ID | Decision |
|---|---|
| S6-01 | Rooms per campus. |
| S6-02 | Timetable versions per term (draft → published, publishing supersedes); weekly slots for a section or an offering. |
| S6-03 | Clashes of room, teacher, section or offering are listed and block publishing (409 `timetable_conflict`). |
| S6-04 | Substitutions move one day's lesson to another teacher. |
| S6-05 | A teacher's day comes from published timetables, minus lessons someone covers, plus covers. |
| S6-06 | Sessions draft → submitted → locked; present and late count, absent counts against, excused doesn't count; unmarked is not absent. |
| S6-07 | Rosters include only students enrolled on that date. |
| S6-08 | Teachers mark their own classes for the last 7 days; managers any day, and lock. |
| S6-09 | Corrections after submitting are approved by another manager and keep the original mark. |
| S6-10 | Students see their own attendance; guardians when the record is shared; staff on the record. |
| S6-11 | Assignments with text submissions; changeable until feedback; late flagged. |
| S6-12 | Module `attendance`; permission `attendance.manage`. Offline capture not selected. |

## Slice 7 (assessments, results and awards)

Full table: `docs/superpowers/specs/2026-10-24-slice7-results-design.md`.

| ID | Decision |
|---|---|
| S7-01 | Schemes: components (maximum, weight, minimum %), pass %, grade bands, decimals; published ones frozen; a change is a revision. |
| S7-02 | Assessments for a section + subject or an offering, pinned to a published scheme revision, with a roster snapshot. |
| S7-03 | Marks are scores or absent / exempt / withheld; missing is no mark; nothing becomes zero. |
| S7-04 | Draft → submitted → moderated (someone other than the submitter) → published (`results.publish`), all marks present, one batch. |
| S7-05 | Total = Σ score ÷ maximum × weight, exact, rounded for display; component minimums can fail a passing total; exempt rescales. |
| S7-06 | Result versions are immutable with hashed inputs; corrections supersede. |
| S7-07 | An offering's published result sets the attempt's outcome. |
| S7-08 | Revaluation raised by a moderator or publisher, approved by another publisher. |
| S7-09 | School promotion decisions per year. |
| S7-10 | Report cards, transcripts and awards are numbered, hashed, verifiable snapshots; reissue supersedes; revoke with reason. |
| S7-11 | Public verification shows institution, kind, number, date, initials and status only. |
| S7-12 | Course outcomes and attainment runs from published marks; not an accreditation claim. |
| S7-13 | App `results`; modules `exams`, `report_cards`, `outcomes`; permissions `assessment.manage`, `results.moderate`, `results.publish`. |

## Slice 8 (fees, payments and reconciliation)

Full table: `docs/superpowers/specs/2026-10-24-slice8-fees-design.md`.

| ID | Decision |
|---|---|
| S8-01 | Fee heads and plans; published plans frozen; invoices keep the plan revision. |
| S8-02 | Balances are computed from posted records; 0 ≤ net allocated ≤ net charges. |
| S8-03 | Credit notes need a second person; going below what is paid returns the excess to credit. |
| S8-04 | Office payments are received when recorded; online ones only on a verified provider event; one receipt per payment, numbers never reused; unapplied money stays visible. |
| S8-05 | Refunds reserve capacity, need a second person, and post only when the money is confirmed returned; they never reduce the charge. |
| S8-06 | Balanced, append-only journals with unique posting keys; trial balance and CSV export are the accounting boundary. |
| S8-07 | Provider events are signed, stored and de-duplicated; out-of-order events never undo a final state; mismatches are quarantined. |
| S8-08 | Settlements move clearing to bank and record provider fees; mismatches open cases. |
| S8-09 | Staff with `fees.read`, the student, and guardians of shared records see statements. |
| S8-10 | App and module `fees`; permissions `fees.read/manage/collect/approve/reconcile`; only a test-mode sandbox provider until D-12. |

## Slice 9 (communication and teacher-led classes)

Full table: `docs/superpowers/specs/2026-10-24-slice9-communication-design.md`.

| ID | Decision |
|---|---|
| S9-01 | A communication policy per institution: guardians may start, calls, classes, default quiet hours. |
| S9-02 | Family conversations (assigned teachers or communication managers with guardians whose link allows messages) and staff conversations; newcomers see history from joining. |
| S9-03 | Messages are stored first, numbered, idempotent per sender and client id; reading is a separate marker. |
| S9-04 | Relationships are rechecked on every read and write; students don't message or call in this slice. |
| S9-05 | In-app notifications respect each recipient's quiet hours. |
| S9-06 | Calls ring for 45 s, need the media provider to connect, and can't be answered again once over. |
| S9-07 | Classes are hosted by the class's own teacher, with a waiting room; without the host they pause, then close after 60 s. |
| S9-08 | Media tokens are signed, role-bound, 5-minute, and revoked by bumping a version. |
| S9-09 | Join/leave times are evidence only; reconnects aren't double-counted. |
| S9-10 | App and module `communication`; permission `communication.manage`; only a test-mode sandbox until D-12; recording off (D-13). |

## Slice 10a (library, transport, hostel)

Full table: `docs/superpowers/specs/2026-10-24-slice10a-library-transport-hostel-design.md`. S10A-01 catalogue and
copies; S10A-02 locked issue, limits, overdue block, renewals; S10A-03 reservations hold returned copies; S10A-04 fines
through fees, waivers kept, lost distinct; S10A-05 route capacity over overlapping dates; S10A-06 trips, one boarding,
approved pickup at drop-off; S10A-07 guardians see only their child's route and trip state; S10A-08 beds never
doubled, transfers atomic; S10A-09 out-passes; S10A-10 app `campus`, modules available.

## Slice 10b (HR, payroll boundary, procurement, assets, labs)

Full table: `docs/superpowers/specs/2026-10-24-slice10b-hr-stores-design.md`. S10B-01 leave with balance, overlap and
no self-approval (requests start submitted: no drafts, my call); S10B-02 staff attendance; S10B-03 own leave only;
S10B-04 pay settings only with `payroll.manage` (approvers see the lines of the cycle they approve); S10B-05 payroll prepared → validated → approved by another → exported and
frozen, one cycle per month (adjustment cycles not built); S10B-06 rule revisions kept on requisitions, two approvers
above the limit; S10B-07 receipts capped at the order, stock never negative; S10B-08 assets; S10B-09 lab booking
without overlap; S10B-10 apps `hr` and `stores`. Asset hand-over is by username, since a store keeper can't list staff.

## Slice 10c (services and grievances, placements, research, quality)

Full table: `docs/superpowers/specs/2026-10-25-slice10c-services-development-design.md`. S10C-01 one case aggregate,
confidential by type; S10C-02 per-viewer projections (requester / current assignee / triage shell), explicit audited
assignment (an admin role alone discloses nothing; an admin can still assign a case to themself, which the audit log
shows); S10C-03 note audiences, excerpt-free notifications, no export; S10C-04 one appeal in 15 days, another reviewer;
S10C-05 consented, eligibility-checked placement applications; S10C-06 internships; S10C-07 consented alumni; S10C-08
research with ethics validity and supervisor-only decisions; S10C-09 versioned evidence and frozen snapshots; S10C-10
apps `cases` and `development`. Supervisors and evidence owners are given by username (offices can't list staff).

## BUILD-11 (operations)

Full table: `docs/superpowers/specs/2026-10-25-build11-operations-design.md`. S11-01 code-defined, scope-respecting
reports with provenance; S11-02 small confidential groups suppressed; S11-03 exports as jobs with rechecked download
and expiry; S11-04 `run_jobs` worker with heartbeat and scheduled tasks; S11-05 health tiles with unknown kept
unknown; S11-06 alerts that resolve on recovery; S11-07 read-only usage; S11-08 backup and restore drill scripts with a
recorded, measured drill; S11-09 app `operations`, permission `report.export`. The separate `course_registration` and
`affiliations` module switches stay unavailable: those features are built and run under Academics, and a switch that
did nothing would mislead (recorded for BUILD-12).
