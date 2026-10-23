# Slice 5a — academic calendar, grades, sections, class placement and teaching assignments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A school's year structure (years, terms, grades, subjects, sections), students placed into sections each
year, teachers assigned with their own class rosters, and an idempotent move-up into next year (TST-035).

**Architecture:** New app `academics` with plain service functions (`structure.py`, `placement.py`, `moveup.py`) and
thin DRF views, following `admissions`. Teacher rosters are a relationship check (active TeachingAssignment), not a
campus permission. Placements are `EnrollmentPeriod` rows hanging off the 4a `Enrollment`.

**Tech Stack:** Django 6.1, DRF 3.18, PostgreSQL 17; Angular 22, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-23-slice5a-school-structure-design.md`

## Global Constraints

- Versioned writes take `version`; stale → 409 `version_conflict`; wrong state → 409 `invalid_transition`; field errors 422.
- Every route needs module `academics` on (`require_module`), else 404. Mark `academics` available in the catalogue.
- Dates on the institution's day (`today_for`). Pages of 5; search from 3 characters.
- Lint with the 120-column ruff command and `--exclude '.venv,*/migrations'` — also when formatting a directory.
- Commits: repo-local author, no co-author line, never push.

## Review Focus

1. Two placements racing for a section's last seat → one placed, one 409 `section_full` (Task 4).
2. A teacher whose assignment ended yesterday opens the roster URL they bookmarked → 404 (Task 5).
3. Move-up re-run after a partial manual placement in the target year → the manually placed student is `already
   placed`, nobody is placed twice (Task 6).
4. A student withdrawn mid-year → their current placement ends and they drop off the roster; reinstating restores it
   (Task 4).
5. Editing a year's end date so a term would fall outside it → 422 on `ends_on`, nothing saved (Task 2).

---

### Task 1: Models, permission and module

**Files:** new app `backend/academics/` (models per spec §3, apps, migrations; add to `LOCAL_APPS` before
`imports`), `backend/accounts/roles.py` (`academic_structure.manage`, group "Academics", label "Set up years, grades,
subjects and sections, place students and assign teachers", campus-scopable; to Registrar),
`backend/institutions/modules.py` (`academics` available). Test: `backend/academics/tests/test_models.py`.

- [ ] Failing tests: unique year code per institution, unique section code per year, one placement per enrollment and
  year (`IntegrityError`), registrar holds the permission, `academics` available.
- [ ] Implement, `makemigrations academics`, full suite, lint, commit `Academic structure models`.

### Task 2: Years, terms, grades and subjects API

**Files:** `backend/academics/structure.py`, `views.py`, `urls.py`, `serializers.py`; `config/urls.py`
(`api/v1/institution/academics/`). Test: `backend/academics/tests/test_structure.py`.

**Interfaces — produces:** `MANAGE = "academic_structure.manage"`; `save_year(actor, institution, year|None, data,
version|None) -> AcademicYear` (no overlap with another year → 422 `starts_on`; existing terms must fit → 422
`ends_on`; status `current` makes any other current year `closed`? — no: refuse a second current year, 409
`another_current_year`); `save_term(actor, year, term|None, data, version|None)`; grade/subject create/patch with
unique codes (422 `code`).

- [ ] Failing tests: overlap → 422; term outside year → 422; overlapping terms → 422; shrinking a year past a term →
  422 `ends_on` (Review Focus 5); second current year → 409; delete a planned empty year → 204, with sections → 409;
  needs whole-institution `academic_structure.manage` (City-scoped manager → 403); any staff can GET; module off → 404.
- [ ] Implement; full suite; lint; commit `Years, terms, grades and subjects`.

### Task 3: Sections and teaching assignments

**Files:** `structure.py`, `views.py`, `urls.py`, `serializers.py`. Test: `backend/academics/tests/test_sections.py`.

**Interfaces — produces:** `can_manage_section(actor, section) -> bool` (MANAGE covering `("campus", section.campus_id)`);
`save_section(actor, institution, section|None, data, version|None)` (active grade/campus, unique code per year,
capacity ≥ placed → 422 `capacity`, class teacher active staff → 422 `class_teacher`, closed year → 409);
`assign_teacher(actor, section, membership_id, subject_id|None) -> TeachingAssignment`; `end_teaching(actor,
assignment)`; `section_item(section, viewer) -> dict` (`placed`, `teachers`).

- [ ] Failing tests: create/patch with the rules above; City manager creates at City (201) and not at Main (403);
  list filters `year`, `grade`, `campus`; teachers added and ended (ends today); another institution's ids → 404.
- [ ] Implement; full suite; lint; commit `Sections and teaching assignments`.

### Task 4: Placement, roster and student record

**Files:** `backend/academics/placement.py`, views/urls; `backend/students/withdrawal.py` (end the current placement
on withdraw, reopen on reinstate); `backend/students/serializers.py` (`placements`, `current_section`);
`backend/students/views.py` (`OwnRecord` adds `current_section`); `backend/students/family.py` (child adds
`current_section` when shared). Test: `backend/academics/tests/test_placement.py`.

**Interfaces — produces:** `place(actor, section, student_ids: list) -> list[EnrollmentPeriod]` (lock section; full
→ 409 `section_full` with how many fit; each student active with an active enrollment whose year label is ≤ the
section's year → else 422 `students` naming numbers; already placed this year in another section → 409 `already_placed`
naming them); `move(actor, period, target_section)` (same year; audit from → to); `end(actor, period)`;
`current_period(student, today) -> EnrollmentPeriod | None` (the current year's active placement).

- [ ] Failing tests: place three into a capacity-2 section → 409 and nothing placed; two racing for the last seat
  (threads, `transaction=True`) → one wins (Review Focus 1); withdrawn → 422; move within the year audited; withdrawal
  ends the placement and reinstate reopens it (Review Focus 4); the record, own record and family child show
  `current_section` `Class 6 · 6A`.
- [ ] Implement; full suite; lint; commit `Class placement`.

### Task 5: Teacher classes

**Files:** `backend/academics/teaching.py` (views), `backend/academics/teaching_urls.py`, `config/urls.py`
(`api/v1/teaching/`). Test: `backend/academics/tests/test_teaching.py`.

**Interfaces — produces:** `GET /api/v1/teaching/classes` → `[{section: {id, code, grade, year}, subjects: [names],
class_teacher: bool}]` for in-effect assignments (start ≤ today ≤ end) in the current year; `GET
/api/v1/teaching/classes/<section>/students` → `[{number, full_name, status}]` or 404.

- [ ] Failing tests: assigned teacher sees the section and its roster with only number, name and status; another
  section → 404; ended yesterday → 404 (Review Focus 2); managers see rosters through the sections API, not here;
  non-staff → 404.
- [ ] Implement; full suite; lint; commit `My classes`.

### Task 6: Move up (TST-035)

**Files:** `backend/academics/moveup.py`, views/urls. Test: `backend/academics/tests/test_moveup.py`.

**Interfaces — produces:** `preview(actor, source, target, mode) -> list[dict]` (`{student: {id, number, full_name},
action: "move" | "already_placed" | "withdrawn" | "not_enrolled"}`; target year must be later than the source's;
`repeat` needs the same grade, `promote` a different grade); `commit(actor, source, target, mode, student_ids) ->
dict` (locks both sections; creates target-year placements with `is_repeat` for repeat; ends nothing in the old year;
capacity check for the whole batch → 409; idempotent; audit `section.moved_up` with counts).

- [ ] Failing tests: TST-035 (one new placement per moving student, old placement intact, no new Student or
  Enrollment, re-run creates nothing); withdrawn and already placed skipped (Review Focus 3); over capacity → 409 and
  nothing; target year not later → 422; scope checks on both sections.
- [ ] Implement; full suite; lint; commit `Move a section up a year`.

### Task 7: Demo data

- [ ] Seed Aster: years 2026–27 (current) and 2027–28 (planned) with two terms each, grades Class 1–10, subjects
  English, Mathematics, Science, Telugu; sections 6A, 6B (2026–27, Main, 40) and 7A (2027–28); `aster.teacher` teaches
  Science in 6A; the class teacher of 6A is `aster.principal`? — no: `aster.teacher`; Arjun placed in 6A. Seed twice
  cleanly; update `test_seed.py`. Commit `Demo academic structure`.

### Task 8: Frontend — academic setup

**Files:** `features/academics/setup-page.ts` (+ html), nav group "Academics" (Academic setup: `academic_structure.manage`,
module academics), routes, `core/api/types.ts`. Test: `features/academics/setup.spec.ts`.

- [ ] Failing specs: years listed with their terms; adding a year sends code and dates; adding a term to a year;
  grades and subjects add/rename with versions; field errors shown.
- [ ] Implement; tests; build; commit `Academic setup page`.

### Task 9: Frontend — sections, placement, move up, My classes, records

**Files:** `features/academics/sections-page.ts`, `section-page.ts` (+ html), `teaching-page.ts`,
`teaching-roster-page.ts`; nav (Sections; My classes for any staff with assignments — shown when
`GET /teaching/classes` is non-empty), routes; `features/students/student-page.ts` (Classes), `features/student/
student-home.ts` and `features/family/child-summary.ts` (current section). Tests in `features/academics/*.spec.ts`.

- [ ] Failing specs: sections filtered by year; section page places chosen students and shows `section_full` as a
  message; adds a teacher; move-up preview lists rows with their actions and commit posts the moving ids; My classes
  lists sections and opens a roster; the student page shows the class history.
- [ ] Implement; tests; build; commit `Sections, placement and My classes`.

### Task 10: Docs and browser check

- [ ] README (Academics pages, the teacher's My classes), `docs/decisions.md` S5A rows, `docs/progress.md`.
- [ ] Browser at 1280 px and 390 px: as `aster.registrar` set up a section, place students, see a full section
  refused, assign a teacher, move a section up; as `aster.teacher` open My classes and a roster at 390 px; as the
  student see the current section.
- [ ] Full suites, lint, build. Commit `Slice 5a docs and verification`.
