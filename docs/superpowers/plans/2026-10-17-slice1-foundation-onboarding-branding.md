# Eduma Slice 1 (foundation, onboarding, institution URLs, branding) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the plumbing and screens the System Admin needs to onboard an institution end to end: create it, give it
a URL (subdomain), build its branded public page, activate it, and hand its admin a first password so they can sign in
to their own branded workspace.

**Architecture:**
- One Django/DRF API resolves the tenant from the request host (`<slug>.<base host>`), on every request.
- One Angular app boots by asking `/api/v1/public/site` what it is serving, then applies that site's theme as CSS
  variables.
- Public pages, the console (`/console`, platform host) and the institution app (`/app`, institution host) share one
  renderer and one site editor.

**Tech Stack:**
- Backend: Python 3.12, Django ~=6.1.1, djangorestframework ~=3.18.1, psycopg[binary] ~=3.3.6, Pillow, pytest ~=9.1 +
  pytest-django ~=4.14.
- Database: PostgreSQL 17 (Docker).
- Frontend: Angular ^22.2 (zoneless, signals, `@Service()`), Vitest, `@fontsource` fonts. Node 24/25.

**Spec:** `docs/superpowers/specs/2026-10-17-foundation-onboarding-branding-design.md` (read it first; section numbers
below refer to it).

**Reference codebase:** `~/Downloads/AP_Police_Student_Connect`, called "SC" below. "Copy from SC" means copy the file,
then make only the changes listed. SC is the house style: comment density, naming, signals, `load()`, `Api`,
`@Service()`.

## Global Constraints

- **Ports:**
  - PostgreSQL `127.0.0.1:5434`, with db, user and password all `eduma`.
  - Django `8001`.
  - Angular dev server `4201`.
  - `EDUMA_BASE_URL` default `http://localhost:4201`.
- **API:** everything under `/api/v1/`.
  - Errors are RFC 9457 problem JSON with `code` (spec section 7).
  - Every mutable record carries an integer `version`; a stale one returns 409 `version_conflict`.
- **UUID primary keys** on every new model, including `User`.
- **Login refusal text,** exactly: `Invalid login ID or password.`
- **Demo password,** exactly: `Demo-pass-2026` (seed only). Tests use `Test-pass-2026`.
- **Fonts:** OFL fonts via `@fontsource`, bundled; no CDN. Heading codes `bricolage`, `fredoka`, `jakarta`,
  `space-grotesk`, `fraunces`, `playfair`. Body codes `dm-sans`, `inter`, `nunito`, `source-sans`, `lora`. Defaults
  `bricolage` and `dm-sans`.
- **Colours:**
  - Eduma theme defaults: primary `#4B5AE4`, secondary `#FFD43B`.
  - Ink `#17132B`.
  - Semantic colours are fixed: danger `#B91C1C`, warning `#92400E`, success `#166534`, info `#6D28D9`.
- **No pictures of people and no invented numbers.** No stock photos of real people anywhere, and no invented metrics or
  quotes in any content.
- **Git:** commit after each task with a plain message. Author is repo-local (already configured). No `Co-Authored-By`
  line. No push.
- **UI habits:**
  - Left sidebar on desktop, drawer below 900 px.
  - Search as you type from 3 characters, no Search button.
  - Back buttons use history (SC `NavigationHistory`).
  - Every status shows text plus colour.
  - Controls are 44 px tall.
  - `prefers-reduced-motion` is respected.

## Review Focus

1. **Mixed-case host or slug** (`Aster-School.localhost`, slug typed as `WWW`): hosts are case-insensitive, so the
   request should resolve to the lowercase slug, and reserved words are refused whatever their case. Tested in Task 3
   and Task 2.
2. **Stale draft save** (two people editing one institution's page): the second save gets 409, and the editor keeps
   that person's unsaved edits and offers "Reload latest". Tested in Task 5 (API) and Task 17 (editor).
3. **Long and non-Latin names** (a 120-character name, a Devanagari or Telugu display name): the pages wrap without
   horizontal scroll, and slug suggestion drops non-ASCII letters (it may return `''`, leaving the field for the admin
   to fill). Tested in Task 15 (slugify) and checked in Task 19 (browser).
4. **Hostile images** (a decompression bomb, a JPEG renamed `.png`, a 0-byte file): 422 `validation_failed`, never
   500, and nothing is stored. Tested in Task 6.
5. **Institution suspended mid-session** (the admin has the editor open): their next call is refused, the app's session
   recheck sends them to `/login`, and the institution host's public page reads "temporarily unavailable". Tested in
   Task 3 (API) and Task 11 (interceptor).

---

## File map

```
docker-compose.yml                      db service, port 5434
README.md                               setup, run, demo logins, tests (Task 9)
docs/decisions.md, docs/progress.md     Task 19
.claude/launch.json                     backend + frontend servers (gitignored, Task 9)
backend/
  manage.py, pytest.ini, conftest.py, requirements.txt, requirements-dev.txt, .env.example
  config/{settings.py, settings_test.py, urls.py, wsgi.py, asgi.py}
  common/{models.py (VersionedModel, AuditEvent), audit.py, exceptions.py, pagination.py, views.py (health, audit list), serializers.py}
  accounts/{models.py (User, Membership, Role), permissions.py, middleware.py, throttles.py, serializers.py, views.py}
  institutions/{models.py, services.py, serializers.py, views.py, management/commands/seed_demo.py}
  sites/{hosts.py, middleware.py, permissions.py, theme.py, content.py, starter.py, eduma_content.py,
         models.py (SiteRevision, BrandAsset), services.py, images.py, serializers.py, views.py}
  testing/factories.py
  */tests/test_*.py
frontend/
  package.json, angular.json, proxy.conf.json, tsconfig*.json
  src/{index.html, main.ts, styles.scss, styles/_tokens.scss, _base.scss, _components.scss, _fonts.scss}
  src/app/{app.ts, app.config.ts, app.routes.ts}
  src/app/core/{api/api.ts, api/types.ts, api-error.ts, auth-store.ts, site-store.ts, guards.ts,
                session-interceptor.ts, load.ts, navigation-history.ts, format.ts, slug.ts}
  src/app/ui/   copied from SC: icon, toast, confirm-dialog, page-header, search-box, pager, empty-state, load-error,
                reveal, status-badge
  src/app/layout/{shell.ts, shell.html, shell.scss, nav.ts}
  src/app/features/public/{site-view.ts, site-header.ts, site-footer.ts, image-slot.ts, landing-page.ts,
                           notice-page.ts, sections/*.ts}
  src/app/features/auth/{login-page.ts, change-password-page.ts}
  src/app/features/console/{overview-page.ts, institutions-page.ts, onboarding-page.ts, institution-page.ts,
                            audit-page.ts, lifecycle-dialog.ts}
  src/app/features/editor/{site-editor.ts, section-form.ts, theme-form.ts, image-picker.ts}
  src/app/features/app/{home-page.ts, profile-page.ts, site-page.ts}
```

---

### Task 1: Backend foundation (project, settings, Docker DB, problem errors, test harness)

**Files:**
- Create: `docker-compose.yml`, `backend/manage.py`, `backend/requirements.txt`, `backend/requirements-dev.txt`,
  `backend/.env.example`, `backend/pytest.ini`, `backend/conftest.py`, `backend/config/{__init__,settings,settings_test,urls,wsgi,asgi}.py`,
  `backend/common/{__init__,apps,exceptions,pagination,views}.py`, `backend/common/tests/test_problems.py`

**Interfaces:**
- Produces:
  - `common.exceptions.Problem(APIException)`, constructed as `Problem(status: int, code: str, detail: str, **extra)`.
  - Subclass `VersionConflict(current_version: int)`, which is 409 `version_conflict` with title "This record changed"
    and detail "Reload the latest record and review your changes."
  - Subclass `InvalidTransition(detail: str)`, which is 409 `invalid_transition`.
  - Subclass `IdempotencyMismatch()`, which is 409 `idempotency_mismatch`.
  - `common.exceptions.problem_handler(exc, context)` as DRF's `EXCEPTION_HANDLER`.
  - `common.pagination.Pages` (copy from SC).
  - `GET /api/v1/health` → `{"status":"ok"}`.

- [ ] **Step 1: Scaffold**
  - Copy SC `docker-compose.yml`: rename the db, user and password to `eduma` and the port to `127.0.0.1:5434:5432`.
  - Copy SC `backend/config/settings.py` structure (`env()`, secret-key guard, `is_local_host` DEBUG guard, proxy
    count, HSTS, admin toggle, session/CSRF cookie names, DB cache throttling), then change:
    - `LOCAL_APPS = ["common", "accounts", "institutions", "sites"]`.
    - Database defaults `eduma` on port `5434`.
    - `ALLOWED_HOSTS` default `"localhost,.localhost,127.0.0.1"`.
    - `CSRF_TRUSTED_ORIGINS` default `"http://localhost:4201,http://*.localhost:4201"`.
    - Cache `LOCATION` `"eduma_cache"`.
    - `EDUMA_BASE_URL = env("EDUMA_BASE_URL", "http://localhost:4201")`.
    - `EDUMA_CONTACT_EMAIL = env("EDUMA_CONTACT_EMAIL", "hello@eduma.example")`.
    - `REST_FRAMEWORK["EXCEPTION_HANDLER"] = "common.exceptions.problem_handler"`.
    - Throttle rates as in SC.
    - `DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024`.
    - Drop `CONNECT_RULES`.
  - `settings_test.py`: copy from SC, plus:
    - `EDUMA_BASE_URL = "http://eduma.test"`.
    - `ALLOWED_HOSTS = [".eduma.test", "eduma.test", "testserver"]`.
    - Media root under a temp `eduma-test-media` folder.
  - Requirements: SC's list minus `openpyxl`, plus `Pillow~=12.0`. Pick the newest Pillow available with `pip index
    versions pillow` and pin `~=` to it.
  - `.env.example` lists every env var with dev defaults: `DJANGO_*`, `POSTGRES_*`, `EDUMA_BASE_URL`,
    `EDUMA_CONTACT_EMAIL`.

- [ ] **Step 2: Write failing tests** in `common/tests/test_problems.py` (use `api` fixture = `APIClient()`; temporary
  test-only views registered via `urls` override are fine, or call `problem_handler` directly with exceptions):

```python
def test_health(api):
    assert api.get("/api/v1/health").json() == {"status": "ok"}

def test_validation_error_is_422_problem():
    response = problem_handler(ValidationError({"slug": ["Bad."], "admin": {"username": ["Taken."]}}), {})
    assert response.status_code == 422
    assert response["Content-Type"].startswith("application/problem+json")
    assert response.data["code"] == "validation_failed"
    assert {"field": "admin.username", "code": "invalid", "message": "Taken."} in response.data["errors"]

def test_not_authenticated_is_403_authentication_required():
    assert problem_handler(NotAuthenticated(), {}).data["code"] == "authentication_required"

def test_version_conflict_carries_current_version():
    data = problem_handler(VersionConflict(8), {}).data
    assert (data["status"], data["code"], data["current_version"]) == (409, "version_conflict", 8)
    assert data["type"] == "urn:eduma:problem:version_conflict"

def test_http404_is_not_found_and_throttled_is_rate_limited():
    assert problem_handler(Http404(), {}).data["code"] == "not_found"
    assert problem_handler(Throttled(wait=5), {}).data["code"] == "rate_limited"
```

- [ ] **Step 3: Run and confirm they fail.** Start the DB first: `open -a Docker` if the daemon is down, then
  `docker compose up -d db`. Run `cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r
  requirements-dev.txt && .venv/bin/pytest common -q`. Expected: FAIL (import errors).

- [ ] **Step 4: Implement `problem_handler`.**
  - Map exceptions to codes:

    | Exception | Status / code |
    |---|---|
    | `ParseError` | 400 `invalid_request` |
    | `NotAuthenticated` / `AuthenticationFailed` | 403 `authentication_required` |
    | `PermissionDenied` | 403 `permission_denied` |
    | `NotFound` / `Http404` | 404 `not_found` |
    | `MethodNotAllowed` | 405 `method_not_allowed` |
    | `ValidationError` | 422 `validation_failed` |
    | `Throttled` | 429 `rate_limited` |
    | `Problem` | its own status and code |

  - Flatten nested validation dicts and lists into `errors` entries `{field: "a.b.0.c", code, message}`, using
    `ErrorDetail.code`. Field `non_field_errors` becomes `""`.
  - `detail` = the first message.
  - Body keys: `type`, `title`, `status`, `detail`, `code`, `errors`, plus extras.
  - Content type `application/problem+json`.
  - Anything else falls through to DRF's default (500 untouched).
  - `urls.py` serves `api/v1/health`, plus admin when `ADMIN_ENABLED`.

- [ ] **Step 5: Run** `.venv/bin/pytest common -q` and `.venv/bin/python manage.py check`. Expected: all pass, no
  issues.

- [ ] **Step 6: Commit** `git add docker-compose.yml backend && git commit -m "Backend foundation: settings, Docker DB, problem-details errors"`.

---

### Task 2: Core models (users, memberships, institutions, audit) and test factories

**Files:**
- Create:
  - `backend/common/models.py` (`VersionedModel`, `AuditEvent`), `backend/common/audit.py`
  - `backend/accounts/{__init__,apps,models,permissions}.py`
  - `backend/institutions/{__init__,apps,models}.py`
  - `backend/sites/{__init__,apps}.py`
  - `backend/testing/{__init__,factories}.py`
  - Tests: `backend/accounts/tests/test_models.py`, `backend/institutions/tests/test_models.py`
- Modify: `backend/conftest.py`

**Interfaces:**
- Produces:
  - `common.models.VersionedModel` (abstract): `id = UUIDField(primary_key, default=uuid4)`, `created_at`,
    `updated_at`, `version = PositiveIntegerField(default=1)`.
    - `save()` increments `version` when not adding.
    - `check_version(supplied: int | None) -> None` raises `VersionConflict(self.version)` if `supplied != self.version`.
  - `common.models.AuditEvent`: fields per spec section 3. `ordering = ["-at"]`.
  - `common.audit.log(actor, action: str, target: Model, summary: str, *, institution=None, changes: dict | None = None) -> AuditEvent`
    - The institution is inferred: the target itself if it is an `Institution`, else `target.institution_id`.
    - The actor is stored as `None` when not authenticated.
  - `accounts.models.User` (`AbstractUser`, UUID pk): `full_name`, `email` (blank ok), `mobile` (blank ok),
    `is_platform_admin`, `must_change_password`, `created_by`.
    - `save()` lowercases and strips `username`.
    - `USERNAME_RE = r"^[a-z0-9][a-z0-9._-]{2,39}$"`, enforced by `validate_username(value) -> str`, which normalizes
      and raises `ValidationError("Use 3–40 lowercase letters, digits, dots, dashes or underscores.")`.
  - `accounts.models.normalize_username(value: str) -> str`.
  - `accounts.models.Role.INSTITUTION_ADMIN`.
  - `accounts.models.Membership(VersionedModel)`: `institution`, `user` (related_name `memberships`), `role`,
    `status` (`active` / `revoked`), `created_by`. `UniqueConstraint(institution, user)`.
  - `accounts.permissions.ROLE_PERMISSIONS: dict[str, frozenset[str]]`, with `INSTITUTION_ADMIN` →
    `{"institution.read", "institution_profile.update", "institution_brand.update"}`.
  - `accounts.permissions.has_perm(user, institution, perm: str) -> bool`: true only for an active user with an active
    membership in that institution whose role grants `perm`.
  - `accounts.permissions.active_membership(user, institution) -> Membership | None`.
  - `institutions.models.Category` (`school`, `college`, `engineering_college`, `university`; labels "School",
    "College", "Engineering college", "University").
  - `LifecycleStatus` (`setup`, `active`, `suspended`, `archived`).
  - `SIGN_IN_STATES = {LifecycleStatus.SETUP, LifecycleStatus.ACTIVE}`.
  - `RESERVED_SLUGS` (spec section 3 list).
  - `validate_slug(value) -> str`: lowercases, then checks the regex `^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$` and the
    reserved list. Messages are "Use 3–40 lowercase letters, digits or dashes, starting and ending with a letter or
    digit." and "This address is reserved."
  - `institutions.models.Institution(VersionedModel)`: fields per spec section 3, including `creation_key`
    (`UUIDField`, unique) and `creation_hash` (`CharField(64)`).
    - Conditional `UniqueConstraint`s on `udise_code` and `aishe_code` when not blank.
    - `slug` unique.
  - `testing.factories` (`PASSWORD = "Test-pass-2026"`):
    - `platform_admin(**kw)`.
    - `institution(**kw)`: unique slug `inst<n>`, status `active`.
    - `member(institution, **kw) -> User`: an Institution Admin with an active membership.
    - `user(**kw)`.
  - `conftest.py` fixtures:
    - `api`.
    - `world` (`platform_admin`, `a`, `b` institutions with `a_admin`, `b_admin`).
    - `client_for(slug: str | None, user=None) -> APIClient`: `HTTP_HOST` is `eduma.test` or `<slug>.eduma.test`;
      `force_authenticate(user)` when a user is given.

- [ ] **Step 1: Write failing tests**

```python
# accounts/tests/test_models.py
def test_username_is_lowercased_and_validated(db):
    u = factories.user(username="  Aster.Admin ")
    assert u.username == "aster.admin"
    with pytest.raises(ValidationError):
        validate_username("ab")

def test_has_perm_needs_active_membership_in_that_institution(world):
    assert has_perm(world.a_admin, world.a, "institution_brand.update")
    assert not has_perm(world.a_admin, world.b, "institution_brand.update")
    Membership.objects.filter(user=world.a_admin).update(status="revoked")
    assert not has_perm(world.a_admin, world.a, "institution_brand.update")

def test_version_increments_and_check_version_raises(world):
    world.a.display_name = "New"; world.a.save()
    assert world.a.version == 2
    with pytest.raises(VersionConflict):
        world.a.check_version(1)

# institutions/tests/test_models.py
@pytest.mark.parametrize("raw,ok", [("aster-school", True), ("WWW", False), ("-ab", False), ("ab", False),
                                     ("Aster", True), ("a" * 41, False), ("api", False)])
def test_validate_slug(raw, ok): ...

def test_udise_unique_only_when_present(db):
    factories.institution(udise_code=""); factories.institution(udise_code="")
    factories.institution(udise_code="28123456789")
    with pytest.raises(IntegrityError):
        factories.institution(udise_code="28123456789")

def test_audit_log_infers_institution(world):
    event = audit.log(world.platform_admin, "institution.updated", world.a, "Updated")
    assert event.institution_id == world.a.id
```

- [ ] **Step 2: Run** `.venv/bin/pytest -q`. Expected: FAIL (missing modules).
- [ ] **Step 3: Implement the models, helpers, factories and fixtures** listed under Interfaces. Set
  `AUTH_USER_MODEL = "accounts.User"`. Run `makemigrations accounts institutions common`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "Users, memberships, institutions and audit models"` (add new files first).

---

### Task 3: Host resolution, sessions and sign-in API

**Files:**
- Create:
  - `backend/sites/{hosts,middleware,permissions}.py`
  - `backend/accounts/{middleware,throttles,serializers,views}.py`
  - Tests: `backend/sites/tests/test_hosts.py`, `backend/accounts/tests/test_auth.py`
- Modify: `backend/config/settings.py` (middleware order), `backend/config/urls.py`

**Interfaces:**
- Consumes: Task 2 models, `has_perm`, `active_membership`, `SIGN_IN_STATES`, `audit.log`.
- Produces:
  - `sites.hosts.resolve(host: str) -> tuple[str, str | None]`: returns `("platform", None)`,
    `("institution", slug)` or `("unknown", None)`. It is case-insensitive and ignores the port.
  - `sites.hosts.institution_url(slug: str) -> str` (for example `http://aster.localhost:4201`).
  - `sites.hosts.platform_url() -> str`.
  - `request.site_kind`, set by `sites.middleware.SiteMiddleware`.
  - `request.institution` (`Institution | None`, any state). Unknown slugs give `site_kind="unknown"`.
  - `request.site_key`, which is `"platform"`, `str(institution.id)` or `None`.
  - `sites.middleware.SessionSiteMiddleware`: signs the session out per spec section 2. It sits after
    `AuthenticationMiddleware`.
  - `accounts.middleware.PasswordChangeRequiredMiddleware` (from SC): returns a 403 problem
    `password_change_required` except for paths starting `/api/v1/session`, `/api/v1/health`, `/api/v1/public/`.
  - `sites.permissions.PlatformAdmin`: on a non-platform host it raises `NotFound`; then it requires
    `is_platform_admin`, otherwise 403.
  - `sites.permissions.member_with(perm: str) -> type[BasePermission]`: on a non-institution host it raises `NotFound`;
    otherwise it requires `has_perm(request.user, request.institution, perm)` and returns 403 when that fails.
  - Endpoints:
    - `GET /api/v1/session` → `{"user": Me | null}`, which also sets the CSRF cookie.
    - `POST /api/v1/session/login` `{username, password}` → `{"user": Me}`.
    - `POST /api/v1/session/logout` → 204.
    - `POST /api/v1/session/change-password` `{old_password, new_password}` → 204.
  - `Me = {id, username, full_name, email, is_platform_admin, must_change_password, membership: {role, permissions: [str]} | null}`.
    `membership` is for the current host's institution only.

- [ ] **Step 1: Write failing tests**

```python
# sites/tests/test_hosts.py   (settings EDUMA_BASE_URL = http://eduma.test)
@pytest.mark.parametrize("host,expected", [
    ("eduma.test", ("platform", None)), ("eduma.test:4201", ("platform", None)),
    ("aster.eduma.test", ("institution", "aster")), ("Aster.EDUMA.test:80", ("institution", "aster")),
    ("a.b.eduma.test", ("unknown", None)), ("evil.com", ("unknown", None))])
def test_resolve(host, expected): assert resolve(host) == expected

def test_institution_url(settings):
    settings.EDUMA_BASE_URL = "http://localhost:4201"
    assert institution_url("aster") == "http://aster.localhost:4201"

# accounts/tests/test_auth.py — real sessions: client = APIClient(HTTP_HOST=...); client.get("/api/v1/session") first
def login(client, username, password=PASSWORD): return client.post("/api/v1/session/login", {...})

def test_platform_admin_signs_in_only_on_platform_host(world):
    assert login(host(None), world.platform_admin.username).status_code == 200
    r = login(host(world.a.slug), world.platform_admin.username)
    assert r.status_code == 400 and r.json()["detail"] == "Invalid login ID or password."

def test_member_signs_in_only_on_own_institution_host(world):
    assert login(host(world.a.slug), world.a_admin.username).status_code == 200
    assert login(host(world.b.slug), world.a_admin.username).json()["detail"] == "Invalid login ID or password."
    assert login(host(None), world.a_admin.username).json()["detail"] == "Invalid login ID or password."

def test_no_sign_in_on_unknown_host(world): ...           # nosuch.eduma.test → generic refusal
def test_member_of_suspended_institution_cannot_sign_in(world): ...   # setup allowed, suspended/archived refused
def test_session_reused_on_another_host_is_signed_out(world):
    c = host(world.a.slug); login(c, world.a_admin.username)
    c.defaults["HTTP_HOST"] = f"{world.b.slug}.eduma.test"
    assert c.get("/api/v1/session").json()["user"] is None
def test_suspension_signs_out_existing_session(world): ...  # login, set status suspended, GET session → user None
def test_revoked_membership_signs_out(world): ...
def test_first_password_must_be_changed(world):
    world.a_admin.must_change_password = True; world.a_admin.save()
    c = host(world.a.slug); login(c, world.a_admin.username)
    assert c.get("/api/v1/institution").json()["code"] == "password_change_required"
    assert c.post("/api/v1/session/change-password", {"old_password": PASSWORD, "new_password": "Brand-new-pass-77"}).status_code == 204
def test_login_requires_csrf(world): ...    # APIClient(enforce_csrf_checks=True) without token → 403
def test_login_is_audited(world): ...       # AuditEvent action "auth.login"
```

  `host(slug)` is a local helper: `APIClient(HTTP_HOST="eduma.test" if slug is None else f"{slug}.eduma.test")`.
  These tests use real sessions, not `force_authenticate`. `/api/v1/institution` does not exist until Task 7, but
  `PasswordChangeRequiredMiddleware` answers before URL routing, so the assertion holds now.

- [ ] **Step 2: Run** `.venv/bin/pytest -q`. Expected: FAIL.

- [ ] **Step 3: Implement `resolve`.**
  - Parse `EDUMA_BASE_URL` once with `urllib.parse.urlsplit`.
  - Strip the port, lowercase, and compare the host to the base host.
  - For a subdomain, require exactly one extra label that passes `validate_slug`.
  - `SiteMiddleware` looks up the `Institution` by slug (any state); a missing slug gives `unknown`.

- [ ] **Step 4: Implement the auth views** by copying SC `accounts/views/auth.py`, `throttles.py`, `serializers.py`,
  then changing:
  - **Login allow rule.** Allow if the site is platform and the user is a platform admin, or the site is an
    institution, its state is in `SIGN_IN_STATES` and `active_membership` exists. Otherwise give the generic refusal
    (`Problem(400, "invalid_credentials", "Invalid login ID or password.")`). The switched-off message stays only for
    an inactive user with a correct password who would otherwise be allowed.
  - **Session binding.** After `login()`, set `request.session["site"] = request.site_key`.
  - **Throttle cache keys** include the client IP or login ID as in SC.

- [ ] **Step 5: Middleware order.** `SiteMiddleware` comes right after `SecurityMiddleware`. `SessionSiteMiddleware`
  and `PasswordChangeRequiredMiddleware` come right after `AuthenticationMiddleware`.

- [ ] **Step 6: Run** `.venv/bin/pytest -q`. Expected: PASS.
- [ ] **Step 7: Commit** `git commit -m "Host-based tenancy, site-bound sessions and sign-in rules"`.

---

### Task 4: Theme maths, content schema and starter content (pure logic)

**Files:**
- Create: `backend/sites/{theme,content,starter,eduma_content}.py`, `backend/sites/tests/{test_theme,test_content}.py`

**Interfaces:**
- Produces:
  - `sites.theme.INK = "#17132B"`, `WHITE = "#FFFFFF"`.
  - `HEADING_FONTS: dict[str, str]`, mapping code to label, e.g. `{"bricolage": "Bricolage Grotesque", ...}`.
    `BODY_FONTS` likewise.
  - `DEFAULT_THEME = {"primary_color": "#4B5AE4", "secondary_color": "#FFD43B", "heading_font": "bricolage", "body_font": "dm-sans"}`.
  - `contrast(a: str, b: str) -> float`: WCAG 2.x relative-luminance ratio.
  - `readable_on(color: str) -> str`: returns `WHITE` or `INK`, whichever has the higher contrast.
  - `text_safe(color: str, background: str = WHITE, target: float = 4.5) -> str`: returns `color` if it already meets
    `target`; otherwise lowers HSL lightness by 0.02 per step (`colorsys`) until it does, returning uppercase
    `#RRGGBB`.
  - `derive(primary: str, secondary: str) -> dict` with keys `on_primary`, `primary_text`, `on_secondary`,
    `secondary_text`. The API theme object is the 4 stored fields plus these 4; the frontend `Theme` type matches.
  - `sites.content.SECTION_TYPES = ("hero", "offerings", "steps", "people", "gallery", "testimonials", "feature", "faq")`.
  - `STEP_ICONS = ("apply", "calendar", "chat", "book", "check", "star", "users", "home", "award", "map")`.
  - `validate_content(data: dict) -> dict`: DRF serializers, one per section type, with the spec section 5 limits;
    raises `ValidationError` with paths like `sections.2.items.0.cta.href`.
  - `referenced_assets(content: dict) -> set[str]`: every `asset` id found anywhere.
  - `validate_href(value: str) -> str`: allowed prefixes `https://`, `http://`, `mailto:`, `tel:`, `#`, `/` (but not
    `//`).
  - `sites.starter.starter_content(display_name: str, category: str) -> dict`: valid content in which `people` and
    `testimonials` are present with `visible=False`.
  - `sites.eduma_content.EDUMA_CONTENT: dict`: valid content for Eduma's own page:
    - **hero:** eyebrow `Schools · Colleges · Engineering · Universities`; a title about running the whole
      institution in one place; CTA "Talk to us" → `mailto:` + `settings.EDUMA_CONTACT_EMAIL`, inserted at request
      time, not import time.
    - **offerings:** the four institution types.
    - **steps:** onboarding in four steps.
    - **feature:** a dark band on teacher–parent communication and teacher-led classes, stated as the product's
      direction without claiming it is live.
    - **faq:** 5 questions. Answers to "Is it live?" style questions must be honest that modules are rolling out.
    - No numbers or ratings.

- [ ] **Step 1: Write failing tests**

```python
def test_contrast_known_pairs():
    assert contrast("#FFFFFF", "#000000") == pytest.approx(21.0)
    assert contrast("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.01)
    assert contrast("#4B5AE4", "#FFFFFF") == pytest.approx(5.41, abs=0.02)

def test_readable_on():
    assert readable_on("#4B5AE4") == "#FFFFFF"
    assert readable_on("#FFD43B") == "#17132B"

def test_text_safe_darkens_only_when_needed():
    assert text_safe("#4B5AE4") == "#4B5AE4"
    darker = text_safe("#FFD43B")
    assert contrast(darker, "#FFFFFF") >= 4.5 and darker != "#FFD43B"

def test_hero_must_be_first_and_visible(): ...           # ValidationError path "sections"
def test_duplicate_section_type_rejected(): ...
def test_javascript_href_rejected():
    with pytest.raises(ValidationError) as e: validate_content(with_hero_cta("javascript:alert(1)"))
    assert "sections.0.primary_cta.href" in str(e.value.detail)
def test_item_limits(): ...                               # 7 offerings items → error; 12 faq ok, 13 → error
def test_starter_and_eduma_content_are_valid():
    for category in Category.values: validate_content(starter_content("Aster School", category))
    validate_content(EDUMA_CONTENT)
def test_starter_has_no_numbers_in_hero(): ...            # no digits in hero badge/title (no invented metrics)
```

- [ ] **Step 2: Run** `.venv/bin/pytest sites -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Starter wording differs by category: school uses "Admissions", grades and "parents"; the
  higher-education categories use programmes, departments and "students". The `eyebrow` is
  `Admissions open · 2027–28` (a year label, not a metric).
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Theme contrast maths, page content schema and starter content"`.

---

### Task 5: Site revisions: draft, save, publish, history, restore

**Files:**
- Create: `backend/sites/{models,services,serializers,views,urls}.py`, `backend/sites/tests/test_revisions.py`
- Modify: `backend/config/urls.py`

**Interfaces:**
- Consumes: Task 4 `validate_content`, `derive`, `DEFAULT_THEME`, the font dicts; Task 3 `PlatformAdmin`,
  `member_with`.
- Produces:
  - `sites.models.SiteRevision(VersionedModel)` and `BrandAsset` (UUID pk), per spec section 3. `SiteRevision` has
    partial unique constraints `one_draft_per_institution` and `one_published_per_institution`, and
    `UniqueConstraint(institution, number)`.
  - `sites.services`, every one transactional and locking the institution's revisions with `select_for_update`:
    - `get_or_create_draft(institution, actor) -> SiteRevision`: copies the published revision, or the
      `DEFAULT_THEME` plus starter content when there is none.
    - `save_draft(institution, actor, version: int, data: dict) -> SiteRevision`: data holds the 4 theme fields, a
      `logo` id or `None`, and `content`. Every referenced asset id, plus the logo, must belong to the institution,
      else 422 on `logo` or `content`.
    - `publish(institution, actor, version: int) -> SiteRevision`: audit `site.published`.
    - `restore(institution, actor, revision_id) -> SiteRevision`: overwrites the draft (creating it if needed) with
      that revision's theme, logo and content. Audit `site.restored`.
  - `SiteRevisionSerializer` output: `{id, number, status, version, theme: {primary_color, secondary_color, heading_font, body_font, on_primary, primary_text, on_secondary, secondary_text}, logo: {id, url} | null, content, created_at, published_at, published_by_name}`.
    PUT takes the 4 stored theme fields at the top level: `{version, primary_color, secondary_color, heading_font, body_font, logo, content}`.
  - Routes, the same views under two prefixes:
    - `api/v1/platform/institutions/<uuid:institution_id>/site/…`, with `PlatformAdmin`.
    - `api/v1/institution/site/…`, with `member_with("institution_brand.update")`.
    - Paths: `draft` (GET, PUT), `draft/publish` (POST), `revisions` (GET), `revisions/<uuid:revision_id>/restore`
      (POST).
  - `sites.views.InstitutionScopedView` mixin: `institution()` returns the platform-path institution, 404 if missing,
    or `request.institution`.

- [ ] **Step 1: Write failing tests**

```python
def test_draft_created_from_defaults_then_published(world):
    c = client_for(world.a.slug, world.a_admin)
    d = c.get("/api/v1/institution/site/draft").json()
    assert d["status"] == "draft" and d["theme"]["primary_color"] == "#4B5AE4" and d["theme"]["on_primary"] == "#FFFFFF"
    p = c.post("/api/v1/institution/site/draft/publish", {"version": d["version"]}).json()
    assert p["status"] == "published"

def test_publish_supersedes_previous(world): ...   # publish twice → first is superseded, numbers 1,2
def test_stale_save_is_409_with_current_version(world):
    d = c.get(draft).json(); c.put(draft, {**payload, "version": d["version"]})
    r = c.put(draft, {**payload, "version": d["version"]})
    assert r.status_code == 409 and r.json()["current_version"] == d["version"] + 1
def test_restore_copies_old_revision_into_draft(world): ...
def test_platform_admin_edits_any_institution_via_platform_path(world):
    c = client_for(None, world.platform_admin)
    assert c.get(f"/api/v1/platform/institutions/{world.b.id}/site/draft").status_code == 200
def test_wrong_host_is_404(world):
    assert client_for(world.a.slug, world.platform_admin).get(f"/api/v1/platform/institutions/{world.a.id}/site/draft").status_code == 404
    assert client_for(None, world.a_admin).get("/api/v1/institution/site/draft").status_code == 404
def test_member_of_a_cannot_reach_b_draft_on_b_host(world):
    assert client_for(world.b.slug, world.a_admin).get("/api/v1/institution/site/draft").status_code == 403
def test_bad_theme_rejected(world): ...           # "#12345", font "comic-sans" → 422 fields primary_color / heading_font
```

- [ ] **Step 2: Run** `.venv/bin/pytest sites -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the models (with migration), services, serializer and views. Run `makemigrations sites`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Site revisions: draft, publish, history and restore"`.

---

### Task 6: Brand image uploads, public site and public assets

**Files:**
- Create: `backend/sites/images.py`, `backend/sites/tests/{test_assets,test_public}.py`
- Modify: `backend/sites/{services,views,urls}.py`

**Interfaces:**
- Produces:
  - `sites.images.clean_image(upload) -> tuple[ContentFile, dict]`, where the dict is
    `{content_type, width, height, byte_size, sha256, ext}`.
    - Rejects files over 5 MB, unreadable files, formats outside PNG/JPEG/WEBP, and images larger than 4000×4000.
    - Guards against decompression bombs (`Image.MAX_IMAGE_PIXELS = 4000 * 4000` plus catching
      `Image.DecompressionBombError`, `UnidentifiedImageError` and `OSError`).
    - Re-encodes with Pillow to the detected format, without EXIF.
    - Raises `ValidationError({"file": [...]})`.
  - `POST …/site/assets` (multipart field `file`) → 201 `{id, url, width, height}`.
  - `GET /api/v1/public/assets/<uuid>`:
    - 200 with `Cache-Control: public, max-age=31536000, immutable` when the institution's state is `setup` or
      `active`; otherwise 404.
    - `X-Content-Type-Options: nosniff`.
  - `GET /api/v1/public/site`: the payload per spec section 5 table. `logo_url` and image `url`s are
    `/api/v1/public/assets/<id>`.
    - Content image items get `url` added next to `asset` in the response; the stored content is not changed.
    - Platform content is `EDUMA_CONTENT` with the mailto filled in.

- [ ] **Step 1: Write failing tests**

```python
def test_upload_png_strips_exif_and_records_hash(world, tmp_path): ...  # JPEG with EXIF → stored file has no EXIF
def test_rejects_non_image_disguised_as_png(world): ...       # b"%PDF..." named logo.png → 422 field "file"
def test_rejects_empty_and_oversize_and_bomb(world): ...      # 0 bytes; 6 MB; 5000x5000 → 422, BrandAsset count 0
def test_asset_of_b_cannot_be_used_in_a_draft(world): ...     # 422 on "logo"
def test_public_site_platform(world):
    body = client_for(None).get("/api/v1/public/site").json()
    assert body["kind"] == "platform" and body["content"]["sections"][0]["type"] == "hero"
@pytest.mark.parametrize("state,mode", [("active", "full"), ("setup", "opening_soon"), ("suspended", "unavailable")])
def test_public_site_modes(world, state, mode): ...
def test_public_site_archived_or_unknown_is_404(world): ...
def test_active_site_shows_published_not_draft(world): ...    # edit draft title; public still shows published title
def test_public_asset_served_only_while_setup_or_active(world): ...
```

- [ ] **Step 2: Run** `.venv/bin/pytest sites -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `clean_image`, the upload view (both prefixes), `PublicSiteView` (`AllowAny`), and
  `public_asset`, which returns a `FileResponse`. Store files at `brand/<institution_id>/<uuid>.<ext>`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Brand image uploads, public site and public assets"`.

---

### Task 7: Onboarding API (platform institutions and an institution's own profile)

**Files:**
- Create: `backend/institutions/{services,serializers,views,urls}.py`, `backend/institutions/tests/test_onboarding.py`
- Modify: `backend/config/urls.py`

**Interfaces:**
- Consumes: `get_or_create_draft`/starter (Task 5), `institution_url`, `audit.log`, `validate_username`.
- Produces:
  - `institutions.services.create_institution(actor, data: dict, key: UUID) -> tuple[Institution, bool]`.
    - Returns `(institution, created)`.
    - `creation_hash` = sha256 of the canonical JSON of `data` with `admin.password` removed.
    - Same key and hash → `(existing, False)`. Same key with a different hash → `IdempotencyMismatch`.
    - Creates, in one transaction: the institution (`setup`), the admin user (`must_change_password=True`), the
      membership, and a draft revision (theme defaults, `starter_content`).
    - Audit `institution.created`.
  - `institutions.services.reset_admin_password(institution, actor, password: str) -> User`: the first active
    `INSTITUTION_ADMIN`; sets `must_change_password`; audit `membership.password_reset`. 409 `invalid_transition` if
    no admin exists.
  - `institutions.services.readiness(institution) -> list[dict]`, each item `{code, label, done}`:
    - `admin_ready` "Institution Admin has signed in and changed their first password": an active admin membership
      whose user has `last_login` and not `must_change_password`.
    - `site_published` "Public page is published".
    - `contacts` "Contact email and phone are filled in".
  - Serializers:
    - `InstitutionCreateSerializer`: identity, contacts, slug, optional codes, nested
      `admin {full_name, username, email, mobile, password}`. Validates slug and username availability; the password
      goes through Django validators. Field errors are nested (`admin.username`).
    - `InstitutionSerializer`: adds `url`, `lifecycle_status`, `status_reason`, `activated_at`, `version`,
      `readiness`, `admin: {id, username, full_name, must_change_password, last_login} | null`.
    - `InstitutionListSerializer`: `id`, `display_name`, `slug`, `url`, `category`, `lifecycle_status`,
      `created_at`, `ready` (bool).
    - `InstitutionProfileSerializer`: `contact_email`, `contact_phone`, `address`, `version`.
  - Endpoints (platform host, `PlatformAdmin`):
    - `GET /api/v1/platform/institutions` (`?search=` on display name, legal name or slug, at least 3 characters;
      `?category=`; `?status=`; `Pages`).
    - `POST` (requires the `Idempotency-Key` UUID header, else 400 `invalid_request`) → 201, or 200 on a replay.
    - `GET`/`PATCH /api/v1/platform/institutions/<id>`: PATCH needs `version`; `slug` is editable only in `setup`
      (otherwise 409 `invalid_transition`); audit `institution.updated` with changed field names.
    - `GET /api/v1/platform/institutions/slug-check?slug=x` → `{available: bool, reason: str}`.
    - `POST /api/v1/platform/institutions/<id>/admin-password` `{password}` → 204.
  - Endpoints (institution host): `GET /api/v1/institution` with `member_with("institution.read")` →
    `InstitutionSerializer` without `admin`. `PATCH` with `member_with("institution_profile.update")` →
    `InstitutionProfileSerializer`.

- [ ] **Step 1: Write failing tests**

```python
PAYLOAD = {"legal_name": "Aster School Trust", "display_name": "Aster School", "category": "school",
           "slug": "aster-school", "contact_email": "office@aster.example", "contact_phone": "+91 90000 00000",
           "address": "1 Lake Road", "admin": {"full_name": "Asha Rao", "username": "aster-school.admin",
           "password": "First-pass-2026"}}

def test_create_is_atomic_and_complete(world):
    r = platform(world).post(URL, PAYLOAD, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid4()))
    assert r.status_code == 201
    inst = Institution.objects.get(slug="aster-school")
    assert inst.lifecycle_status == "setup" and r.json()["url"] == "http://aster-school.eduma.test"
    admin = User.objects.get(username="aster-school.admin")
    assert admin.must_change_password and has_perm(admin, inst, "institution_brand.update")
    assert SiteRevision.objects.get(institution=inst).status == "draft"

def test_retry_with_same_key_returns_same_institution(world): ...     # 201 then 200, one institution, one user
def test_same_key_different_body_is_409(world): ...                  # code idempotency_mismatch
def test_taken_slug_or_username_writes_nothing(world): ...           # 422 errors field "slug" / "admin.username"; counts unchanged
def test_missing_idempotency_key_is_400(world): ...
def test_list_search_needs_three_chars_and_filters(world): ...       # "as" ignored; "ast" finds; ?status=setup
def test_slug_check(world): ...                                      # taken → available False; "www" → reserved
def test_slug_locked_after_setup(world): ...                         # active institution PATCH slug → 409
def test_reset_admin_password_forces_change(world): ...
def test_institution_admin_reads_and_edits_own_profile(world): ...   # GET /api/v1/institution; PATCH with version
def test_platform_routes_refuse_institution_admin(world): ...        # on platform host with a_admin → 403
```

- [ ] **Step 2: Run** `.venv/bin/pytest institutions -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Put the forced-password assertion from Task 3 against `/api/v1/institution` here if it
  was deferred.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Onboarding API: create institution with admin and starter page"`.

---

### Task 8: Lifecycle transitions, platform overview and audit lists

**Files:**
- Create: `backend/institutions/tests/test_lifecycle.py`, `backend/common/tests/test_audit_api.py`
- Modify: `backend/institutions/{services,views,urls}.py`, `backend/common/{views,serializers}.py`

**Interfaces:**
- Produces:
  - `institutions.services.transition(institution_id, actor, *, to: str, reason: str, version: int, override_reason: str = "") -> Institution`.
    - Allowed moves:
      - `setup` → `active`;
      - `active` → `suspended`;
      - `suspended` → `active`;
      - `setup`, `active` or `suspended` → `archived`.
    - Every move needs a non-blank `reason` (422 on `reason`).
    - `setup` → `active` with unmet readiness and a blank `override_reason` → 422 on `override_reason` with
      "Readiness checks are not complete: <labels>. Give an override reason to activate anyway."
    - `suspended` → `active` without an active admin → `InvalidTransition`.
    - Sets `status_reason`, and `activated_at` on first activation.
    - Audit actions:
      - `institution.activated`;
      - `institution.suspended`;
      - `institution.reactivated`;
      - `institution.archived`.

      `changes` carries `{"from", "to", "reason", "override_reason"}`.
  - `POST /api/v1/platform/institutions/<id>/transition` → `InstitutionSerializer`.
  - `GET /api/v1/platform/overview` → `{counts: {setup, active, suspended, archived}, needs_action: [{id, display_name, slug, missing: [label]}]}`.
    `needs_action` lists `setup` institutions only, oldest first, at most 20.
  - `GET /api/v1/platform/audit` (`PlatformAdmin`, `Pages`, `?search=` on summary or actor name, `?action=` prefix,
    `?institution=<uuid>`) → `{id, at, actor_name, institution_name, action, summary, changes}`.
  - `GET /api/v1/platform/institutions/<id>/audit` is the same list filtered to that institution.

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.parametrize("start,to,ok", [("setup","active",True), ("active","suspended",True), ("suspended","active",True),
    ("active","archived",True), ("archived","active",False), ("setup","suspended",False), ("active","active",False)])
def test_transition_table(world, start, to, ok): ...      # not ok → 409 invalid_transition

def test_activation_needs_readiness_or_override(world):
    inst = factories.institution(lifecycle_status="setup")
    r = post_transition(inst, "active", reason="Go live")
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "override_reason"
    r = post_transition(inst, "active", reason="Go live", override_reason="Pilot demo")
    assert r.json()["lifecycle_status"] == "active"
    assert AuditEvent.objects.filter(action="institution.activated", changes__override_reason="Pilot demo").exists()

def test_reason_required(world): ...
def test_stale_version_is_409(world): ...
def test_overview_counts_and_needs_action(world): ...
def test_audit_list_is_platform_only_and_filters(world): ...  # institution admin on its host → 404 for /platform/audit
```

- [ ] **Step 2: Run** `.venv/bin/pytest -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/bin/pytest -q`, then lint with
  `.venv/bin/pip install ruff && .venv/bin/ruff check --select F,E,W,I --line-length 120 --exclude .venv,*/migrations .`
  (ruff is not added to requirements, as in SC). Expected: PASS, no lint errors.
- [ ] **Step 5: Commit** `git commit -m "Institution lifecycle, platform overview and audit lists"`.

---

### Task 9: Demo seed, README and launch config

**Files:**
- Create: `backend/institutions/management/commands/seed_demo.py`, `backend/institutions/tests/test_seed.py`,
  `README.md`, `.claude/launch.json`

**Interfaces:**
- Produces:
  - `python manage.py seed_demo`, which is idempotent and raises `CommandError` when `settings.DEBUG` is false.
  - It creates:
    - `eduma.admin` (platform admin, "Eduma Platform Admin");
    - four institutions with admins `<slug>.admin`, all with password `Demo-pass-2026` and
      `must_change_password=False`, except Vector, which has it `True` and no `last_login`.
  - Every run resets the demo passwords.

  | slug | display name | category | state | primary / secondary | heading / body |
  |---|---|---|---|---|---|
  | `aster` | Aster School | school | active, published | `#5B3FD9` / `#FFC93C` | fredoka / nunito |
  | `meridian` | Meridian College | college | active, published | `#0F766E` / `#F9A8D4` | fraunces / source-sans |
  | `vector` | Vector Engineering College | engineering_college | setup, draft only | `#1D4ED8` / `#FDE047` | space-grotesk / inter |
  | `summit` | Summit University | university | active, published | `#7C2D12` / `#FCD34D` | playfair / lora |

- [ ] **Step 1: Write the failing test** `test_seed_runs_twice_without_duplicates(db, settings)`: with
  `settings.DEBUG = True`, call `call_command("seed_demo")` twice and assert 4 institutions, 5 users and 3 published
  revisions. With `DEBUG = False`, assert it raises `CommandError`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Use `create_institution` for new institutions (fixed creation keys
  `uuid5(NAMESPACE_DNS, "<slug>.eduma.demo")`), then `save_draft` and `publish` with the theme above.
- [ ] **Step 4: Write `README.md`**, modelled on SC's README:
  - What you need: Docker, Python 3.12, Node 24+.
  - First-time setup: DB, venv, migrate, seed, `npm install`.
  - Running: API on 8001, `npm start` on 4201.
  - URLs: `http://localhost:4201` (Eduma), `http://localhost:4201/login` (platform, unlinked),
    `http://aster.localhost:4201` and so on. Note: use Chrome or Firefox; Safari may not resolve `*.localhost`.
  - Demo logins table.
  - Tests.
  - Settings (env vars).

  Write `.claude/launch.json` with `backend` (`backend/.venv/bin/python backend/manage.py runserver 8001`, port 8001)
  and `frontend` (`npm --prefix frontend start`, port 4201).
- [ ] **Step 5: Run** `.venv/bin/pytest -q`, then `.venv/bin/python manage.py migrate && .venv/bin/python manage.py
  seed_demo`, then `curl -s -H 'Host: aster.localhost:8001' localhost:8001/api/v1/public/site | head -c 200` with the
  server running. Expected: tests pass and the JSON contains `"display_name":"Aster School"`.
- [ ] **Step 6: Commit** `git commit -m "Demo seed and README"`. `.claude/` is gitignored, so `launch.json` stays
  local.

---

### Task 10: Frontend foundation (project, fonts, tokens, shared UI, problem errors)

**Files:**
- Create:
  - `frontend/` config: `package.json`, `angular.json`, `proxy.conf.json`, `tsconfig*.json`
  - `src/index.html`, `src/main.ts`, `src/styles.scss`, `src/styles/{_tokens,_base,_components,_fonts}.scss`
  - `src/app/{app.ts,app.config.ts,app.routes.ts}`, `src/app/core/{api/api.ts,api/types.ts,api-error.ts,load.ts,navigation-history.ts,format.ts}`
  - `src/app/ui/*` (copied list), `src/app/core/api-error.spec.ts`
  - `public/eduma-logo.png` (copy of `logo_eduma.png`)

**Interfaces:**
- Produces:
  - `Api` (SC): base path `/api/v1/`.
  - `load()` (SC).
  - `NavigationHistory` (SC).
  - UI components with SC selectors: `app-icon`, `app-page-header`, `app-search-box`, `app-pager`, `app-empty-state`,
    `app-load-error`, `app-reveal`, `app-status-badge`, `app-confirm-host`, `app-toast-host`; plus `ToastService`
    and `ConfirmDialog`.
  - `apiErrorMessage(err) -> string`: reads problem `detail`; prefers `errors[0].message` with the field as its label
    when `code === "validation_failed"`.
  - `fieldErrors(err) -> Record<string, string>` maps `errors[].field` to `message` for inline form errors.
  - `isProblem(err, code: string) -> boolean`.
  - `types.ts` holds the API shapes from Tasks 3–8. Names: `Me`, `SiteKind`, `Theme`, `Section`, `SiteContent`,
    `PublicSite`, `Revision`, `InstitutionListItem`, `InstitutionDetail`, `ReadinessItem`, `Overview`, `AuditItem`,
    `Page<T>`.
  - CSS tokens in `_tokens.scss`:
    - `--brand-primary`, `--brand-on-primary`, `--brand-primary-text`, `--brand-secondary`, `--brand-on-secondary`,
      `--brand-secondary-text`, `--font-heading`, `--font-body`, with Eduma defaults.
    - Derived `--brand-primary-soft: color-mix(in srgb, var(--brand-primary) 14%, white)`, `--brand-secondary-soft`
      (35%), `--canvas: color-mix(in srgb, var(--brand-primary) 6%, white)`.
    - `--ink: #17132B`, `--muted: #4A4560` (≥ 7:1 on white), `--border: #E4E1EE`.
    - Semantic colours from Global Constraints.
    - `--shadow-hard: 4px 4px 0 var(--ink)`.
    - Radii 12/20/28/pill.
  - `_fonts.scss` imports the `@fontsource-variable` weight CSS for all 11 fonts.

- [ ] **Step 1: Create the project.**
  - Copy SC `package.json`:
    - name `eduma`;
    - remove leaflet and SC's three fonts;
    - add `@fontsource-variable/{bricolage-grotesque,fredoka,plus-jakarta-sans,space-grotesk,fraunces,playfair-display,dm-sans,inter,nunito,source-sans-3,lora}`.
    - Check each package with `npm view <pkg> version`. For any that does not exist, use the static `@fontsource/<name>`
      package and record it in a comment in `_fonts.scss`.
  - Copy SC `angular.json`, renaming the project `frontend` and removing leaflet. In `serve.options`, set
    `"port": 4201`, `"host": "127.0.0.1"` and `"allowedHosts": [".localhost"]`.
  - `proxy.conf.json`: `{"/api": {"target": "http://127.0.0.1:8001", "secure": false, "changeOrigin": false}}`.
  - Copy the tsconfig files.
  - `index.html`: title `Eduma`, `meta robots` absent, favicon `eduma-logo.png`.
  - Run `npm install`.

- [ ] **Step 2: Write the failing test** `api-error.spec.ts`:

```ts
it('reads problem detail', () =>
  expect(apiErrorMessage({ status: 409, error: { code: 'version_conflict', detail: 'Reload the latest record and review your changes.' } }))
    .toBe('Reload the latest record and review your changes.'));
it('maps field errors', () =>
  expect(fieldErrors({ status: 422, error: { code: 'validation_failed', errors: [{ field: 'admin.username', code: 'invalid', message: 'Taken.' }] } }))
    .toEqual({ 'admin.username': 'Taken.' }));
it('says unreachable on status 0', () => expect(apiErrorMessage({ status: 0 })).toContain('Cannot reach the server'));
```

- [ ] **Step 3: Run** `npx ng test --watch=false`. Expected: FAIL.
- [ ] **Step 4: Implement** `api-error.ts`. Copy the listed core and ui files from SC: change `/api/` to `/api/v1/` in
  `Api`, and replace SC colour names with Eduma tokens. Write the tokens, base and components SCSS (buttons:
  `.btn-primary` filled `--brand-primary` with `--shadow-hard`, `.btn-secondary` outlined ink, `.pill`, `.card`,
  `.field`, `.badge-*`) and `app.ts` (from SC).
- [ ] **Step 5: Run** `npx ng test --watch=false && npx ng build`. Expected: tests pass; build succeeds (warnings
  about budgets are fine; raise `initial` to 800kB/1.5MB if fonts' CSS trips it).
- [ ] **Step 6: Commit** `git add frontend && git commit -m "Frontend foundation: fonts, tokens, shared UI, problem errors"`.

---

### Task 11: Site store, theming, auth store, guards and routes

**Files:**
- Create: `src/app/core/{site-store,auth-store,guards,session-interceptor}.ts` + specs,
  `src/app/features/public/notice-page.ts`
- Modify: `src/app/app.config.ts`, `src/app/app.routes.ts`

**Interfaces:**
- Consumes: `PublicSite`, `Me`, `Theme` types.
- Produces:
  - `FONT_FAMILIES: Record<string, string>` (codes → CSS family stack, e.g.
    `bricolage: "'Bricolage Grotesque Variable', system-ui, sans-serif"`).
  - `themeVariables(theme: Theme): Record<string, string>` → the 8 `--brand-*`/`--font-*` variables.
  - `SiteStore` (`@Service`):
    - `site = signal<PublicSite | null>`.
    - `kind = computed<'platform' | 'institution' | 'unknown'>`.
    - `load(): Promise<void>`: GETs `/api/v1/public/site`. A 404 sets kind `unknown`; other errors keep `unknown`
      with a retry message.
    - `apply(theme: Theme, logoUrl: string | null, title: string): void`: sets the variables on
      `document.documentElement`, the favicon `href`, and a document title suffix.
    - `institutionName(): string`.
  - `AuthStore` (from SC): endpoints `/api/v1/session`, `.../login`, `.../logout`, `.../change-password`. Exposes
    `isPlatformAdmin` and `isMember` computeds. `signOut()` goes to `/`.
  - Guards:
    - `signedIn`: no user → `/login`; must change password → `/change-password`.
    - `platformOnly`: kind platform and `is_platform_admin`, else `/`.
    - `memberOnly`: kind institution and membership, else `/`.
    - `guestOnly` (for `/login`): a signed-in user goes to `/console` or `/app`; kind `unknown` goes to `/`.
  - `sessionInterceptor` (SC) watches `/api/v1/` except `/api/v1/session` and `/api/v1/public/`.
  - Routes:
    - `''` → `LandingPage` (Task 12).
    - `login` (`guestOnly`).
    - `change-password` (`signedIn`).
    - `console` (Shell, `canActivateChild: [signedIn, platformOnly]`): children `''`, `institutions`,
      `institutions/new`, `institutions/:id`, `audit`.
    - `app` (Shell, `[signedIn, memberOnly]`): children `''`, `site`, `profile`.
    - `**` → `NoticePage` with `data: {kind: 'not-found'}`.
  - The app initializer awaits `site.load()` and then `auth.loadSession()`. It applies the Eduma theme for platform or
    unknown, and the institution theme otherwise.

- [ ] **Step 1: Write failing tests** (`site-store.spec.ts`, `guards.spec.ts`, `session-interceptor.spec.ts`), using
  `HttpTestingController` as SC's specs do:

```ts
it('maps a theme to CSS variables', () => {
  const vars = themeVariables({ primary_color: '#5B3FD9', on_primary: '#FFFFFF', primary_text: '#5B3FD9',
    secondary_color: '#FFC93C', on_secondary: '#17132B', secondary_text: '#8A6500', heading_font: 'fredoka', body_font: 'nunito' } as Theme);
  expect(vars['--brand-primary']).toBe('#5B3FD9');
  expect(vars['--font-heading']).toContain('Fredoka');
});
it('treats 404 as an unknown site', async () => { /* flush 404 → kind() === 'unknown' */ });
it('platformOnly sends an institution member home', () => { /* kind institution → UrlTree '/' */ });
it('guestOnly sends a signed-in platform admin to /console', () => {});
it('rechecks the session when a call is refused with 403', () => {});   // Review Focus 5
```

- [ ] **Step 2: Run** `npx ng test --watch=false`. Expected: FAIL.
- [ ] **Step 3: Implement.** `NoticePage` renders three messages from route data or the site mode:
  - `not-found`: "There is no Eduma site at this address."
  - `unavailable`: "<name> is temporarily unavailable."
  - `opening_soon`: handled by the landing page.

  Each message has the Eduma wordmark and no links.
- [ ] **Step 4: Run** the tests and `npx ng build`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Site store, theming, auth store, guards and routes"`.

---

### Task 12: Public page renderer and landing page

**Files:**
- Create: `src/app/features/public/{site-view,site-header,site-footer,image-slot,landing-page}.ts`,
  `src/app/features/public/sections/{hero,offerings,steps,people,gallery,testimonials,feature,faq}.ts`,
  `src/app/features/public/public.scss`, `site-view.spec.ts`

**Interfaces:**
- Consumes: `PublicSite`, `SiteContent`, `Section`, `SiteStore`.
- Produces:
  - `<app-site-view [site]="PublicSite" [preview]="boolean" />`: renders the header (logo or wordmark, and a "Sign in"
    link only when `site.kind === 'institution'` and not `preview`), the visible sections in order, and the footer.
    In `preview` mode links do not navigate.
  - `<app-image-slot [image]="{url?, alt}" [tone]="0|1|2" [icon]="string" />`: an `<img>` when there is a url,
    otherwise a tinted tile (`--brand-primary-soft`, `--brand-secondary-soft` or a mix) with an icon and an `alt`
    label.
  - `LandingPage`:
    - `mode === 'unavailable'` renders the `NoticePage` unavailable message.
    - `mode === 'opening_soon'` renders the header, the hero title only, "Opening soon" and the footer.
    - Otherwise it renders `<app-site-view>`.
  - Section anchors: `id="s-<section.id>"`, so `#<section-id>` links work.

- [ ] **Step 1: Write failing tests** `site-view.spec.ts`:

```ts
it('renders only visible sections in order', () => { /* content [hero, faq(hidden), steps] → DOM order hero, steps */ });
it('shows Sign in for an institution but not for the platform', () => {});
it('falls back to a tinted tile when an image has no url', () => {});
it('opening soon shows the hero title and no other sections', () => {});
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the reference look per spec section 6:
  - **Hero:** centred pill eyebrow; heading 64/68 px on desktop and 40/44 on phones, in `--font-heading` at weight
    800; subtitle; two CTAs; up to 3 image cards with 2 px ink borders, rotated -6°, 0° and 5° and overlapping on
    desktop, stacked straight on phones; round badge (`--brand-secondary`) overlapping the cards; stickers as small
    rotated pills.
  - **Offerings:** a 3-column card grid (1 column below 700 px), card colours cycling through 3 tones, an outlined
    full-width CTA per card, and tags as small pills.
  - **Steps:** a horizontal row of round icon badges joined by a dotted SVG path on desktop, a vertical list on phones.
  - **Testimonials:** sticky-note cards rotated ±2–4° in the 3 tones, with ★ ratings rendered as text plus an
    `aria-label`.
  - **Feature:** a full-bleed `--ink` band with white text and secondary-coloured pills.
  - **FAQ:** a two-column layout with `<details>` accordions.
  - **Footer:** `--ink` background.
  - Animations only under `prefers-reduced-motion: no-preference`, and only hover lift on cards.
- [ ] **Step 4: Run** the tests and `npx ng build`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Public page renderer and landing page"`.

---

### Task 13: Sign-in and change-password pages

**Files:**
- Create: `src/app/features/auth/{login-page,change-password-page}.ts` (+ html, scss), `login-page.spec.ts`

**Interfaces:**
- Consumes: `AuthStore.login/changePassword`, `SiteStore`, `fieldErrors`, `Reveal`.
- Produces:
  - `LoginPage`. The platform variant shows the Eduma logo and "Eduma platform sign-in", with no other links. The
    institution variant shows the institution logo or wordmark, "Sign in to <display name>", and a link back to `/`.
    On success it navigates to `/console`, `/app` or `/change-password`.
  - `ChangePasswordPage`: current password, new password and confirmation, with mismatch shown before submit. It
    explains why when forced ("Choose your own password before you continue."). On success it navigates to the user's
    home.

- [ ] **Step 1: Write failing tests**: the platform variant has no `a[href="/"]`; the institution variant shows the
  institution name; a refused login shows `Invalid login ID or password.` and keeps the typed login ID.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement**, modelled on SC `features/auth/login-page.*`: centred narrow card, `autocomplete`
  attributes, controls above the keyboard on phones.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Sign-in and change-password pages"`.

---

### Task 14: App shell (console and institution app)

**Files:**
- Create: `src/app/layout/{shell.ts,shell.html,shell.scss,nav.ts}`, `nav.spec.ts`

**Interfaces:**
- Produces:
  - `navFor(kind: 'platform' | 'institution'): NavItem[]`, where `NavItem = {label, icon, link, exact?}`:
    - platform: Overview `/console`, Institutions `/console/institutions`, Audit log `/console/audit`.
    - institution: Home `/app`, Public site `/app/site`, Profile `/app/profile`.
  - `Shell`:
    - A 248 px left sidebar showing the logo (Eduma's, or the institution's from `SiteStore`) and the name.
    - The account menu has the user's name, Change password and Sign out.
    - On an institution host the sidebar also has a "View public page" link to `/`.
    - Below 900 px it becomes a top bar plus drawer: focus is trapped while the drawer is open and Esc closes it.

- [ ] **Step 1: Write the failing test** `nav.spec.ts`: `navFor('platform').map(i => i.link)` equals the three console
  links; `navFor('institution')` equals the three app links.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement**, adapting SC `layout/shell.*`: replace the role-based nav with `navFor(site.kind())`, and
  use brand tokens for the active item (`--brand-primary-soft` background, `--brand-primary-text` text).
- [ ] **Step 4: Run** the tests and `npx ng build`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "App shell with left sidebar"`.

---

### Task 15: Console: overview, institutions list, onboarding wizard

**Files:**
- Create: `src/app/core/slug.ts` + spec, `src/app/features/console/{overview-page,institutions-page,onboarding-page}.ts`
  (+ html/scss), `onboarding-page.spec.ts`

**Interfaces:**
- Consumes: `/api/v1/platform/overview`, `/institutions` (list, create, slug-check), `SearchBox`, `Pager`.
- Produces:
  - `slugify(name: string): string`: lowercase; ASCII letters, digits and dashes only; collapses runs of dashes; trims
    to 40 characters; strips leading and trailing dashes; returns `''` if fewer than 3 characters remain.
  - `OverviewPage`: four count tiles labelled by state, and a "Needs action" list linking to
    `/console/institutions/:id`. The empty state reads "Nothing needs action."
  - `InstitutionsPage`:
    - SC search box (3 characters, debounced) and selects for category and state.
    - A table on desktop, cards on phones, and a pager.
    - The primary action is "Add institution".
    - Each row opens the detail page.
    - The URL shows as text with a copy button.
  - `OnboardingPage`:
    - Five steps (spec section 4): a stepper on desktop, "Step n of 5" on phones.
    - Per-step validation before Next.
    - The slug suggestion follows the display name until the slug field is edited by hand.
    - The slug-check result is shown inline, debounced 300 ms.
    - The admin login ID is suggested as `<slug>.admin`.
    - The password has a reveal toggle.
    - The Review step lists every value except the password.
    - Create sends `Idempotency-Key`, made once in the constructor with `crypto.randomUUID()`.
    - On 422 it jumps to the first step containing an errored field and shows the inline errors.
    - On success it navigates to `/console/institutions/<id>?tab=branding`.

- [ ] **Step 1: Write failing tests**

```ts
it('slugifies', () => {
  expect(slugify('Aster School, Vijayawada')).toBe('aster-school-vijayawada');
  expect(slugify('  St. Mary\'s  ')).toBe('st-marys');
  expect(slugify('श्री विद्या')).toBe('');                 // Review Focus 3
  expect(slugify('a'.repeat(60)).length).toBe(40);
});
it('reuses one idempotency key across retries', () => { /* two create attempts → same header value */ });
it('jumps to the admin step on admin.username error', () => {});
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `npx ng build`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Console: overview, institution directory and onboarding wizard"`.

---

### Task 16: Console: institution detail, lifecycle, password reset, audit

**Files:**
- Create: `src/app/features/console/{institution-page,lifecycle-dialog,audit-page}.ts` (+ html/scss),
  `lifecycle-dialog.spec.ts`

**Interfaces:**
- Consumes: `/api/v1/platform/institutions/<id>` (GET, PATCH, transition, admin-password, audit), `ConfirmDialog`.
  The Branding tab is created here empty and filled with the editor in Task 17.
- Produces:
  - `allowedMoves(status): {to, label, tone}[]`:
    - setup → Activate;
    - active → Suspend;
    - suspended → Reactivate;
    - setup, active or suspended → Archive.
  - `InstitutionPage`:
    - **Header:** name, state badge, URL (copy/open, opening the URL in a new tab), and lifecycle buttons from
      `allowedMoves`.
    - **Tabs** (Overview, Branding, Activity), with the tab kept in `?tab=` and the default `overview`.
    - **Overview tab:**
      - readiness checklist (✓/✗ with text);
      - profile form (edit with version, conflict → "This record changed" plus Reload);
      - admin card with "Reset password" (prompt for a new first password with reveal).
    - **Activity tab:** the institution's audit list.
  - `LifecycleDialog`:
    - Shows the named action ("Suspend Aster School"), its effect text and a required reason.
    - For Activate with unmet readiness it lists the unmet items and requires an override reason.
    - Submits `{to, reason, override_reason, version}`.
  - `AuditPage`: search (3 characters), action prefix select (`auth.`, `institution.`, `site.`, `membership.`),
    pager, table (when, who, institution, action, summary).

- [ ] **Step 1: Write failing tests**: `allowedMoves('setup')` gives Activate and Archive; `allowedMoves('archived')`
  is empty; the dialog's submit is disabled until a reason is entered, and until an override reason is entered when
  readiness is unmet.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `npx ng build`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Console: institution detail, lifecycle and audit log"`.

---

### Task 17: Site editor (shared by console and institution app)

**Files:**
- Create: `src/app/features/editor/{site-editor,theme-form,section-form,image-picker}.ts` (+ html/scss),
  `site-editor.spec.ts`
- Modify: `src/app/features/console/institution-page.*` (Branding tab)

**Interfaces:**
- Consumes: the Task 5/6 endpoints under `siteBase(scope)`, `<app-site-view>`, `fieldErrors`, `isProblem`.
- Produces:
  - `EditorScope = { kind: 'platform'; institutionId: string } | { kind: 'institution' }`.
  - `siteBase(scope): string` returns `platform/institutions/<id>/site` or `institution/site` (relative to
    `/api/v1/`).
  - `<app-site-editor [scope]="EditorScope" [institution]="{display_name, contact_email, contact_phone, address, slug}" />`.
  - State signals: `draft: Revision`, `form: {theme, logo, content}` (a deep copy), `dirty`, `saving`, `conflict`.
  - `moveSection(index: number, delta: -1 | 1)`: never moves the hero, and nothing can move above it.
  - `toggleSection(index)`: the hero cannot be hidden.
  - Item list add/remove within the limits; the Add button is disabled at the limit.
  - **Save draft:** `PUT` with the version. On 409, `conflict` is set and a banner reads "Someone else saved changes."
    with "Reload latest (discard mine)" and "Keep editing". Local edits are kept.
  - **Publish:** saves first if dirty, then publishes, then toasts "Published · your public page is live" (or
    "...will go live when the institution is activated" in `setup`).
  - **History:** a side panel listing revisions with Restore (confirm).
  - **Preview:**
    - `<app-site-view [site]="previewSite()" [preview]="true">` inside a container that sets the theme variables
      locally via `[style]`, so the console's own theme is untouched.
    - A desktop/phone width toggle (`100%` / `390px`).
    - On phones, Edit/Preview tabs.
  - **Unsaved changes:** a `canDeactivate` guard and a `beforeunload` handler ask before leaving.
  - `ThemeForm`:
    - colour inputs (native `<input type="color">` plus a hex text field);
    - a line under each colour: "Buttons use white text" or "Buttons use dark text", from `derive` returned on save
      (computed client-side for the live preview with the same rule, a copy of `readable_on` in TS);
    - heading and body font selects, each option rendered in its font;
    - logo picker.
  - `ImagePicker`: shows allowed types and size before choosing, upload progress, the 422 message inline, and Remove.

- [ ] **Step 1: Write failing tests**

```ts
it('keeps local edits on a 409 and offers reload', () => { /* flush 409 → conflict() true, form title unchanged */ }); // Review Focus 2
it('never moves a section above the hero', () => {});
it('cannot hide the hero', () => {});
it('disables Add at the item limit', () => { /* offerings with 6 items → add disabled */ });
it('preview applies the draft theme locally', () => { /* container style has --brand-primary = form colour */ });
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Section forms are one component switching on `section.type`, with fields per spec
  section 5 and `maxlength` attributes mirroring the server limits. Wire the editor into the console Branding tab with
  `{kind:'platform', institutionId}`.
- [ ] **Step 4: Run** the tests and `npx ng build`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Site editor with live preview, publish and history"`.

---

### Task 18: Institution app: home, public site, profile

**Files:**
- Create: `src/app/features/app/{home-page,site-page,profile-page}.ts` (+ html/scss), `home-page.spec.ts`

**Interfaces:**
- Consumes: `GET`/`PATCH /api/v1/institution`, `<app-site-editor [scope]="{kind:'institution'}">`.
- Produces:
  - `HomePage`:
    - Greeting with the institution name and state badge.
    - The setup checklist (readiness items with ✓/✗; items they can act on link to `/app/site` or `/app/profile`;
      "Activation is done by the Eduma team" when everything is ready but the state is still `setup`).
    - The public URL with a copy button.
  - `SitePage`: hosts the editor.
  - `ProfilePage`: contact email, phone and address, saved with version and conflict handling (as in Task 16's profile
    form; reuse one `ProfileForm` component if it fits without flags, otherwise keep two small forms).

- [ ] **Step 1: Write the failing test**: the checklist renders a link to `/app/site` for an unmet `site_published` item
  and the "Activation is done by the Eduma team" line when all items are done in `setup`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests and `npx ng build`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Institution app: home checklist, public site editor and profile"`.

---

### Task 19: End-to-end verification, decisions and progress docs

**Files:**
- Create: `docs/decisions.md`, `docs/progress.md`
- Modify: any file needed to fix defects found

- [ ] **Step 1: Run every automated check.** All must pass; fix and re-run until clean:
  - `cd backend && .venv/bin/pytest -q`
  - `ruff check` (Task 8 command)
  - `.venv/bin/python manage.py check --deploy --settings=config.settings` with `DJANGO_DEBUG=0
    DJANGO_SECRET_KEY=x-long-random-test-key-1234567890abcdef DJANGO_ALLOWED_HOSTS=.eduma.app`. Expected: no errors
    beyond the silenced ones.
  - `cd frontend && npx ng test --watch=false && npx ng build`

- [ ] **Step 2: Browser walk-through.** Start the `backend` and `frontend` launch configs, run `seed_demo`, and use the
  built-in browser at 1440 px and 390 px. Check each item and fix defects:
  - (a) `localhost:4201` shows the Eduma landing page with no sign-in link anywhere.
  - (b) `localhost:4201/login` as `eduma.admin`, then Overview, Institutions, and search "mer".
  - (c) Onboard a new institution with a 120-character display name (Review Focus 3), then the Branding tab: upload a
    logo (generate a PNG with Pillow in the scratchpad), change colours and fonts, edit the hero, publish, and Activate
    with an override reason.
  - (d) Open `http://<new-slug>.localhost:4201` and check the branded page and its Sign in link.
  - (e) Sign in as the new admin with the first password, which forces a change, then Home checklist, Public site, and
    Profile.
  - (f) Suspend that institution from the console while (e) is open; the institution tab returns to sign-in and its
    public page reads unavailable (Review Focus 5).
  - (g) Aster, Meridian and Summit pages each show their own fonts and colours.
  - (h) Keyboard only through the sign-in page, the wizard and the editor, checking that focus is visible.
  - (i) No horizontal scroll at 390 px on any of these pages.

  Take screenshots of the Eduma landing page (desktop) and the Aster landing page for the user.

- [ ] **Step 3: Write `docs/decisions.md`.** It is the successor to pack 14:
  - spec section 1 decisions S1-01 to S1-11, with the date (17 Oct 2026) and evidence ("user answers in chat");
  - pack defaults D-02, D-07, D-08, D-13, D-15 and D-18 as accepted for local development;
  - open items carried forward (D-01, D-03, D-05, D-06, D-12, D-14, D-16, D-17).

- [ ] **Step 4: Write `docs/progress.md`:**
  - Slice 1 status per task.
  - Test commands with their actual pass counts.
  - Browser evidence: what was checked, at which widths, and what was not checked (screen readers, Safari, real
    devices).
  - Known limitations: no AV scanner, no MFA, no RLS, no SSR, local subdomains only.
  - Next slice: BUILD-03 remainder.

- [ ] **Step 5: Commit** `git add -A && git commit -m "Slice 1 verification, decisions and progress"`.
