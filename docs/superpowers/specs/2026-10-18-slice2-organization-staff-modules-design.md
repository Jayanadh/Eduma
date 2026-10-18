# Eduma slice 2 — organization, staff roles, modules and the restricted state

**Date:** 18 October 2026 · **Status:** written from the spec pack at the user's request ("skip the questions, plan it
from the spec pack"); every call below not in the pack is marked as a build ruling.
**Source pack:** `Eduma_All_Specifications.md` — 01 §6–7 (capability matrix, configuration boundaries), 02 §2–4, §7, §9
(authorization, role templates, action matrix, delegation, denial cases), 03 WF-ONB and WF-ACL, 04 SCR-009/011/012/014/
015, 05 walkthroughs 3, 5 and 6, 08 §3 (Campus/Department, Membership, RoleDefinition/PermissionGrant,
InstitutionEntitlement), 13 BUILD-03.
**Builds on:** slice 1 (`2026-10-17-foundation-onboarding-branding-design.md`) and its rulings in `docs/progress.md`,
plus the 18 Oct changes (S1-07 branding is the Institution Admin's; S1-11 five rows a page; S1-12 own domains; S1-13
dropdowns).

## 1. What this slice is for

After slice 1 an institution has exactly one person in it: its Institution Admin. That admin can brand the page and
nothing else. This slice lets the admin **bring the institution's staff in with the right authority**, which every later
module (admissions, academics, fees) depends on:

- describe the institution's **campuses and departments**;
- add **staff logins** and give each person **roles scoped** to the whole institution, a campus or a department, with
  start and end dates;
- use **built-in roles** (Principal, Teacher, Campus Admin…) or make **custom roles** from a permission list, never
  beyond the editor's own authority;
- let the platform record which **modules** each institution's plan includes;
- add the **`restricted`** lifecycle state (read-only for members).

**Success:** at Aster, the Institution Admin adds a City campus and a Science department, creates a Campus Admin for
City and a Teacher in Science. The Campus Admin signs in, sees only City's staff, can add a teacher at City, and is
refused when trying to make anyone an Institution Admin, to touch Science staff outside City, or to change their own
roles. Removing a role takes effect on the person's very next request. The platform restricts Aster; Aster's staff can
still sign in and look but every change is refused with the reason shown.

**Anti-goals (failure even if it "works"):**
- a role name checked in code instead of a permission (02 §3);
- anyone able to grant more than they hold, change their own roles, or remove the last Institution Admin (02 §7);
- a menu hidden in the browser but the API still allowing it (02 §2);
- module menus or pages for modules that are not built (01 §3, 04 §3: "Do not show unimplemented modules as working
  features");
- the platform admin browsing an institution's staff (02 §3: System Admin has no routine institution record browsing).

## 2. Decisions for this slice

| ID | Decision | Pack reference / why |
|---|---|---|
| S2-01 | `Membership.role` is replaced by **role assignments**: a membership has any number of assignments, each naming a role, a scope (whole institution, a campus or a department), `starts_on`, optional `ends_on`, and a status (active/ended). Ended assignments stay as history. Existing memberships migrate to an Institution Admin assignment for the whole institution. | 08 §3 Membership ("role assignments separately repeatable"), RoleDefinition/PermissionGrant |
| S2-02 | **Built-in roles are defined in code** (key, label, description, permissions) and are the same for every institution; they gain permissions as later modules are built. **Custom roles** are rows per institution (name, description, permissions, active/archived, version). | 02 §3 "Templates are editable within protected platform boundaries. Institutions create named roles from allowed permissions". Build ruling: templates live in code, not per-institution copies. |
| S2-03 | **Permissions are a registry in code** (`accounts/permissions.py`): name, group, label, description, and whether it applies only to the whole institution. Only permissions for features that exist are registered; each later slice adds its own. | 02 §4 canonical `<resource>.<action>` names; 04 §3 no fake modules |
| S2-04 | `institution.read` (see the institution's home, details and modules) comes with **membership itself**, not with a role, so every active member can open the workspace. | Build ruling: a signed-in member with no role still needs a home that explains that. |
| S2-05 | New staff logins use a **first password with a forced change**, as for Institution Admins. A login ID is global and must be new; this slice never attaches an existing login to another institution. | S1-06. Build ruling: attaching existing logins would let one institution's admin reset a password another institution relies on. |
| S2-06 | **Grant ceiling** (exact rule in §4.3): you may give or end a role at a scope only if you hold `membership.assign` there and every permission in that role there. You may act on a person (password, details, removal) only if you could have given every role they hold. Nobody changes their own roles, password-by-reset, or membership through these screens. | 02 §4 `role.manage`/`membership.assign` "grant ceiling"; 02 §7; 02 §9 |
| S2-07 | The **last open-ended Institution Admin** cannot be ended, removed or switched off; the API answers 409 `last_admin`. | 02 §7, WF-ACL |
| S2-08 | Role and assignment changes **take effect immediately** and are audited with before/after values; there is no approval step yet. The role editor shows a before/after preview and how many people it affects. | 02 §4 role editor preview. Build ruling: approval routing arrives with the configuration engine (S2-12). |
| S2-09 | **Modules**: a catalogue in code (`institutions/modules.py`). The platform records which modules an institution's plan includes as `Institution.modules` (a list of keys), edited like any other institution field (versioned, audited diff). New institutions get the catalogue's defaults for their category. Dependencies are enforced. No module is built yet, so every module shows "Arrives in a later release" and no institution-side on/off switch exists yet. | 01 §6–7, 08 §3 InstitutionEntitlement, 04 §3. Build ruling: entitlement limits and effective dates, and institution-side enablement, arrive with the first built module (admissions). |
| S2-10 | **`restricted`** lifecycle state: members can sign in and read; every change they attempt on the institution host is refused (403 `institution_restricted`) except signing in/out and changing their own password. The public page stays up. Moves: active → restricted, restricted → active (needs an active Institution Admin, like reactivation), restricted → suspended, restricted → archived. | 03 WF-ONB transitions; S1-09 deferred it to this slice. Build ruling: "named restricted capabilities" are, for now, one capability: all changes. |
| S2-11 | Every institution gets a **Main campus** (code `MAIN`) when it is created; existing institutions get one by migration. Departments may be nested; a child department belongs to its parent's campus. | 01 WF-ONB step 1 ("primary campus"), 08 §3 Campus/Department |
| S2-12 | **Deferred, with reasons:** typed configuration revisions with impact preview (built with their first real consumer — admission forms and the academic calendar — so the engine is shaped by a real rule, not guessed); groups and affiliation grants (need a university exchange to be meaningful; with the university academic slice); guardian/relationship grants (with student records, BUILD-04); invitations and recovery (S1-06); support access grants (BUILD-12); maker/checker approval of role changes (with the configuration engine). | 13 BUILD-03 lists these; this slice delivers the parts that are usable today. |
| S2-13 | `organization.manage` is a new permission name for campuses and departments (02's matrix has no entry for them; `academic_structure.manage` is for programs and curricula and is left for the academic slice). `membership.read` is new for seeing staff and their roles, which `membership.assign` alone does not cover for read-only people such as a Principal. | 02 §4 has no matching names. |

## 3. Data model

All new models use `VersionedModel` (UUID id, timestamps, integer `version`) unless stated. All are institution-owned.

**Campus** — `institution`, `code` (2–20 chars, letters, digits and dashes, stored uppercase), `name` (≤120), `address`
(blank allowed), `is_active`. Unique `(institution, code)`. Ordered active first, then name.

**Department** — `institution`, `code` (same rule), `name` (≤120), `campus` (nullable FK, same institution), `parent`
(nullable FK to Department, same institution), `is_active`. Unique `(institution, code)`. With a parent, `campus` is
always the parent's campus (set by the server, not editable). No cycles. Ordered active first, then name.

**CustomRole** — `institution`, `name` (≤60, unique among the institution's active custom roles, compared
case-insensitively), `description` (≤300, blank allowed), `permissions` (Postgres `ArrayField` of registry names, stored
sorted and de-duplicated), `is_active` (archived when false), `created_by`.

**RoleAssignment** — `membership`, `institution` (denormalised from membership, for queries and audit), exactly one of
`role_key` (a built-in role key) or `custom_role` (FK), `scope_type` (`institution` | `campus` | `department`), `campus`
(FK, set iff scope_type is campus), `department` (FK, set iff department), `starts_on` (date, default today in the
institution's time zone), `ends_on` (nullable date, ≥ starts_on), `status` (`active` | `ended`), `created_by`,
`ended_by`, `ended_at`, `end_reason` (≤300). A database check constraint enforces the role and scope exclusivity.

An assignment is **in effect** when `status = active`, `starts_on ≤ today` and (`ends_on` is null or `ends_on ≥ today`),
where today is in the institution's time zone.

**Membership** — loses `role`. Gains nothing else (status active/revoked stays; revoking ends all its assignments with
reason "Removed from staff").

**Institution** — gains `modules` (`ArrayField` of module keys, default empty; filled from category defaults on create
and by data migration).

**Migrations:** (1) add the new tables and `Institution.modules`; (2) data: one in-effect Institution Admin assignment
(scope institution, `starts_on` = membership's creation date) per existing membership, a `MAIN`/"Main campus" per
institution, category default modules per institution; (3) drop `Membership.role`.

## 4. Authorization

### 4.1 Permission registry (this slice)

| Permission | Group | Label shown in the role editor | Whole institution only |
|---|---|---|---|
| `institution_profile.update` | Institution | Edit the institution's contact details | yes |
| `institution_brand.update` | Institution | Edit the logo, colours and public page | yes |
| `organization.manage` | Organization | Add and change campuses and departments | yes |
| `membership.read` | Staff | See staff and their roles | no |
| `membership.assign` | Staff | Add staff, give and end roles, reset staff passwords and remove staff | no |
| `role.manage` | Staff | Create and change custom roles | yes |

`institution.read` is implicit for every active member (S2-04) and is not in the editor.

### 4.2 Built-in roles

| Key | Label | Permissions now | Typical scope |
|---|---|---|---|
| `institution_admin` | Institution Admin | all six | whole institution (only) |
| `campus_admin` | Campus Admin | `membership.read`, `membership.assign` | a campus |
| `principal` | Principal / Director | `membership.read` | whole institution or a campus |
| `head_of_department` | Head of Department | `membership.read` | a department |
| `registrar` | Registrar | — | any |
| `teacher` | Teacher / Faculty | — | any |
| `admissions_officer` | Admissions Officer | — | any |
| `accountant` | Accountant / Cashier | — | any |
| `exam_officer` | Examination Officer | — | any |

Each built-in role's description says what it can do **today** and that more comes with each module ("Signs in and sees
the institution's home. Admissions permissions arrive with the Admissions module."). A role containing any
whole-institution-only permission can be given only at whole-institution scope (so Institution Admin is institution-wide
only); the API refuses otherwise with a field error naming those permissions.

### 4.3 The rules, exactly

- **Scope coverage.** A whole-institution scope covers everything. A campus scope covers that campus and every department
  whose `campus` is it. A department scope covers that department and its descendants. A department with no campus is
  covered only by whole-institution scope or by an ancestor department.
- **has_perm(user, institution, perm, scope=None).** True iff the user's membership in the institution is active and some
  in-effect assignment's role holds `perm` and its scope covers `scope` (None means "the whole institution", so only a
  whole-institution assignment satisfies it). `institution.read` is true for any active member. Built-in role
  permissions come from code; custom role permissions from the row (archived roles grant nothing).
- **can_assign(actor, role, scope).** True iff `has_perm(actor, membership.assign, scope)` and, for every permission p of
  the role, `has_perm(actor, p, scope)`. This one rule is the grant ceiling: only someone holding every Institution Admin
  permission institution-wide can create another Institution Admin.
- **can_manage_person(actor, target membership).** True iff the target is not the actor, and either the actor holds
  `membership.assign` for the whole institution and `can_assign` holds for each of the target's in-effect and future assignments,
  or the target has at least one in-effect or future assignment and `can_assign` holds for every one of them (a role
  starting later counts now, so a reset today cannot hand over tomorrow's authority; corrected after final review). (So a Campus Admin
  can reset a City teacher's password but not that of someone who is also a Science teacher outside City, nor of a
  Principal.)
- **Visibility of staff** (`membership.read`): a whole-institution holder sees every membership, including people with
  no role and removed people; otherwise you see memberships with at least one in-effect or future assignment covered by one of
  your `membership.read` scopes. Anything else is 404, never 403, so existence does not leak (02 §2).
- **Custom roles** (`role.manage`, whole institution): a role's permissions must be registry names (unknown names are a
  field error) and a subset of the editor's whole-institution permissions; an edit is refused if the role currently
  holds a permission the editor lacks. Adding a whole-institution-only permission to a role that is given at a campus or
  department scope is refused, naming how many such assignments exist. Archiving is refused while the role has
  in-effect or future assignments.
- **Last admin** (S2-07): ending an `institution_admin` assignment or removing its membership is refused if no other
  in-effect, open-ended `institution_admin` assignment of an active membership and active user would remain.
  Assignments are never edited (end one and give another), so an end date can only be set when a role is given.
- **Self:** the staff and assignment endpoints refuse to act on the caller's own membership (403
  `own_membership`), with a message pointing to their profile page for their own details and password.
- **Restricted** (S2-10): a middleware after `SiteMiddleware` answers any non-safe method on an institution host whose
  institution is `restricted` with 403 problem `institution_restricted` ("<name> is read-only for now: <reason>"), except
  `/api/v1/session/login`, `/logout` and `/change-password`.

### 4.4 Existing code that changes

- `accounts.permissions.ROLE_PERMISSIONS` and `Role` go; `has_perm` becomes scope-aware; `member_with(perm)` keeps
  working (whole-institution check).
- `institutions.services._admins`/`first_admin`/readiness use in-effect `institution_admin` assignments.
- `MeSerializer.membership` becomes `{ roles: [{label, scope_label}], permissions: [...], restricted: bool,
  status_reason: str }`, where permissions are those held at any scope plus `institution.read` (for menus only; the
  server checks scope on every call).
- `SIGN_IN_STATES` gains `restricted`; the public page treats `restricted` like `active`.
- `testing.factories.member(institution, role="institution_admin", scope=None, **kw)` creates the membership and one
  assignment.

## 5. API (institution host, under `/api/v1/institution/`)

Every list is paged (5 a page, `?page=`, `?page_size=` up to 200 for pickers) and searchable with `?search=` (ignored
under 3 characters). Every change takes `version` and answers 409 `version_conflict` when stale. Every change writes an
audit event (`campus.*`, `department.*`, `role.*`, `staff.*`, `assignment.*`).

| Route | Methods | Permission | Notes |
|---|---|---|---|
| `campuses` | GET, POST | read: member; write: `organization.manage` | `?active=1` for pickers |
| `campuses/<id>` | GET, PATCH | same | PATCH `is_active=false` refused (409 `in_use`) while the campus has active departments or in-effect/future assignments, or is the last active campus |
| `departments` | GET, POST | same | `?campus=<id>`, `?active=1` |
| `departments/<id>` | GET, PATCH | same | deactivation refused while it has active children or assignments; parent changes re-check cycles |
| `permissions` | GET | `role.manage` or `membership.read` | the registry, grouped |
| `roles` | GET, POST | GET: `membership.read` or `role.manage` or `membership.assign`; POST: `role.manage` | GET lists built-in then custom roles, each with permissions and `assigned_count` (in-effect and future); `?assignable=1` returns only roles the caller could give somewhere (pickers) |
| `roles/<id>` | GET, PATCH | `role.manage` | custom roles only; PATCH name/description/permissions/is_active |
| `staff` | GET, POST | GET: `membership.read`; POST: `membership.assign` | POST creates login + membership + first assignment atomically (full_name, username, email, mobile, password, role, scope) |
| `staff/<membership id>` | GET, PATCH | GET: visible; PATCH: `can_manage_person` | detail with assignments (in effect, future, ended); PATCH full_name/email/mobile |
| `staff/<id>/assignments` | POST | `can_assign` | role, scope_type, campus, department, starts_on, ends_on |
| `staff/<id>/assignments/<aid>/end` | POST | `can_assign` for that assignment | reason required |
| `staff/<id>/password` | POST | `can_manage_person` | first password; forces change; Django validators |
| `staff/<id>/remove` | POST | `can_manage_person` | reason required; ends assignments; sessions end on next request |
| `staff/<id>/restore` | POST | `membership.assign` whole institution | back to active with no roles |

Platform side: `GET /api/v1/platform/modules` (catalogue), `modules` accepted on create and PATCH of
`/api/v1/platform/institutions/<id>`; lifecycle transition accepts `restricted`.

## 6. Modules catalogue

| Key | Label | Depends on | Default for |
|---|---|---|---|
| `admissions` | Admissions and enrollment | `students` | all |
| `students` | Students and guardians | — | all |
| `academics` | Academic structure and timetable | — | all |
| `attendance` | Attendance | `academics` | all |
| `exams` | Assessment and results | `academics` | all |
| `report_cards` | Grades, sections, report cards and promotion | `exams` | school |
| `course_registration` | Course registration, credits and degree audit | `academics` | college, engineering college, university |
| `outcomes` | Lab batches, projects and outcome evidence | `exams` | engineering college, university |
| `affiliations` | Affiliated colleges and central examinations | `exams` | university |
| `fees` | Fees | `students` | all |
| `communication` | Messages, calls and online classes | `students` | all |
| `reports` | Reports | — | all |
| `library`, `transport`, `hostel`, `hr_payroll`, `assets`, `services`, `placements`, `quality` | Library; Transport; Hostel and mess; HR and payroll; Assets, purchasing and labs; Student services and cases; Placements, internships and alumni; Quality, accreditation and research | — | none (applicable, 01 §6) |

Validation: unknown keys refused; a module whose dependency is missing is refused naming it ("Attendance needs Academic
structure and timetable."). Each entry has `available: false` until its slice ships.

## 7. Screens

### Institution workspace (`/app`, institution host)

Menu, shown by permission (≤6 entries, 04 §1): **Home**; **Staff** (`membership.read`); **Roles** (`role.manage`);
**Organization** (`organization.manage`); **Public site** (`institution_brand.update`); **Profile**. Routes check the same
permission (guard → home); the API is the real check.

- **Home** keeps the setup checklist (admins) and adds "Modules in your plan": each module with "Arrives in a later
  release". A member with no role sees "You have no role here yet. Ask your Institution Admin." The sidebar footer shows
  the first role label (or "Staff") instead of the fixed "Institution Admin".
- **Restricted banner** in the shell for every member: "Read-only for now: <reason>. You can look around, but changes are
  paused." (warning tone, text + colour).
- **Organization** (SCR-015, campuses part): two sections, Campuses and Departments, each a paged searchable list
  (code, name, campus/parent, status) with **Add** and **Edit** in a form panel; deactivate/reactivate from the form.
  Department form: parent picker (active departments, excluding itself and its descendants), campus picker hidden when
  a parent is chosen.
- **Staff** (SCR-014): paged list searchable by name or login ID with each person's roles as chips ("Teacher · Science");
  **Add staff** form (name, login ID suggested from the name, email, mobile, first password, role, scope). Detail page:
  details form; **Roles** list (in effect / starts later / ended, with scope and dates) with **Give a role** (role picker
  limited to assignable roles, scope picker, dates) and **End** (reason prompt); **Reset password**; **Remove from staff**
  / **Restore**. Actions the caller cannot take are hidden; a refusal from the server still shows its message.
- **Roles**: built-in roles (read-only cards: label, description, permissions, how many people) and custom roles (same,
  plus Edit/Archive); **New role** and the role editor: name, description, permission checkboxes grouped with their
  descriptions (permissions the editor lacks are disabled with "You don't have this"), and a live preview: "Adds: …
  Removes: … Affects N people." Save sends `version`.

### Console (platform host)

- **Onboarding wizard** gains a **Modules** step after Web address: checkboxes grouped Core / Operations, pre-ticked with
  the category's defaults (re-applied when the category changes, until the admin touches the list); ticking a module
  ticks its dependencies; unticking one unticks modules that need it. Review lists the chosen modules.
- **Institution page** gains a **Modules** tab with the same checkbox list and Save (version-checked; server errors shown).
- **Lifecycle**: Active shows Restrict / Suspend / Archive; Restricted shows Lift restriction / Suspend / Archive. The
  restrict prompt says what members will experience. Status badge `restricted` ("Restricted", warning tone). Overview
  and the directory filter gain the state.

## 8. Demo data (`seed_demo`, idempotent)

Aster: campuses `MAIN` Main campus and `CITY` City campus; departments `SCI` Science (Main) with child `PHY` Physics, and
`LANG` Languages; staff `aster.principal` (Principal, whole institution), `aster.campus` (Campus Admin, City),
`aster.teacher` (Teacher, Science); custom role "Front office" (`membership.read`) given to `aster.office` at City. All
demo staff use `Demo-pass-2026` and have already changed it. Every demo institution gets its category's default modules.

## 9. Tests that must exist (beyond unit tests of each rule)

Mandatory denial cases from 02 §9 that apply now, each as an API test:
1. A member of A cannot read or change B's campuses, staff or roles by ID on A's host (404), nor on B's host (403/404).
2. Stale role: after an assignment is ended, the person's next request with that permission is refused.
3. Escalation through custom role data: unknown permission names, and permissions the editor lacks, are refused.
4. Self-escalation: nobody can give themselves a role, end their own, or reset their own password through staff routes.
5. Campus Admin cannot give Institution Admin, cannot act outside their campus, cannot see staff outside it (404).
6. Last Institution Admin cannot be ended, removed, or given an end date.
7. Restricted: every write by a member is refused with `institution_restricted`; sign-in, sign-out and own password
   change still work; lifting the restriction restores writes.
8. Assignment dates: a future assignment grants nothing until its start date; an expired one grants nothing.
9. The platform admin cannot reach any institution staff/role/organization route (404 on the platform host).

Frontend: unit tests for the module tick/untick helper, menu-by-permission, the role editor preview diff and the staff
action visibility helper. Browser check of every new screen at 1280 px and 390 px.

## 10. Left to the builder

File layout within the existing apps (a new `organization` app for Campus/Department is fine; roles and assignments
belong in `accounts`), exact copy wording within the tone above, component structure, and the order of tasks, provided
each commit builds and passes its tests.
