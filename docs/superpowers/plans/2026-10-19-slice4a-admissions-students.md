# Eduma Slice 4a (admissions to enrollment, students, student logins) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Online applications at an institution's address, staff review to offer within places, acceptance, and
enrollment into student records with student logins.

**Architecture:**
- `Membership.kind` separates staff, applicants and students.
- Two new apps: `admissions` (cycles, places, questions, documents, applications, submissions, notes) and `students`
  (person, student, enrollment).
- Every state change is a service function that locks the application or place row.
- Angular: a public Apply page, an applicant portal, staff Admissions and Students pages, and a student portal.

**Tech Stack:** as slices 1–3.

**Spec:** `docs/superpowers/specs/2026-10-19-slice4a-admissions-students-design.md`.

## Global Constraints

- **Slices 1–3 constraints hold.** That covers problem JSON, `version`/409, UUIDs, 5 a page, search from 3 characters, ruff with line length 120 excluding migrations, no push and no `Co-Authored-By`.
- **Permission names, exactly:** `admission_cycle.manage`, `application.review`, `admission.approve`, `student.read`, `student.update`.
- **Membership kinds, exactly:** `staff`, `applicant`, `student`.
- **Application stages, exactly:** `draft`, `submitted`, `under_review`, `needs_information`, `eligible`, `rejected`, `offered`, `offer_expired`, `accepted`, `enrolled`, `withdrawn`.
- **Problem codes:** `no_seats` (409), `invalid_transition` (409), `admissions_closed` (409), `module_off` (never shown, since the gate answers 404).
- **Number formats:**
  - Student number: `<academic-year start year>-<0001…>` per institution.
  - Application number: `A<start year>-<0001…>` per cycle.
- **Documents:** PDF/JPEG/PNG, at most 5 MB, sniffed from the file content. Downloads use `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`.

## Review Focus

1. Two browser tabs submitting the same draft → one submission, the second gets a 409 `version_conflict` (Task 5).
2. A date of birth in the future or an impossible date (31 Feb) → 422 on `date_of_birth` (Task 5).
3. An applicant uploading for a requirement code from another cycle → 422 (Task 6).
4. Staff enrolling with a weak first password → 422 on `password`, nothing created (Task 8).
5. A place's campus deactivated after publishing → its applications stay reviewable by whole-institution reviewers (Task 7).

---

### Task 1: Membership kinds, new permissions, module availability

**Files:**
- Modify:
  - `backend/accounts/models.py` (`Membership.Kind`, `kind`), plus a migration
  - `backend/accounts/roles.py` (five permissions; built-in role grants per S4-11)
  - `backend/accounts/permissions.py`: `has_perm` gives `institution.read` only to staff memberships; `perms_anywhere` is empty for non-staff
  - `backend/accounts/serializers.py`: Me gets `membership.kind`
  - `backend/institutions/modules.py`: `admissions`, `students` set to `available=True`
  - `backend/sites/permissions.py`: `member_with` refuses non-staff
  - `backend/accounts/views.py`: no change to sign-in
- Test: `backend/accounts/tests/test_kinds.py`

**Interfaces:**
- `Membership.Kind.STAFF/APPLICANT/STUDENT`, default staff.
- `accounts.permissions.member_of_kind(user, institution, kind) -> Membership | None`.
- Me: `membership.kind`.

- [ ] **Step 1: Write the failing tests:**
  - `test_applicant_and_student_memberships_get_no_workspace`: a member of kind applicant gets `has_perm(..., "institution.read")` False, and `GET /api/v1/institution` gives 403. They can still sign in on the host, and Me shows `kind: "applicant"`.
  - `test_builtin_roles_gain_admissions_permissions`:
    - Registrar ⊇ {`admission.approve`, `application.review`, `student.read`, `student.update`}
    - Admissions Officer ∋ `application.review`
    - Principal ∋ `student.read`
    - Institution Admin ∋ all five
- [ ] **Step 2–4: RED, then implement, then GREEN.** The full suite stays green.
- [ ] **Step 5: Commit** `Membership kinds and admissions permissions`.

### Task 2: Students app (Person, Student, Enrollment) and the module gate helper

**Files:**
- Create: `backend/students/{apps,models}.py`, `backend/students/migrations`, `backend/students/tests/test_models.py`
- Create: `backend/configuration/gates.py`

**Interfaces:**
- `students.models.Person`, `Student`, `Enrollment`, as in spec §3.
- `Student.objects.next_number(institution, start_year: int) -> str`, run under a lock on the institution row.
- `configuration.gates.module_on(institution, key) -> bool`.
- `configuration.gates.require_module(institution, key)`, which raises `Http404`.

- [ ] **Step 1: Write the failing tests:**
  - Numbers run `2027-0001`, then `2027-0002`, and are per institution.
  - Only one active enrollment per student (IntegrityError).
  - `module_on` follows `modules.enabled` ∩ plan.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Students, enrollments and the module gate`.

### Task 3: Admission cycles (models, staff API, publish/close)

**Files:**
- Create: `backend/admissions/{apps,models,cycles,cycle_views,urls}.py`, migrations
- Create: `backend/admissions/tests/test_cycles.py`

**Interfaces:**
- Models per spec §3.
- `admissions.cycles.save_cycle(institution, actor, cycle | None, data) -> AdmissionCycle`. Nested `places`, `questions` and `documents` are replaced as whole lists, and only while the cycle is a draft.
- `publish(institution, actor, cycle, version)`: needs at least one place and `opens_on <= closes_on`.
- `close(...)`.
- `place_usage(place) -> int`.
- Routes under `institution/admissions/` (spec §5).

- [ ] **Step 1: Write the failing tests:**
  - An admin creates a cycle with two places, three questions and two documents. `academic_year` comes from `academic.year_start` for `opens_on`.
  - A PATCH after publishing gives 409 `invalid_transition`.
  - Publishing a cycle with no places gives 422.
  - Without `admission_cycle.manage`, the answer is 403.
  - With the module off, the answer is 404.
  - Bad question kinds and duplicate codes give 422.
  - Another institution's cycle gives 404.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Admission cycles`.

### Task 4: Public admissions page data and applicant sign-up

**Files:**
- Create: `backend/admissions/{public,applicant_auth}.py`, `backend/admissions/tests/test_public_signup.py`
- Modify: `backend/config/urls.py`

**Interfaces:**
- `GET /api/v1/public/admissions` (spec §5).
- `POST /api/v1/applicant/signup` `{full_name, username, email, phone, password}` → 201 with the Me payload, and the session is signed in. It uses the login throttle, Django password validation and global login-ID uniqueness.

- [ ] **Step 1: Write the failing tests:**
  - The public page lists only published, unclosed cycles, with no seat numbers.
  - With the module off, it returns `{"open": false, "cycles": []}`.
  - Sign-up creates a user and an applicant membership, and the session is signed in.
  - A duplicate login ID gives 422 on `username`.
  - On the platform host the route returns 404.
  - Sign-up is refused while the institution is suspended.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Public admissions information and applicant sign-up`.

### Task 5: Applications — the applicant side

**Files:**
- Create:
  - `backend/admissions/applications.py` (services)
  - `backend/admissions/applicant_views.py`
  - `backend/admissions/serializers.py` (applicant and staff shapes kept separate)
  - `backend/admissions/tests/test_applicant.py`

**Interfaces:**
- `start(owner, institution, cycle_id, place_id, key) -> Application`
- `edit(owner, application, version, data) -> Application`
- `submit(owner, application, version) -> Application`
- `withdraw(owner, application, version)`
- `accept(owner, application, version)`
- `applicant_item(application) -> dict`: excludes notes, reviewer, decided_by and review notes.

- [ ] **Step 1: Write the failing tests:**
  - TST-033 owner isolation, with two applicants and injected fields ignored.
  - Submit validation lists each missing field.
  - Submitting is refused outside the open/close dates.
  - A date of birth in the future, or 2027-02-31, gives 422 (Review Focus 2).
  - A double submit gives 409 (Review Focus 1).
  - The submission snapshot is stored, and numbers run `A2027-0001`.
  - Editing is only allowed in draft and needs_information.
  - Withdraw works before acceptance and is refused after it.
  - Accept is only allowed in `offered` before expiry; after expiry it gives 409.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Applications: applicant side`.

### Task 6: Documents

**Files:**
- Create: `backend/admissions/documents.py`, `backend/admissions/tests/test_documents.py`
- Modify: views and urls

**Interfaces:**
- `upload(actor, application, requirement_code, file) -> Document`
- `download_response(document) -> FileResponse`
- Private storage `FileSystemStorage(location=PRIVATE_MEDIA_ROOT)`. The setting is `DJANGO_PRIVATE_MEDIA_ROOT`, defaulting to `backend/private_media`, which is git-ignored.

- [ ] **Step 1: Write the failing tests:**
  - A PDF and a PNG are accepted.
  - A text file named `.pdf` gives 422.
  - A file over 5 MB gives 422.
  - A requirement code from another cycle gives 422 (Review Focus 3).
  - Replacing a document marks the old one `replaced`.
  - Another applicant's document gives 404.
  - Download headers match the Global Constraints.
  - Uploading is only allowed in draft and needs_information.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Application documents`.

### Task 7: Staff review, offers and seats

**Files:**
- Create: `backend/admissions/review.py`, `staff_views.py`, `tests/test_review.py`

**Interfaces:**
- `start_review`, `request_information(message)`, `mark_eligible`, `reject(reason)`, `offer(expires_on)`, `verify_document`, `reject_document(note)`, `add_note`.
- Every one checks the actor's scope through `can_review(actor, application)` and `can_approve(actor, application)`.
- A staff list and detail. The detail includes notes, submissions and documents with review state.

- [ ] **Step 1: Write the failing tests:**
  - The full happy path to `offered`.
  - Asking for information reopens the application, and resubmitting returns it to `submitted` with the same number and revision 2.
  - Seats: making two offers when one place is left gives one 409 `no_seats`, and an expired offer frees its seat.
  - A City reviewer sees only City applications.
  - Review Focus 5: a place whose campus was deactivated stays reviewable by whole-institution reviewers.
  - Applicant payloads never contain `notes`.
  - A wrong-stage move gives 409 with the current stage named.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Admissions review, offers and seats`.

### Task 8: Enrollment, students API, student portal API

**Files:**
- Create: `backend/admissions/enrollment.py`
- Create: `backend/students/{views,serializers,urls}.py`, `backend/students/tests/test_students.py`
- Modify: `backend/admissions/tests/test_enrollment.py`

**Interfaces:**
- `enroll(actor, application, version, password) -> Student`. It is idempotent: an already-enrolled application returns its student. It creates the Person, the Student, the Enrollment and a User with kind `student` and `must_change_password=True`.
- Students list, detail and PATCH.
- `GET /api/v1/student/me`.

- [ ] **Step 1: Write the failing tests:**
  - TST-009: enrolling twice gives one of everything.
  - Enrolling before acceptance gives 409.
  - A weak password gives 422 and creates nothing (Review Focus 4).
  - The student signs in on the institution's host, and `GET /api/v1/student/me` shows the number `2027-0001`. The student gets 403 on `/api/v1/institution` and 404 on staff routes.
  - The students list is scoped and searchable.
  - PATCH is version-checked and refused without `student.update`.
  - With the module off, the answer is 404.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Enrollment into student records and student logins`.

### Task 9: Denial sweep and demo data

**Files:**
- Create: `backend/admissions/tests/test_denials.py`
- Modify: `seed_demo.py` (+ test)

- [ ] **Step 1: Write the sweep.** Every admissions, applicant and student route is tried:
  - on the platform host, expecting 404;
  - on another institution's host with Aster ids, expecting 404;
  - signed out, expecting 403 `authentication_required`;
  - as an applicant against staff routes, expecting 403 or 404.
- [ ] **Step 2: Extend the demo data.** It is idempotent and adds:
  - an Aster cycle "Admissions 2027–28", published, open from today to today+60, with places Class 1 (40, Main) and Class 6 (10, Main), three questions and two documents (birth certificate and photo, both required);
  - an applicant `aster.parent` ("Aster Demo Parent") with one submitted application;
  - one enrolled student `aster.student` with student number `2027-0001` and the password `Demo-pass-2026`, already changed;
  - an Admissions Officer `aster.admissions` and a Registrar `aster.registrar`.
- [ ] **Step 3: Run the tests, then commit** `Admissions denial sweep and demo data`.

### Task 10: Frontend — kinds, routing, public Apply page, sign-up

**Files:**
- Modify: `core/api/types.ts`, `core/auth-store.ts` (`home` by kind), `core/guards.ts` (`memberOnly` staff only; `applicantOnly`, `studentOnly`), `app.routes.ts`
- Create: `features/apply/apply-page.ts`, `features/apply/signup-page.ts`, specs

- [ ] **Step 1: Write the failing tests:**
  - `home` is `/apply/applications` for an applicant, `/student` for a student and `/app` for staff.
  - `memberOnly` refuses an applicant.
  - The Apply page lists cycles and their places. When admissions are closed it shows "Admissions are not open right now."
  - Sign-up posts the body and then navigates to `/apply/applications`.
- [ ] **Step 2–4: RED, then implement, then GREEN.** The build is clean.
- [ ] **Step 5: Commit** `Apply page, applicant sign-up and routing by kind`.

### Task 11: Frontend — applicant portal

**Files:**
- Create: `features/apply/applications-page.ts`, `application-form-page.ts`, specs

- [ ] **Step 1: Write the failing tests:**
  - The form saves with `version` and shows a missing-items list from the server's 422.
  - A document upload posts multipart.
  - Submit is disabled until the form is saved.
  - In `offered`, the page shows "Accept offer" and the expiry date.
  - In `needs_information`, it shows the staff message and reopens the form.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Applicant portal`.

### Task 12: Frontend — staff Admissions (cycles and applications)

**Files:**
- Create: `features/admissions/{cycles-page,cycle-editor-page,applications-page,application-review-page}.ts`, specs
- Modify: `layout/nav.ts` (group "Admissions": Cycles needs `admission_cycle.manage`; Applications needs `application.review` or `admission.approve`; both only when `modules_enabled` includes admissions, which needs the module list on Me)
- Modify: `accounts/serializers.py` (Me gets `modules_enabled`)

- [ ] **Step 1: Write the failing tests:**
  - The nav shows the Admissions group only when the module is on.
  - The cycle editor's place, question and document lists add and remove rows, and the editor publishes.
  - The review page shows only the actions its stage allows (eligible → "Offer a place" with an expiry date).
  - Enroll asks for a first password.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Staff admissions pages`.

### Task 13: Frontend — Students directory and record, student portal

**Files:**
- Create: `features/students/{students-page,student-page}.ts`, `features/student/student-home.ts`, specs
- Modify: nav (People: Students, with `student.read` and the module on), routes

- [ ] **Step 1: Write the failing tests:**
  - The directory searches from 3 characters and pages.
  - The record edits with `version`.
  - The student portal shows the student number and the current enrollment.
- [ ] **Step 2–4: RED, then implement, then GREEN.**
- [ ] **Step 5: Commit** `Students directory and student portal`.

### Task 14: Docs and browser check

- [ ] **Docs:** update `README.md` (new personas and pages), `docs/decisions.md` (S4 rows) and `docs/progress.md`.
- [ ] **Browser checks, at 1280 px and 390 px:**
  1. As a new parent, sign up and apply.
  2. Upload both documents and submit.
  3. As `aster.admissions`, review, ask for information, then mark eligible after the resubmission.
  4. As `aster.registrar`, offer a place.
  5. As the parent, accept.
  6. As `aster.registrar`, enroll.
  7. As the new student, sign in, change the password and see the portal.
- [ ] Run the full suites, lint and build. Commit `Slice 4a docs and verification`.
