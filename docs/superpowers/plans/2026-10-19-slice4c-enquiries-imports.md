# Slice 4c — enquiries and staged student imports — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish BUILD-04: enquiries from first question to application, and a staged, provenance-tracked,
re-runnable student import with dry run, duplicate review, error file and undo.

**Architecture:** Enquiries live in `admissions` beside applications (same campus-scope rule as `review.visible`).
Imports get their own app `imports`: `contract.py` parses and validates a CSV into rows (pure functions), `services.py`
uploads, decides, commits, discards and undoes (transactions and locks), thin DRF views on top. Commit reuses
`students` models and `students.guardians` for proposed links.

**Tech Stack:** Django 6.1, DRF 3.18, PostgreSQL 17, Python `csv`/`hashlib`; Angular 22, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-19-slice4c-enquiries-imports-design.md`

## Global Constraints

- Versioned writes take `version`; stale → 409 `version_conflict`. Wrong state → 409 `invalid_transition`. Field errors 422.
- Admissions routes need module `admissions`; imports and student logins need `students`; else 404.
- Private files under `PRIVATE_MEDIA_ROOT`, never under `MEDIA_ROOT`; no URL serves an import file.
- Dates on the institution's day (`today_for`). Pages of 5; search from 3 characters.
- Backend lint with the 120-column ruff command, migrations excluded. Commits: repo-local author, no co-author line.

## Review Focus

1. Two commits of the same batch at once (double click) → one commit, the other 409; no duplicate students (Task 4).
2. A CSV saved by Excel: UTF-8 BOM, `\r\n` line ends, trailing blank lines, spaces around values → parsed cleanly (Task 3).
3. A row whose `source_record_id` was imported by a *different* batch committed after this dry run → treated as
   already imported at commit, not created twice (Task 4).
4. An enquiry assigned to a staff member who later loses `enquiry.manage` → still shown with its assignee, and
   reassigning to someone without the permission → 422 (Task 2).
5. Undo after one of the batch's students got a login via "Give a login" → 409, nothing removed (Tasks 4–5).

---

### Task 1: Models and permissions

**Files:** `backend/admissions/models.py` (Enquiry, FollowUp), new app `backend/imports/` (models, apps,
migrations; add to `LOCAL_APPS`), `backend/students/models.py` (`GuardianLink.Source.IMPORT`),
`backend/accounts/roles.py` (`enquiry.manage` campus-scopable, group "Admissions", to Registrar, Admissions Officer;
`data.import` institution-only, group "Settings", label "Import students from a spreadsheet"); migrations.
Test: `backend/admissions/tests/test_enquiry_models.py`, `backend/imports/tests/test_models.py`.

**Interfaces — produces:** `Enquiry.Source`, `Enquiry.Status` (`open`, `following_up`, `converted`, `closed`),
`FollowUp.How`; `Enquiry.objects.next_number(institution, year) -> str` (`E2026-0001`); `ImportJob.Status`,
`ImportRow.State`, `ImportRow.Decision`; `ImportedRecord` unique constraint `one_import_per_source_record`.

- [ ] Failing tests: numbers run per institution and year; one ImportedRecord per (institution, source system,
  entity, source id) → `IntegrityError` on a second; permission registry entries and role grants.
- [ ] Implement; `makemigrations admissions imports students`; tests and full suite pass; commit `Enquiry and import models`.

### Task 2: Enquiries API (public form and staff)

**Files:** `backend/admissions/enquiries.py` (services), `backend/admissions/enquiry_views.py`, `admissions/urls.py`,
`config/urls.py` (`api/v1/public/enquiries`), `config/settings.py` (throttle rate `enquiry: 10/hour`),
`admissions/serializers.py`. Test: `backend/admissions/tests/test_enquiries.py`.

**Interfaces — produces:** `enquiries.visible(actor, institution) -> QuerySet`; `can_manage(actor, enquiry) -> bool`;
`create(institution, data, actor=None, source) -> Enquiry`; `add_follow_up(actor, enquiry, data) -> FollowUp`
(status `open` → `following_up`); `assign(actor, enquiry, version, user_id)` (assignee must hold `enquiry.manage`
covering the enquiry → else 422 `assigned_to`); `convert(actor, enquiry, version, application_number)`;
`close(actor, enquiry, version, reason)`; `reopen(actor, enquiry, version)`; `enquiry_item(enquiry, viewer) -> dict`.

- [ ] Failing tests: public create → 201 `{number: "E<year>-0001"}`, source website, audit; honeypot `website` filled →
  201, nothing stored; neither phone nor email → 422 `phone`; place from another institution → 422; throttle → 429
  after 10; module off → 404; staff list scoped by campus (City officer sees City-place enquiries and not Main-place
  ones; none-place only whole-institution); filters `status`, `assigned=me`, `due=1`, `source`; follow-up moves to
  following_up; assign to someone without the permission → 422 (Review Focus 4) and an existing assignee who lost it
  still shows; convert with another institution's application number → 422, own → converted and final (close → 409);
  close needs reason; reopen closed → open; stale version → 409; another institution's ids → 404.
- [ ] Implement; full suite; lint; commit `Enquiries`.

### Task 3: Import contract, upload and dry run

**Files:** `backend/imports/contract.py`, `backend/imports/services.py` (upload, decide, discard),
`backend/imports/views.py`, `backend/imports/urls.py`, `config/urls.py` (`api/v1/institution/imports`).
Test: `backend/imports/tests/test_contract.py`, `backend/imports/tests/test_upload.py`.

**Interfaces — produces:** `COLUMNS: tuple[str, ...]` and `REQUIRED: frozenset[str]` (spec S4C-06 order);
`parse(content: bytes) -> list[dict]` (UTF-8 with or without BOM, `csv.DictReader`, strips values, drops blank lines;
raises `ValidationError({"file": [...]})` for non-UTF-8, no header, missing required columns (named), > 5,000 rows);
`check(row: dict, institution, today) -> tuple[dict, list[dict]]` (normalised values, errors with codes `required`,
`bad_date`, `future_date`, `unknown_campus`, `bad_year`, `entry_before_admission`, `bad_email`, `too_long`);
`checksum(values: dict) -> str`; `services.upload(actor, institution, file, source_system) -> ImportJob` (≤2 MB else
422; stores file; builds rows with state by S4C-07/S4C-08; totals); `services.decide(actor, row, decision)`.

- [ ] Failing tests: Excel-style file (BOM, CRLF, blank trailing lines, padded values) parses (Review Focus 2);
  missing columns → 422 naming them; each error code once; duplicate of an existing student and of an earlier row →
  `duplicate` with `duplicate_of`; same source id twice → second is `error` `repeated_source_id`; previously imported
  unchanged → `unchanged`, changed → `changed`; totals exact; `data.import` required (Registrar 403); another
  institution's job → 404; file stored under `PRIVATE_MEDIA_ROOT/imports/`.
- [ ] Implement; full suite; lint; commit `Import upload and dry run`.

### Task 4: Commit, provenance, guardians, discard, undo, error file

**Files:** `backend/imports/services.py`, `views.py`, `urls.py`; `backend/students/guardians.py` (`propose` accepts
`source`). Test: `backend/imports/tests/test_commit.py`.

**Interfaces — produces:** `commit(actor, job, version) -> ImportJob` (lock job, then institution; 409 when not
`validated`; 409 `undecided_duplicates` when any duplicate has no decision; re-check provenance per row; create per
S4C-09; audit `import.committed` and per student `student.imported`; totals `created`, `skipped`, `unchanged`,
`changed`, `errors`); `discard(actor, job, version)` (deletes file); `undo(actor, job, version)` (S4C-11 checks:
student.version == 1, no login, no verified link, single enrollment; else 409 naming the first blocker);
`error_csv(job) -> str` (`row,column,code,message,source_record_id`; neutralised).

- [ ] Failing tests: TST-025 end to end (preview → decide → commit → counts; second commit 409; re-upload → all
  unchanged, commit creates nothing); parallel commit (two threads, `transaction=True`) → one success, one 409, one set
  of students (Review Focus 1); a source id committed by another batch after this dry run → `unchanged` at commit
  (Review Focus 3); guardian columns → proposed link, source import, no user; family portal empty; numbers `2026-0001…`
  from the academic year; undo right after commit removes students, persons, enrollments, links and provenance;
  undo after a student edit → 409; error CSV neutralises `=`, `+`, `-`, `@` and has no address or phone column.
- [ ] Implement; full suite; lint; commit `Import commit, undo and error file`.

### Task 5: Give a login to a student

**Files:** `backend/students/views.py`, `urls.py`, `backend/students/withdrawal.py` or a small `logins.py`
(`give_login(actor, student, version, password) -> Student`). Test: `backend/students/tests/test_logins.py`.

- [ ] Failing tests: imported student gets `<slug>.<number>`, must change password, membership kind student; twice →
  409; weak password → 422, nothing created; needs `student.update`; withdrawn student → 409; undo of its batch then →
  409 (Review Focus 5).
- [ ] Implement; full suite; lint; commit `Give a student a login`.

### Task 6: Demo data

- [ ] Seed two Aster enquiries (one website, open; one walk-in, following up with a follow-up note and due date) and a
  sample file `backend/imports/fixtures/aster-students-sample.csv` (8 synthetic rows: 6 good, 1 bad date, 1 duplicate
  of Arjun Demo) referenced in the README. Seed runs twice cleanly; update `institutions/tests/test_seed.py`.
- [ ] Commit `Demo enquiries and sample import file`.

### Task 7: Frontend — enquiries

**Files:** `features/apply/apply-page.ts` (Ask a question form), `features/admissions/enquiries-page.ts`,
`enquiry-page.ts`, `enquiry-new-page.ts`, `layout/nav.ts` (Admissions → Enquiries, `enquiry.manage`, module
admissions), `app.routes.ts`, `core/api/types.ts`. Test: `features/admissions/enquiries.spec.ts`,
`features/apply/apply.spec.ts`.

- [ ] Failing specs: the question form posts the fields with an empty honeypot and shows the reference; the list
  shows counts and sends filters; detail adds a follow-up, assigns, converts by number, closes with a reason (prompt).
- [ ] Implement; tests; build; commit `Enquiries pages`.

### Task 8: Frontend — data transfer and student logins

**Files:** `features/settings/data-page.ts` (batches + upload), `features/settings/import-page.ts` (batch), nav entry
under Administration (`data.import`, module students), routes `settings/data`, `settings/data/:id`;
`features/students/student-page.ts` (Give a login). Test: `features/settings/data.spec.ts`,
`features/students/students.spec.ts`.

- [ ] Failing specs: upload sends `file` and `source_system`; the batch page filters rows by state, sends a decision,
  keeps Commit disabled until no duplicate is undecided, then commits with the version; undo asks first; the student
  page posts a first password for "Give a login".
- [ ] Implement; tests; build; commit `Data transfer pages`.

### Task 9: Docs and browser check

- [ ] README (Enquiries, Data transfer, the sample file), `docs/decisions.md` S4C rows, `docs/progress.md` (BUILD-04
  complete).
- [ ] Browser at 1280 px and 390 px: ask a question from Aster's Apply page; as `aster.admissions` follow up, assign,
  convert; as `aster.admin` import the sample file, read the dry run, skip the duplicate, commit, download errors,
  re-upload (all already imported), undo a fresh batch; give an imported student a login and sign in as them.
- [ ] Full suites, lint, build. Commit `Slice 4c docs and verification`.
