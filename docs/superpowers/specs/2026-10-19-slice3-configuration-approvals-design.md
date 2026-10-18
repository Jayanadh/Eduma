# Eduma slice 3 — configuration engine, module enablement and approvals (finishing BUILD-03)

**Date:** 19 October 2026 · **Status:** written from the spec pack at the user's request ("finish what you left and then
start this"); build rulings are marked.
**Source pack:** `Eduma_All_Specifications.md` — 01 §7 (configuration boundaries), 02 §4 (`configuration.edit` /
`configuration.publish`), 03 WF-ACL ("approve sensitive changes") and WF-CFG (draft → validated → approved → published
→ superseded, effective intervals, rollback), 04 SCR-013, 05 walkthrough 5, 08 §3 (SettingDefinition/SettingRevision),
09 §6 (typed settings, precedence, approval, immutable revisions), 11 TST-008, D-15.
**Builds on:** slices 1–2 (`docs/progress.md`), and S2-12, which deferred these parts of BUILD-03.

## 1. What this slice is for

Institutions need to change how Eduma behaves for them without code and without rewriting history: switch on the
modules their plan includes, decide that powerful staff roles need a second person's approval, set when their academic
year starts. Every such change is a **versioned setting**: drafted, checked, previewed, approved where it matters,
published from a chosen day, and replaceable later without erasing what was in force before. The admissions slice next
reads the academic year and module switches from here.

**Success:** at Aster, the Institution Admin drafts "academic year starts in April", sees "The 2026–27 year runs 1 Apr
2026 – 31 Mar 2027", schedules it from 1 Apr 2027 and today's value is unchanged. They turn on Admissions and Students
(both in Aster's plan) and the home page shows them as switched on. With a second Institution Admin in place, they
publish "role changes need approval"; the City Campus Admin then gives someone the Campus Admin role and it waits,
granting nothing, until an Institution Admin who is not the requester approves it.

**Anti-goals:** a setting change that silently alters what was in force on an earlier day; one person both requesting
and approving a change that needs approval; a module switched on that the plan does not include; free text or code as a
"rule".

## 2. Decisions

| ID | Decision | Pack reference / why |
|---|---|---|
| S3-01 | **Settings are defined in code** (key, label, help, type, default, whether publishing needs approval, validation, a human description of a value and a preview of a change). Institutions hold **revisions**. Only settings with a consumer are registered; later slices add theirs. | 09 §6 "registered typed definitions"; D-15 |
| S3-02 | A revision moves **draft → pending (approval) → published → superseded**, or back from pending to draft ("returned"), or draft → withdrawn. One open revision (draft or pending) per setting at a time. Published revisions are never edited. | WF-CFG; build ruling: "validated" is not a stored state — validation runs on every save and again on publish |
| S3-03 | **Effective dating**: publishing chooses `effective_from` (today or later, never earlier). The value in force on a day is the latest published revision whose `effective_from` is on or before that day. Publishing a revision cancels (supersedes) any published revision scheduled on or after its own start day that has not taken effect. Rollback restores an older revision's value into a new draft; nothing is erased. | WF-CFG "prevent overlapping incompatible intervals", "rollback publishes a safe replacement" |
| S3-04 | **Approval** (maker ≠ checker): a setting marked `needs_approval` goes to pending on submit; another person holding `configuration.publish` approves (it publishes) or returns it with a note. The submitter can never approve their own. If nobody else holds `configuration.publish`, submitting is refused with that reason. | 02 §4 "publication authority separated for high-impact rules" |
| S3-05 | New permissions `configuration.edit` (draft, submit, withdraw, restore into a draft) and `configuration.publish` (publish without approval, approve, return), both whole-institution only, both given to Institution Admin. | 02 §4 action matrix |
| S3-06 | First three settings: **`modules.enabled`** (which of the plan's modules are switched on; may only contain entitled modules whose dependencies are also on), **`access.role_approval`** (whether powerful roles need a second person's approval; needs approval itself; cannot be turned on unless at least two people hold `membership.assign` for the whole institution), **`academic.year_start`** (month 1–12; default June for schools, July otherwise). | 01 §7 "Institution Admin enables entitled modules"; WF-ACL; SCR-012 academic period |
| S3-07 | The modules in force for an institution are its **entitlement ∩ enabled setting**: if the platform removes a module from the plan, it is off whatever the setting says. Still none is built, so "on" changes the home page's labels only; the admissions slice uses it first. | 01 §7 "intersection of … entitlement, institution enablement" |
| S3-08 | **Role-change approval** (consumer of `access.role_approval`): while it is in force, giving a **powerful role** — one holding any permission other than `membership.read` — creates the assignment as `pending`. Pending grants nothing. Someone else who could give that role at that scope approves it (it becomes active, starting on its own `starts_on` or today if that has passed) or rejects it with a reason (it becomes ended). The requester cannot approve. Adding staff with a powerful first role works the same way: the login is created, the role waits. | WF-ACL "validate → preview → approve sensitive changes → publish" |
| S3-09 | **Campus overrides** of settings are not built: none of the first three settings is allowed to differ by campus. The revision model keeps a `campus` column (null) so overrides can arrive with the first setting that needs them. | 09 §6 precedence; build ruling (YAGNI) |
| S3-10 | **Workspace menu grouped** to stay within six top-level entries (04 §1): Home; People (Staff, Roles); Administration (Organization, Settings, Public site, Profile). | 04 §1–2 |
| S3-11 | **Not in this slice, with reasons:** support access grants (SCR-010, read-only time-bound access for Eduma support) go to BUILD-11 with platform operations, where support cases live; groups and university affiliation grants go to BUILD-05 (pack: "Add university affiliation grants and scoped academic exchange"); guardian relationship grants go to BUILD-04 with student records; invitations and password recovery wait for the email/SMS provider decision (D-12) and S1-06 chose first passwords. | 13 BUILD-03/05/11 |

## 3. Data model

**SettingRevision** (`VersionedModel`, new app `configuration`): `institution`, `campus` (null; S3-09), `key`, `number`
(per institution+key, from 1), `value` (JSON), `status` (`draft`, `pending`, `published`, `superseded`, `withdrawn`),
`effective_from` (date, set on submit), `reason` (≤300, the change's why, required on submit), `return_note` (≤300),
`created_by`, `submitted_by`, `submitted_at`, `approved_by`, `published_at`. Partial unique constraint: one row per
(institution, key) whose status is draft or pending. Ordered by `-number`.

**RoleAssignment** gains status `pending` and `requested_by` is `created_by`; `decided_by`, `decided_at` record the
approval or rejection (rejection also sets `status=ended`, `end_reason`, `ended_by`, `ended_at`).

No platform-level setting rows: defaults live in the registry.

## 4. Rules

- **Value in force** `setting(institution, key, on=today) -> value`: latest `published` revision with
  `effective_from <= on` (by `effective_from`, then `number`); none → the definition's default (which may depend on the
  institution's category). For `modules.enabled` the value is then intersected with `institution.modules`.
- **Saving a draft** validates the value (type and the setting's own rule) → 422 on `value`. Version-checked.
- **Submit** `{version, effective_from, reason}`: `effective_from >= today` (institution's day) else 422; validates
  again; needs_approval → `pending` (refused 409 `no_approver` when nobody else holds `configuration.publish`), else
  publish now (needs `configuration.publish`; an editor without it gets 403 "Ask someone who can publish settings").
- **Publish** (on submit or on approval): status `published`, `published_at`; every other `published` revision of the
  key with `effective_from >= this.effective_from` and `effective_from > today` — or equal to this one's start day —
  becomes `superseded`.
- **Approve** (configuration.publish, not the submitter): validates again (the world may have changed), publishes.
  **Return** `{note}`: back to `draft` with `return_note`.
- **Withdraw** a draft or own pending revision: `withdrawn`.
- **Restore** an older revision: its value goes into the draft (created if none), version-checked like slice 1's site
  restore.
- All writes lock the institution row; all are audited (`setting.drafted` is not audited; `setting.submitted`,
  `setting.published`, `setting.approved`, `setting.returned`, `setting.withdrawn`, `setting.restored` are, with
  from/to descriptions).

### Setting rules

| Key | Type | Default | Rule | Preview of a change |
|---|---|---|---|---|
| `modules.enabled` | list of module keys | `[]` | each key in the institution's plan; each enabled module's dependencies enabled too ("Attendance needs Academic structure and timetable switched on.") | "Switches on: …", "Switches off: …" |
| `access.role_approval` | boolean | `false` | turning on requires ≥2 active people with whole-institution `membership.assign` | on: "From <date>, giving powerful roles (any that can change the institution or its staff) waits for a second person's approval." off: "From <date>, roles take effect when given. Requests already waiting still need a decision." |
| `academic.year_start` | month 1–12 | 6 for school, 7 otherwise | 1–12 | "The <yyyy–yy> year runs <d Mon yyyy> – <d Mon yyyy>." for the year containing the effective date |

### Role-change approval

- "Powerful" = `role.permissions - {"membership.read"}` is not empty.
- `give_role`/`create_staff`: if `setting(inst, "access.role_approval")` is true today and the role is powerful →
  assignment `status="pending"`; audit `assignment.requested`.
- `approve(actor, assignment)`: actor ≠ requester, `can_assign(actor, role perms, scope)`, assignment pending →
  `status="active"`, `starts_on = max(starts_on, today)`, `decided_by/at`; audit `assignment.approved`. Last-admin and
  other rules unchanged.
- `reject(actor, assignment, reason)`: same authority → ended with reason; audit `assignment.rejected`.
- `remove` of a person ends their pending requests too.
- **Approvals list** `GET institution/approvals`: pending role requests the caller could approve (not their own) and
  pending setting revisions (when they hold `configuration.publish` and are not the submitter).

## 5. API (institution host, `/api/v1/institution/`)

| Route | Method | Permission |
|---|---|---|
| `settings` | GET | `configuration.edit` or `configuration.publish` — each definition with `value_now`, `description_now`, `scheduled` (the next published change, if any), `open` (draft/pending summary) |
| `settings/<key>` | GET | same — plus `draft`/`pending` revision, `preview` lines for the open revision, history (published/superseded/withdrawn, paged 5) |
| `settings/<key>/draft` | POST (create from value in force, or return the open draft), PUT `{version, value}` | `configuration.edit` |
| `settings/<key>/draft/submit` | POST `{version, effective_from, reason}` | `configuration.edit` (+ publish rule above) |
| `settings/<key>/draft/withdraw` | POST `{version}` | `configuration.edit` |
| `settings/<key>/revisions/<id>/approve` | POST `{version}` | `configuration.publish`, not the submitter |
| `settings/<key>/revisions/<id>/return` | POST `{version, note}` | same |
| `settings/<key>/revisions/<id>/restore` | POST `{version}` (the open draft's, or null) | `configuration.edit` |
| `staff/<id>/assignments/<aid>/approve` | POST | approver rules §4 |
| `staff/<id>/assignments/<aid>/reject` | POST `{reason}` | same |
| `approvals` | GET | any member (empty for most) |

`GET institution` gains `modules_enabled` (modules in force) and `academic_year` `{label, starts_on, ends_on}` for today.
Unknown setting keys → 404.

## 6. Screens

- **Menu** (S3-10): Home · **People**: Staff, Roles · **Administration**: Organization, Settings, Public site, Profile.
  Group headings show only when they have an item.
- **Settings** `/app/settings` (SCR-013): one card per setting — label, value in force described in words, "Changes on
  <date> to …" when scheduled, a badge for "Draft" or "Waiting for approval"; **Change** opens the editor.
- **Setting editor** `/app/settings/:key`: what is in force now; the typed control (switch, month select, module
  checkboxes limited to the plan, using the module picker's tick/untick); saving the draft shows the server's preview
  lines; "Starts on" date (today by default), "Why" (required); **Publish** or **Send for approval** (by the setting's
  rule); when pending: who sent it and when, and for other publishers **Approve** / **Return with a note**; the
  submitter sees "Waiting for approval" and **Withdraw**; **History** (paged): each revision's value, dates, who, status,
  **Restore into a draft**.
- **Home**: "Waiting for your approval" card listing the approvals list with links; modules show "Switched on" /
  "Not switched on" with "arrives in a later release"; the academic year line.
- **Staff detail**: pending roles in their own group "Waiting for approval" with **Approve** / **Reject** for those who
  may, and "Requested by … " for others.

## 7. Tests that must exist

1. TST-008 shape: a change scheduled for a future day leaves today's value unchanged; on that day (frozen clock) the new
   value is in force; the earlier revision stays in history unchanged.
2. A later publish cancels a not-yet-effective scheduled revision; a past one stays as history.
3. Maker ≠ checker: the submitter cannot approve; approval by another publisher publishes; return sends it back to draft
   with the note; `no_approver` when nobody else can publish.
4. Modules: enabling an unentitled module → 422; dependency missing → 422; platform removing a module turns it off in
   force without touching the setting.
5. Role approval: cannot be switched on with one whole-institution assigner; while on, a powerful role given by a Campus
   Admin is pending and grants nothing; the requester cannot approve; an Institution Admin approves → in force; reject
   ends it with the reason; a non-powerful role (teacher) is not held for approval.
6. Version conflicts on draft save, submit, approve and restore; another institution's revision id → 404; the platform
   host → 404 on every route.

## 8. Left to the builder

File layout inside the new `configuration` app; exact copy within the tone above; how the editor lays out on phones.
