# Eduma slice 4a — admissions to enrollment, students and student logins (BUILD-04, part 1)

**Date:** 19 October 2026 · **Status:** written from the spec pack at the user's request ("start this"); build rulings
marked.
**Source pack:** 03 WF-ADM; 04 SCR-016–019 and the applicant route contract; 05 §3 applicant self-service mode and
walkthrough 7; 08 §4 (Person, Student, AdmissionCycle/PublishedApplicationForm, Application, ApplicationAuthority,
ApplicationSubmission/InformationRequest, ApplicationDocument/Review, Offer/AdmissionDecision, Enrollment); 09 §4.7
(applicant ownership API); 02 §4 (`application.*`, `admission.approve`, `student.read/update`); TST-002, TST-009, TST-033.
**Builds on:** slices 1–3. Uses `modules.enabled` (S3-07) and `academic.year_start` (S3-06).
**Part 2 (slice 4b):** guardian links and parent logins, the fuller student and family portals, enquiries, withdrawal
after enrollment, staged spreadsheet imports (TST-025).

## 1. What this slice is for

A school can open admissions for next year, families apply online at the school's own address, staff review the
applications, make offers within the places available, and turn accepted offers into enrolled students who get their
own logins. Every step is recorded; nobody sees an application that is not theirs; places are never over-filled.

**Success:** Aster opens "Admissions 2027–28" with Class 1 (40 places) and Class 6 (10 places) at Main campus, three
questions and two required documents. A parent signs up at `aster.localhost:4201/apply`, fills in an application for
their child, uploads the birth certificate and photo, and submits. The Admissions Officer reviews it, asks for a clearer
photo; the parent replaces it and resubmits; the officer marks it eligible; the Registrar offers a place (expiring in
14 days); the parent accepts; the Registrar enrolls the child, which creates student number `2027-0001` and a student
login with a first password. Two applicants never see each other's applications or files. Accepting twice, enrolling
twice or racing for the last place never creates two students or overfills a class.

**Anti-goals:** an applicant seeing staff notes or another applicant's data; a browser value deciding institution,
owner, stage or outcome; enrolling before acceptance; a person merged into another because a name or phone matched;
admissions screens shown when the module is switched off.

## 2. Decisions

| ID | Decision | Pack reference / why |
|---|---|---|
| S4-01 | `Membership` gains `kind`: `staff` (all existing), `applicant`, `student` (and `guardian` in 4b). Only staff memberships get `institution.read` and the `/app` workspace; applicants land on `/apply/applications`, students on `/student`. Sign-in, sessions and suspension rules are unchanged for every kind. | 09 §4.7 "limited applicant membership … never grants student-directory, employee or institution-configuration access" |
| S4-02 | **Applicant accounts** are created by the applicant on the institution's address (`/apply/signup`): name, login ID, optional email and phone, password. No email/SMS verification yet (D-12 open); the account is marked unverified. One account per institution in this slice; using one login at several institutions comes later. | 09 §4.7 "policy-enabled account verification flow"; build ruling |
| S4-03 | **Admission cycle** = the pack's AdmissionCycle + PublishedApplicationForm in one record: name, academic year (from `academic.year_start`), open/close dates, instructions, **places** (code, label such as "Class 1" or "B.Sc Physics", optional campus, seats), **questions** (code, label, kind `text`/`long_text`/`date`/`choice`/`yes_no`, options, required) and **required documents** (code, label, required). Editable only while `draft`; publishing freezes it (the frozen cycle is the form revision); `closed` stops new applications and submissions. | 08 §4; build ruling: a separate form-revision table arrives when a published form needs changing mid-cycle |
| S4-04 | **Application** core fields are fixed (learner name, date of birth, guardian name/relationship/phone/email, address, previous school) because enrollment needs them; cycle questions go in `answers`. Stages: `draft → submitted → under_review → needs_information ⇄ (resubmitted) → eligible / rejected → offered → accepted → enrolled`; `withdrawn` by the applicant before `accepted`; an offer past its expiry date becomes `offer_expired`. Each submission stores an immutable **snapshot** (revision number, answers, document list). | WF-ADM states; 05 §3 "submitted versions remain preserved" |
| S4-05 | **Who does what:** applicants (owners) create, edit (draft and needs_information only), upload, submit, withdraw and accept. Staff with `application.review` start review, verify or reject documents, request information, mark eligible or reject, and write internal notes. Staff with `admission.approve` make offers and enroll. `admission_cycle.manage` sets up cycles. Review scope follows the place's campus (a campus-scoped reviewer sees applications for places at that campus; places with no campus need whole-institution scope). | 02 §4 action matrix; walkthrough "assigned cycle/program" → build ruling: campus is the assignable scope today |
| S4-06 | **Seats:** offers, acceptances and enrollments count against a place's seats; making an offer locks the place's row and refuses when full. Expired offers and withdrawals free the seat. | WF-ADM "atomic seat allocation" |
| S4-07 | **Enrollment** (by `admission.approve`, only from `accepted`) creates, in one transaction and once only (a second call returns the same student): a `Person` for the learner (never merged with an existing one), a `Student` (number `<start year>-<4-digit sequence>` per institution), an `Enrollment` (academic year, place label/code, campus, entry date, status active), and a student login with a first password chosen by the staff member (forced change), membership kind `student`. The guardian named in the application is stored on the application only; guardian records and logins come in 4b. | WF-ADM; TST-009 |
| S4-08 | **Admission payment policy**: none in this slice (fees are BUILD-08); enrollment needs no payment. | WF-ADM "applicable admission-payment policy" |
| S4-09 | **Documents** are private files (PDF, JPEG or PNG, ≤ 5 MB, content checked, not just the extension) stored outside the public media path, served only to the owner and to staff who may review that application, never cached publicly. A replaced document keeps the old one as `replaced`. | 08 §4 ApplicationDocument; TST-033 |
| S4-10 | **Module gate:** every admissions route needs `admissions` switched on (`setting(..., "modules.enabled")`) and every student route needs `students`; otherwise 404 for applicants and staff alike, and the public page says admissions are not open. The catalogue marks `admissions` and `students` as available. | 01 §7; S3-07 |
| S4-11 | New permissions: `admission_cycle.manage` (whole institution), `application.review`, `admission.approve`, `student.read`, `student.update` (campus-scopable). Built-in roles gain: Institution Admin all; Registrar `admission.approve`, `application.review`, `student.read`, `student.update`; Admissions Officer `application.review`; Principal `student.read`. | 02 §3–4 |
| S4-12 | Applicant routes live under `/api/v1/applicant/` on the institution host (the host is the institution; no slug in the path, S1-05). Public admission information is `/api/v1/public/admissions`. | 09 §4.7 adapted to host-based tenancy |

## 3. Data model

New app `admissions`: **AdmissionCycle** (`VersionedModel`: institution, name ≤120, academic_year label, opens_on,
closes_on, instructions ≤2000, status draft/published/closed, created_by), **Place** (cycle, code, label ≤80, campus
null, seats ≥1, order; unique cycle+code), **Question** (cycle, code, label ≤200, help ≤300, kind, options list,
required, order; unique cycle+code), **DocumentRequirement** (cycle, code, label, help, required, order),
**Application** (`VersionedModel`: institution, cycle, place, owner (User), number null (assigned on first submit:
`A<start year>-<4-digit sequence per cycle>`), stage, learner_name, date_of_birth, guardian_name,
guardian_relationship, guardian_phone, guardian_email, address, previous_school, answers JSON, revision (submissions
so far), information_request ≤1000, decision_reason ≤500, offer_expires_on null, submitted_at, decided_by, student
null), **Submission** (application, revision, snapshot JSON, submitted_at, submitted_by), **Document** (application,
requirement, file (private storage), original_name, content_type, size, status `pending`/`verified`/`rejected`/
`replaced`, review_note, reviewed_by, uploaded_by, uploaded_at), **Note** (application, author, text ≤2000, created_at).

New app `students`: **Person** (`VersionedModel`: institution, full_name, date_of_birth null, phone, email, address),
**Student** (`VersionedModel`: institution, person (one-to-one), number (unique per institution), admitted_on, status
active/withdrawn, application (one-to-one, null), user null), **Enrollment** (`VersionedModel`: student, institution,
academic_year, place_code, place_label, campus null, entry_date, status active/ended; one active per student).

`Membership.kind` (default `staff`). Data migration: none needed (existing rows are staff).

## 4. Rules (in addition to §2)

- **Applicant editing:** only in `draft` and `needs_information`, version-checked; the client can never set stage,
  owner, number, reviewer fields or outcome (unknown fields ignored, never trusted).
- **Submit:** cycle published and today within open/close dates (institution's day); all required core fields,
  required questions answered with valid values (date parses, choice in options, yes_no boolean) and every required
  document present and not rejected; else 422 listing each missing item as a field error
  (`answers.<code>`, `documents.<code>`). Creates a Submission snapshot; `needs_information → submitted` keeps the
  number.
- **Staff transitions:** `submitted → under_review` (start review); `under_review → needs_information` (message
  required) / `eligible` / `rejected` (reason required); `eligible → offered` (expiry date ≥ today + 1, seat check);
  `offered → accepted` (applicant, before expiry); `accepted → enrolled` (first password); any other move 409
  `invalid_transition` naming the current stage. Concurrent transitions are serialised by locking the application row.
- **Offer expiry:** an `offered` application whose `offer_expires_on` is before today is shown and treated as
  `offer_expired` (computed on read and stored the first time something touches it); it no longer holds a seat;
  accepting it is refused.
- **Seats in use** for a place = applications at `offered` (not expired), `accepted` or `enrolled`.
- **Visibility:** applicants see only their own applications (`owner == user`); anything else is 404. Staff list/detail
  require `application.review` or `admission.approve` covering the place's campus (whole institution when the place has
  no campus). Applicant payloads never include notes, reviewer names, document review notes on verified documents, or
  other applicants' data.
- **Audit:** cycle created/published/closed; application submitted (by owner), every staff transition, document
  verified/rejected, offer made/accepted, enrollment; student created.

## 5. API

Public (institution host): `GET /api/v1/public/admissions` → `{open: bool, cycles: [{id, name, academic_year, opens_on,
closes_on, instructions, places: [{id, label, campus_name}], documents: [{code, label, required}]}]}` for published
cycles not yet closed; never seat counts or applicant data. 404 off the institution host or when the module is off →
`{open: false, cycles: []}`.

Applicant (`/api/v1/applicant/`, institution host): `signup` POST (throttled like login; signs the new account in);
`applications` GET (own) / POST `{cycle, place}` (Idempotency-Key header honoured); `applications/<id>` GET / PATCH
(`version` + core fields + `answers`); `.../submit`, `.../withdraw`, `.../accept` POST `{version}`;
`.../documents` POST multipart `{requirement, file}`; `.../documents/<doc>` GET (download).

Staff (`/api/v1/institution/admissions/`): `cycles` GET/POST, `cycles/<id>` GET/PATCH (draft only; nested places,
questions, documents replaced as lists), `cycles/<id>/publish`, `cycles/<id>/close` POST; `applications` GET (`cycle`,
`stage`, `place`, `search` ≥3 chars on number/learner/guardian, paged) ; `applications/<id>` GET; `.../start-review`,
`.../request-information {message}`, `.../eligible`, `.../reject {reason}`, `.../offer {expires_on}`,
`.../enroll {password}` POST (all with `version`); `.../notes` POST `{text}`; `.../documents/<doc>/verify` and
`/reject {note}` POST; `.../documents/<doc>` GET. Summary for SCR-016: `cycles/<id>` includes per place `seats`,
`in_use`, and counts per stage.

Students (`/api/v1/institution/students`): GET (search by number/name, `status`, paged; `student.read` covering the
enrollment's campus), `students/<id>` GET, PATCH `{version, full_name, date_of_birth, phone, email, address}`
(`student.update`). Student portal: `GET /api/v1/student/me` (kind student) → own Person, Student number, enrollment.

## 6. Screens

- **Public page**: the institution's "Apply" call to action and an **Admissions** page `/apply`: open cycles with places,
  dates, instructions and required documents; **Start an application** (sign up or sign in). Closed or switched-off:
  "Admissions are not open right now."
- **Applicant portal** (`/apply/applications`, kind applicant): own applications with stage and next step; **New
  application** (cycle and place); the **application form** in sections — Learner, Parent or guardian, Questions,
  Documents — saving as it goes (version-checked), with a "Missing before you can submit" list; **Submit**; after
  submission a read-only view with the stage explained, the information request (and the form reopened) when asked,
  **Accept offer** before its expiry, **Withdraw** before acceptance.
- **Staff — Admissions** (menu group "Admissions" when the module is on and the person holds an admissions permission):
  **Cycles** list and editor (details, places, questions, documents; Publish, Close) with seats and stage counts;
  **Applications** list (filters, search, paged) and detail (answers, documents with view/verify/reject, submission
  history, internal notes, and the actions the stage allows).
- **Staff — Students** (menu, People group, `student.read`): directory (search, paged) and record (details, enrollment,
  admission provenance link; edit with `student.update`).
- **Student portal** (`/student`, kind student): my details, student number, current enrollment, "More arrives with
  each module".

## 7. Tests that must exist

1. TST-033: two applicants at one institution — each sees and changes only their own application and files (404 for
   the other's ids, including document downloads); injected `owner`, `stage`, `number`, `institution` fields are
   ignored; an applicant cannot reach staff or student routes (404/403) or `/app`.
2. TST-009: enrolling twice returns the same student, one Student, one Enrollment, one login; enrolling before
   acceptance or after withdrawal is refused with a reason.
3. Seats: the last seat offered twice in parallel (two threads or two sequential calls racing the lock) → one offer, one
   409 `no_seats`; an expired offer frees its seat.
4. Submit validation: missing required question/document → 422 with each field; outside open/close dates → 422/409;
   draft-only and needs-information-only editing.
5. Module gate: admissions switched off → public says not open, applicant and staff routes 404.
6. Scope: a City-campus reviewer sees City places' applications only.
7. Documents: wrong type by content (a text file named .pdf) → 422; > 5 MB → 422; another institution's document id →
   404; responses carry `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`.
8. Student login works only on the institution's address and lands on the student portal; it cannot open `/app`.

## 8. Left to the builder

Layout of the applicant form on phones (one column, sections), copy within the tone above, file layout inside the two
new apps.
