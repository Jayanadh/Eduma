# Eduma slice 5c–5e — course registration, attempts and degree progress, university affiliation (BUILD-05, parts 3–5)

**Date:** 24 October 2026 · **Status:** written from the spec pack at the user's request ("continue and build faster";
5c, 5d and 5e as one slice, no per-slice browser check or review). Build rulings marked.
**Source pack:** 03 WF-ACA §6.2 (registration checks, states, seat claims, waitlist), §6.3 (attempts, equivalence,
degree audit), ACL §6 (exchange grants, affiliation snapshots); 05 API §4.3 (course registration, 409
`capacity_exhausted`); 04 SCR-028/029 (registration and degree progress), SCR-031 (affiliation exchange); 08
CourseRegistration/CourseAttempt; EX-03 and TST-013 (7.57 / 8.43 SGPA fixture); TST-010; BUILD-05 bullets 2–5.
D-01 (real regulations) and D-15 (rule limits) are open, so every rule is generic and typed; nothing claims a real
university's scheme.
**Builds on:** 5b (programs, regulations, courses, offerings, pins), 5a (terms), 4a (enrollment), 1 (institutions).
**Later:** timetable conflicts (BUILD-06, there is no timetable yet); exam results feeding attempts (BUILD-07);
transcripts and awards (BUILD-07).

## 1. What this slice is for

A college student registers for a term's offerings against their pinned regulation; the server checks every rule and
claims seats so the last seat goes to exactly one person, a lecture and its lab commit together, and a full course can
be waitlisted. Every attempt at a course is kept; a repeat counts by the regulation's repeat rule and credits count
once; SGPA/CGPA follow EX-03. Transfer credit is recorded with its evidence and authority. Degree progress shows
completed, in progress, planned and unmet credits — advisory, never an award. A college affiliated to a university
submits approved result batches across the tenant boundary under an explicit grant; the university reviews row by
row; corrections are new revisions with history.

**Success:** Meridian's registration window for Semester 1 is open; Ananya registers PHY101-A with lab PHY101L-A1 in
one confirmation; two students racing for PHY101-A's last seat → one registered, one 409 `capacity_exhausted`; PHY201
without PHY101 passed → refused `prerequisite` unless an adviser granted an override (reason, authority, regulation
version recorded; capacity still applies). Courses A (4 credits, 8) and B (3 credits, 7) give SGPA 7.57; repeating B
with 9 under `replace` gives 8.43 with both B attempts kept and 7 credits earned. Summit University and Meridian have
an active grant; Meridian submits a Semester 1 batch; Summit accepts one row and rejects another with a reason;
Meridian's revision 2 corrects the rejected row; a revoked grant stops both sides.

**Anti-goals:** two registrations for the last seat; a lab without its lecture (or a lecture whose labs exist without
one); an override that bypasses capacity; a hidden bypass; an attempt erased by a repeat; credits counted twice;
rounded semester results averaged; a degree-progress page that reads as an award; a university editing a college's
record; access continuing after a grant is revoked or expires.

## 2. Decisions

| ID | Decision |
|---|---|
| S5C-01 | **Registration window** per term: opens, closes, drop deadline, credit limit (default 30), whether registrations need an adviser's approval. Managed by `registration.manage` for the whole institution. |
| S5C-02 | **Checks**, each with its own code: `not_enrolled`, `no_regulation`, `window_closed`, `hold`, `offering_closed`, `not_in_regulation`, `prerequisite`, `already_passed`, `credit_limit`, `linked_section`, `capacity_exhausted`. Overridable: `window_closed`, `hold`, `not_in_regulation`, `prerequisite`, `already_passed`, `credit_limit`. Never: enrollment, regulation, offering status, links, capacity. Timetable conflicts wait for BUILD-06 (*build ruling*). |
| S5C-03 | **One confirmation, many offerings**: a request names one or more offerings of the same term that commit together. An offering with linked labs needs exactly one of them in the same request (or already registered); a linked lab needs its lecture. Seats are claimed with the offerings locked in id order. Full → 409 `capacity_exhausted` for the whole request, or `waitlisted` when the request asks for it and is a single offering with no links (*build ruling*). |
| S5C-04 | **States** `pending_approval` (holds a seat), `waitlisted`, `registered`, `rejected`, `dropped` (until the drop deadline; its attempt is removed), `withdrawn` (after; its attempt stays as `withdrawn`). One active registration per enrollment and offering (database constraint); asking again returns the existing one. |
| S5C-05 | **Waitlist promotion** when a seat frees (drop, withdraw, reject): oldest first, rechecking eligibility; one that no longer qualifies is rejected with the failed code. |
| S5C-06 | **Overrides**: `registration.override` grants one per student, offering and check, with reason and expiry; the registration records which overrides it used, who granted them, and the regulation and window versions. Used once. |
| S5C-07 | **Holds** (academic or administrative) with reason, placed and lifted by `registration.manage`; an active hold refuses registration with `hold`. |
| S5C-08 | Students register from their portal for themselves; staff with `registration.manage` register for them, approve or reject pending ones, drop and withdraw. New built-in role **Academic Adviser** (`student.read`, `registration.manage`, `registration.override`); Registrar gains the three new permissions. |
| S5D-01 | **Attempts**: a registered registration creates the attempt (number = previous attempts at that course + 1). Outcomes `in_progress` → `passed` / `failed` (with grade point 0–10) / `absent` / `withheld` / `exempt` / `withdrawn`, recorded by `academic_record.manage` until exam results (BUILD-07) feed them. Never deleted once recorded. |
| S5D-02 | **Repeat rule** on the regulation (set while draft, copied by revise): `replace` (latest graded attempt counts; default), `best`, `all` (every graded attempt counts in the average). Credits count once per course in every rule. |
| S5D-03 | **SGPA/CGPA** = Σ(credits × grade point) / Σ credits over counted graded attempts (passed and failed), computed exactly from attempts and shown to two decimals (half up). Absent, withheld, exempt, in progress and withdrawn are distinct and not zero. SGPA is per term; CGPA over all terms. |
| S5D-04 | **Transfer credit**: source institution and course, source credits, evidence, decision (pending → approved / rejected) with approved credits, the equivalent course (optional) and category, awarding authority, decided by `academic_record.manage`. |
| S5D-05 | **Degree progress** (advisory): credits required; earned (passed attempts + approved transfers) and accepted toward this award (only courses of the pinned regulation or transfers mapped to it); in progress; planned (regulation courses not yet taken); unmet; by category; each regulation course's status. Labelled "advisory — not an award". |
| S5E-01 | **Affiliation grant** between a college or engineering college (granting) and a university (receiving): purpose, data categories (identity, program and regulation, course attempts and outcomes), permitted action (submit result batches), effective dates, approval evidence. Proposed by the platform admin, approved by the granting college's Institution Admin, revocable by either side's Institution Admin. In effect = approved, not revoked, today within its dates. |
| S5E-02 | **Batches**: the college (`affiliation.submit`) builds a batch for a grant, program and term: a row per student pinned to the program with attempts that term, snapshotting number, name, program, regulation and attempts. Rows with problems (no regulation, an attempt still in progress) are listed and must be removed before submitting. Submitting rechecks the grant. |
| S5E-03 | **Review**: the university (`affiliation.review`) sees submitted batches only while the grant is in effect (rechecked on every read); accepts or rejects each row (a reason required); a batch with every row decided is `reviewed`. |
| S5E-04 | **Corrections**: the next revision of the same batch (same reference) carries the rejected rows re-snapshotted and any accepted rows marked as corrections; submitting a revision twice changes nothing. The university's current record of a student is their latest accepted row; earlier ones stay as history. The university never changes the college's records. |

## 3. Data model

`academics`: **RegistrationWindow** (`VersionedModel`: institution, term (one), opens_on, closes_on, drop_until,
max_credits (4,1), needs_approval); **Hold** (institution, student, kind, reason, placed_by/on, lifted_by/on);
**CourseRegistration** (`VersionedModel`: institution, enrollment, offering, state, curriculum, window,
requested_by, decided_by/at, reason_code; partial unique enrollment+offering over active states); **RegistrationOverride**
(institution, student, offering, check, reason, expires_on, granted_by/at, curriculum, window_version, used_by
registration null); **CourseAttempt** (institution, enrollment, course, attempt_no, registration null, term, credits,
outcome, grade_point (4,2) null, recorded_by/at; unique enrollment+course+attempt_no); **CreditTransfer**
(`VersionedModel`: institution, enrollment, source_institution, source_course, source_credits, evidence, decision,
approved_credits, course null, category, awarding_authority, decided_by/at, created_by). **CurriculumVersion.repeat_rule**.

`affiliations` (new app): **AffiliationGrant** (`VersionedModel`: college, university, purpose, starts_on, ends_on,
evidence, status proposed/active/revoked, proposed_by, approved_by/at, revoked_by/at/reason); **SubmissionBatch**
(grant, reference uuid, revision, program_code, term_label, status draft/submitted/reviewed, created_by,
submitted_by/at; unique reference+revision); **SubmissionRow** (batch, student (the college's, for re-snapshotting),
number, full_name, program, regulation, attempts JSON, problems JSON, is_correction, status pending/accepted/rejected,
reason, decided_by/at).

## 4. API

Institution (`/api/v1/institution/academics/`): `windows` GET/POST, `windows/<id>` PATCH; `registrations` GET
(`offering`, `student`, `state`) / POST `{student, offerings[], waitlist}`; `registrations/<id>/approve|reject|drop|withdraw`
POST `{version}`; `students/<id>/holds` GET/POST, `holds/<id>/lift` POST; `overrides` POST / GET (`student`);
`attempts` GET (`student`), `attempts/<id>` PATCH `{outcome, grade_point}`; `transfers` GET (`student`) / POST,
`transfers/<id>/decide` POST; `students/<id>/progress` GET.
Student portal (`/api/v1/student/`): `registration` GET (window, eligible offerings with seats and checks, my
registrations), POST `{offerings[], waitlist}`; `registrations/<id>/drop` POST; `progress` GET.
Teaching: `classes/offerings/<id>/students` (registered students).
Affiliations: console `/api/v1/platform/affiliations` GET/POST; institution `/api/v1/institution/affiliations` GET,
`<id>/approve|revoke` POST, `<id>/batches` GET/POST `{program, term}`, `batches/<id>` GET/DELETE row
`rows/<row>`, `batches/<id>/submit` POST, `batches/<id>/revise` POST `{corrections[]}`; university side
`received` GET, `received/<id>` GET, `received/<id>/rows/<row>` POST `{decision, reason}`.

## 5. Screens

Student: **Registration** (open window, offerings of my regulation with seats and the checks that would fail, choose,
confirm; my registrations with Drop) and **Degree progress**. Staff: offerings page gains the term's **Registration
window**; offering page lists registrations (approve, reject, drop) and the waitlist; the student record gains
**Courses** (registrations, register for them, holds, overrides, attempts with outcomes, transfer credit, degree
progress). My classes opens an offering's class list. Console: **Affiliations** (propose grants). Institution
**Affiliations**: a college approves/revokes grants and builds, previews, submits and corrects batches; a university
reviews received batches row by row.

## 6. Tests that must exist

TST-010 (prerequisite → blocked; full → waitlisted on request; override records reason/authority/version and doesn't
bypass capacity; last-seat race → one registered, one 409; lecture+lab atomic); duplicate request returns the existing
registration; drop before/after the deadline; waitlist promotion rechecks; holds; credit limit; window closed.
TST-013 (7.57; repeat → 8.43 under replace, both attempts kept, 7 credits; `best` and `all`); transfer credit counted
in earned and, when mapped, toward the award; progress buckets. Affiliation: inactive/expired grant refuses submit and
review; duplicate submit keeps one revision; partial rejection → revision 2 of rejected rows; corrected accepted row
keeps history; revoked after submission → the university loses access; a row with a draft regulation or an attempt in
progress blocks submit. Isolation: other institutions' ids 404; module `academics` gates.

## 7. Left to the builder

Layouts and copy; seed content (synthetic).
