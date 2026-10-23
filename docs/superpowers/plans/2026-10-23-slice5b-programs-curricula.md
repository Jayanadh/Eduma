# Slice 5b — programs, curriculum versions, courses, offerings and college batches — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The higher-education structure: programs, immutable published regulations (curriculum versions) with
courses, prerequisites and semesters, a course catalogue, term offerings with linked labs and teachers, college
batches built on 5a sections, and students pinned to their program and regulation.

**Architecture:** Extends the `academics` app (`programs.py`, `curricula.py`, `offerings.py` services; views in
`views.py`/`he_views.py`). 5a's Section, EnrollmentPeriod and TeachingAssignment gain a second target (program /
offering) guarded by check constraints. Pinning lives on `students.Enrollment` and is set by `admissions.enrollment`.

**Tech Stack:** Django 6.1, DRF 3.18, PostgreSQL 17; Angular 22, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-23-slice5b-programs-curricula-design.md`

## Global Constraints

- Versioned writes take `version`; stale → 409; wrong state → 409 `invalid_transition`; field errors 422.
- Module `academics` gates every route (404 when off).
- Lint: `ruff check`/`ruff format --check` at 120 columns with `--exclude '.venv,*/migrations'`, also when formatting.
- Run the full suite and check its last line says `passed` with no `failed` **before** committing (never chain a commit
  after a grep-filtered pytest).
- Commits: repo-local author, no co-author line, never push. Demo regulation content is labelled synthetic.

## Review Focus

1. Revising a published curriculum twice in a row → revisions 2 and 3, each a draft copy of the published one, never a
   copy of a draft (Task 3).
2. A prerequisite loop through three courses (A→B→C→A) added one edge at a time → the closing edge is refused (Task 3).
3. A section given both a grade and a program, or neither, through PATCH (not only POST) → 422, nothing saved (Task 5).
4. Enrolling into a place whose program has only a retired curriculum → pinned to the program alone, never to the
   retired curriculum (Task 6).
5. A department-scoped manager reading another department's curriculum is fine, but publishing it → 403 (Task 3).

---

### Task 1: Models and constraints

**Files:** `backend/academics/models.py` (new models; Section/EnrollmentPeriod/TeachingAssignment changes with
`CheckConstraint`s `section_grade_or_program`, `period_grade_or_program`, `teaching_one_target`),
`backend/admissions/models.py` (`Place.program`), `backend/students/models.py` (`Enrollment.program`,
`Enrollment.curriculum`); migrations. Test: `backend/academics/tests/test_he_models.py`.

- [ ] Failing tests: unique program/course codes per institution; unique curriculum course; unique offering
  course+term+code; a section with both grade and program or neither → `IntegrityError`; a teaching assignment with
  both or neither target → `IntegrityError`.
- [ ] Implement; migrations; full suite; commit `Programs, curricula, courses and offerings models`.

### Task 2: Programs and courses API

**Files:** `backend/academics/programs.py`, `he_views.py`, `urls.py`, `serializers.py`. Test: `test_programs.py`.

**Interfaces — produces:** `department_scope(department_id) -> Scope` (department or whole); `save_program(actor,
institution, program|None, data, version|None)`; `save_course(...)`; `program_item`, `course_item`.

- [ ] Failing tests: create/patch with unique codes (422 `code`), department belongs to the institution (422
  `department`), length 1–16, credits in halves 0–30 (422 `credits`); a Physics-department manager edits a Physics course
  (200) and not a Chemistry one (403) nor a department-less one (403); courses search ≥3 and page; any staff can read;
  module off 404; another institution's ids 404.
- [ ] Implement; full suite; commit `Programs and courses`.

### Task 3: Curriculum versions

**Files:** `backend/academics/curricula.py`, views/urls/serializers. Test: `test_curricula.py`.

**Interfaces — produces:** `create(actor, program, data) -> CurriculumVersion` (revision 1 of a new regulation code,
draft); `add_course(actor, curriculum, data)`, `change_course`, `remove_course` (draft only → 409 `published`);
`publish(actor, curriculum, version)` (≥1 course → else 422; status published); `retire(...)`; `revise(actor,
curriculum, version) -> CurriculumVersion` (from a published one only; next revision number for that regulation;
copies courses and prerequisites); `curriculum_item` (courses grouped by term with prerequisites as codes).

- [ ] Failing tests: per spec §7.1–2 plus Review Focus 1, 2 and 5.
- [ ] Implement (loop check: walk prerequisites from the new prerequisite back to the course); full suite; commit
  `Curriculum versions`.

### Task 4: Offerings and offering teachers

**Files:** `backend/academics/offerings.py`, views/urls/serializers; `backend/academics/teaching.py` (My classes
lists offerings: `{offering: {id, course, code, term}, subjects: [], class_teacher: false}`); `sections.py`
(`assign_teacher` unchanged for sections; new `assign_offering_teacher`). Test: `test_offerings.py`.

- [ ] Failing tests: per spec §7.4 and §7.7; offering scope by course department else campus; status changes; a
  cancelled offering keeps its teacher history.
- [ ] Implement; full suite; commit `Course offerings`.

### Task 5: College batches

**Files:** `backend/academics/sections.py` (program XOR grade: 422 `grade`), `placement.py` (copy grade or program;
`label` uses program name), `moveup.py` (program sections: `promote` needs the same program in a later year, `repeat`
refused 422 `mode`), serializers. Test: `test_batches.py`.

- [ ] Failing tests: per spec §7.5 and Review Focus 3; move-up of a batch into next year's batch of the same program;
  another program → 422.
- [ ] Implement; full suite; commit `College batches`.

### Task 6: Pinning students to a program and regulation

**Files:** `backend/admissions/cycles.py` (places accept `program` of the institution, 422 otherwise),
`backend/admissions/enrollment.py` (pin), `backend/students/views.py` + `urls.py` (`students/<id>/program`),
`backend/students/serializers.py` (`program`, `curriculum` on the record). Test:
`backend/academics/tests/test_pinning.py`.

**Interfaces — produces:** `academics.curricula.for_cohort(program, entry_year) -> CurriculumVersion | None` (published,
cohort ≤ entry year, latest cohort then highest revision).

- [ ] Failing tests: per spec §7.6 and Review Focus 4.
- [ ] Implement; full suite; commit `Pin students to a program and regulation`.

### Task 7: Demo data

- [ ] Meridian College: academics on; year 2026–27 (current) with two semesters; department Physics (and Mathematics);
  program BSC-PHY; courses PHY101, PHY101L, MAT101, PHY201; regulation R2026 (synthetic) published with 120 credits;
  Term 1 offerings PHY101-A (60) and PHY101L-A1 linked; a teacher `meridian.faculty` teaching PHY101-A; batch
  `BSC-PHY 2026 A`. Seed twice cleanly; update `test_seed.py`. Commit `Demo college structure`.

### Task 8: Frontend — programs and curricula

**Files:** `features/academics/programs-page.ts`, `program-page.ts`, `curriculum-page.ts` (+ html), routes, nav
(Programs for college categories), types. Test: `features/academics/programs.spec.ts`.

- [ ] Failing specs: list and add a program; curriculum page groups courses by term with prerequisites; adding a
  course to a draft sends course, category, term and prerequisites; publish posts the version; a published curriculum
  shows no edit controls and offers New revision.
- [ ] Implement; tests; build; commit `Programs and curricula pages`.

### Task 9: Frontend — courses, offerings, batches, pins, cycle places, menu

**Files:** `features/academics/courses-page.ts`, `offerings-page.ts`, `offering-page.ts`; section forms accept a
program; `features/students/student-page.ts` (Program and regulation with Change); `features/admissions/
cycle-editor-page.*` (place program); `layout/nav.ts` + shell (menu by institution category); types. Tests in
`features/academics/*.spec.ts`, `features/students/students.spec.ts`, `features/admissions/admissions.spec.ts`.

- [ ] Failing specs: course search and add; offering add with link; menu shows Programs/Courses/Offerings only for
  college categories; student pin change posts program and curriculum with the version; cycle place sends program.
- [ ] Implement; tests; build; commit `Courses, offerings and pins`.

### Task 10: Docs and browser check

- [ ] README (Meridian personas and pages), `docs/decisions.md` S5B rows, `docs/progress.md`.
- [ ] Browser at 1280 px and 390 px: as `meridian.admin` add a course to a draft regulation, publish it, see editing
  refused, revise; add an offering with a linked lab and a teacher; place students into a batch; pin a student; as
  `meridian.faculty` see the offering and batch under My classes at 390 px; as `aster.admin` see grades, not programs.
- [ ] Full suites, lint, build. Commit `Slice 5b docs and verification`.
