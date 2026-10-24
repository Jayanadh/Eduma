# Eduma slice 6 — timetable, teaching and attendance (BUILD-06)

**Date:** 24 October 2026 · **Status:** from the spec pack, fast mode (user: "complete all the remaining build").
**Source:** 03 WF-ATT §7; 08 TimetableSlot, AttendanceSession/Mark, AttendanceCorrection, Assignment/Submission;
TST-011; BUILD-06. Offline capture is not selected (BUILD-06: "only if selected"), so there is no offline mode; the
page shows saved / submitted / locked state honestly. Teaching resources are scoped to assignments with text
submissions (no LMS adapter, no files yet).

## Decisions

| ID | Decision |
|---|---|
| S6-01 | **Rooms** per campus (code, name, capacity), managed with `academic_structure.manage`. |
| S6-02 | **Timetable versions** per term: draft → published; publishing supersedes the previous published version. A **slot** is weekly (weekday, start, end) for a section (with optional subject) or an offering, with an optional room and teacher. |
| S6-03 | **Conflicts** (same weekday, overlapping times, same room / teacher / section / offering in one version) are listed on the draft; publishing with conflicts → 409 `timetable_conflict`. |
| S6-04 | **Substitutions** name a slot, a date and a substitute teacher with a reason; the substitute takes that day's session and the regular teacher doesn't. |
| S6-05 | **Teacher day view**: published slots on that weekday within the term for the teacher (minus substituted ones), plus their substitutions, each with its attendance state. |
| S6-06 | **Attendance sessions**: one per section/offering, date and slot; states draft → submitted → locked. Marks `present`, `late`, `absent`, `excused`; unmarked is not absent. Present and late count in the numerator; present, late and absent in the denominator; excused in neither. |
| S6-07 | **Roster eligibility**: a section's active placements / an offering's registered students whose enrollment covers the date (entry on or before it, no exit before it). Only eligible dates count (TST-011). |
| S6-08 | **Teacher scope**: the session's teacher (assignment in effect, or substitute that date) marks and submits, for dates from 7 days ago up to today; a manager (`attendance.manage`) may too and locks. |
| S6-09 | **Corrections** after submit: requested with a reason (teacher or manager), approved or rejected by `attendance.manage` (not the requester); approval changes the mark and keeps the original in the correction record. |
| S6-10 | **Visibility**: students see their own attendance; guardians see a child's when the record is shared; staff with `student.read` see it on the record. |
| S6-11 | **Assignments**: a teacher posts title, instructions and due time to a section or offering they teach; students on the roster submit text once (a resubmission replaces it until feedback is given; late is flagged); the teacher gives feedback. |
| S6-12 | Module `attendance` (needs `academics`) gates attendance and assignments; new permission `attendance.manage` (Registrar; campus-scopable). |

## Tests

TST-011 (mid-year enrollment counts only eligible dates; teacher scope; corrections keep originals); timetable conflict
listing and publish refusal; substitution day view and marking rights; unmarked vs absent; 7-day window; guardian
visibility follows sharing; assignment submit/feedback/no overwrite after feedback; isolation; module gate.
