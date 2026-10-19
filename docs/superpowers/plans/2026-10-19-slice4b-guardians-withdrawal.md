# Slice 4b — guardian links, family portal, withdrawal, staff records and history — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish BUILD-04's people half: verified guardian links with a family portal, withdrawal and reinstatement of
students, employee numbers for staff, a history on every student record, and duplicate warnings at enrollment.

**Architecture:** New `GuardianLink` and `Employee` models beside the existing `students` and `accounts` apps; link
and withdrawal rules live in `students/guardians.py` and `students/withdrawal.py` as plain service functions called by
thin DRF views (the pattern of `admissions/review.py`). The family portal is a new kind-gated API under
`/api/v1/family/` and an Angular portal page using the existing `PortalFrame`.

**Tech Stack:** Django 6.1, DRF 3.18, PostgreSQL 17, pytest; Angular 22 (zoneless, signals), Vitest.

**Spec:** `docs/superpowers/specs/2026-10-19-slice4b-guardians-withdrawal-design.md`

## Global Constraints

- Every versioned write takes `version` and answers 409 `version_conflict` when stale (`VersionedModel.check_version`).
- Errors are RFC 9457 problem JSON with a `code`; field errors 422; wrong state 409 `invalid_transition`.
- Students routes need the `students` module on (`configuration.gates.require_module`), else 404.
- Dates are the institution's own day (`accounts.permissions.today_for`).
- Backend lint: `.venv/bin/ruff check --select F,E,W,I --line-length 120 --exclude '.venv,*/migrations' .` and
  `ruff format --check` with the same options. Never run ruff over migrations or at the default line length.
- Copy is plain and short; no stock photos; pages of 5 with the shared pager; search from 3 characters.
- Commits: repo-local author, no co-author line, never push.

## Review Focus

1. A guardian whose link ended yesterday (`ends_on` < today) → the child disappears from `/family` today (Task 4).
2. A family request for a student id that belongs to another institution, with a valid active link at this one → 404
   (Task 4).
3. Withdrawing a student whose enrollment `entry_date` is in the future (enrolled for next year) with today's date →
   422 "before the enrollment starts" (Task 5).
4. Verifying a link with a new login ID that already exists anywhere → 422 on `login.username`, nothing created, link
   still proposed (Task 3).
5. Staff who hold `student.read` at City campus listing guardians of a Main-campus student → 404 (Task 3).

---

### Task 1: Models, kinds and the new permission

**Files:**
- Modify: `backend/students/models.py` (GuardianLink; `Student.left_on`; `Enrollment.exit_date`, `exit_reason`),
  `backend/accounts/models.py` (`Membership.Kind.GUARDIAN`; `Employee`), `backend/accounts/roles.py`
  (`guardian_link.manage`, campus-scopable, group "Students", label "Verify and revoke guardian links"; given to
  Registrar; Institution Admin gets it through `*PERMISSIONS`), migrations for both apps.
- Test: `backend/students/tests/test_models.py`, `backend/accounts/tests/test_kinds.py`

**Interfaces:**
- Produces: `GuardianLink.Status.PROPOSED/ACTIVE/REVOKED`; `GuardianLink.Basis` (`parent`, `legal_guardian`,
  `court_order`, `student_consent`, `other`); `GuardianLink.Method` (`documents_in_person`, `documents_on_file`,
  `court_order`, `other`); `GuardianLink.Source` (`enrollment`, `staff`); fields per spec §3, related names
  `student.guardian_links`, `person.guardian_of`; `GuardianLink.in_effect(today) -> bool` (active and
  `starts_on <= today <= ends_on or ends_on is None`). `Employee` (`membership` one-to-one, related name `employee`).

- [ ] **Step 1: Failing tests:** `test_one_live_link_per_student_and_adult` (a second proposed link for the same pair
  raises `IntegrityError`; after revoking the first, a new one is allowed); `test_link_in_effect_follows_dates`
  (active with `ends_on` yesterday → False; proposed → False; active, no end → True);
  `test_employee_number_unique_per_institution_but_blank_repeats` (two blank numbers fine at one institution; the same
  number at two institutions fine; the same number twice at one → `IntegrityError`);
  `test_registrar_holds_guardian_link_manage` (`BUILTIN_ROLES["registrar"]`, `["institution_admin"]` include it;
  `PERMISSIONS["guardian_link.manage"].institution_only is False`).
- [ ] **Step 2: Run** `cd backend && .venv/bin/python -m pytest students/tests/test_models.py accounts/tests/test_kinds.py -q` → FAIL.
- [ ] **Step 3: Implement** the models and constraints (`UniqueConstraint(fields=["student", "adult"],
  condition=Q(status__in=["proposed", "active"]), name="one_live_guardian_link")`; `UniqueConstraint(fields=
  ["institution", "employee_number"], condition=~Q(employee_number=""), name="unique_employee_number")`), the permission
  and role grant, then `makemigrations students accounts`.
- [ ] **Step 4: Run** the same tests → PASS; then the full backend suite → PASS.
- [ ] **Step 5: Commit** `Guardian link and employee models`.

### Task 2: Links proposed at enrollment and by staff

**Files:**
- Create: `backend/students/guardians.py`
- Modify: `backend/admissions/enrollment.py` (call `propose_from_application` inside its transaction; log
  `student.enrolled` with target the student), `backend/admissions/tests/test_enrollment.py`
  (`test_enrolling_twice_makes_one_student` now expects `Person.objects.count() == 2`: learner and adult)
- Test: `backend/students/tests/test_guardians.py`

**Interfaces:**
- Consumes: Task 1 models.
- Produces: `propose_from_application(actor, student: Student, application: Application) -> GuardianLink` (adult
  Person from `guardian_name/phone/email/address`, `user = application.owner`, relationship =
  `guardian_relationship`, source `enrollment`; returns the existing live link when re-run);
  `propose(actor, student: Student, adult: dict, relationship: str) -> GuardianLink` (source `staff`, no user);
  `log_link(actor, link, action: str, summary: str)` (audit with target **the student**, changes `{link, adult,
  relationship, status}` only).

- [ ] **Step 1: Failing tests:** `test_enrollment_proposes_one_link_to_the_owner` (after enroll: one link, status
  proposed, user = owner, relationship "Mother", adult name "Asha Rao"; enroll again → still one);
  `test_matching_phone_never_links` (two families with the same guardian phone, one enrolled → the other owner has no
  link to that student); `test_staff_propose_needs_no_login` (link created with `user=None`, source staff, audit row
  `student.guardian_proposed` on the student).
- [ ] **Step 2: Run** `pytest students/tests/test_guardians.py admissions/tests/test_enrollment.py -q` → FAIL.
- [ ] **Step 3: Implement** the three functions and wire `propose_from_application` into `enroll`.
- [ ] **Step 4: Run** → PASS; full backend suite → PASS.
- [ ] **Step 5: Commit** `Guardian links proposed at enrollment`.

### Task 3: Verify, revoke and the staff guardian API

**Files:**
- Modify: `backend/students/guardians.py`, `backend/students/views.py`, `backend/students/serializers.py`,
  `backend/students/urls.py`
- Test: `backend/students/tests/test_guardian_api.py`

**Interfaces:**
- Produces: `can_manage_links(actor, student) -> bool` (`guardian_link.manage` at the student's current campus, as
  `_scope` in `students/views.py`); `verify(actor, link, version, data: dict) -> GuardianLink`;
  `revoke(actor, link, version, reason: str) -> GuardianLink`; `link_item(link, full: bool) -> dict` (`full` adds
  `restrictions`, `authority_basis`, `verification_method`, `verification_reference`; always `id, version, adult:
  {full_name, phone, email}, relationship, status, in_effect, access: {record, fees, messages}, starts_on, ends_on,
  has_login, source, needs_adult_review`). Routes per spec §5 under `institution/students/<uuid:pk>/guardians`.
- Rules: verify requires status proposed (409) and student active (409); 18+ on the day needs basis
  `student_consent` (422 on `authority_basis`); `login` creates `User` (`must_change_password=True`, password policy,
  username normalized and unique → 422 `login.username`) or reuses `link.user`; the adult's membership at this
  institution: none → create guardian; applicant → guardian; staff/student → 409 `kind_conflict`. `needs_adult_review`
  = active, verified before the 18th birthday, student 18+ today, basis ≠ `student_consent`.

- [ ] **Step 1: Failing tests:** `test_verify_activates_and_makes_a_guardian` (applicant owner → membership kind
  guardian; link active with flags record=True, fees=False); `test_verify_twice_and_stale_version_409`;
  `test_adult_student_needs_consent` (DOB 18 years ago → 422; with `student_consent` → 200);
  `test_new_login_for_guardian` (creates user, forced change; taken username → 422 and link still proposed, no user
  row); `test_staff_or_student_login_cannot_be_linked` (409 `kind_conflict`); `test_revoke_needs_reason_and_is_final`;
  `test_read_without_manage_hides_evidence` (`student.read` only → no `restrictions`/`verification_reference` keys;
  POST verify → 403); `test_other_campus_reader_gets_404` (Review Focus 5); `test_other_institution_ids_404`;
  `test_guardians_need_students_module`.
- [ ] **Step 2: Run** `pytest students/tests/test_guardian_api.py -q` → FAIL.
- [ ] **Step 3: Implement** services and views (lock the link row with `select_for_update`; one transaction for
  verify including the login).
- [ ] **Step 4: Run** → PASS; full suite → PASS.
- [ ] **Step 5: Commit** `Verify and revoke guardian links`.

### Task 4: Family API and kind routing

**Files:**
- Create: `backend/students/family.py` (views), `backend/students/family_urls.py`
- Modify: `backend/config/urls.py` (`api/v1/family/`), `backend/admissions/applicant_views.py` (`ApplicantView`
  admits only kinds applicant and guardian; others 404)
- Test: `backend/students/tests/test_family.py`

**Interfaces:**
- Produces: `GET /api/v1/family/children` → list (not paged; a family is small) of `child_item(link) -> dict`
  (`{id: student id, full_name, shared}` plus `number, status, left_on, enrollment` only when `access_record`);
  `GET /api/v1/family/children/<uuid>` → one item or 404. Kind guardian only; institution host only; module off →
  `[]` for the list and 404 for one child.

- [ ] **Step 1: Failing tests:** `test_proposed_link_shows_nothing`; `test_active_link_shows_child_then_revoke_hides`
  (revoke → list empty and detail 404); `test_ended_link_hides_child` (Review Focus 1); `test_record_off_is_neutral`
  (`shared` False and no `number`/`enrollment` keys); `test_other_family_child_404`;
  `test_other_institution_student_404` (Review Focus 2: same user, guardian at a and b, asks a's host for b's
  student); `test_payload_has_no_evidence_or_other_guardians`; `test_guardian_keeps_applicant_pages`;
  `test_staff_and_students_cannot_use_applicant_routes` (404); `test_guardian_cannot_reach_staff_or_student_api`.
- [ ] **Step 2: Run** `pytest students/tests/test_family.py -q` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS; full suite → PASS.
- [ ] **Step 5: Commit** `Family portal API`.

### Task 5: Withdrawal and reinstatement

**Files:**
- Create: `backend/students/withdrawal.py`
- Modify: `backend/students/views.py`, `backend/students/urls.py`, `backend/students/serializers.py`
  (`student_item` adds `left_on`, `exit_reason` of the latest ended enrollment, `can_withdraw`, `can_reinstate`;
  `enrollment_item` adds `exit_date`, `exit_reason`)
- Test: `backend/students/tests/test_withdrawal.py`

**Interfaces:**
- Produces: `withdraw(actor, student, version, effective_on: date, reason: str, clearance_note: str) -> Student`;
  `reinstate(actor, student, version) -> Student`. Both need `student.update` at the student's scope (403), lock the
  student row, audit `student.withdrawn` / `student.reinstated` on the student.
- Rules: `effective_on > today` → 422 "Withdrawal can't be scheduled yet; record it on the day."; `effective_on <`
  active enrollment's `entry_date` → 422 "That is before the enrollment starts."; reason blank → 422; not active →
  409. Withdraw: enrollment `ended`, `exit_date`, `exit_reason`; student `withdrawn`, `left_on`; student membership
  revoked. Reinstate: student withdrawn and no enrollment newer than the ended one → reopen it, clear `exit_*` and
  `left_on`, membership active.

- [ ] **Step 1: Failing tests:** `test_future_date_422`; `test_before_entry_422` (Review Focus 3);
  `test_withdraw_ends_enrollment_and_sign_in` (the student's session client then gets 403/401 on `student/me` and a
  fresh login is refused); `test_withdraw_twice_409_and_stale_409`; `test_reinstate_restores_sign_in`;
  `test_withdraw_needs_student_update`; `test_records_and_audit_remain`.
- [ ] **Step 2: Run** `pytest students/tests/test_withdrawal.py -q` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS; full suite → PASS.
- [ ] **Step 5: Commit** `Withdraw and reinstate students`.

### Task 6: Employee records, history and possible duplicates

**Files:**
- Modify: `backend/accounts/staff_serializers.py` (`StaffInput` and `DetailsInput` gain `employee_number` ≤20 and
  `joined_on`; `staff_item`/`staff_detail` add `employee: {number, joined_on, left_on}`), `backend/accounts/staff.py`
  (`create_staff` makes the Employee; `remove` sets `left_on` today when empty; `restore` clears it),
  `backend/accounts/staff_views.py` (PATCH writes employee fields; duplicate number → 422 `employee_number`),
  `backend/students/views.py` + `urls.py` (`StudentHistory`: `GET students/<id>/history`, paged, audit rows with
  `object_type="student"` and that id, newest first → `{at, actor, action, summary, changes}`),
  `backend/admissions/serializers.py` (`staff_item` adds `possible_duplicates`)
- Test: `backend/accounts/tests/test_employee.py`, `backend/students/tests/test_history.py`,
  `backend/admissions/tests/test_enrollment.py`

**Interfaces:**
- Produces: `students.views.possible_duplicates(institution, name: str, date_of_birth) -> list[dict]` (`{id, number,
  full_name}`; match `Lower` of whitespace-collapsed name and equal DOB; empty when DOB is null).

- [ ] **Step 1: Failing tests:** `test_add_staff_with_employee_number` and `test_duplicate_employee_number_422`;
  `test_only_a_manager_edits_employee_details` (Campus Admin on an Institution Admin → 403);
  `test_remove_sets_left_on_and_restore_clears_it`; `test_history_lists_this_students_changes` (enrolled, corrected,
  link verified, withdrawn → four entries newest first; no `restrictions` text anywhere in the payload);
  `test_history_needs_scope` (other-campus reader → 404); `test_possible_duplicates_warns_but_enrolls_separately`
  (existing "arjun  DEMO" same DOB listed; enrolling creates a second Person and Student).
- [ ] **Step 2: Run** the three test files → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS; full suite and lint → PASS.
- [ ] **Step 5: Commit** `Employee details, student history and duplicate warnings`.

### Task 7: Demo data

**Files:** Modify `backend/institutions/management/commands/seed_demo.py`.

- [ ] **Step 1:** Arjun's enrollment link to `aster.parent` verified by the registrar (basis parent, method
  documents_in_person, reference "Seen at admission", record on); a second guardian "Lakshmi Demo" (grandmother) with
  login `aster.grandparent`, record off; employee numbers `AST-001`… for Aster staff with joining dates. Idempotent on
  re-run.
- [ ] **Step 2: Run** `.venv/bin/python manage.py seed_demo` twice → no errors; `aster.parent` membership kind guardian.
- [ ] **Step 3: Commit** `Demo guardians and employee numbers`.

### Task 8: Frontend — family portal and routing by kind

**Files:**
- Create: `frontend/src/app/features/family/family-home.ts`, `family-child-page.ts`, `family.spec.ts`
- Modify: `core/api/types.ts` (`Membership.kind` adds `'guardian'`; `FamilyChild`), `core/auth-store.ts` (`home`:
  guardian → `/family`), `core/guards.ts` (`applicantOnly` admits applicant and guardian; `guardianOnly`),
  `app.routes.ts` (`family`, `family/children/:id` with `[signedIn, guardianOnly]`),
  `features/apply/portal-frame.ts` (guardians get a "Your children" / "Applications" switch)

**Interfaces:** `FamilyChild = {id, full_name, shared, number?, status?, left_on?, enrollment?: StudentEnrollment}`.

- [ ] **Step 1: Failing specs:** lists shared and unshared children (shared shows number and class; unshared shows
  "Your school has not shared this record with you." and no number); child page shows "Left on 1 Mar 2027" for a
  withdrawn child; guardian home is `/family`; `applicantOnly` lets a guardian through.
- [ ] **Step 2: Run** `cd frontend && npx ng test --watch=false` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS; `npx ng build` clean.
- [ ] **Step 5: Commit** `Family portal`.

### Task 9: Frontend — guardians, withdrawal and history on the student record; staff employee fields

**Files:**
- Create: `frontend/src/app/features/students/guardians-section.ts`, `withdraw-dialog` via `ConfirmDialog.prompt`
  where it fits, `history-section.ts`
- Modify: `features/students/student-page.ts` (sections, header actions, "Left on"), `students-page.ts` (status
  filter Active / Withdrawn / All), `features/admissions/application-review-page.html` (duplicate warning),
  `features/staff/add-staff-page.ts` and `staff-detail-page.ts` (Employee number, Joined on), `core/api/types.ts`
- Test: `features/students/students.spec.ts`, `features/staff/*.spec.ts`

- [ ] **Step 1: Failing specs:** verify sends `version`, basis, method, reference, access flags and optional login;
  revoke asks for a reason; withdraw posts `effective_on` and reason; history renders newest first with paging;
  the status filter sends `status=withdrawn`; add staff sends `employee_number`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (forms reuse the page patterns of `student-page.ts`; leave-guard on the verify form).
- [ ] **Step 4: Run** → PASS; `npx ng build` clean.
- [ ] **Step 5: Commit** `Guardians, withdrawal and history on student records`.

### Task 10: Docs and browser check

- [ ] **Docs:** README (personas `aster.grandparent`, guardian landing, pages), `docs/decisions.md` S4B rows,
  `docs/progress.md`.
- [ ] **Browser, 1280 px and 390 px:** as `aster.registrar` verify a proposed link and add a second guardian with a
  login; as that guardian sign in, change the password, see the child unshared; revoke → gone on reload; withdraw a
  student → their login refused, record shows "Left on"; reinstate → sign-in works; set an employee number on a staff
  page.
- [ ] Full suites, lint and build. Commit `Slice 4b docs and verification`.
