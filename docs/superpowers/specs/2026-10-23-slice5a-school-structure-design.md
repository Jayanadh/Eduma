# Eduma slice 5a — academic calendar, grades, sections, class placement and teaching assignments (BUILD-05, part 1)

**Date:** 23 October 2026 · **Status:** written from the spec pack at the user's request ("skip the questions, plan it
from the spec pack"; "continue the build in the same way"); build rulings marked.
**Source pack:** 03 WF-ACA §6.1 (school model) and §6.4 (rollover); 04 SCR-021 (academic setup), SCR-023 (teacher
home, roster only); 08 §5 AcademicYear/Term, GradeLevel/Section/Cohort, TeachingAssignment, §4 EnrollmentPeriod;
02 `academic_structure.manage`; TST-035; BUILD-05 "grades/sections", "distinct school/college/university record
behavior".
**Builds on:** slices 1–4c (Enrollment, Student, campuses, departments, staff memberships, Employee).
**Later parts of BUILD-05:** 5b programs, curriculum versions, courses and offerings (higher education); 5c course
registration (windows, prerequisites, seats, waitlists, linked sections, overrides; TST-010); 5d attempts, credit
equivalence and advisory degree progress; 5e university affiliation grants and exchange.

## 1. What this slice is for

A school sets up its year once: the academic year and its terms, the grades it teaches, its subjects, and the sections
of each grade with a class teacher and subject teachers. Enrolled students are placed into sections; a teacher sees the
classes they teach and who is in them. At the year's end, a section moves on to next year's section in one step,
without creating duplicate students or losing last year's placement.

**Success:** Aster creates academic year 2026–27 (1 Jun 2026 – 31 Mar 2027) with Term 1 and Term 2; grades Class 1–10;
subjects English, Mathematics, Science, Telugu; sections 6A and 6B at Main campus (capacity 40) with class teachers.
The Registrar places Arjun and the imported Class 6 students into 6A; a 41st placement is refused. `aster.teacher` is
assigned Science for 6A and sees 6A's list of students under **My classes**. Next year the Registrar creates 2027–28
and its 7A, and moves 6A to 7A: every active student gets a 2027–28 placement in 7A; withdrawn students and anyone
already placed are listed and skipped; running it again creates nothing. Arjun's record shows 6A (2026–27) and 7A
(2027–28).

**Anti-goals:** a second student or a second active study episode created by moving up a year; a teacher reading
students they do not teach; a section over capacity; a past year's placement rewritten; school grades reused as
college programs.

## 2. Decisions

| ID | Decision | Pack reference / why |
|---|---|---|
| S5A-01 | **AcademicYear**: code (`2026–27`), start and end dates (end after start), status `planned` → `current` → `closed`; years of one institution must not overlap; exactly one current year at a time (making one current closes nothing automatically). **Term**: year, name (`Term 1`), ordinal, start and end inside the year, not overlapping. | 08 AcademicYear/Term "overlaps governed by institutional calendar policy" — build ruling: no overlaps |
| S5A-02 | **GradeLevel** (code `C6`, name `Class 6`, order) and **Subject** (code, name) are institution-wide lists with an active flag; codes unique per institution. Grades are a school concept; programs (5b) are separate. | 08 "School grade and HE program remain distinct concepts" |
| S5A-03 | **Section**: academic year, grade, campus, code (`6A`, unique per year), capacity ≥ 1, class teacher (a staff membership, optional). Sections of a closed year are read-only. | 08 Section; walkthrough 7 |
| S5A-04 | **EnrollmentPeriod** (the pack's placement): enrollment, academic year, section, grade and campus (copied from the section), state `active`/`ended`, repeat flag, placed by/at. One per enrollment and academic year (period key = year, terms come later). Placing locks the section and refuses when full (409 `section_full`); a student must be enrolled (active study episode) and not withdrawn; moving a student to another section in the same year ends nothing — it updates that year's placement and is audited with from → to. | 08 EnrollmentPeriod; WF-ACA §6.1 |
| S5A-05 | **TeachingAssignment**: section, subject (or none for the class teacher role), staff membership, starts/ends; several teachers allowed. Teachers see **My classes** (their current-year sections with their subjects) and each section's roster (number, name, current status) — nothing else of the student record. This is a relationship grant, not a campus permission. | 08 TeachingAssignment "Authorization follows active assignment"; SCR-023 |
| S5A-06 | **Move up** (rollover): from a section to a target section in a later year (`promote`) or the same grade in the next year (`repeat`, marked). Preview lists each student as `move`, `already placed`, `withdrawn` or `not enrolled`; commit creates the target year's placements for the `move` rows in one transaction, idempotently (a re-run finds them placed). Promotion criteria arrive with results (BUILD-07); here staff choose who moves. | WF-ACA §6.4; TST-035 |
| S5A-07 | Permission `academic_structure.manage` (campus-scopable): years, terms, grades and subjects need it for the whole institution; sections, placements, teaching assignments and move-up need it covering the section's campus. Given to Institution Admin and Registrar. Reading the structure (years, grades, sections without rosters) is open to all staff. | 02 `academic_structure.manage` |
| S5A-08 | **Enrollment link**: a placement's year must match an academic year whose code equals the enrollment's `academic_year` label or a later one (moved up). Enrollments keep their admission place label; the current section is shown beside it. | Build ruling: 4a stored the year as a label |
| S5A-09 | The student record, the student's own page and the family portal show the current section (`Class 6 · 6A`) and staff see the placement history. | WF-ACA §6.1 "preserving the previous year's section" |
| S5A-10 | Module `academics` must be on for every route here; off → 404 (catalogue marks it available). | S3-07 |

## 3. Data model

New app `academics`: **AcademicYear** (`VersionedModel`: institution, code ≤20, starts_on, ends_on, status; unique
institution+code), **Term** (year, name ≤40, ordinal, starts_on, ends_on; unique year+ordinal), **GradeLevel**
(`VersionedModel`: institution, code ≤20, name ≤60, order, is_active; unique institution+code), **Subject**
(`VersionedModel`: institution, code ≤20, name ≤80, is_active; unique institution+code), **Section** (`VersionedModel`:
institution, year, grade, campus, code ≤20, capacity, class_teacher null (Membership); unique year+code),
**TeachingAssignment** (section, subject null, membership, starts_on, ends_on null, created_by), **EnrollmentPeriod**
(`VersionedModel`: enrollment, institution, year, section, grade, campus, state, is_repeat, placed_by, placed_at;
unique enrollment+year).

## 4. Rules (in addition to §2)

- Changing a year's dates may not leave a term outside it (422 on `ends_on`); deleting is not offered — a planned
  year with no sections may be removed (S5A-01 ruling), otherwise close it.
- Sections: capacity may not drop below current placements (422 `capacity`); grade and campus must be active; class
  teacher must be an active staff membership of this institution.
- Placements in a closed year are refused (409). Withdrawing a student (4b) ends their current-year placement.
- Move-up commit locks the source and target sections; capacity counts existing target placements; if the batch would
  overfill the target, nothing is created (409 `section_full` naming how many fit).
- Audit: year/term/grade/subject/section created/changed, placement made/moved/ended, assignment added/ended,
  move-up committed (counts).

## 5. API (`/api/v1/institution/academics/`)

`years` GET/POST, `years/<id>` GET/PATCH/DELETE (planned, empty only), `years/<id>/terms` POST, `terms/<id>`
PATCH/DELETE; `grades`, `subjects` GET/POST, `<id>` PATCH; `sections` GET (`year`, `grade`, `campus`, paged) / POST,
`sections/<id>` GET (with placements count, teachers) / PATCH; `sections/<id>/students` GET (roster; managers and the
section's teachers) / POST `{students: [student ids]}` (place); `sections/<id>/students/<student>` DELETE (end
placement) and `…/move` POST `{section}`; `sections/<id>/teachers` POST `{membership, subject}`, `teachers/<id>/end`
POST; `sections/<id>/move-up/preview` POST `{target, mode}` → rows; `…/move-up` POST `{target, mode, students}`.
Teacher: `/api/v1/teaching/classes` GET; `/api/v1/teaching/classes/<section>/students` GET.
Students: record gains `placements: [{year, grade, section, campus, state, is_repeat}]` and `current_section`.

## 6. Screens

- **Academics → Academic setup** (`/app/academics`): tabs Years & terms, Grades, Subjects; forms inline.
- **Academics → Sections** (`/app/academics/sections`): filter by year and grade; a section page with its details,
  teachers (add/end), roster with **Place students** (search the year's unplaced enrolled students, pick, place) and
  **Move up** (choose target section and mode, preview the rows, confirm).
- **My classes** (`/app/teaching`, any staff with an active assignment): their sections and subjects; a section's
  roster.
- Student record: **Classes** section (history); student page and family portal: current section.

## 7. Tests that must exist

1. Years and terms: overlapping years → 422; term outside its year → 422; overlapping terms → 422; one current year.
2. Sections: unique code per year; capacity below placements → 422; closed year read-only.
3. Placement: full section → 409 `section_full` (two placements racing the last seat: one wins); withdrawn or not
   enrolled → 422; moving within a year audits from → to; withdrawal ends the current placement.
4. Teacher access: a teacher sees rosters of sections they teach only (another section → 404; students API still
   403); an ended assignment removes access; rosters carry number, name and status only.
5. TST-035: move-up preview and commit create one placement per moving student in the target year, skip withdrawn and
   already placed, a re-run creates nothing, the old year's placement stays, no new Student or Enrollment appears;
   overfilling the target → 409 and nothing created.
6. Scope: a City-campus academic manager cannot create sections at Main (403) or see their rosters (404).
7. Module off → 404 everywhere here; another institution's ids → 404.

## 8. Left to the builder

Screen layouts, copy within the tone above, file layout inside `academics`.
