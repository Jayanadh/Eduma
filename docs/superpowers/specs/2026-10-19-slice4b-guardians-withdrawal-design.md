# Eduma slice 4b — guardian links, family portal, withdrawal, staff records and history (BUILD-04, part 2)

**Date:** 19 October 2026 · **Status:** written from the spec pack at the user's request ("skip the questions, plan it
from the spec pack"; "continue and finish the build"); build rulings marked.
**Source pack:** 02 §5 (guardian and adult student relationships); 03 WF-ACL guardian relationship, WF-ADM withdrawal;
04 SCR-018/019/020, SCR-035 (parent home); 05 walkthroughs 7 and 14; 08 §3 RelationshipGrant, §4 Person, Student,
GuardianLink, Employee, Enrollment; BUILD-04 checklist ("applicant/student/employee records … authorized guardian
relationships"; "withdrawal states"; "student detail screens reflect persisted changes and retain history").
**Builds on:** slices 1–4a. **Part 3 (slice 4c):** enquiries and staged spreadsheet imports (TST-025, SCR-042).

## 1. What this slice is for

A school can say, deliberately and on the record, which adults may see which child, and those adults get a family
login that shows exactly that and nothing more. A student who leaves is withdrawn properly: the record stays, the
login stops, and the reason and date are kept. Staff get an employee number and joining date. Every student record
shows its own history.

**Success:** Arjun Demo (2027-0001) is enrolled from Aster Demo Parent's application. Enrollment *proposes* a link
from Arjun to that parent; it grants nothing yet. The Registrar opens Arjun's guardians, checks the parent's ID in
person, verifies the link (basis "parent", method "documents seen in person", reference "Aadhaar seen 19 Oct"), and
leaves "record" access on. The parent signs in and lands on **Your children** with Arjun's number and class, and can
still open their other application (Meera). The Registrar adds Arjun's grandmother as a second guardian with her own
login but no record access; she sees Arjun listed with "Your school has not shared this record with you". Revoking
her link removes Arjun from her portal on the next request. In March, Arjun leaves: the Registrar withdraws him from
1 Mar 2027 with a reason; his enrollment ends, his login stops working, his record and history remain, and his parent
sees "Left on 1 Mar 2027".

**Anti-goals:** a link made because a phone number or surname matched; a proposed or revoked link showing anything;
one guardian seeing another guardian's restrictions or verification evidence; a teacher-level role reading custody
notes; parental access silently continuing into adulthood; withdrawal deleting anything or implying a refund.

## 2. Decisions

| ID | Decision | Pack reference / why |
|---|---|---|
| S4B-01 | **GuardianLink** joins a student to an adult **Person** (institution-owned, never merged automatically) with relationship, status `proposed` → `active` → `revoked`, access flags, dates, authority basis, verification method and reference, and a restrictions note. "Expired" is an active link whose end date has passed (computed, never stored). One live (proposed or active) link per student and adult. | 03 WF-ACL; 08 GuardianLink; build ruling: the pack's `verified` and `active` are one step here, since verification is the act that makes it active from its start date |
| S4B-02 | Links come from two places only: **enrollment** proposes one to the application's owner (adult from the application's guardian fields, login = owner); **staff** propose one on the student record (name, relationship, phone, email). Nothing else creates a link; matching phones or names never do. | 02 §5 "A shared phone number or surname cannot establish a guardian link" |
| S4B-03 | **Verify** (proposed → active) records authority basis (`parent`, `legal_guardian`, `court_order`, `student_consent`, `other`), method (`documents_in_person`, `documents_on_file`, `court_order`, `other`) and a reference ≤120, start date (default today), optional end date, and access flags. **Revoke** needs a reason; it takes effect immediately. Neither can be undone in place: a new link is proposed instead. | WF-ACL; "Invitation acceptance proves control of an account, not legal authority" |
| S4B-04 | **Access flags:** `record` (identity, number, enrollment — the only category with content today), `fees` and `messages` (stored now, used by Fees and Communication). Default on verify: `record` on, others off. Paying fees never implies record access. | 02 §5; walkthrough 7 "paying fees does not automatically authorize academic or communication access" |
| S4B-05 | **Adult students:** verifying a link for a student who is 18 or older on that day (date of birth known) requires basis `student_consent`; otherwise 422. A link whose student has turned 18 since it was verified is flagged "review: now an adult" on the guardians page; access continues until staff revoke or re-verify it (no silent change either way). | 02 §5 "do not automatically extend parental access"; "Turning 18 triggers a review … must not silently broaden access or delete records" |
| S4B-06 | **Family logins:** `Membership.Kind.GUARDIAN`. Verifying a link whose adult has a login turns that login's `applicant` membership into `guardian`; otherwise staff may create a login at verification (login ID and first password, forced change). Guardians keep the applicant pages (siblings). A login that is staff or student at this institution cannot be linked (409 `kind_conflict`). | Build ruling: one membership per institution and user (S2); a teacher with a child at the school uses a second login until shared identities arrive |
| S4B-07 | New permission `guardian_link.manage` (campus-scopable, follows the student's current campus): propose, verify, revoke, and read restriction notes and verification references. Given to Institution Admin and Registrar. `student.read` shows links (adult, relationship, status, flags, dates) without notes or evidence. | 02 §5 "Do not expose custody or safeguarding notes to ordinary teachers or other guardians" |
| S4B-08 | **Family portal** `/family` (kind guardian): **Your children** — children with an active, in-effect link; each shows number, name and current class only when `record` is on, else a neutral line. A child page `/family/children/:id` shows the same. Anything else is 404. Withdrawn children show "Left on <date>". Students module off → empty list with "Nothing is shared here yet". | SCR-035 (minimal); walkthrough 14 "Hide inaccessible categories without showing suggestive counts" |
| S4B-09 | **Withdrawal** (`student.update`, the student's campus): effective date today or earlier and not before the enrollment's entry date, reason required, optional clearance note. Ends the active enrollment (`exit_date`, `exit_reason`), sets the student `withdrawn` with `left_on`, revokes the student's membership and signs the student out. Fees and refunds are not touched (Fees, BUILD-08). **Reinstate** reverses the latest withdrawal when no later enrollment exists. | WF-ADM "Withdrawal after enrollment records effective date, academic consequences, clearance and fee/refund decision separately"; build ruling: no scheduled future withdrawals yet |
| S4B-10 | **Employee record:** `Employee` per staff membership — optional employee number (unique per institution), joined on, left on. Set on Add staff and on the staff page by whoever may manage that person (`membership.assign`, rank rule). Removing staff sets `left_on` to today if empty; restoring clears it. Leave, payroll and contracts are BUILD-10. | 08 Employee; BUILD-04 "employee records" |
| S4B-11 | **History:** the student record shows its audit entries (enrollment, corrections with from → to, links proposed/verified/revoked without their notes or evidence, withdrawal and reinstatement), newest first, paged, to `student.read` holders who can see the student. | Walkthrough 7 "audit shows changes without exposing restricted former values" |
| S4B-12 | **Possible duplicates:** the staff application view lists existing students at the institution with the same name (case and spacing ignored) and date of birth. A warning only: enrolling still makes a new Person. | 08 §4 "Duplicate detection assists review; it does not automatically merge" |

## 3. Data model

`students`: **GuardianLink** (`VersionedModel`: institution, student, adult → Person, user null (the adult's login),
relationship ≤40, status, access_record, access_fees, access_messages (booleans), starts_on null, ends_on null,
authority_basis, verification_method, verification_reference ≤120, restrictions ≤1000, source `enrollment`/`staff`,
proposed_by, verified_by, verified_at, revoked_by, revoked_at, revoke_reason ≤500; partial unique constraint on
(student, adult) where status in proposed/active). **Enrollment** gains `exit_date` null and `exit_reason` ≤500.
**Student** gains `left_on` null.

`accounts`: `Membership.Kind.GUARDIAN`. **Employee** (`VersionedModel`: institution, membership one-to-one,
employee_number ≤20 blank allowed, joined_on null, left_on null; unique (institution, employee_number) when not blank).

## 4. Rules (in addition to §2)

- **Enrollment** (4a) also creates the proposed link, in the same transaction, idempotently (a re-run finds it).
- **Verify** locks the link row; version-checked; refuses when the student is withdrawn (409) or the link is not
  proposed (409 `invalid_transition`). Creating a login validates login ID uniqueness and the password policy (422,
  nothing created).
- **Family queries** always filter by `user = request.user`, `status = active`, start ≤ today ≤ end (institution's
  day), and the institution of the host. The student id in a URL is never trusted on its own.
- **Revocation** of a guardian's last active link leaves the membership `guardian` (they keep applicant pages) — the
  portal is simply empty.
- **Withdrawal** locks the student row; version-checked; a second withdrawal is 409. Reinstate: only the latest ended
  enrollment, only if the student is withdrawn; restores the membership (a new first password is not needed: the old
  one works again).
- **Audit:** link proposed/verified/revoked, login created for a guardian, student withdrawn/reinstated, employee
  details changed.

## 5. API

Staff (`/api/v1/institution/students/<id>/`): `guardians` GET (links; notes and evidence only with
`guardian_link.manage`) / POST `{adult: {full_name, phone, email}, relationship}`; `guardians/<link>/verify` POST
`{version, authority_basis, verification_method, verification_reference, starts_on, ends_on, access: {record, fees,
messages}, restrictions, login: null | {username, password}}`; `guardians/<link>/revoke` POST `{version, reason}`;
`withdraw` POST `{version, effective_on, reason, clearance_note}`; `reinstate` POST `{version}`; `history` GET (paged).
Student list gains `status` filter use for withdrawn.

Staff list and detail (`/api/v1/institution/staff…`) carry `employee: {number, joined_on, left_on, version}`; PATCH
`staff/<id>` accepts `employee_number`, `joined_on`. Add staff accepts the same.

Applications (staff detail) gain `possible_duplicates: [{id, number, full_name}]`.

Family (`/api/v1/family/`, institution host, kind guardian): `children` GET → `[{id, full_name, shared: bool,
number?, status?, left_on?, enrollment?}]`; `children/<id>` GET → the same item or 404.

## 6. Screens

- **Student record**: a **Guardians** section (links with status badges, relationship, access, dates, "review: now an
  adult"), **Add guardian**, **Verify** and **Revoke** (each a focused form or dialog), a **History** section, and
  **Withdraw** / **Reinstate** in the header for `student.update`. Withdrawn records show "Left on …" and the reason.
- **Students directory**: status filter (Active, Withdrawn, All).
- **Application review**: "Possible duplicate of 2027-0001 Arjun Demo" warning with a link, when any.
- **Add staff** and **staff page**: Employee number and Joined on.
- **Family portal** `/family`: portal frame "Your children", child cards → child page; a link to **Applications**.
  Guardians signing in land here.

## 7. Tests that must exist

1. Links never appear from matching data: two applications with the same guardian phone produce links only through
   enrollment of each, each to its owner; a proposed link shows nothing in the family portal.
2. Verify → the child appears; revoke → 404 on the next request; a second live link for the same pair → 409; verify
   twice → 409; another institution's student or link id → 404.
3. Isolation: guardian A cannot see guardian B's child; family payloads never include restrictions, evidence or other
   guardians; `record` off → `shared: false` with no number or class.
4. Adult student: verifying for an 18-year-old without `student_consent` → 422; with it → active.
5. Kinds: an applicant becomes guardian on verification and still lists and opens their applications; linking a staff
   or student login → 409; a guardian cannot open `/app`, staff APIs or the student portal.
6. `guardian_link.manage` is needed to propose/verify/revoke and to read notes; `student.read` alone sees links
   without them; campus scope follows the student's current campus.
7. Withdrawal: future date → 422; before entry → 422; success ends the enrollment, sets `left_on`, and the student can
   no longer sign in (and an existing session is refused); withdrawing again → 409; stale version → 409; reinstate
   restores enrollment and sign-in.
8. Employee number unique per institution (blank allowed many times); only someone who may manage the person edits it.
9. History shows that student's changes only, without restricted values; another student's history is not reachable
   without scope.
10. Possible duplicates: same name (different case/spacing) and date of birth → listed; enrolling still makes a
    separate Person and Student.
11. Module gate: students off → family children empty, staff guardian/withdraw routes 404.

## 8. Left to the builder

Form layout (dialog vs page) for verify and withdraw, copy within the tone above, file layout inside `students` and
`accounts`.
