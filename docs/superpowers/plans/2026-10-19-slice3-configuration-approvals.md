# Eduma Slice 3 (configuration engine, module enablement, approvals) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Versioned, effective-dated institution settings with preview, maker/checker approval and rollback; the first
three settings (module switches, role-change approval, academic year start) and the role-approval flow they drive.

**Architecture:**
- A new `configuration` app: a code registry of setting definitions, `SettingRevision` rows per institution, and one
  function `setting(institution, key, on)` that every consumer asks.
- Role-change approval reuses `RoleAssignment` with a new `pending` status; approval follows the existing grant ceiling.
- Angular: grouped menu, Settings list and editor, approvals on Home and the staff page.

**Tech Stack:** as slices 1–2 (Django 6.1 + DRF 3.18, PostgreSQL 17, pytest; Angular 22, Vitest).

**Spec:** `docs/superpowers/specs/2026-10-19-slice3-configuration-approvals-design.md` (sections below refer to it).

## Global Constraints

- Slice 1–2 Global Constraints hold (ports, problem JSON with `code`, `version` + 409 `version_conflict`, UUID keys,
  5 rows a page, search from 3 characters, no invented numbers, 44 px controls, text + colour statuses, no push, no
  `Co-Authored-By`).
- Backend style check: `ruff check --select F,E,W,I --line-length 120 --exclude '.venv,*/migrations' .` and
  `ruff format --check` with the same options.
- Setting keys exactly: `modules.enabled`, `access.role_approval`, `academic.year_start`.
- Permission names exactly: `configuration.edit`, `configuration.publish` (both `institution_only=True`, group
  "Settings").
- Revision statuses exactly: `draft`, `pending`, `published`, `superseded`, `withdrawn`. Assignment status adds `pending`.
- Problem codes: `no_approver` (409), `own_request` (403, a submitter/requester approving their own).
- "Today" is `accounts.permissions.today_for(institution)`.

## Review Focus

1. Submitting with `effective_from` before today, or not a date → 422 on `effective_from` (Task 2).
2. Approving after the world changed (a module removed from the plan between submit and approve) → 422, nothing
   published (Task 2).
3. Two "create draft" calls for the same setting → one open revision; the second gets the same draft back (Task 3).
4. `access.role_approval` turned off while requests wait → they stay pending and can still be approved (Task 4).
5. A person removed while a role request waits → the request ends with "Removed from staff" (Task 4).

---

### Task 1: Setting registry, revisions model and the value in force

**Files:**
- Create: `backend/configuration/{__init__,apps,models,registry}.py`, `migrations/0001_initial.py`,
  `tests/{__init__,test_registry}.py`
- Modify: `backend/config/settings.py` (`LOCAL_APPS` + `"configuration"`), `backend/accounts/roles.py` (two permissions,
  in `PERMISSIONS` after `role.manage`; Institution Admin gets them automatically)

**Interfaces:**
- Produces (`configuration/registry.py`): `Definition` frozen dataclass `(key, label, help, kind: "modules" | "bool" |
  "month", default: Callable[[Institution], Any], needs_approval: bool, clean: Callable[[Institution, Any], Any],
  describe: Callable[[Institution, Any], str], preview: Callable[[Institution, Any, Any, date], list[str]])`;
  `DEFINITIONS: dict[str, Definition]` (spec §4 table, in that order); `definition(key) -> Definition` (raises `Http404`).
  `academic_year(month: int, on: date) -> tuple[str, date, date]` ("2026–27", start, end).
- Produces (`configuration/models.py`): `SettingRevision` per spec §3 with `Status` choices, constraint
  `one_open_revision` (unique institution+key where status in draft/pending), ordering `["-number"]`.
- Produces (`configuration/registry.py` or `values.py`): `setting(institution, key, on: date | None = None) -> Any`
  (value in force; `modules.enabled` intersected with `institution.modules`, order kept sorted).

- [ ] **Step 1: Failing tests** (`configuration/tests/test_registry.py`):
  - `test_defaults_follow_category`: `setting(school, "academic.year_start") == 6`, college → 7;
    `setting(inst, "access.role_approval") is False`; `setting(inst, "modules.enabled") == []`.
  - `test_value_in_force_follows_effective_dates`: published revisions value 4 from today and value 1 from today+10 →
    today 4, today+10 → 1; a `superseded` one is ignored.
  - `test_enabled_modules_are_cut_to_the_plan`: published `["students", "fees"]`, plan `["students"]` → `["students"]`.
  - `test_clean_rules`: `clean(modules)` refuses `"library"` not in plan ("Library is not in this institution's plan."),
    refuses `["fees"]` without students ("Fees needs Students and guardians switched on."); month 13 → error;
    `access.role_approval` True with one whole-institution assigner → error "Turning this on needs at least two people
    who can add staff for the whole institution."; True with two → ok.
  - `test_descriptions_and_previews`: `describe(inst, 4)` for the year → "Starts in April";
    `preview(inst, 6, 4, date(2027, 4, 1))` → `["The 2027–28 year runs 1 Apr 2027 – 31 Mar 2028."]`;
    module preview `["students"]→["students","fees"]` → `["Switches on: Fees"]`; role approval False→True on 2027-04-01 →
    `["From 1 Apr 2027, giving powerful roles (any that can change the institution or its staff) waits for a second
    person's approval."]`.
  - `test_admin_gets_configuration_permissions`: both names in `BUILTIN_ROLES["institution_admin"].permissions`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest configuration -q` → FAIL.
- [ ] **Step 3: Implement** (dates in the descriptions via `"%-d %b %Y"`-style formatting without leading zero).
- [ ] **Step 4: Run** → PASS; whole suite PASS (role-registry tests updated for the two new permissions).
- [ ] **Step 5: Commit** `Setting registry, revisions and the value in force`.

### Task 2: Revision lifecycle services

**Files:**
- Create: `backend/configuration/services.py`, `tests/test_services.py`

**Interfaces:**
- Consumes: Task 1; `accounts.permissions.has_perm`, `today_for`; `common.audit`, `Problem`.
- Produces: `open_draft(institution, actor, key) -> SettingRevision` (existing draft, else new draft with the value in
  force; a pending revision → 409 `version_conflict`-style Problem "A change is waiting for approval."),
  `save_draft(institution, actor, key, version, value)`, `submit(institution, actor, key, version, effective_from,
  reason)`, `approve(institution, actor, revision_id, version)`, `return_to_draft(institution, actor, revision_id,
  version, note)`, `withdraw(institution, actor, key, version)`, `restore(institution, actor, key, revision_id,
  version | None)` — each returns the `SettingRevision`; all lock the institution row and audit per spec §4.

- [ ] **Step 1: Failing tests** (`configuration/tests/test_services.py`):
  - `test_future_change_leaves_today_alone` (TST-008 shape): submit year_start 4 from today+30 by an admin (no
    approval needed) → published; `setting(..., on=today) == 6`, `on=today+30 == 4`; monkeypatch `timezone.now` to
    today+31 → `setting(...) == 4`; the first revision is unchanged in history.
  - `test_later_publish_cancels_unstarted_schedule`: publish 4 from today+30, then 8 from today+10 → the first is
    `superseded`; publish 9 from today → a past-effective published revision (from today-5, made by direct create) stays
    `published`.
  - `test_maker_is_not_checker`: with two admins, A submits `access.role_approval` True → `pending`; A approves → 403
    `own_request`; B approves → `published`; return by B → `draft` with `return_note`.
  - `test_no_approver`: single admin submitting role approval → 409 `no_approver`.
  - `test_editor_without_publish_cannot_publish`: custom role with `configuration.edit` only submits year_start → 403.
  - `test_effective_from_in_the_past_is_refused` (Review Focus 1): yesterday → 422 on `effective_from`.
  - `test_approval_rechecks_the_value` (Review Focus 2): submit `modules.enabled` `["students"]` needing no approval is
    immediate, so use a pending role-approval submit, then reduce whole-institution assigners to one before approval →
    approve → 422, revision stays `pending`.
  - `test_restore_puts_old_value_in_a_draft`: after two publishes, restore #1 → draft value equals #1's; stale draft
    version → 409.
  - `test_withdraw_and_one_open_revision`: open_draft twice → same id (Review Focus 3); withdraw → `withdrawn`; a
    pending revision blocks open_draft.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; suite PASS.
- [ ] **Step 5: Commit** `Setting drafts, approval, scheduling and rollback`.

### Task 3: Settings API

**Files:**
- Create: `backend/configuration/{serializers,views,urls}.py`, `tests/test_api.py`
- Modify: `backend/config/urls.py` (`path("api/v1/institution/", include("configuration.urls"))`),
  `backend/institutions/serializers.py` (`OwnInstitutionSerializer`: `modules_enabled`, `academic_year`
  `{label, starts_on, ends_on}`)

**Interfaces:**
- Produces routes per spec §5. List item: `{key, label, help, kind, needs_approval, value_now, description_now,
  scheduled: {effective_from, description} | null, open: {id, status, version} | null}`. Detail adds `draft`/`pending`
  `{id, number, status, version, value, description, effective_from, reason, return_note, created_by_name,
  submitted_by_name, submitted_at, can_approve}`, `preview: [str]`, and `history` (paged, 5) items `{id, number, status,
  value, description, effective_from, reason, published_at, by_name}`; `choices` for `modules` kind: the plan's modules
  `[{key, label, depends_on}]`.

- [ ] **Step 1: Failing tests** (`configuration/tests/test_api.py`): list shows three settings with `value_now`; detail
  of unknown key → 404; teacher → 403; platform host → 404; Birch's admin with an Aster revision id → 404; draft PUT
  stale → 409; draft create twice → same id; submit returns the published revision; `GET /api/v1/institution` has
  `modules_enabled` and `academic_year.label` for today; preview lines appear on the detail once a draft differs.
- [ ] **Step 2–4:** FAIL → implement → PASS; suite PASS.
- [ ] **Step 5: Commit** `Settings API`.

### Task 4: Role-change approval

**Files:**
- Modify: `backend/accounts/models.py` (`Status.PENDING`; `decided_by`, `decided_at`), migration,
  `backend/accounts/staff.py` (`give_role`/`create_staff` consult `setting(..., "access.role_approval")`; `approve_request`,
  `reject_request`; `remove` ends pending), `staff_views.py`, `staff_serializers.py` (phase `"waiting"`, `requested_by_name`,
  `can_decide`), `urls.py`; Create: `backend/accounts/approvals.py` (`GET institution/approvals`)
- Test: `backend/accounts/tests/test_role_approval.py`

**Interfaces:**
- Produces: `powerful(perms: frozenset[str]) -> bool` (anything beyond `membership.read`) in `accounts/roles.py`;
  `approve_request(actor, assignment) -> RoleAssignment`, `reject_request(actor, assignment, reason) -> RoleAssignment`;
  routes `staff/<pk>/assignments/<aid>/approve` (POST) and `/reject` (POST `{reason}`); `approvals` → `{roles: [{staff_id,
  assignment_id, person, role_label, scope_label, requested_by_name, requested_at}], settings: [{key, label, revision_id,
  submitted_by_name, description}]}` (not paged; at most the open items).

- [ ] **Step 1: Failing tests**: `test_powerful_roles_wait_while_approval_is_on` (Campus Admin gives Campus Admin at
  City → `pending`, person holds nothing; teacher role → active at once); `test_requester_cannot_approve` (403
  `own_request`); `test_admin_approves_and_it_takes_effect` (status active, `starts_on` today, decided_by set);
  `test_reject_ends_with_reason`; `test_turning_approval_off_keeps_waiting_requests` (Review Focus 4);
  `test_removing_a_person_ends_their_requests` (Review Focus 5); `test_add_staff_with_a_powerful_role_waits`;
  `test_approvals_list_shows_what_the_caller_may_decide` (admin B sees A's request, A does not; pending setting appears
  for the other publisher only).
- [ ] **Step 2–4:** FAIL → implement → PASS; suite PASS.
- [ ] **Step 5: Commit** `Powerful roles wait for a second person's approval when the setting is on`.

### Task 5: Demo data

**Files:** Modify `backend/institutions/management/commands/seed_demo.py`, `tests/test_seed.py`.

- [ ] **Step 1:** Extend the seed test: Aster has a published `modules.enabled` `["admissions", "students"]` (once),
  `access.role_approval` stays at its default; a second Aster Institution Admin `aster.deputy` ("Aster Deputy Admin")
  exists with `Demo-pass-2026`; `User.objects.count() == 10`.
- [ ] **Step 2–4:** FAIL → implement (through `configuration.services`, actor `aster.admin`) → PASS; reseed dev DB.
- [ ] **Step 5: Commit** `Demo: Aster switches on Admissions and Students, and has a deputy admin`.

### Task 6: Frontend — grouped menu, settings pages

**Files:**
- Modify: `frontend/src/app/layout/nav.ts` (+spec), `layout/shell.html`, `core/api/types.ts`, `app.routes.ts`
- Create: `features/settings/settings-page.ts`, `features/settings/setting-editor-page.ts`, `features/settings/*.spec.ts`

**Interfaces:**
- Produces: `NavItem` gains `group?: 'People' | 'Administration'`; `navFor` order Home; Staff, Roles (People);
  Organization, Settings, Public site, Profile (Administration); Settings needs `configuration.edit`. Routes
  `/app/settings`, `/app/settings/:key` with `requires('configuration.edit')`, editor with `leaveGuard`.

- [ ] **Step 1: Failing tests**: nav — admin's items carry the groups in order; a teacher sees Home and Profile (under
  Administration). Editor — saving a draft PUTs `{version, value}` and shows the returned preview lines; "Publish"
  label for `academic.year_start`, "Send for approval" for `access.role_approval`; submit sends
  `{version, effective_from, reason}`; a pending revision with `can_approve` shows Approve and Return.
- [ ] **Step 2–4:** FAIL → implement → PASS; build clean.
- [ ] **Step 5: Commit** `Settings pages and a grouped menu`.

### Task 7: Frontend — approvals on Home and the staff page; modules and academic year on Home

**Files:** Modify `features/app/home-page.ts` (+spec), `features/staff/staff-detail-page.ts` (+spec), `core/api/types.ts`.

- [ ] **Step 1: Failing tests**: Home shows "Waiting for your approval" with one item per approvals entry and nothing
  when both lists are empty; modules show "Switched on" for `modules_enabled` ones; the academic year line reads
  "Academic year 2026–27 (1 Jun 2026 – 31 May 2027)". Staff detail: a `waiting` assignment shows "Waiting for approval"
  and, with `can_decide`, Approve and Reject (reject asks for a reason and POSTs it).
- [ ] **Step 2–4:** FAIL → implement → PASS; build clean.
- [ ] **Step 5: Commit** `Approvals on Home and the staff page`.

### Task 8: Docs and browser check

- [ ] Update `README.md` (Settings, approvals, `aster.deputy`), `docs/decisions.md` (S3 rows), `docs/progress.md`.
- [ ] Browser (1280 and 390 px): as `aster.admin` schedule the academic year change and see today's value unchanged;
  switch a module on; send role approval for approval; as `aster.deputy` approve it from Home; as `aster.campus` give
  Campus Admin at City and see it wait; as `aster.admin` approve it on the staff page.
- [ ] Full suites, lint, build. Commit `Slice 3 docs and verification`.
