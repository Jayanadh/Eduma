# Eduma — progress and evidence

The durable record that `Eduma_Build_Pack/prompt.md` asks for: what is built, how it was checked, what was not, and
what comes next. Read this first when continuing.

## Where things stand (24 October 2026, slice 5b — BUILD-05 part 2)

**Slice 5b is built and checked locally.** Spec: `docs/superpowers/specs/2026-10-23-slice5b-programs-curricula-design.md`.
Plan: `docs/superpowers/plans/2026-10-23-slice5b-programs-curricula.md`. Branch `slice-5b-programs-curricula`, cut from
`slice-5a-school-structure` (with its review fixes merged). Next in BUILD-05: 5c course registration (TST-010); 5d
attempts, equivalence and degree progress (TST-013); 5e university affiliation.

| Built in slice 5b | Where |
|---|---|
| Programs and the course catalogue, managed at their department (else the whole institution) | `backend/academics/programs.py`, `features/academics/programs-page.ts`, `courses-page.ts` |
| Regulations (curriculum versions): draft → published → retired; a published one never changes and New revision drafts a copy; courses by term with category, elective group and prerequisites (no loops) | `backend/academics/curricula.py`, `features/academics/program-page.*`, `curriculum-page.*` |
| Course offerings per term with seats, status and teachers; a lab linked to its lecture; My classes lists a teacher's offerings | `backend/academics/offerings.py`, `teaching.py`, `features/academics/offerings-page.ts`, `offering-page.ts` |
| College batches: a section names a program instead of a grade; placement, class lists and move-up work as for classes (a batch moves up only within its program) | `backend/academics/sections.py`, `placement.py`, `moveup.py`, sections pages |
| Students pinned to a program and regulation: on enrolling into a place that names a program, or changed on the record | `backend/admissions/enrollment.py`, `backend/students/pinning.py`, `features/students/program-section.ts`, cycle editor |
| The menu follows the institution's category: colleges and universities get Programs, Courses and Offerings | `accounts/serializers.py` (`category`), `layout/nav.ts` |
| Demo: Meridian College with 2026–27 (two semesters), Physics and Mathematics, BSC-PHY and R2026 (a synthetic regulation for development), PHY101-A with lab PHY101L-A1, `meridian.faculty`, batch BSC-PHY 2026 A, two students | `seed_demo.py` |

Checks on 24 Oct 2026: backend `pytest` 513 passed; `ruff check` and `ruff format --check` clean; frontend `ng test`
200 passed; `ng build` clean.
Browser (built-in, Chromium): as `meridian.admin` at 1280 px the menu showed Programs, Courses and Offerings; R2026
rev 1 showed no edit controls (and the API refused a change with 409 `published`); New revision drafted rev 2 with
the same courses and prerequisites; MAT101 was taken out and added back in term 2 needing PHY101; rev 2 was published
and froze; PHY101-B and its lab PHY101L-B1 (linked to it) were offered, the lecture opened and given
`meridian.faculty`; Rahul Demo was placed in batch BSC-PHY 2026 A (2 of 60) and pinned to R2026 rev 2 from his
record. As `meridian.faculty` at 390 px My classes showed the batch (class teacher) and PHY101-A and PHY101-B, and the
batch's class list opened. At 390 px the regulation, offerings and courses pages fitted with no sideways scroll. As
`aster.admin` the Sections page showed grades and "Add a section", and the menu had no Programs, Courses or
Offerings. No console errors. Found and fixed: after adding a course to a regulation the form reset its selects but
kept sending the old category and term (spec added, red first); the course list drew a stray divider. The check's
rev 2, PHY101-B, PHY101L-B1, Rahul's placement and pin remain in the local database.

Final review (fresh reviewer, 24 Oct 2026): every Review Focus item held. Fixed with a failing test first: a
published regulation could still change underneath, through a course's credits (now 409 `in_use` once the course is
in a published or retired regulation) or the program's length (now 422 below the highest term any regulation uses); a
batch accepted a student pinned to another program (refused; students not pinned yet may still join, as imports carry
no program); a cancelled or closed offering still took edits, and two simultaneous links could form a loop (the term's
offerings are now locked while a link is checked); ending an already-ended teaching assignment moved its end date
(sections and offerings, 409 now); a student whose program was made inactive couldn't have it re-saved, and the pin
card hid it; the regulation page kept sending a prerequisite after that course was removed; the enrollment audit now
records the program and regulation pinned. Added tests for a department-scoped manager editing their own course and
programs by department, and another institution's course (404). Backend `pytest` 519 passed, frontend `ng test` 202
passed, lint and build clean. Deferred minors: a lab may be linked to an offering of another department; the pin
endpoint lets `student.update` move a student to another program (only another program's regulation is refused, as
§7.6 asks); the Courses page has no edit form; add forms show to managers of any scope (out-of-scope adds end in a
403 message); Academic setup still lists grades for colleges; `for_cohort` breaks a same-cohort tie between two
regulation codes by revision number; lists check permissions per row.

## Slice 5a (23 October 2026) — BUILD-05 part 1

**Slice 5a is built and checked locally.** Spec: `docs/superpowers/specs/2026-10-23-slice5a-school-structure-design.md`.
Plan: `docs/superpowers/plans/2026-10-23-slice5a-school-structure.md`. Branch `slice-5a-school-structure`, cut from
`slice-4c-enquiries-imports` (with its review fixes merged). Next in BUILD-05: 5b programs, curricula, courses and
offerings; 5c course registration; 5d attempts, equivalence and degree progress; 5e university affiliation.

| Built in slice 5a | Where |
|---|---|
| Academic years and terms, grades, subjects; `academic_structure.manage`; module `academics` | `backend/academics/structure.py`, `frontend/src/app/features/academics/setup-page.*` |
| Sections with capacity, class teacher and subject teachers | `backend/academics/sections.py`, `features/academics/sections-page.*`, `section-page.*` |
| Placement (EnrollmentPeriod): place, move, take out; withdrawal ends it and reinstating reopens it; records, the student's page and the family portal show this year's class | `backend/academics/placement.py`, `students/` |
| My classes and class lists for teachers | `backend/academics/teaching.py`, `features/academics/teaching-*.ts` |
| Move up / repeat into next year (TST-035) | `backend/academics/moveup.py`, section page |
| Demo: 2026–27 and 2027–28 with terms, Classes 1–10, four subjects, sections 6A/6B and 6A/7A, `aster.teacher` teaching Science, Arjun in 2027–28 6A | `seed_demo.py` |

Checks on 23 Oct 2026: backend `pytest` 474 passed; `ruff check` and `ruff format --check` clean; frontend `ng test`
185 passed; `ng build` clean.
Browser (built-in, Chromium): as `aster.registrar` at 1280 px the Sections list showed the seeded sections; a new
one-place section 6C refused two students ("6C has room for 1 more", nobody placed); Kiran Rao and Ananya Iyer were
placed in 2026–27 6A; 6A was moved up into 2027–28 7A (preview: both "Moves up"; afterwards a second preview showed
both "already placed"; Kiran's record kept 6A and gained 7A); as `aster.teacher` at 390 px My classes showed both 6A
sections (one as class teacher) and 6A's list, while the student records API answered 403 and an untaught class 404;
as Kiran at 390 px the record showed the class. Found and fixed: the record showed next year's class while this year
was current. The check's 6C section and the placements remain in the local database.

Final review (fresh reviewer, 23 Oct 2026), fixed with a failing test first: a student taken out of a class can be
placed again that year (they were stuck with "already placed"); a placement now records why it ended, so taken-out
students don't move up and reinstating reopens only what the withdrawal ended; withdrawing leaves closed years'
placements alone; a section can be moved up after its year is closed; a year's status only moves forward
(planned → current → closed); the class teacher is the section's one whole-class teaching assignment (it opens the
class list; setting a new one ends the old); a section with students keeps its year, grade and campus, and a closed
year's section can't be moved out of it; the move-up screen lets staff untick students who stay behind; Take out asks
first. Backend `pytest` 482 passed, frontend `ng test` 186 passed, lint and build clean. Deferred minors: teachers get
placement ids on the managers' roster route; two placements of one student at once can 500; one-current-year and
year overlap aren't safe under concurrent requests; ending an ended assignment moves its end; duplicate subject
assignments; terms aren't audited and stay editable in closed years; the current section shows with Academics off;
year names aren't normalised (hyphen vs en dash); the section page loads every section for its dropdowns and they
include other campuses and earlier years; place-search results go stale; an out-of-scope roster shows "Nobody placed";
the setup status dropdown keeps a refused value; the new-section year defaults to the newest; no Back links on the
section and class-list pages; the setup route is `/app/academics/setup`; the Registrar description omits Academics.


## Slice 4c (23 October 2026) — BUILD-04 complete

**Slice 4c is built and checked locally, finishing BUILD-04** (admissions, people and imports). Spec:
`docs/superpowers/specs/2026-10-19-slice4c-enquiries-imports-design.md`. Plan:
`docs/superpowers/plans/2026-10-19-slice4c-enquiries-imports.md`. Branch `slice-4c-enquiries-imports`, cut from
`slice-4b-guardians` (with its review fixes merged). Next: BUILD-05, academic structures.

| Built in slice 4c | Where |
|---|---|
| Enquiries: public question form (throttled, honeypot), staff list with counts and filters, follow-ups, assignment, link to an application, close/reopen; `enquiry.manage` | `backend/admissions/enquiries.py`, `enquiry_views.py`, `frontend/src/app/features/admissions/enquir*`, `features/apply/apply-page.ts` |
| Staged student imports: `students-v1` contract, dry run with row errors, duplicate decisions, commit with provenance and proposed guardian links, re-runs that create nothing twice, error file, discard, undo; `data.import` | `backend/imports/`, `frontend/src/app/features/settings/data-page.ts`, `import-page.*` |
| Give a student a login | `backend/students/logins.py`, `features/students/student-page.ts` |
| Demo: two Aster enquiries; sample file `backend/imports/fixtures/aster-students-sample.csv` (6 ready, 1 error, 1 duplicate of Arjun Demo) | `seed_demo.py` |

Checks on 23 Oct 2026: backend `pytest` 426 passed; `ruff check` and `ruff format --check` clean; frontend `ng test`
175 passed; `ng build` clean.
Browser (built-in, Chromium): at 390 px a parent asked a question from Aster's Apply page and got reference E2026-0003
(no sideways scroll); as `aster.admissions` at 1280 px the Enquiries list showed counts by status, and the enquiry was
assigned, followed up and linked to application A2027-0001; as `aster.admin` the sample file's dry run showed 8 rows,
6 ready, 1 possible duplicate (of 2027-0001 Arjun Demo), 1 error; Import stayed disabled until the duplicate was
skipped, then imported 6; the error file listed row 8's impossible date; re-uploading the file showed 6 already
imported and created nothing; a one-row import was undone and its student was gone; Kiran Rao (2026-0001, imported)
was given a login and signed in at 390 px, changed the password and saw his record. Found and fixed: the enquiry
reference and its full stop wrapped onto separate lines; Settings and Data transfer were both highlighted in the menu
(Data transfer now lives at `/app/data`). The check's enquiry, the six imported students and Kiran's login remain in
the local database.

Final review (fresh reviewer, 23 Oct 2026), fixed with a failing test first: undo is refused once staff have added or
checked a guardian on an imported student (it had deleted staff-added guardians); campus-scoped officers must pick a
place on their campus before an enquiry is saved (they got a server error after the save, and retries duplicated
it), and an assignee is checked against the enquiry's new place; enquiries can no longer point at a draft cycle's
places (that locked the cycle editor); numbering, the undo check and undo run in a few queries per batch, and files
are limited to 2,000 rows until imports move to the job queue; a re-import under a differently spelled source system
finds the earlier one; the public question form takes JSON only (another site can't post into it through visitors'
browsers); a malformed CSV, an over-long source id or email are a file or row error, not a server error; a refused
link to an application now says why. Backend `pytest` 436 passed, frontend `ng test` 176 passed, lint and build clean.
Deferred minors: undo locks students but not links being verified at that moment; the checksum covers raw rather than
normalised values (an en dash vs hyphen reads as changed); no duplicate re-check at commit; no byte-order mark on the
template and error files (Excel shows the en dash oddly); the question form shows only while a cycle is open; counts
by source aren't shown on the list; Import is enabled when only skipped duplicates remain; the assignee dropdown can
disagree with the text after a refusal or a lost permission; a PATCH can clear both phone and email; converting
doesn't check the actor can see that application; totals after commit mix dry-run and commit counts; unknown header
columns are ignored silently; imports routes add `urls.W002` warnings; a discarded or failed upload's file is deleted
or left outside the transaction; the New enquiry page's place list is empty for a role with only `enquiry.manage`;
Data transfer lives at `/app/data` (deliberate); two old migrations had their imports reordered; some isolation tests
are thinner than they look.


## Slice 4b (19 October 2026)

**Slice 4b is built and checked locally: the second part of BUILD-04.** Spec:
`docs/superpowers/specs/2026-10-19-slice4b-guardians-withdrawal-design.md`. Plan:
`docs/superpowers/plans/2026-10-19-slice4b-guardians-withdrawal.md`. Branch `slice-4b-guardians`, cut from
`slice-4-admissions` (with its review fixes merged). Left for slice 4c, which finishes BUILD-04: enquiries and staged
spreadsheet imports (TST-025, SCR-042).

| Built in slice 4b | Where |
|---|---|
| Guardian links: proposed by enrollment or staff, verified with evidence and access, revoked; adult-student consent and review flag; `guardian_link.manage` | `backend/students/guardians.py`, `models.py`, `views.py` |
| Guardian logins and the family portal (`/family`, child pages); guardians keep the applicant pages; applicant pages for applicants and guardians only | `backend/students/family.py`, `frontend/src/app/features/family/` |
| Withdrawal and reinstatement | `backend/students/withdrawal.py`, `frontend/src/app/features/students/student-page.ts` |
| Employee number and joining/leaving dates on staff | `backend/accounts/models.py`, `staff.py`, `frontend/src/app/features/staff/` |
| Student record history; possible-duplicate warning on applications; directory status filter | `backend/students/views.py`, `frontend/src/app/features/students/`, `features/admissions/` |
| Demo: `aster.parent` verified for Arjun, `aster.grandparent` with nothing shared, employee numbers `AST-001`… | `backend/institutions/management/commands/seed_demo.py` |

Checks on 19 Oct 2026: backend `pytest` 383 passed; `ruff check` and `ruff format --check` clean; frontend `ng test`
166 passed; `ng build` clean.
Browser (built-in, Chromium): as `aster.registrar` at 1280 px, added Diya Krishnan's father as a guardian, verified
him with evidence, record access off and a new login; he signed in at 390 px, was made to change the password and saw
Diya listed as not shared (no sideways scroll); after the registrar revoked the link his portal showed nothing and the
child's page was 404; `aster.parent` at 390 px saw Arjun's number and class. Withdrawing Diya today was refused
("before the enrollment starts", as she is enrolled for next year); with her test enrollment moved to June 2026 the
withdrawal succeeded (banner, ended enrollment, her login refused), and Reinstate restored her sign-in; her history
listed every step. As `aster.admin` changed a teacher's employee number. The check's guardian (`ravi.krishnan`,
revoked) and Diya's backdated enrollment remain in the local database.

Final review (fresh reviewer, 23 Oct 2026), fixed with a failing test first: the family portal no longer carries the
registrar's leaving reason (it could be safeguarding-sensitive); a student enrolled for next year can be withdrawn
before the year starts (not before the admission day). Ruled: no backfill of guardian links for students enrolled
before 4b — nothing is deployed, the demo's Arjun is backfilled by the seed. Backend `pytest` 385 passed, lint clean.
Deferred minors: proposing a link on a withdrawn student is accepted; a login cannot be added to a link verified
without one; an existing login cannot be attached to a staff-proposed link; field errors the forms don't show are
silent; the record's history does not refresh after actions; withdraw/reinstate reset unsaved detail edits; the
withdrawal date defaults to the browser's day; verify does not lock the student; a concurrent duplicate login ID gives
a 500; no separate audit line for a guardian login being created; the duplicate warning ignores the viewer's student
scope; eleven old migrations were reformatted (no behaviour change); seed employee numbers can collide with typed
ones; the adult-review flag uses the UTC day.


## Slice 4a (19 October 2026)

**Slice 4a is built and checked locally: the first half of BUILD-04**, from an admission cycle to an enrolled student
with their own login. Spec: `docs/superpowers/specs/2026-10-19-slice4a-admissions-students-design.md`. Plan:
`docs/superpowers/plans/2026-10-19-slice4a-admissions-students.md`. Branch `slice-4-admissions`, cut from
`slice-3-configuration`. Left for slice 4b: guardian records and parent logins, a fuller student portal, enquiries,
withdrawal after enrollment and staged CSV imports (TST-025).

| Built in slice 4a | Where |
|---|---|
| Membership kinds (staff, applicant, student) and routing by kind | `backend/accounts/`, `frontend/src/app/core/guards.ts` |
| Admission cycles with places and seats, questions and required documents; draft → published → closed | `backend/admissions/cycles.py`, `frontend/src/app/features/admissions/` |
| Public admissions page, applicant sign-up, applications with private document uploads, submit with snapshots, withdraw, accept | `backend/admissions/public.py`, `applicant_*.py`, `applications.py`, `documents.py`, `frontend/src/app/features/apply/` |
| Staff review: documents checked or sent back, more information, eligible / not offered, offers within seats, internal notes | `backend/admissions/review.py`, `staff_views.py` |
| Enrollment: Person, Student number, Enrollment and student login in one step, once only | `backend/admissions/enrollment.py`, `backend/students/` |
| Students directory and record (corrections with version check); the student's own record at `/student` | `backend/students/views.py`, `frontend/src/app/features/students/`, `features/student/` |
| Demo: Aster's Admissions 2027 cycle, `aster.admissions`, `aster.registrar`, `aster.parent`, student `aster.2027-0001` | `backend/institutions/management/commands/seed_demo.py` |

Checks on 19 Oct 2026: backend `pytest` 329 passed; `ruff check` and `ruff format --check` (120 columns, migrations
excluded) clean; frontend `ng test` 150 passed; `ng build` clean.
Browser (built-in, Chromium), at 1280 px unless noted: a new parent signed up on Aster's Apply page, filled in a Class 1
application, uploaded a PDF and a PNG and submitted (A2027-0003); as `aster.admissions` started the review, checked both
documents and asked for more information; the parent saw the question, added it and resubmitted; the officer marked it
eligible and had no Offer button; as `aster.registrar` offered the place until 15 Nov; the parent accepted at 390 px;
the registrar enrolled with a first password (student 2027-0002, login `aster.2027-0002`), corrected a detail on the
record and found the student by search; the new student signed in at 390 px, was made to change the password and saw
their number and class, with no sideways scroll; `/app` sent the student away and the staff API refused them.
Found and fixed during the check: every search box's label pointed at the wrong element (the id sat on both the
component and its input), so clicking the label did not focus the box; the enroll dialog's button said "Set password".
The check's applicant, application and student remain in the local database; `seed_demo` does not remove them.

Final review (fresh reviewer, 19 Oct 2026), fixed with a failing test first: student-style login IDs
(`<school>.<year>-<n>`) are reserved, so nobody can take one before enrollment, and enrolling names a taken one
clearly; applicant pages are for applicant logins only; applicants and students never appear among staff nor hold
staff permissions, even with a role row; a family asked for more information can reply after the closing date, and
staff can decline while waiting; an expired offer can be offered again or declined; uploading a document keeps
unsaved form entries; the "before you can submit" list names each missing item; a cycle with unsaved edits cannot be
opened, and its editor warns before leaving. Backend `pytest` 339 passed, frontend `ng test` 154 passed, lint and
build clean. Deferred minors: module-off routes answer 403 (not 404) to people without the permission; enroll
returns an existing student before the permission check; cycle summaries show all campuses' counts to campus
reviewers and count drafts; document buttons show in stages that refuse them; submission history lacks content;
not-yet-open cycles are offered and refuse; editor default dates use UTC; reviewers see draft-cycle controls they
cannot use; student edits accept a future birth date and do not rename the login; the record links to an application
some readers cannot open; the enroll toast omits the login ID; Apply shows when admissions is off; no separate
student-created audit event; seed has two questions; a failed document save can leave its file on disk.
Two test cycles from the check ("Mid-year intake 2027", "Sports quota 2027 (draft)") remain as drafts locally.


## Slice 3 (18 October 2026)

**Slice 3 is built and checked locally, finishing BUILD-03** except the parts the pack places elsewhere (support access
→ BUILD-11, groups and affiliation grants → BUILD-05, guardian grants → BUILD-04, invitations/recovery → after D-12).
Spec: `docs/superpowers/specs/2026-10-19-slice3-configuration-approvals-design.md`. Plan:
`docs/superpowers/plans/2026-10-19-slice3-configuration-approvals.md`. Branch `slice-3-configuration`, cut from
`slice-2-organization-access`.

| Built in slice 3 | Where |
|---|---|
| Configuration engine: typed settings in code, revisions with drafts, preview, approval by a second person, effective dates, cancelling unstarted schedules, history and restore | `backend/configuration/` |
| Settings: modules switched on (plan ∩ switched on), approval for powerful roles, academic year start | `backend/configuration/registry.py` |
| Role-change approval: powerful roles wait (grant nothing) until someone else who could give them approves; reject with a reason; approvals list | `backend/accounts/staff.py`, `approvals.py` |
| Settings list and editor; grouped menu; "Waiting for your approval" on Home; approve/reject on the staff page; academic year and switched-on modules on Home | `frontend/src/app/features/settings/`, `layout/`, `features/app/`, `features/staff/` |
| Slice 2 review follow-ups: 422/409 for model and race errors, unique active role names, rank re-checked under the lock, private platform notes, audit wording, roles search, one query per staff page, reversible role migrations, route guards, Add staff leave-guard, can_give, onboarding fallback | across backend and frontend |

Checks: backend `pytest` all passing, `ruff check`/`ruff format --check` clean; frontend `ng test` 132 passed, `ng build`
clean. Final review (fresh reviewer): fixed, each with a failing test first — nobody approves a role requested for
themselves; turning approval off can never get stuck (a lone remaining approver may switch it off, audited); turning it on
needs two people who could approve any role; a held custom role cannot gain powers while approval is on; Settings opens
to approvers who only publish. Deferred minor items: expired role requests stay approvable without effect; approve and
return ignore the setting key in the URL; same-day republish labels the earlier one "Replaced before it started"; some
audit lines lack "from" values; approver counting is per person; the editor drops an unsaved edit when paging history.
Browser: as `aster.admin` scheduled the academic year to April from 1 Apr 2027 (today still June) and sent
"approval for powerful roles" for approval; as `aster.deputy` approved it from Home; as `aster.campus` asked to make
`aster.office` a Campus Admin — it waited; the deputy approved it on the staff page. The demo was then put back (role
ended, approval off through the same two-person steps). Settings editor checked at 390 px with no sideways scroll.


**Slice 2 is built and checked locally:** organization, staff roles, modules and the restricted state. Spec:
`docs/superpowers/specs/2026-10-18-slice2-organization-staff-modules-design.md`. Plan:
`docs/superpowers/plans/2026-10-18-slice2-organization-staff-modules.md`. Branch `slice-2-organization-access`, cut from
`slice-1-foundation` (local commits only, nothing pushed).

| Built in slice 2 | Where |
|---|---|
| Campuses and departments (nested, campus follows parent, no cycles, deactivation refused while in use); a Main campus for every institution | `backend/organization/`, `frontend/src/app/features/org/` |
| Scoped, dated role assignments; permission registry and nine built-in roles; custom roles within the editor's own authority; grant ceiling, no self-changes, last-admin guard | `backend/accounts/roles.py`, `permissions.py`, `role_views.py` |
| Staff: add with a first password, give and end roles, reset passwords, remove and restore; Campus Admins see and act only within their campus | `backend/accounts/staff*.py`, `frontend/src/app/features/staff/` |
| Roles page and editor with a before/after preview | `frontend/src/app/features/roles/` |
| Module catalogue (20 modules, category defaults, dependencies); Modules step in onboarding and tab on the institution page; "Modules in your plan" on Home | `backend/institutions/modules.py`, `frontend/src/app/core/modules.ts` |
| `restricted` state: read-only for members with the reason shown; public page stays up | `backend/sites/middleware.py` |
| Workspace menu by permission; restricted banner | `frontend/src/app/layout/` |

Checks on 18 Oct 2026 (after the final review's fixes): backend `pytest` 235 passed; `ruff check --select F,E,W,I --line-length 120 --exclude
'.venv,*/migrations' .` and `ruff format --check` (same options) clean; frontend `ng test` 120 passed; `ng build` clean.
Browser (built-in, Chromium): as `aster.admin` added a campus, a member of staff with a first password, gave and ended a
role, created a custom role; as `aster.campus` saw only City staff, Roles redirected home; as `eduma.admin` restricted
Aster (banner shown, a write refused with the reason) and lifted it; onboarding Modules step and the Modules tab;
Home and a staff page at 390 px with no sideways scroll.

Final review (fresh reviewer, 18 Oct 2026), fixed with a failing test first: a role starting later now counts when
deciding who may reset or remove a person (it was a way for a Campus Admin to take over a future Institution Admin's
account); department loops can no longer form through two moves at once nor hang a permission check; roles are grouped
by the server's phase on the institution's calendar; Profile is read-only for members who cannot change it. Deferred
minor items are listed under "Known limits".

Known limits (slice 2, deferred minor items): `?campus=` with a malformed id on the departments list is a 500;
un-archiving a custom role skips the name check (no screen does it); two identical creates at the same instant can 500;
`status_reason` is readable by every member; `/app/site` has no route guard; the restriction-lifted audit line reads
"Restriction_lifted"; onboarding sends no modules if the catalogue fails to load; the role-migration start date uses
UTC and the migration cannot be rolled back past the role removal; staff lists re-query permissions and roles per row;
the roles list has no search.

## Slice 1 (17 October 2026)

**Slice 1 is built and checked locally:** foundation, onboarding, institution web addresses and branding. Spec:
`docs/superpowers/specs/2026-10-17-foundation-onboarding-branding-design.md`. Plan:
`docs/superpowers/plans/2026-10-17-slice1-foundation-onboarding-branding.md`. Branch `slice-1-foundation` (local commits
only, nothing pushed).

| Built | Where |
|---|---|
| Host-based tenancy: Eduma at the base host, each institution at `<slug>.<base host>`; unknown addresses get a neutral "no Eduma site here" | `backend/sites/hosts.py`, `sites/middleware.py` |
| Sign-in per address: platform `/login` (unlinked, platform admins only), institution `/login` (its members only); sessions tied to the address they were made on; first passwords must be changed | `backend/accounts/`, `frontend/src/app/features/auth/` |
| Onboarding wizard (5 steps, live address check, idempotent create), institution directory (search as you type, filters), overview, institution detail (readiness, profile, admin password reset, lifecycle with reasons), audit log | `backend/institutions/`, `frontend/src/app/features/console/` |
| Lifecycle `setup → active ⇄ suspended → archived`; suspension signs members out on their next request and shows "temporarily unavailable" | `backend/institutions/services.py` |
| Branding: logo, two colours (readable text colours derived and checked), heading and body fonts from 11 bundled OFL fonts | `backend/sites/theme.py`, `frontend/src/app/core/contrast.ts` |
| Public page: 8 section types (hero, offerings, steps, people, gallery, testimonials, highlight band, FAQ) in the reference's style, themed per institution | `frontend/src/app/features/public/` |
| Site editor: live preview (wide and phone), drafts with conflict detection, publish, history and restore, image uploads (re-encoded, metadata stripped) | `frontend/src/app/features/editor/`, `backend/sites/services.py`, `sites/images.py` |
| Institution workspace in its own branding: home checklist, public site editor, profile | `frontend/src/app/features/app/` |
| Demo data: `eduma.admin` and four institutions (`aster`, `meridian`, `vector`, `summit`) | `backend/institutions/management/commands/seed_demo.py` |

## Automated checks (last run 17 Oct 2026)

| Command | Result |
|---|---|
| `cd backend && pytest` | 170 passed |
| `ruff check --select F,E,W,I --line-length 120 --exclude '.venv,*/migrations' .` and `ruff format --check` | clean |
| `DJANGO_DEBUG=0 … manage.py check --deploy` | no issues (2 silenced on purpose: HSTS subdomains/preload) |
| `manage.py makemigrations --check` | no changes |
| `cd frontend && npx ng test --watch=false` | 90 passed (21 files) |
| `npx ng build` | builds; initial bundle 406 kB (106 kB transferred) |

## Browser checks (built-in browser, Chromium, 17 Oct 2026)

Checked by hand at 1440 px and 390 px:

1. `localhost:4201` shows the Eduma page with no link to `/login`.
2. Platform sign-in, overview, directory, search, the audit log, and an institution's detail and activity pages.
3. Onboarded a new institution through the wizard with a 116-character name ("Lotus Valley International Residential
   School and Junior College of Science, Commerce and the Humanities, Vijayawada", address `lotus-valley`). Then:
   uploaded a logo, changed colours and font, published, and activated with an override reason.
4. `lotus-valley.localhost:4201` showed its own logo, colours and fonts, with Sign in.
5. Its admin's first sign-in forced a password change; `/app` could not be reached before it.
6. Suspending it from the console signed the admin out on their next action, and its address now reads "temporarily
   unavailable".
7. Aster, Meridian, Summit and Vector ("Opening soon") each show their own fonts and colours.
8. Keyboard only: sign-in and the wizard. The phone drawer moves focus in, makes the page behind it inert, and returns
   focus on Esc.
9. No horizontal scroll at 390 px on eight pages: landing, sign-in, workspace home, overview, directory, wizard, editor,
   audit.

Defects these checks found, each fixed with a test that failed first:
- the starter heading went over 120 characters for long names;
- the readiness list was stale after publishing from the console;
- the sign-in form showed instead of the "unavailable" page after a suspension;
- the suggested address was cut mid-word;
- selects showed their first option;
- the start-up injection error.

Screenshots (headless Chrome): `docs/screenshots/eduma-landing.png`, `eduma-landing-phone.png`, `aster-landing.png`,
`meridian-landing.png`, `lotus-unavailable.png`.

Walk-through data left in the local database:
- the institution `lotus-valley` is suspended;
- its admin `lotus-valley.admin` now has the password `Demo-pass-2027`;
- Aster's draft has two saved versions.

`seed_demo` does not touch any of these.

**Not checked:**
- screen readers;
- Safari (it may not resolve `*.localhost`);
- real phones;
- 200% zoom;
- load or performance;
- anything on a server, where real HTTPS and wildcard certificates would apply.

## Known limits (deliberate in this slice)

- **Uploads:** re-encoded with Pillow; there is no anti-virus scanner (see the `shortcut:` note in
  `backend/sites/images.py`).
- **Security:** no MFA or step-up authentication; no PostgreSQL row-level security (isolation is enforced in the
  application and tested).
- **Hosting:** no server-side rendering, so link previews show the generic title; custom domains are not supported.
- **Eduma's own page:** its content is in code (`backend/sites/eduma_content.py`), and its hero image slots show tinted
  tiles. They could be replaced with product screenshots once the content schema allows static images.
- **Email:** none is sent; first passwords are handed over in person.

## Final review (fresh reviewer, 17 Oct 2026)

Verdict: ready with fixes, no critical issues. Fixed, each with a test that failed first:

- unchanged first password accepted — test_first_password_cannot_be_kept RED→GREEN, suite 170/170 backend.
- suggested login ID over 40 chars for long names — onboarding spec "fits the 40-character limit" RED→GREEN, suite 90/90 frontend.
- network blip shown as "no Eduma site" / recheck signing out — session-interceptor "keeps the user when the recheck itself fails" and LandingPage "offers to try again" RED→GREEN, suite 90/90.
- mid-tone brand colours giving under 4.5:1 button text (spec claim was false) — derive() now adds primary_fill/secondary_fill; test_mid_tones_get_a_fill_that_text_can_sit_on and contrast.spec fill test RED→GREEN; spec sentence corrected.
- (upgraded from Minor 7) restore overwriting a newer draft — test_restore_over_a_newer_draft_is_409 and editor restore-version test RED→GREEN.
- (upgraded from Minor 10) edits typed during an in-flight save/publish marked saved or dropped — two site-editor tests RED→GREEN.

Still open (small; none reachable through normal use of the screens unless noted):

- malformed create bodies (JSON array, admin as a string) give 500 instead of 400/422 (request_digest before validation).
- a replayed create with a changed first password returns the original institution and keeps the old password.
- duplicate section ids are accepted by the content schema (only reachable by crafting API requests).
- after a publish conflict where the draft is gone, "Keep mine and save" is still offered.
- wizard sends a hidden UDISE/AISHE value after a category switch, and keeps showing a server error after the field is edited.
- a lifecycle action or password reset on the detail page resets unsaved edits in its profile form.
- suspended/archived institutions' images 404 in the platform editor's preview.
- the Django admin (DJANGO_ADMIN=1) cannot stay signed in because its login does not set session["site"].
- a switched-off login is distinguishable by response timing (extra password check).
- PATCH without version returns 409 version_conflict rather than 422 "version required".
- sites/public.py comment says "never unpublished page content" though the draft hero title is used when nothing is published.

## Decisions made while building

Each line: what was decided, why, and what it costs if wrong.

- Setup: Ruling: work on branch slice-1-foundation in the main checkout instead of a separate worktree — new local repo with only doc commits on main; a worktree would split venv/node_modules/launch paths — cost if wrong: none, merge/branch-delete is the same.
- Task 1: Ruling: LOCAL_APPS starts as ["common"]; later tasks add accounts/institutions/sites as they create them — apps listed before they exist break manage.py check — cost if wrong: none. Ruling: problem test asserts response.content_type (what DRF renders) not the unrendered Content-Type header — cost if wrong: none.
- Task 2: Ruling: AuditEvent uses UUID pk too (Global Constraints: UUID on every new model) — cost if wrong: none.
- Task 3: Ruling: refusals use Problem(400, invalid_credentials) and switched-off Problem(400, login_switched_off) so the app can tell them apart by code — cost if wrong: none. Ruling: switched-off message only when the login could otherwise sign in on this host (stops cross-host account probing) — cost if wrong: an off user on the wrong host sees the generic refusal.
- Task 4: Ruling: Eduma hero eyebrow is "From schools to universities" — the plan's "Schools · Colleges · Engineering · Universities" is 47 chars, over the spec's 40-char eyebrow limit; the offerings section names all four types — cost if wrong: one string.
- Task 4: Ruling: common.exceptions._flatten renamed flatten_errors (public) so content tests can assert dotted field paths — cost if wrong: none.
- Task 4: Ruling: starter gallery starts hidden as well as people/testimonials (empty photo tiles on a live page look broken) — cost if wrong: admin toggles it on.
- Task 5: Ruling: saving or publishing when the draft no longer exists (someone published it) returns 409 version_conflict with current_version null, not 404, so the editor shows one "reload" path for every stale state — cost if wrong: frontend treats it as conflict.
- Task 5: Ruling: revisions are serialized per institution by locking the Institution row (select_for_update) rather than revision rows — covers draft creation races too — cost if wrong: brief contention per institution only.
- Task 6: Ruling: no global Image.MAX_IMAGE_PIXELS change — the 4000×4000 dimension check runs on the header before any decode, and Pillow's own DecompressionBombError is caught; avoids a process-wide side effect — cost if wrong: none (bomb test passes).
- Task 6: Ruling: public site code lives in sites/public.py (not views.py) to keep visitor-facing logic apart from editor views — cost if wrong: none.
- Task 6: Ruling: an active institution with no published page (activated by override) serves mode "opening_soon", and the platform logo_url is the bundled /eduma-logo.png — spec silent — cost if wrong: one branch.
- Task 6: Ruling: images are re-oriented with ImageOps.exif_transpose before metadata is dropped so phone photos are not sideways — cost if wrong: none.
- Task 7: Ruling: create_institution(actor, data, key, digest) takes the digest computed from the raw request; the view checks for a replay BEFORE validating, because a replayed body's slug/login ID are already taken and would otherwise fail validation with 422 instead of returning the original — cost if wrong: none.
- Task 7: Ruling: readiness is one annotation helper (with_readiness) used by both the list's `ready` flag and the detail checklist, so the two can never disagree — cost if wrong: none.
- Task 7: Ruling: Task 3's deferred forced-password check now asserts /api/v1/institution returns 200 after the change — cost if wrong: none.
- Task 7: Ruling: institution admins may PATCH only contact_email/contact_phone/address on their own profile (other fields silently ignored, not rejected) — cost if wrong: frontend never sends others.
- Task 8: Ruling: backend formatted with `ruff format --line-length 120` (plus the plan's ruff check) so lint stays clean mechanically — SC has no recorded formatter — cost if wrong: style-only diff.
- Task 8: Ruling: invalid move messages name the states ("An institution that is suspended cannot move to setting up.") and an unknown target state is 422 (choice field), not 409 — cost if wrong: none.
- Task 9: Ruling: seed activates demo institutions through services.transition (audited "Demo data") instead of setting the field, and marks active admins as having signed in so readiness passes — cost if wrong: none.
- Task 10: Ruling: SC's token names (--text, --primary, --accent-soft, --surface, --muted…) are kept as aliases of the Eduma brand variables so copied SC components work unchanged — cost if wrong: none.
- Task 10: Ruling: copied format.ts trimmed to date/dateTime/number/readable (SC's weekly-list helpers dropped with their tests); status-badge tones replaced with Eduma lifecycle/revision states — cost if wrong: none.
- Task 10: Ruling: Sass needs unique namespaces for each font @use (`as font-<name>`) — cost if wrong: none.
- Task 11: Ruling: routes are added by the task that builds each page (Task 11 adds only the not-found catch-all and the initializer), so every commit builds — cost if wrong: none.
- Task 11: Ruling: guestOnly also sends visitors away from /login on an unavailable (suspended) institution, not only an unknown address; signOut goes to "/" (this address's public page) — cost if wrong: none.
- Task 11: Ruling: SiteStore also exposes logoUrl() (site logo, Eduma's on the platform, null → show name) and failed() for a retry message — cost if wrong: none.
- Task 12: Ruling: public styles live in one global public.scss scoped under .site (section components hold markup only) — component style budgets (10 kB) would otherwise be exceeded — cost if wrong: none.
- Task 12: Ruling: empty image slots are decorative (aria-hidden) for visitors; their purpose label shows only in the editor preview — cost if wrong: none.
- Task 12: Ruling: hero cards stay overlapped (smaller) on phones instead of stacking straight; checked at 390px with no horizontal scroll — cost if wrong: CSS only.
- Task 13: Ruling: a refused sign-in clears only the password field; a forced password change offers Sign out instead of Cancel (there is nowhere else to go) — cost if wrong: none.
- Task 14: Ruling: the drawer's focus containment uses `inert` on the rest of the page (plus focus to the drawer, Esc and backdrop close, focus back to the menu button) instead of a hand-written Tab trap — cost if wrong: none in current browsers.
- Task 14: Ruling: added SiteTitleStrategy so tab titles read "<page> · <site name>" — not in the plan; tiny — cost if wrong: none.
- Task 14: Ruling: active nav item uses a primary-tint background with an inset primary bar and ink text (not --brand-primary-text on the tint, which can fall under 4.5:1) — cost if wrong: none.
- Task 15: Ruling: the directory is a list (cards at every width) rather than a desktop table — it holds 5 short fields and stays readable at 390px without a second layout — cost if wrong: CSS/markup only.
- Task 15: Ruling: added ui/CopyUrl (address + Copy + optional Open) shared by list/detail/home; LoadError now renders nothing for an empty message (load-error.spec RED→GREEN).
- Task 15: Ruling: the wizard posts with HttpClient directly (Api.post has no headers option) to send Idempotency-Key — cost if wrong: none.
- Task 16: Ruling: no separate LifecycleDialog component — lifecycle actions use the house ConfirmDialog.prompt (required textarea) built by a tested pure function lifecycleQuestion(); activating before readiness lists the unmet items and the one answer is sent as both reason and override_reason — cost if wrong: admins cannot give two different texts.
- Task 16: Ruling: one AuditList component serves the Audit log page (with filters) and the institution Activity tab — cost if wrong: none.
- Task 17: Ruling: content is a mutable copy bound with ngModel plus an `edits` counter; the preview gets a structuredClone per change (stable inputs keep the caret; preview always fresh) — cost if wrong: perf on very large pages only (content is capped).
- Task 17: Ruling: the conflict banner offers "Reload latest (discard mine)" and an explicit "Keep mine and save" (re-reads the current version, then saves) instead of "Keep editing", which could only fail again — explicit overwrite, never silent — cost if wrong: one button.
- Task 17: Ruling: public.scss now uses @container site queries and cqi units instead of viewport media queries/vw, so the editor's 390px preview lays out like a phone; visitors see no difference (.site is the full width) — cost if wrong: browsers without container queries (pre-2023) get desktop layout.
- Task 17: Ruling: added core/contrast.ts, a TS port of the server's contrast rules with parity tests against server-printed values (#FFD43B→#8D6E00 etc.) so the preview shows exact readable colours — cost if wrong: none (server re-derives on save).
- Task 17: Ruling: UnsavedChanges service + leaveGuard on the institution route; switching detail tabs also asks — cost if wrong: none.
- Task 18: Ruling: kept two small profile forms (console edits all details; the workspace only contacts) rather than one form with flags, as the plan allowed — cost if wrong: some duplicated markup.
- Final: Ruling: a JPEG named .png is accepted (re-encoded, stored and served with its real type image/jpeg plus nosniff) rather than refused as the plan's Review Focus 4 wording said — re-encoding is the safety check and refusing a real image for its name would only frustrate admins — cost if wrong: one extension check.
- Final: Ruling: per-login-ID throttle lockout (20/hour) kept as specified — cost if wrong: an attacker can delay one known admin's sign-in for an hour.
- Final: Ruling: opening-soon page shows the draft's look and hero title before publication, as spec §5 says — cost if wrong: an unpublished heading is visible.
- Final: Ruling: draft-only brand images are publicly fetchable by UUID while setup/active (branding is public by classification) — cost if wrong: unpublished images can be seen by someone who has the id.
- Final: Ruling: wildcard CSRF trusted origins for subdomains kept (spec §2; token check still applies) — cost if wrong: none known.
- Final: Ruling: no upload quota or unreferenced-asset cleanup this slice — operational work later — cost if wrong: storage growth.
- Final: Ruling: JSON body size for draft PUT left to the reverse proxy limit at deployment — cost if wrong: a signed-in editor could send a large body.
- Final: Ruling: status_reason readable by institution admins — it explains their own institution's state to them — cost if wrong: an internal remark is shown to the institution.
- Final: Ruling: slugify drops accented letters (ASCII only, as planned) — cost if wrong: "École" suggests "cole"; the admin can type the address.
- Final: Ruling: star rating as aria-label text kept (screen readers not tested this slice) — cost if wrong: rating may not be announced.
- Final: Ruling: directory as a list rather than a table (covered by Task 15 ruling).

## Next slice (from the build pack, BUILD-03 onwards)

- **Rest of BUILD-03:**
  - campuses and departments;
  - groups and affiliation grants;
  - custom roles and other staff roles with delegation limits;
  - module entitlements and the `restricted` state;
  - typed configuration revisions with impact preview.
- **Then:** admissions (the "Apply" call to action points to `/apply`), people and guardians, academic structures for
  all four categories, attendance, results, fees, communication, and the operational modules.
- **Process:** each slice starts with its own spec and plan (superpowers brainstorming → writing-plans).
