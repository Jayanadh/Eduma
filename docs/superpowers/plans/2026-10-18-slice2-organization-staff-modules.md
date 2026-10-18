# Eduma Slice 2 (organization, staff roles, modules, restricted state) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an Institution Admin describe campuses and departments, bring staff in with scoped, dated, ceiling-checked
roles (built-in or custom), let the platform record each institution's modules, and add the `restricted` state.

**Architecture:**
- Authority moves from `Membership.role` to `RoleAssignment` rows (role + scope + dates); one module,
  `accounts/permissions.py`, answers every "may this person do this here?" question, and every view asks it.
- Campuses and departments live in a new `organization` app; modules are a code catalogue plus `Institution.modules`.
- Angular gets three workspace pages (Organization, Staff, Roles), a menu driven by permissions, and two console
  additions (Modules step/tab, restrict/lift).

**Tech Stack:** as slice 1 — Django 6.1 + DRF 3.18, PostgreSQL 17 (`ArrayField`), pytest; Angular 22 (zoneless,
signals), Vitest.

**Spec:** `docs/superpowers/specs/2026-10-18-slice2-organization-staff-modules-design.md` (section numbers below refer to
it). Slice 1 conventions: `docs/superpowers/plans/2026-10-17-slice1-foundation-onboarding-branding.md` Global
Constraints.

## Global Constraints

- Everything in slice 1's Global Constraints still holds (ports, `/api/v1/`, problem JSON with `code`, integer `version`
  with 409 `version_conflict`, UUID keys, `Demo-pass-2026` demo / `Test-pass-2026` tests, no stock people photos, no
  invented numbers, 44 px controls, text + colour statuses, history Back, search from 3 characters with no button).
- Lists: 5 rows a page (`common.pagination.Pages`, `ui/pager.ts` `PAGE_SIZE`); pickers request `page_size=200`.
- Codes for campuses and departments: `^[A-Z0-9][A-Z0-9-]{1,19}$` after upper-casing; message
  "Use 2–20 letters, digits or dashes."
- Permission names exactly: `institution.read` (implicit), `institution_profile.update`, `institution_brand.update`,
  `organization.manage`, `membership.read`, `membership.assign`, `role.manage`.
- Built-in role keys exactly: `institution_admin`, `campus_admin`, `principal`, `head_of_department`, `registrar`,
  `teacher`, `admissions_officer`, `accountant`, `exam_officer` (labels and permissions: spec §4.2).
- Problem codes: `last_admin` (409), `own_membership` (403), `in_use` (409), `institution_restricted` (403).
- "Today" for assignments is `timezone.localdate(timezone=ZoneInfo(institution.timezone))`.
- Backend style: no formatter run over the tree (slice 2 ruling, 18 Oct); keep lines ≤120 by hand.
- Git: commit after each task, plain message, no `Co-Authored-By`, no push.

## Review Focus

1. A login ID already used by another institution's person → 422 on `username`, nothing created (Task 6).
2. A campus or department id from another institution sent as a scope, parent or campus → 422 field error, never 500
   or a cross-tenant link (Tasks 3, 7).
3. A department parent change that would make a cycle (A under B, then B under A) → 422 on `parent` (Task 3).
4. An assignment starting "today" while UTC is still yesterday (Asia/Kolkata just after midnight) is in effect (Task 2).
5. Restricted institution: a multipart image upload (`/institution/site/assets`) is refused like any write, and GETs
   still answer (Task 9).

---

### Task 1: Organization models, Main campus, factories

**Files:**
- Create: `backend/organization/__init__.py`, `apps.py`, `models.py`, `migrations/0001_initial.py`,
  `migrations/0002_main_campus.py` (data: one `MAIN`/"Main campus" per existing institution), `tests/__init__.py`,
  `tests/test_models.py`
- Modify: `backend/config/settings.py` (`LOCAL_APPS` + `"organization"` after `"institutions"`),
  `backend/institutions/services.py` (`create_institution` creates the Main campus), `backend/testing/factories.py`

**Interfaces:**
- Produces: `organization.models.Campus(institution, code, name, address, is_active)`,
  `organization.models.Department(institution, code, name, campus, parent, is_active)`, both `VersionedModel`,
  `related_name="campuses"` / `"departments"`; `organization.models.validate_code(value) -> str` (strip, upper, regex);
  `Department.descendant_ids() -> set[UUID]` (all levels, one query over the institution's departments);
  factories `campus(institution, **kw) -> Campus`, `department(institution, **kw) -> Department`.

- [ ] **Step 1: Write failing tests** in `organization/tests/test_models.py`:
  - `test_code_is_upper_cased_and_checked`: `validate_code(" sci-1 ") == "SCI-1"`; `"x"`, `"a b"`, `"-AB"` raise
    `ValidationError`.
  - `test_codes_unique_per_institution_not_globally`: same code in A twice → `IntegrityError`; same code in A and B OK.
  - `test_descendants_cover_all_levels`: SCI → PHY → LAB; `sci.descendant_ids() == {phy.id, lab.id}`.
  - `test_new_institution_gets_a_main_campus` (in `institutions/tests/test_onboarding.py`, extend
    `test_create_is_atomic_and_complete`): after create, `Campus.objects.filter(institution=created, code="MAIN",
    name="Main campus").count() == 1`.
- [ ] **Step 2: Run** `cd backend && .venv/bin/python -m pytest organization institutions/tests/test_onboarding.py -q`
  → FAIL (no module).
- [ ] **Step 3: Implement** the app, models (unique constraints `(institution, code)` named
  `unique_campus_code`/`unique_department_code`; ordering `["-is_active", "name"]`), `makemigrations organization`,
  the data migration, the `Campus.objects.create(...)` line in `create_institution` (inside its transaction), factories.
- [ ] **Step 4: Run** the same command plus the whole suite → PASS.
- [ ] **Step 5: Commit** `Campuses and departments, and a Main campus for every institution`.

### Task 2: Roles, assignments and scope-aware permission checks

**Files:**
- Create: `backend/accounts/roles.py`, `backend/accounts/tests/test_permissions.py`, migrations
  `accounts/0003_roles_assignments.py` (CustomRole, RoleAssignment), `0004_assign_existing_admins.py` (data),
  `0005_remove_membership_role.py`
- Modify: `backend/accounts/models.py` (drop `Role`, `Membership.role`; add models), `backend/accounts/permissions.py`,
  `backend/accounts/serializers.py` (`MeSerializer.get_membership`), `backend/institutions/services.py`
  (`_admins`, `first_admin`, `with_readiness`, `create_institution` creates an assignment),
  `backend/testing/factories.py`, existing tests that used `role=`

**Interfaces:**
- Produces (`accounts/roles.py`):
  - `Permission` frozen dataclass `(name, group, label, institution_only: bool)`; `PERMISSIONS: dict[str, Permission]`
    in spec §4.1 order; `IMPLICIT = "institution.read"`.
  - `BuiltinRole` frozen dataclass `(key, label, description, permissions: frozenset[str])`;
    `BUILTIN_ROLES: dict[str, BuiltinRole]` (spec §4.2; `institution_admin` holds every key of `PERMISSIONS`).
  - `institution_only(perms: Iterable[str]) -> list[str]` (sorted names whose `institution_only` is true).
- Produces (`accounts/models.py`): `CustomRole` and `RoleAssignment` as spec §3; `RoleAssignment.Status` (`active`,
  `ended`); `RoleAssignment.ScopeType` (`institution`, `campus`, `department`); check constraints
  `assignment_one_role` (exactly one of role_key/custom_role) and `assignment_scope_matches` (campus iff campus scope,
  department iff department scope); `RoleAssignment.permissions -> frozenset[str]` property (built-in from code,
  custom from the row, empty if the custom role is archived); `RoleAssignment.scope -> Scope`;
  `RoleAssignment.role_label -> str`; `RoleAssignment.scope_label -> str` ("Whole institution" / campus name /
  department name).
- Produces (`accounts/permissions.py`):
  - `Scope = tuple[str, uuid.UUID | None]`; `WHOLE: Scope = ("institution", None)`.
  - `today_for(institution) -> date`.
  - `in_effect(assignments: QuerySet, today: date) -> QuerySet` (status active, starts_on ≤ today, ends_on null or ≥).
  - `active_membership(user, institution) -> Membership | None` (unchanged signature).
  - `grants(membership) -> list[tuple[frozenset[str], Scope]]` (in-effect assignments of an active membership whose
    user is active).
  - `covers(institution, holder: Scope, target: Scope) -> bool` (spec §4.3 coverage; one query over the institution's
    departments: `id, parent_id, campus_id`).
  - `has_perm(user, institution, perm: str, scope: Scope = WHOLE) -> bool` (`institution.read` → any active member).
  - `perms_anywhere(user, institution) -> set[str]` (union over grants, plus `institution.read` for an active member).
  - `can_assign(actor, institution, perms: frozenset[str], scope: Scope) -> bool` (spec §4.3).
  - `can_manage_person(actor, target: Membership) -> bool` (spec §4.3).
- Produces (factories): `member(institution, role="institution_admin", scope=None, *, custom_role=None, starts_on=None,
  ends_on=None, **user_kw) -> User` (scope is `None` | `Campus` | `Department`); `custom_role(institution,
  permissions=(), **kw) -> CustomRole`.
- Me payload: `membership = {"roles": [{"label", "scope_label"}], "permissions": sorted(perms_anywhere),
  "restricted": bool, "status_reason": str}` or `None`.

- [ ] **Step 1: Write failing tests** in `accounts/tests/test_permissions.py` (use `world`, factories):
  - `test_builtin_admin_holds_every_registered_permission`: `BUILTIN_ROLES["institution_admin"].permissions ==
    frozenset(PERMISSIONS)`; every `BuiltinRole.permissions <= set(PERMISSIONS)`.
  - `test_institution_read_comes_with_membership`: a `teacher` member has `institution.read`, not `membership.read`.
  - `test_campus_scope_covers_its_departments_only`: Campus Admin at City; `has_perm(.., "membership.assign",
    ("campus", city.id))` and `(("department", city_dept.id))` true; Main campus, a Main department and `WHOLE` false.
  - `test_department_scope_covers_descendants`: HoD at SCI covers PHY, not LANG, not SCI's campus.
  - `test_ended_future_and_expired_assignments_grant_nothing`: ended (status), `starts_on` tomorrow, `ends_on`
    yesterday → `has_perm` false; `ends_on` today → true.
  - `test_today_uses_institution_time_zone` (Review Focus 4): freeze `django.utils.timezone.now` at
    `2026-10-18T19:00:00Z` (00:30 on 19 Oct in Asia/Kolkata); an assignment with `starts_on=date(2026, 10, 19)` is in
    effect for an `Asia/Kolkata` institution and not for a `UTC` one.
  - `test_archived_custom_role_grants_nothing`.
  - `test_revoked_membership_or_inactive_user_grants_nothing`.
  - `test_can_assign_is_the_grant_ceiling`: Campus Admin (City) may assign `teacher` at City, not at Main, not
    `institution_admin` anywhere, not a custom role holding `role.manage`; Institution Admin may assign
    `institution_admin` at `WHOLE`.
  - `test_can_manage_person`: Campus Admin manages a City teacher; not a teacher who also has a Main assignment; not a
    Principal (WHOLE); not themselves; not a member with no roles (only a whole-institution `membership.assign` holder
    can).
  - `test_me_lists_roles_permissions_and_restriction` (in `accounts/tests/`, via `GET /api/v1/session` with a real
    login on Aster's host for a Campus Admin): `membership == {"roles": [{"label": "Campus Admin", "scope_label":
    "City campus"}], "permissions": ["institution.read", "membership.assign", "membership.read"], "restricted": False,
    "status_reason": ""}`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest accounts -q` → FAIL.
- [ ] **Step 3: Implement** `roles.py`, the models and three migrations (data migration uses
  `apps.get_model`; `starts_on` = `membership.created_at.date()`), `permissions.py`, the Me payload,
  `institutions.services` (admins = memberships with an in-effect `institution_admin` assignment at whole scope;
  `create_institution` makes that assignment with `starts_on` = today for the institution), factories; replace every
  `role=`/`Role.` use found by `grep -rn "Role\b\|role=" backend --include=*.py`.
- [ ] **Step 4: Run** the whole backend suite → PASS (slice 1 tests must pass unchanged except the factory call sites).
- [ ] **Step 5: Commit** `Roles become scoped, dated assignments with a grant ceiling`.

### Task 3: Organization API (campuses and departments)

**Files:**
- Create: `backend/organization/serializers.py`, `views.py`, `urls.py`, `tests/test_api.py`
- Modify: `backend/config/urls.py` (`path("api/v1/institution/", include("organization.urls"))` before the
  `api/v1/institution` profile route)

**Interfaces:**
- Consumes: `has_perm`, `member_with` (`sites/permissions.py`), `Pages`, `audit.log`, `Problem`.
- Produces routes (spec §5): `campuses`, `campuses/<uuid:pk>`, `departments`, `departments/<uuid:pk>` on the
  institution host. Response shapes: campus `{id, code, name, address, is_active, version}`; department `{id, code,
  name, campus: {id, name} | null, parent: {id, name} | null, is_active, version}`. Query: `search` (≥3 chars, code or
  name), `active=1`, `campus=<id>` (departments), `page`, `page_size`.
- Audit actions: `campus.created`, `campus.updated`, `department.created`, `department.updated` with a from/to diff.

- [ ] **Step 1: Write failing tests** (`organization/tests/test_api.py`):
  - `test_members_list_admins_change`: a `teacher` lists campuses (200) but POST is 403; admin POST
    `{"code": "city", "name": "City campus"}` → 201 with `code == "CITY"`; duplicate code → 422 on `code`.
  - `test_lists_page_by_five_and_search_from_three_chars`: 7 campuses → `count == 8` (with MAIN), 5 results;
    `search=ci` ignored, `search=cit` finds City.
  - `test_department_takes_parent_campus_and_rejects_cycles` (Review Focus 3): PHY created with parent SCI (Main) and
    `campus=<City id>` in the body → saved campus is Main; then PATCH SCI `parent=PHY` → 422 on `parent`.
  - `test_other_institution_ids_are_field_errors` (Review Focus 2): department POST with `campus` = a Birch campus id
    or `parent` = a Birch department id → 422 on that field.
  - `test_deactivation_refused_while_in_use`: campus with an active department → PATCH `is_active=false` → 409
    `in_use`; last active campus → 409 `in_use`; department with an active child or an in-effect assignment → 409.
  - `test_stale_version_is_409`.
  - `test_other_hosts_cannot_reach`: Birch admin on Birch's host GET `campuses/<aster campus id>` → 404; platform
    admin on the platform host GET `/api/v1/institution/campuses` → 404.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest organization -q` → FAIL.
- [ ] **Step 3: Implement** with `ListCreateAPIView` / `RetrieveUpdateAPIView`; querysets always
  `filter(institution=request.institution)`; serializer `validate_campus`/`validate_parent` look up within the
  institution; cycle check uses `Department.descendant_ids()`; PATCH takes `version` and calls `check_version`; writes
  in `transaction.atomic()` with audit.
- [ ] **Step 4: Run** → PASS; whole suite PASS.
- [ ] **Step 5: Commit** `Campus and department API`.

### Task 4: Modules catalogue and entitlements

**Files:**
- Create: `backend/institutions/modules.py`, `backend/institutions/migrations/0003_modules.py` (field +
  data: category defaults), `backend/institutions/tests/test_modules.py`
- Modify: `backend/institutions/models.py` (`modules = ArrayField(models.CharField(max_length=40), default=list,
  blank=True)`), `backend/institutions/serializers.py` (`"modules"` in `EDITABLE_FIELDS`; `validate_modules`;
  create defaults), `backend/institutions/views.py` + `config/urls.py` (`GET /api/v1/platform/modules`)

**Interfaces:**
- Produces: `Module` frozen dataclass `(key, label, group: "core" | "operations", depends_on: tuple[str, ...],
  default_for: frozenset[str], available: bool = False)`; `MODULES: dict[str, Module]` exactly spec §6 (group "core"
  for the first twelve rows, "operations" for the eight in the last row); `default_modules(category: str) -> list[str]`
  (sorted); `check_modules(keys: list[str]) -> list[str]` (sorted, de-duplicated; raises
  `django.core.exceptions.ValidationError` with "Unknown module: x." or "<Label> needs <Dependency label>.").
- `GET /api/v1/platform/modules` → `[{key, label, group, depends_on, default_for, available}]` (PlatformAdmin).
- `InstitutionSerializer`/`OwnInstitutionSerializer` include `modules`; create without `modules` stores
  `default_modules(category)`.

- [ ] **Step 1: Write failing tests**:
  - `test_defaults_follow_category`: `"report_cards" in default_modules("school")`, not in `"college"`;
    `"affiliations"` only for `"university"`; `"library"` in none.
  - `test_dependencies_and_unknown_keys`: `check_modules(["attendance"])` raises with "Attendance needs Academic
    structure and timetable."; `["nope"]` raises "Unknown module: nope."; `["students", "students", "fees"]` →
    `["fees", "students"]`.
  - `test_create_uses_defaults_and_patch_is_versioned_and_audited`: onboarding POST without `modules` → response
    `modules == default_modules("school")`; PATCH `{"version", "modules": [...]}` → 200, audit `institution.updated`
    has `changes["modules"]`; bad list → 422 on `modules`.
  - `test_catalogue_is_platform_only`: platform GET `/api/v1/platform/modules` → 20 entries; Aster admin on Aster's host
    → 404.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest institutions/tests/test_modules.py -q` → FAIL.
- [ ] **Step 3: Implement**; the onboarding replay digest (`request_digest`) is computed from the raw body, so leave
  defaults to the serializer.
- [ ] **Step 4: Run** → PASS; whole suite PASS.
- [ ] **Step 5: Commit** `Module catalogue and per-institution modules`.

### Task 5: Roles API (permission registry, built-in and custom roles)

**Files:**
- Create: `backend/accounts/role_views.py`, `backend/accounts/role_serializers.py`, `backend/accounts/urls.py`,
  `backend/accounts/tests/test_roles_api.py`
- Modify: `backend/config/urls.py` (`path("api/v1/institution/", include("accounts.urls"))`)

**Interfaces:**
- Consumes: Task 2 (`PERMISSIONS`, `BUILTIN_ROLES`, `has_perm`, `can_assign`, `perms_anywhere`, `in_effect`).
- Produces routes: `permissions`, `roles`, `roles/<uuid:pk>` (spec §5). Role item shape: `{id: <uuid or builtin key>,
  builtin: bool, label, description, permissions: [names], assigned_count, is_active, version | null}`; `?assignable=1`
  keeps roles for which `can_assign(actor, institution, perms, scope)` holds for at least one of the actor's
  `membership.assign` scopes. Registry shape: `[{group, permissions: [{name, label, institution_only}]}]`.
- Audit: `role.created`, `role.updated` (permissions from/to), `role.archived`.

- [ ] **Step 1: Write failing tests**:
  - `test_lists_builtin_then_custom_with_counts`: Aster admin GET `roles?page_size=200` → first nine have
    `builtin: true` in spec §4.2 order; a custom role with two in-effect assignments shows `assigned_count == 2`.
  - `test_create_custom_role_within_ceiling`: admin POST `{"name": "Front office", "permissions": ["membership.read"]}`
    → 201; `["membership.read", "nope"]` → 422 on `permissions` naming `nope`; `["institution.read"]` → 422 (implicit,
    not assignable).
  - `test_editor_cannot_exceed_own_permissions`: a member holding a custom role with `role.manage` + `membership.read`
    at WHOLE POSTs `["organization.manage"]` → 422 "You can only give permissions you hold yourself."; PATCH of a role
    that holds `institution_brand.update` → 403.
  - `test_institution_only_permission_refused_when_role_given_narrowly`: role assigned at City, PATCH adds
    `organization.manage` → 422 mentioning "1 person has this role at a campus or department".
  - `test_names_unique_case_insensitively_among_active`; `test_archive_refused_while_assigned` (409 `in_use`);
    `test_stale_version_409`.
  - `test_assignable_filter`: Campus Admin `roles?assignable=1` excludes `institution_admin`, `campus_admin` and any
    custom role holding `role.manage`; includes `teacher`.
  - `test_roles_not_on_other_hosts`: Birch admin GET `roles/<aster custom role id>` on Birch → 404.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest accounts/tests/test_roles_api.py -q` → FAIL.
- [ ] **Step 3: Implement** (list built-ins from code and custom rows into one list, then paginate with `Pages` over
  the combined list; mutating custom roles under `select_for_update`).
- [ ] **Step 4: Run** → PASS; whole suite PASS.
- [ ] **Step 5: Commit** `Role API: built-in and custom roles within the grant ceiling`.

### Task 6: Staff API — list, add, detail, edit details

**Files:**
- Create: `backend/accounts/staff_views.py`, `backend/accounts/staff_serializers.py`, `backend/accounts/staff.py`
  (services), `backend/accounts/tests/test_staff_api.py`
- Modify: `backend/accounts/urls.py`

**Interfaces:**
- Consumes: Task 2 decisions, Task 3 models, Task 5 role lookup.
- Produces: `accounts.staff.resolve_role(institution, role: str) -> tuple[str | None, CustomRole | None, frozenset[str]]`
  (built-in key or custom role id; 422 on `role` if unknown or archived);
  `accounts.staff.resolve_scope(institution, scope_type: str, campus_id, department_id) -> Scope` (422 on the field for
  ids outside the institution or inactive); `accounts.staff.visible_memberships(actor, institution) -> QuerySet`
  (spec §4.3 visibility); `accounts.staff.create_staff(actor, institution, data: dict) -> Membership` (atomic: user with
  `must_change_password=True`, membership, first assignment; audit `staff.created`).
- Routes: `staff` (GET, POST), `staff/<uuid:pk>` (GET, PATCH). List item `{id, full_name, username, status,
  roles: [{label, scope_label}]}`; detail adds `email, mobile, last_login, must_change_password, version,
  assignments: [{id, role_label, scope_type, scope_label, starts_on, ends_on, status, end_reason, in_effect: bool}],
  can_manage: bool`.

- [ ] **Step 1: Write failing tests**:
  - `test_admin_adds_staff_with_first_password_and_role`: POST `{"full_name": "Ravi Kumar", "username": "ravi.k",
    "email": "", "mobile": "", "password": "First-pass-2026", "role": "teacher", "scope_type": "department",
    "department": <SCI id>}` → 201; the user `must_change_password`; one in-effect assignment; audit `staff.created`;
    `password` never appears in any audit `changes`.
  - `test_login_id_taken_anywhere_is_a_field_error` (Review Focus 1): username of Birch's admin → 422 on `username`;
    `User.objects.count()` unchanged.
  - `test_weak_password_and_missing_scope_refused`: `"password": "password"` → 422 on `password`; `scope_type:
    "campus"` without `campus` → 422 on `campus`.
  - `test_campus_admin_sees_and_adds_only_within_campus`: City Campus Admin list shows City staff only (`count`);
    GET a Main teacher's id → 404; POST a teacher at Main → 403; POST `institution_admin` at City → 403.
  - `test_list_search_and_paging`: 6 staff + admin → 5 results, `count == 7`; `search=rav` finds Ravi, `search=ra`
    ignored.
  - `test_edit_details_needs_can_manage_and_version`: admin PATCH Ravi's `full_name` with version → 200; stale → 409;
    Ravi PATCHing himself via `staff/<own id>` → 403 `own_membership`.
  - `test_principal_reads_but_cannot_add`: Principal GET `staff` 200, POST 403.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest accounts/tests/test_staff_api.py -q` → FAIL.
- [ ] **Step 3: Implement**; password through `password_validation.validate_password(password, candidate_user)`;
  username through `validate_username` and global uniqueness.
- [ ] **Step 4: Run** → PASS; whole suite PASS.
- [ ] **Step 5: Commit** `Staff API: list, add with a first password, details`.

### Task 7: Staff API — roles, end, password, remove, restore

**Files:**
- Modify: `backend/accounts/staff.py`, `staff_views.py`, `staff_serializers.py`, `urls.py`
- Test: `backend/accounts/tests/test_staff_actions.py`

**Interfaces:**
- Produces services in `accounts/staff.py`: `give_role(actor, membership, data) -> RoleAssignment`,
  `end_assignment(actor, assignment, reason: str) -> RoleAssignment`, `reset_password(actor, membership, password: str)
  -> None`, `remove(actor, membership, reason: str, version: int) -> Membership`, `restore(actor, membership, version:
  int) -> Membership`, `check_last_admin(institution, *, losing: RoleAssignment | Membership) -> None` (409
  `last_admin`, "Add another Institution Admin first."). All lock the institution row (`select_for_update`) as
  `sites.services` does, and audit `assignment.given`, `assignment.ended`, `staff.password_reset`, `staff.removed`,
  `staff.restored`.
- Routes: `staff/<pk>/assignments` (POST), `staff/<pk>/assignments/<uuid:aid>/end` (POST), `staff/<pk>/password`,
  `staff/<pk>/remove`, `staff/<pk>/restore` (POST).

- [ ] **Step 1: Write failing tests**:
  - `test_give_role_checks_ceiling_dates_and_scope`: admin gives Ravi `principal` at WHOLE → 201; `ends_on` before
    `starts_on` → 422 on `ends_on`; `head_of_department` with a Birch department id → 422 on `department`;
    `institution_admin` at City → 422 on `scope_type` naming the whole-institution-only permissions.
  - `test_ended_role_stops_on_next_request` (02 §9 stale role): Campus Admin's assignment ended by the admin → the
    Campus Admin's next `GET staff` is 403.
  - `test_nobody_changes_their_own_roles` (02 §9 self-escalation): admin POST to own `assignments`, own `end`, own
    `password`, own `remove` → 403 `own_membership` each.
  - `test_last_admin_cannot_go`: admins A and B; B ends A's admin role → 201/200; A (now no admin) cannot act; a third
    admin C whose admin role has an `ends_on` does not count, so B's role cannot be ended by C → 409 `last_admin`;
    C's `remove` of B → 409 `last_admin`.
  - `test_reset_password_forces_change_and_respects_rank`: Campus Admin resets a City teacher (204, teacher
    `must_change_password`); resets the Principal → 403.
  - `test_remove_ends_roles_and_session_restore_gives_none`: remove Ravi → membership `revoked`, all assignments
    `ended` with reason "Removed from staff"; Ravi's existing session → next request 403/anonymous (session middleware);
    sign-in refused; restore → active with no in-effect assignments; Campus Admin restore → 403.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest accounts/tests/test_staff_actions.py -q` → FAIL.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** → PASS; whole suite PASS.
- [ ] **Step 5: Commit** `Staff API: give and end roles, reset passwords, remove and restore`.

### Task 8: Platform cannot browse; denial-case sweep

**Files:**
- Test: `backend/accounts/tests/test_denials.py`

**Interfaces:** none new.

- [ ] **Step 1: Write the sweep test** `test_every_institution_route_refuses_other_hosts` parametrised over every route
  added in Tasks 3, 5, 6, 7 (GET and the matching write): on the platform host as the platform admin → 404; on Birch's
  host as Birch's admin with Aster ids → 404; on Aster's host anonymously → 403 `authentication_required`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest accounts/tests/test_denials.py -q` → PASS (fix any route that leaks
  before committing).
- [ ] **Step 3: Commit** `Denial sweep for slice 2 routes`.

### Task 9: The restricted state

**Files:**
- Modify: `backend/institutions/models.py` (`RESTRICTED = "restricted", "Restricted"`; `SIGN_IN_STATES` +
  `RESTRICTED`), migration `institutions/0004_restricted.py` (choices only), `backend/institutions/services.py`
  (`TRANSITIONS` + `(ACTIVE, RESTRICTED): "institution.restricted"`, `(RESTRICTED, ACTIVE):
  "institution.restriction_lifted"`, `(RESTRICTED, SUSPENDED)`, `(RESTRICTED, ARCHIVED)`; lifting needs
  `first_admin`), `backend/sites/middleware.py` (`RestrictedMiddleware`), `backend/config/settings.py` (after
  `sites.middleware.SiteMiddleware`), `backend/sites/public.py` (restricted serves like active),
  `backend/accounts/serializers.py` (Me `restricted`, `status_reason`)
- Test: `backend/institutions/tests/test_restricted.py`

**Interfaces:**
- Produces: `RestrictedMiddleware`; open paths `("/api/v1/session/login", "/api/v1/session/logout",
  "/api/v1/session/change-password")`; body as `PasswordChangeRequiredMiddleware` with code `institution_restricted`,
  title "Read-only for now", detail `f"{name} is read-only for now: {reason}"`.

- [ ] **Step 1: Write failing tests**:
  - `test_restrict_and_lift_are_audited_moves`: active → restricted (`institution.restricted`), restricted → active
    (`institution.restriction_lifted`); setup → restricted → 409.
  - `test_members_read_but_cannot_write`: after restricting Aster, admin GET `campuses` 200; POST `campuses` → 403
    `institution_restricted` with the reason in `detail`; PUT `site/draft` → 403; multipart POST `site/assets` → 403
    (Review Focus 5); real sign-in, change-password and sign-out still work.
  - `test_public_page_stays_up`: `GET /api/v1/public/site` on Aster → `mode == "full"`.
  - `test_platform_host_is_unaffected`: platform admin PATCHes Aster's details while restricted → 200.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest institutions/tests/test_restricted.py -q` → FAIL.
- [ ] **Step 3: Implement**.
- [ ] **Step 4: Run** → PASS; whole suite PASS.
- [ ] **Step 5: Commit** `Restricted state: members can read, changes are paused`.

### Task 10: Demo data

**Files:**
- Modify: `backend/institutions/management/commands/seed_demo.py`, `backend/institutions/tests/test_seed.py`

- [ ] **Step 1: Extend** `test_seed_runs_twice_without_duplicates`: Aster has campuses `{"MAIN", "CITY"}`,
  departments `{"SCI", "PHY", "LANG"}` with PHY under SCI; users `aster.principal`, `aster.campus`, `aster.teacher`,
  `aster.office` exist once, check `Demo-pass-2026`, `must_change_password` false; `aster.office` holds custom role
  "Front office" (`["membership.read"]`) at City; every institution's `modules == default_modules(category)` on first
  run; `User.objects.count() == 9`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** with `get_or_create` keyed on code/username/name (spec §8).
  **Step 4: Run** → PASS; run `manage.py migrate && manage.py seed_demo` against the dev DB.
- [ ] **Step 5: Commit** `Demo campuses, departments, staff and modules`.

### Task 11: Frontend core — permissions, menu, restricted banner, lifecycle

**Files:**
- Modify: `frontend/src/app/core/api/types.ts` (`LifecycleStatus` + `'restricted'`; `Me.membership` per Task 2;
  `InstitutionDetail.modules: string[]`; new `Campus`, `Department`, `RoleItem`, `PermissionGroup`, `StaffItem`,
  `StaffDetail`, `Assignment`, `ModuleInfo` types matching Tasks 3–7), `core/auth-store.ts` (`can(perm: string):
  boolean`, `roleLabel = computed(...)`), `core/guards.ts` (`requires(perm: string): CanActivateFn` → `/app` when
  missing), `layout/nav.ts` (`navFor(kind, can: (perm) => boolean)`), `layout/shell.ts`/`shell.html` (role label,
  restricted banner), `ui/status-badge.ts` (`restricted`: warning, "Restricted"),
  `features/console/lifecycle.ts` (moves per spec §7), `features/console/overview-page.ts` (STATES + restricted),
  `features/console/institutions-page.ts` (filter option)
- Test: `layout/nav.spec.ts`, `features/console/lifecycle.spec.ts`, `core/guards.spec.ts`, `ui/status-badge.spec.ts`

**Interfaces:**
- Produces: `AuthStore.can(perm)`; `requires(perm)`; `navFor('institution', can)` returns, in order, Home `/app`
  (`home`), Staff `/app/staff` (`users`, needs `membership.read`), Roles `/app/roles` (`key`, `role.manage`),
  Organization `/app/organization` (`building`, `organization.manage`), Public site `/app/site` (`globe`,
  `institution_brand.update`), Profile `/app/profile` (`user`). Add icons `users` and `user` to `ui/icon.ts` if absent.

- [ ] **Step 1: Write failing tests**: `nav.spec.ts` — with only `institution.read`, items are Home and Profile; with
  `membership.read` Staff appears between them; full admin set gives all six in order. `lifecycle.spec.ts` —
  `allowedMoves('active')` labels `['Restrict', 'Suspend', 'Archive']`; `allowedMoves('restricted')` labels
  `['Lift restriction', 'Suspend', 'Archive']`. `guards.spec.ts` — `requires('role.manage')` sends a teacher to
  `/app`. `status-badge.spec.ts` — `restricted` renders "Restricted".
- [ ] **Step 2: Run** `cd frontend && npx ng test --watch=false` → FAIL.
- [ ] **Step 3: Implement**. Restrict effect copy: "Its members can still sign in and look, but every change is paused
  until you lift it. They see your reason." Lift effect: "Its members can make changes again." Banner copy (spec §7).
- [ ] **Step 4: Run** → PASS; `npx ng build --configuration development` clean.
- [ ] **Step 5: Commit** `Menu by permission, restricted banner and moves`.

### Task 12: Console — Modules step and Modules tab

**Files:**
- Create: `frontend/src/app/core/modules.ts`, `core/modules.spec.ts`, `features/console/module-picker.ts`
- Modify: `features/console/onboarding-page.{ts,html}` (step "Modules" after "Web address"; `GROUP_STEP`/`FIELD_GROUP`
  updated so a `modules` error returns to it; review row), `features/console/institution-page.{ts,html}` (tab
  `{ key: 'modules', label: 'Modules' }` between Overview and Activity)

**Interfaces:**
- Produces: `tick(selected: readonly string[], key: string, catalogue: ModuleInfo[]): string[]` (adds key and its
  dependencies, recursively); `untick(selected, key, catalogue): string[]` (removes key and everything that depends on
  it, recursively); `defaultsFor(category: Category, catalogue): string[]`. `ModulePicker` component: inputs
  `catalogue`, `selected` (model `string[]`), renders two fieldsets (Core, Operations) of checkboxes with "Needs: …"
  hints.

- [ ] **Step 1: Write failing tests** (`modules.spec.ts`): ticking `report_cards` adds `exams` and `academics`;
  unticking `academics` removes `attendance`, `exams`, `report_cards`, `course_registration`, `outcomes`,
  `affiliations`; `defaultsFor('school')` contains `report_cards` and not `course_registration`. Onboarding spec:
  changing category before touching the list resets the defaults; after a manual tick it does not.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (catalogue from `GET platform/modules`, loaded once by the wizard
  and the tab; the tab saves with `PATCH platform/institutions/<id> {version, modules}`, conflict and field errors shown
  like the profile form). **Step 4: Run** → PASS; build clean.
- [ ] **Step 5: Commit** `Modules in onboarding and on the institution page`.

### Task 13: Workspace — Organization page

**Files:**
- Create: `features/org/organization-page.ts`, `features/org/campus-form.ts`, `features/org/department-form.ts`,
  `features/org/organization-page.spec.ts`
- Modify: `app.routes.ts` (`/app/organization`, `canActivate: [requires('organization.manage')]`)

**Interfaces:**
- Consumes: Task 3 routes; `SearchBox`, `Pager`, `StatusBadge` (active/inactive use text "Active"/"Inactive"),
  `ToastService`.
- Produces: page with two sections (Campuses, Departments), each: search, paged list, Add; a form panel for add/edit
  (code, name, address | campus/parent pickers, Active checkbox); department parent picker excludes the department
  itself and its descendants (filter by a `GET departments?page_size=200` and the server's error as backstop).

- [ ] **Step 1: Write failing tests**: adding a campus POSTs `{code, name, address}` and reloads the list; a 422 on
  `code` shows under the Code field; choosing a parent hides the campus picker.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** → PASS; build clean.
- [ ] **Step 5: Commit** `Organization page: campuses and departments`.

### Task 14: Workspace — Staff list, Add staff, Staff detail

**Files:**
- Create: `features/staff/staff-page.ts` (list), `features/staff/add-staff-page.ts`, `features/staff/staff-detail-page.ts`,
  `features/staff/scope-picker.ts` (scope type + campus/department selects, emits `{scope_type, campus, department}`),
  `features/staff/*.spec.ts`
- Modify: `app.routes.ts` (`/app/staff`, `/app/staff/new`, `/app/staff/:id`; `requires('membership.read')`, `new`
  also `requires('membership.assign')`; `leaveGuard` on `new`)

**Interfaces:**
- Consumes: Task 6/7 routes, `roles?assignable=1&page_size=200`, `campuses?active=1&page_size=200`,
  `departments?active=1&page_size=200`, `slugify` (login ID suggestion `<first>.<last>` from the name, ≤40 chars),
  `ConfirmDialog.prompt` (end reason, remove reason), `ConfirmDialog.firstPassword` (reset).
- Produces: list rows with role chips "<label> · <scope>"; detail sections Details (form, hidden if `!can_manage`),
  Roles (in effect / starts later / ended groups, End buttons only when `can_manage`), Give a role (form), Reset
  password, Remove / Restore.

- [ ] **Step 1: Write failing tests**: add-staff suggests `ravi.kumar` from "Ravi Kumar" until the field is edited;
  the scope picker shows the campus select only for campus scope; the detail page hides End and Reset when
  `can_manage` is false; a 409 `last_admin` on End shows its message in a toast.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** → PASS; build clean.
- [ ] **Step 5: Commit** `Staff pages: list, add with a first password, detail and role changes`.

### Task 15: Workspace — Roles page and role editor

**Files:**
- Create: `features/roles/roles-page.ts`, `features/roles/role-editor-page.ts`, `features/roles/role-diff.ts`,
  `features/roles/role-diff.spec.ts`, `features/roles/role-editor-page.spec.ts`
- Modify: `app.routes.ts` (`/app/roles`, `/app/roles/new`, `/app/roles/:id`; `requires('role.manage')`; `leaveGuard` on
  the editor)

**Interfaces:**
- Produces: `roleDiff(before: readonly string[], after: readonly string[]): { added: string[]; removed: string[] }`
  (sorted). Roles page: built-in cards (read-only) then custom cards with Edit/Archive, paged. Editor: name,
  description, permission checkboxes grouped from `GET permissions`, those not in `AuthStore` permissions disabled with
  "You don't have this", preview "Adds: … · Removes: … · Affects N people" (N = `assigned_count`), Save with `version`.

- [ ] **Step 1: Write failing tests**: `roleDiff(['a','b'], ['b','c'])` → `{added: ['c'], removed: ['a']}`; the editor
  disables a permission the user lacks; saving sends `{name, description, permissions, version}`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** → PASS; build clean.
- [ ] **Step 5: Commit** `Roles page and custom role editor with a change preview`.

### Task 16: Home additions, docs and browser verification

**Files:**
- Modify: `features/app/home-page.ts` (+ spec): "Modules in your plan" card listing `institution.modules` labels with
  "Arrives in a later release" (labels from a `MODULE_LABELS` record in `core/modules.ts` mirroring spec §6, as the
  institution host cannot call the platform catalogue); a member with no roles sees "You have no role here yet. Ask
  your Institution Admin." and no setup checklist unless they hold `institution_profile.update`.
- Modify: `README.md` (demo staff logins table and new pages), `docs/progress.md` (status, rulings made while
  building, browser checks), `docs/decisions.md` (S2-01…S2-13 summary rows).

- [ ] **Step 1: Write failing tests** for the home card and the no-role message; **Step 2** FAIL; **Step 3**
  implement; **Step 4** PASS; full backend and frontend suites PASS; build clean.
- [ ] **Step 5: Browser check** (built-in browser, 1280 px and 390 px): as `aster.admin` add a campus, a department, a
  staff member with a role, end a role, create a custom role; as `aster.campus` confirm only City staff and the refused
  actions; as `eduma.admin` restrict Aster and confirm the banner and a refused save as `aster.admin`, then lift it;
  the onboarding Modules step and the Modules tab. Screenshots to `docs/screenshots/slice2-*.png`.
- [ ] **Step 6: Commit** `Slice 2 home, docs and verification`.
