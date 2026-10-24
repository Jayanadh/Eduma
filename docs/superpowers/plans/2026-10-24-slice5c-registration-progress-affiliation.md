# Slice 5c–5e — registration, attempts and progress, affiliation — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-10-24-slice5c-registration-progress-affiliation-design.md`

**Fast mode (user, 24 Oct 2026):** tests first for each task, only the affected tests per task, the full suites once
before the slice's last commit; no browser check and no fresh review until everything is built.

## Global constraints

- Versioned writes take `version`; 409 `version_conflict` / `invalid_transition`; 422 field errors; problem codes as
  in the spec. Module `academics` gates academics routes.
- Lint: ruff at 120 columns with `--exclude '.venv,*/migrations'`. Commits: repo-local author, no co-author line,
  never push.

## Tasks

1. **Models, permissions, migrations** — the spec §3 models; `CurriculumVersion.repeat_rule` (revise copies it);
   permissions `registration.manage`, `registration.override`, `academic_record.manage`, `affiliation.submit`,
   `affiliation.review`; role Academic Adviser; Registrar gains the academics ones, Institution Admin all. Commit
   `Registration, attempt and affiliation models`.
2. **Registration** — `academics/registration.py` (checks, overrides, holds, seats, waitlist, drop/withdraw/approve/
   reject), windows, staff and student-portal APIs, offering class lists for teachers. Tests: TST-010 incl. a threaded
   last-seat race. Commit `Course registration`.
3. **Attempts, transfer credit, degree progress** — `academics/progress.py`; attempt outcomes; transfers; SGPA/CGPA
   by repeat rule; progress API (staff and student). Tests: TST-013 and progress buckets. Commit
   `Attempts, transfer credit and degree progress`.
4. **Affiliation** — new app `affiliations`: grants (console propose, college approve, revoke), batches (build,
   preview, submit, revise), review. Tests per spec §6. Commit `University affiliation exchange`.
5. **Demo data** — Meridian Semester 1 window open, Ananya registered with an attempt history; Summit University ↔
   Meridian grant active with one submitted batch; `meridian.adviser`, `summit.registrar`. Seed test. Commit
   `Demo registration and affiliation`.
6. **Frontend: student** — Registration and Degree progress pages in the student portal. Commit
   `Student registration and progress pages`.
7. **Frontend: staff** — registration window on the offerings page; offering registrations; student record Courses
   section; My classes offering lists; menu. Commit `Registration and records for staff`.
8. **Frontend: affiliations** — console grants; institution Affiliations page and batch page. Commit
   `Affiliation pages`.
9. **Docs and full suites** — README personas, decisions, progress; both suites, lint, build. Commit
   `Slice 5c–5e docs`.
