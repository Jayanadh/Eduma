# Eduma slice 5b — programs, curriculum versions, courses, offerings and college batches (BUILD-05, part 2)

**Date:** 23 October 2026 · **Status:** written from the spec pack at the user's request ("skip the questions, plan it
from the spec pack"; "continue the build in the same way"); build rulings marked.
**Source pack:** 03 WF-ACA §6.2 (higher-education model); 08 §4 Enrollment ("program optional, curriculum revision
optional"), §5 Program/CurriculumVersion ("Published curriculum immutable; new regulation creates revision"),
Course/CurriculumCourse, CourseOffering, TeachingAssignment; 04 SCR-021; 13 glossary "Curriculum/regulation version —
B.Tech CSE 2026 regulations"; 01 §10 (departments, programs, regulations, batches, terms); FIX-COL journey "Admission →
curriculum/semester placement"; BUILD-05 "university support is not merely a renamed school interface". D-01 is open,
so every rule here is generic and the demo regulation is labelled synthetic.
**Builds on:** slice 5a (years, terms, sections, placements, teaching assignments), 4a (places, enrollment).
**Later:** 5c course registration (windows, prerequisites checked at registration, seats, waitlists, linked-section
claims, overrides; TST-010); 5d attempts, credit equivalence and advisory degree progress (TST-013); 5e affiliation.

## 1. What this slice is for

A college describes what it teaches the way colleges do: programs (B.Sc Physics) with a versioned regulation that a
cohort follows (R2026: which courses, in which semester, core or elective, with prerequisites, and how many credits
make the degree), a course catalogue with credits, and each term's offerings of those courses with capacity and
teachers — a lecture with its linked lab. Students are pinned to their program and regulation when they enrol; a
regulation, once published, never changes under them. College batches (B.Sc Physics 2026, section A) are sections like
a school's, so placement, rosters and moving up work the same.

**Success:** Meridian College creates program `BSC-PHY` (B.Sc Physics, Physics department, 6 semesters) and courses
PHY101 Mechanics (4 credits, theory), PHY101L Mechanics Lab (1, lab), MAT101 Calculus (4), PHY201 Electromagnetism (4,
prerequisite PHY101). Regulation R2026 (synthetic) for the 2026 cohort lists them with semesters and categories,
needs 120 credits, and is published; editing it is refused; revision 2 is drafted from it. For Term 1 of 2026–27 it
offers PHY101 section A (60 seats) taught by a Physics teacher and PHY101L section A1 linked to it. Admissions place
"B.Sc Physics" maps to the program, so enrolling a student pins BSC-PHY / R2026 rev 1; the student's record shows it.
The batch "BSC-PHY 2026 A" is a section of program BSC-PHY in 2026–27; students are placed into it and its teacher
sees it under My classes.

**Anti-goals:** a published regulation changed in place; a prerequisite loop; a course in a curriculum twice; a school
grade reused as a program or a program shown to a school as if it were a grade; an offering linked to itself or to
another term's offering; a student pinned to another program's regulation.

## 2. Decisions

| ID | Decision | Pack reference / why |
|---|---|---|
| S5B-01 | **Program**: code (unique per institution), name, qualification (`B.Sc`, `B.Tech`…), department (optional), length in terms (1–16), active flag. | 08 Program |
| S5B-02 | **CurriculumVersion** (regulation): program, regulation code (`R2026`), revision (1, 2… per program+code), cohort (entry year it applies from), credits required, status `draft` → `published` → `retired`. Only a draft changes. **New revision** copies a published version's courses into a draft revision n+1. Publishing needs at least one course and checks prerequisites. | 08 "Published curriculum immutable; new regulation creates revision" |
| S5B-03 | **Course**: code (unique per institution), title, credits (0–30 in halves), kind (`theory`, `lab`, `project`, `tutorial`, `other`), department (optional), active flag. | 08 Course |
| S5B-04 | **CurriculumCourse**: curriculum, course (once per curriculum), category (`core`, `elective`, `open_elective`, `lab`, `project`), recommended term (1…program length), elective group (optional label), prerequisites (other courses of the same curriculum; no loops). | 08 CurriculumCourse "relation carries versioned rules" |
| S5B-05 | **CourseOffering**: course, term (5a Term), campus, section code (`A`, `A1`), capacity ≥ 1, status `planned` → `open` → `closed` (or `cancelled`), linked offering (optional: another offering of the same term, not itself — a lab linked to its lecture). Unique course+term+section code. Teachers via TeachingAssignment, which now names a section **or** an offering. | 08 CourseOffering, TeachingAssignment; WF-ACA §6.2 "linked lecture/lab/tutorial" |
| S5B-06 | **College batches**: a 5a Section names a grade **or** a program (exactly one). Batches use placement, rosters, teaching assignments and move-up as in 5a; labels read `B.Sc Physics · BSC-PHY 2026 A`. | Pack: batches; reuse rather than a parallel model |
| S5B-07 | **Pinning**: Enrollment gains program and curriculum (both optional). Admissions places may name a program; enrolling into such a place pins the program and its published curriculum whose cohort is the latest ≤ the cycle's entry year (if none, the program alone). Staff with `student.update` may set or change the pin on the record to a published curriculum of the same program (audited from → to). | 08 Enrollment; FIX-COL |
| S5B-08 | **Scope**: `academic_structure.manage` for programs and courses at their department (none → whole institution); curricula follow their program; offerings follow the course's department, else the offering's campus. | 02 "Assigned institution/campus/program" |
| S5B-09 | **Distinct experiences**: school category shows Grades and grade sections; college, engineering college and university show Programs, Courses, Offerings and batches. The backend allows both everywhere (a school may run a junior college); the menu follows the category. | BUILD-05 completion evidence |
| S5B-10 | Demo data for Meridian College is labelled "synthetic regulation for development". | 01 "must not be labeled real … regulations" |

## 3. Data model

`academics`: **Program** (`VersionedModel`: institution, code ≤20, name ≤120, qualification ≤40, department null,
length_terms, is_active; unique institution+code), **CurriculumVersion** (`VersionedModel`: program, regulation ≤20,
revision, cohort (year int), credits_required (decimal 6,1), status, published_by/at; unique program+regulation+
revision), **Course** (`VersionedModel`: institution, code ≤20, title ≤150, credits (decimal 4,1), kind, department
null, is_active; unique institution+code), **CurriculumCourse** (curriculum, course, category, term (int), elective_group
≤40, prerequisites M2M to Course; unique curriculum+course), **CourseOffering** (`VersionedModel`: institution, course,
term, campus, code ≤20, capacity, status, linked_to null self; unique course+term+code). **Section**: `grade` nullable,
`program` null; check exactly one. **EnrollmentPeriod.grade** nullable, **program** null. **TeachingAssignment**:
`section` nullable, `offering` null; check exactly one.

`admissions`: **Place.program** null. `students`: **Enrollment.program**, **Enrollment.curriculum** null.

## 4. Rules (in addition to §2)

- Curriculum course term must be 1…program length; prerequisites must already be in the curriculum and must not form
  a loop (422 `prerequisites`); a course may not require itself.
- Publishing a curriculum freezes it (status published, published by/at, audit); a second published revision of the same
  regulation may coexist (cohorts pinned to rev 1 keep it); retiring stops new pins.
- Offerings: term not in a closed year; capacity not below what 5c will register (none yet); linked offering same term,
  not itself, and not a chain back to itself; cancelled offerings keep their teachers' history.
- My classes lists offerings a teacher teaches (rosters of offerings arrive with registration in 5c — empty for now).
- Audit: program/course saved, curriculum drafted/published/retired/revised, offering saved, pin set/changed.

## 5. API (`/api/v1/institution/academics/`)

`programs` GET/POST, `programs/<id>` GET/PATCH; `programs/<id>/curricula` GET/POST; `curricula/<id>` GET/PATCH (draft
only); `curricula/<id>/courses` POST `{course, category, term, elective_group, prerequisites}`; `curricula/<id>/courses/
<cc>` PATCH/DELETE (draft only); `curricula/<id>/publish`, `/retire`, `/revise` POST; `courses` GET (search ≥3, paged)
/ POST, `courses/<id>` PATCH; `offerings` GET (`term`, `course`, paged) / POST, `offerings/<id>` GET/PATCH;
`offerings/<id>/teachers` POST, `offerings/<id>/teachers/<a>/end` POST. Sections accept `program` instead of `grade`.
Students: `students/<id>/program` POST `{version, program, curriculum}`; record gains `program` and `curriculum`.
Admissions cycles: places accept `program`.

## 6. Screens

- **Academics → Programs** (college categories): list; program page with its curricula (draft/published/retired),
  a curriculum page listing courses by term with category and prerequisites, add/remove while draft, Publish, Retire,
  New revision.
- **Academics → Courses**: catalogue with search; add/edit.
- **Academics → Offerings**: by term; add an offering (course, campus, code, capacity, linked to), status, teachers.
- **Sections** (colleges): batches by program.
- **Student record**: Program and regulation, with Change for `student.update`.
- **Cycle editor**: each place may name a program.
- Menu: Programs, Courses and Offerings for college categories; Grades stay on Academic setup for schools.

## 7. Tests that must exist

1. Published curriculum: PATCH, adding or removing courses → 409; revise → draft rev n+1 with the same courses and
   prerequisites; publish with no courses → 422; retired curricula refuse new pins.
2. Prerequisites: not in the curriculum → 422; loop A→B→A → 422; self → 422; term outside the program length → 422.
3. Courses and programs: unique codes per institution (422); department-scoped manager edits their department's
   course (200) and not another's (403).
4. Offerings: unique course+term+code; link to another term's offering or itself → 422; closed year → 409.
5. Batches: section with a program and no grade (201); both or neither → 422; placement and roster work; the label
   uses the program.
6. Pinning: enrolling into a place with a program pins the latest published curriculum for the cohort; with none
   published, the program alone; changing the pin to another program's curriculum → 422; audit from → to.
7. Teaching: a teacher assigned to an offering sees it under My classes; assignment must name exactly one target.
8. Isolation: another institution's programs, curricula, courses, offerings → 404; module off → 404.

## 8. Left to the builder

Layouts, copy within the tone above, the synthetic demo regulation's content, file layout inside `academics`.
