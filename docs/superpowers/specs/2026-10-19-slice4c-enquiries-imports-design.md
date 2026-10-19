# Eduma slice 4c — enquiries and staged student imports (BUILD-04, part 3)

**Date:** 19 October 2026 · **Status:** written from the spec pack at the user's request ("skip the questions, plan it
from the spec pack"; "continue the build in the same way"); build rulings marked.
**Source pack:** 01 §9.1 (enquiry capture, follow-ups, source tracking, counselor assignment); 03 WF-ADM; 04 SCR-042;
08 §4 provenance, ImportJob/ImportRow; 09 `POST I/imports`, `/validate`, `/commit`, `GET …/errors`; 11 §6 import
contracts and cutover; TST-002, TST-025; BUILD-04 "staged CSV/import mapping, row errors, duplicate review,
provenance and reconciliation"; D-16 (import formats) still open, so one synthetic contract is used.
**Builds on:** slices 1–4b. Finishes BUILD-04.

## 1. What this slice is for

Families who are not ready to apply can ask a question; the admissions office tracks every enquiry to an answer or an
application. A school moving to Eduma can bring its existing students in from a spreadsheet safely: nothing reaches the
real records until a person has seen a dry run, settled possible duplicates and committed; every imported student
remembers where it came from; running the same file again creates nothing twice.

**Success:** a parent asks "Is there a school bus to Benz Circle?" from Aster's Apply page; it appears for the
Admissions Officer as enquiry E2026-0001 (source: website), who assigns it to themself, logs a phone call with a
follow-up date, and later links it to the family's application A2027-0004 (converted). The Institution Admin uploads
`aster-students.csv` (40 rows, source system "Old ERP"): the dry run shows 37 ready, 2 errors (a bad date, an unknown
campus code) and 1 possible duplicate of 2027-0001 Arjun Demo; they choose "skip" for the duplicate and commit; 37
students exist with numbers, enrollments and proposed guardian links; the error file downloads with row numbers;
uploading the same file again shows 37 "already imported" and commits nothing new.

**Anti-goals:** a CSV writing straight into student tables; a re-run creating duplicates; a person merged because a name
or phone matched; an error file that runs spreadsheet formulas; an imported guardian seeing anything before staff
verify them; an enquiry form that anyone can use to flood the office.

## 2. Decisions

| ID | Decision | Pack reference / why |
|---|---|---|
| S4C-01 | **Enquiry**: number `E<year>-NNNN` per institution, contact name, phone and/or email (one required), learner name, optional date of birth, optional interested place (from a published cycle), message ≤1000, source (`website`, `walk_in`, `phone`, `referral`, `event`, `other`), status `open` → `following_up` → `converted` / `closed` (reason), assigned staff member, next follow-up date. **Follow-ups**: note, how (`phone`, `email`, `in_person`, `message`), when, by whom, next date. | 01 §9.1 |
| S4C-02 | Families ask from the Apply page without an account (name, phone or email, learner name, place, message); throttled per address and per IP, with a hidden honeypot field; module `admissions` must be on. Staff record walk-in and phone enquiries themselves. | Build ruling: no captcha provider yet (D-12) |
| S4C-03 | New permission `enquiry.manage` (campus-scopable by the interested place's campus; no place → whole institution). Given to Institution Admin, Registrar and Admissions Officer. Assignees must hold it there. | 02 roles: Admissions Officer handles enquiries |
| S4C-04 | **Convert**: link an enquiry to an application of the same institution by number (status `converted`). Closing needs a reason. Reopening a closed enquiry is allowed; converted is final. | WF-ADM "enquiry … through enrollment" |
| S4C-05 | **Staged import** (`data.import`, institution-only, Institution Admin): upload a CSV (UTF-8, header row, ≤2 MB, ≤5,000 rows) with a source-system name → stored privately → parsed into rows → **dry run** (each row valid, error, possible duplicate, already imported, or changed since last import) → staff decide each possible duplicate (`create` or `skip`) → **commit** imports valid, decided rows in one transaction → reconciliation counts. Rows with errors are reported and never imported. | 11 §6; 09 imports API; build ruling: synchronous for now — a 50,000-row file needs the job queue (later) |
| S4C-06 | **Contract `students-v1`** (columns): `source_record_id`*, `full_name`*, `date_of_birth`* (ISO date or `unknown`), `phone`, `email`, `address`, `admitted_on`* , `academic_year`* (e.g. `2026–27` or `2026-27`), `place_code`*, `place_label`*, `campus_code`, `entry_date`*, `guardian_name`, `guardian_relationship`, `guardian_phone`, `guardian_email`. A template CSV with one synthetic row is downloadable. | 11 §6 Learner, Enrollment, Guardian link contracts; D-16 open |
| S4C-07 | **Provenance**: every imported student has an `ImportedRecord` (institution, source system, entity `student`, source record id, row checksum, batch). Unique per institution + source system + entity + source id. Re-importing an unchanged row → "already imported" (skipped); a changed row → "changed since the last import" (skipped and listed; corrections are made on the record). | 11 §6 "uniqueness is institution + source system + entity type + source record ID. A checksum detects changed content on retry." |
| S4C-08 | **Duplicates**: an existing student, or an earlier row in the same file, with the same name (case and spacing ignored) and date of birth is a possible duplicate; commit is refused (409) while any is undecided. `create` makes a separate person; nothing is ever merged. The same source id twice in one file is an error. | 08 §4; 11 §6 "do not merge by name/phone alone" |
| S4C-09 | **Commit creates** Person, Student (number from the academic year's start year, `2026-NNNN`), active Enrollment (place code and label, campus, entry date), ImportedRecord, and — when guardian columns are present — a guardian Person and a **proposed** GuardianLink (source `import`). No logins are created; no link is active until verified. Committing twice → 409. | 11 §6 "Quarantine unverified links; no invitations until relationship review" |
| S4C-10 | **Error file**: CSV of row number, column, code, message and source id only; any cell starting with `=`, `+`, `-`, `@`, tab or carriage return is prefixed with `'`. | 11 §6 "Error exports neutralize spreadsheet formula interpretation and avoid unnecessary sensitive fields" |
| S4C-11 | **Undo** a committed batch while nothing it created has changed since (students still at their first version, no link verified, no login, no later enrollment): removes what the batch created and marks it undone, audited. Otherwise refused (409) with the reason. Discarding a not-yet-committed batch deletes its stored file. | 11 §6 "an imported batch may be reversed only if dependencies permit" |
| S4C-12 | **Student logins for imported students**: on the student record, staff with `student.update` may give a student without a login one (`<slug>.<number>`, first password, forced change). | Imported students must be able to use the portal; mirrors enrollment's rule |

## 3. Data model

`admissions`: **Enquiry** (`VersionedModel`: institution, number, contact_name ≤150, phone ≤30, email, learner_name
≤150, learner_date_of_birth null, place null (Place), message ≤1000, source, status, close_reason ≤500, assigned_to
null (User), next_follow_up_on null, application null (Application), created_by null; unique institution+number),
**FollowUp** (enquiry, author, how, note ≤1000, at, next_follow_up_on null).

New app `imports`: **ImportJob** (`VersionedModel`: institution, contract `students-v1`, source_system ≤60, file
(private storage), original_name, checksum (sha256 hex), size, status `validated`/`committed`/`discarded`/`undone`,
totals JSON, created_by, committed_by, committed_at, undone_by, undone_at), **ImportRow** (job, row_number,
source_record_id, raw JSON, errors JSON list of `{field, code, message}`, state `valid`/`error`/`duplicate`/
`unchanged`/`changed`, duplicate_of JSON list of `{kind: student|row, id|row_number, label}`, decision `''`/`create`/
`skip`, checksum, student null; unique job+row_number), **ImportedRecord** (institution, source_system, entity_type,
source_record_id, checksum, job, student; unique institution+source_system+entity_type+source_record_id).

`students`: `GuardianLink.Source.IMPORT`.

## 4. Rules (in addition to §2)

- Upload parses and validates in one request; the response is the job with its totals. The file is stored privately
  under `PRIVATE_MEDIA_ROOT/imports/<institution>/<uuid>.csv`, never served publicly.
- Validation: header must contain every required column (else 422 on `file` naming the missing ones); each row: required
  values, ISO dates, `date_of_birth` not in the future, `entry_date` not before `admitted_on`, email shape, campus code
  an active campus of this institution, academic year label `YYYY–YY`/`YYYY-YY` with consecutive years; `full_name`
  ≤150 etc.
- Row checksum: sha256 of the normalised values in contract column order.
- Commit locks the job and the institution (numbers handed out one at a time), re-checks provenance inside the lock
  (a row imported by another batch meanwhile becomes `unchanged`), and is all-or-nothing.
- Every job action is audited (`import.uploaded`, `import.committed`, `import.discarded`, `import.undone`) with counts,
  never row contents. Each created student gets a `student.imported` history line naming the batch.
- Enquiry list for staff: those whose place's campus their `enquiry.manage` covers (no place → whole-institution
  holders); filters status, assigned to me, follow-up due (next date ≤ today), source; search ≥3 on number, contact,
  learner, phone.

## 5. API

Public: `POST /api/v1/public/enquiries` `{contact_name, phone, email, learner_name, place, message, website (honeypot)}`
→ 201 `{number}`; throttle scope `enquiry` (10/hour per IP).

Staff (`/api/v1/institution/admissions/enquiries`): GET (filters, paged) / POST (staff-recorded, with `source`);
`<id>` GET / PATCH `{version, assigned_to, next_follow_up_on, place, …contact fields}`; `<id>/follow-ups` POST `{how,
note, next_follow_up_on}`; `<id>/convert` POST `{version, application_number}`; `<id>/close` POST `{version, reason}`;
`<id>/reopen` POST `{version}`. Summary on the list: counts by status and by source.

Imports (`/api/v1/institution/imports`, `data.import`): GET jobs (paged); POST multipart `{file, source_system}` →
job; `<id>` GET (job + totals); `<id>/rows` GET (`state` filter, paged); `<id>/rows/<row>/decide` POST `{decision}`;
`<id>/commit` POST `{version}`; `<id>/discard` POST `{version}`; `<id>/undo` POST `{version}`; `<id>/errors.csv` GET;
`template.csv` GET.

Students: `POST /api/v1/institution/students/<id>/login {version, password}` (`student.update`).

## 6. Screens

- **Apply page**: an **Ask a question** form under the open cycles (name, phone or email, learner, place, question),
  then "Thank you — your reference is E2026-0001".
- **Admissions → Enquiries**: list (counts by status and source, filters, search, paged) and detail (contact, learner,
  message, follow-up timeline with "Add follow-up", assign, next follow-up date, Convert by application number, Close
  with reason, Reopen); **New enquiry** for walk-ins and calls.
- **Settings → Data transfer** (`/app/settings/data`, `data.import`): batches list; **Import students** (source system,
  file, template download, the column list); batch page: totals (ready, errors, possible duplicates, already imported,
  changed), rows filtered by state with each row's problems, Create/Skip per possible duplicate, **Commit** (disabled
  until every duplicate is decided and at least one row is ready), **Download errors**, **Discard**, and after commit
  the reconciliation (created, skipped, by reason) with **Undo** while allowed.
- **Student record**: **Give a login** for a student without one.

## 7. Tests that must exist

1. TST-025: a file with valid rows, bad rows and a duplicate → preview counts exact; commit creates exactly the valid,
   decided rows; committing again → 409; uploading the same file again → every row `unchanged`, commit creates nothing;
   a changed row → `changed`, not applied.
2. Duplicates: an existing student and an earlier row in the file both flagged; commit refused until decided; `create`
   makes a separate person; `skip` creates nothing; the same source id twice in a file → error.
3. Errors: missing columns → 422 naming them; bad date, future birth date, unknown campus, bad academic year, entry
   before admission → row errors with codes; error CSV neutralises `=cmd`, `+1`, `-1`, `@x`; no address or phone in it.
4. Guardians from import are proposed links with no login; the family portal shows nothing.
5. Undo: right after commit → everything the batch created is gone and provenance cleared; after a student was edited
   or a link verified → 409; discard deletes the stored file.
6. TST-002: another institution's job, rows, error file and enquiries → 404; `data.import` needed (403 for a
   Registrar); the file is never reachable by URL.
7. Enquiries: public form creates `E<year>-0001` with source website; honeypot filled → 201 but nothing stored; throttle
   → 429; module off → 404; campus-scoped officer sees only their campus's places; convert needs an application of the
   same institution; close needs a reason; version conflicts → 409.
8. Give a login: makes `<slug>.<number>` with a forced change; twice → 409; reserved pattern respected.

## 8. Left to the builder

Layouts, copy within the tone above, file layout inside `imports`, the template's synthetic example row.
