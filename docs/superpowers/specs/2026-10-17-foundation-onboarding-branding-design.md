# Eduma slice 1 — foundation, onboarding, institution URLs and branding

**Date:** 17 October 2026 · **Status:** design approved in chat on 17 Oct 2026; this written spec awaits review.
**Source pack:** `Eduma_Build_Pack/` (00–15, prompt.md), `Eduma_Decision_Register.md`, `logo_eduma.png`, the user's
"Zoomies" reference image (playful public pages).
**Covers:** BUILD-01 (foundation, identity, tenant context), BUILD-02 (platform onboarding and lifecycle) and the branding
part of BUILD-03. Screens SCR-001/002 (as host-based sign-in), 003 (password only), 004, 005, 006, 007, 011, 012.

Everything else in the 49-screen catalog stays in scope and follows in later spec → plan → build cycles (section 11).

## 1. Decisions taken for this slice

| ID | Decision | Supersedes |
|---|---|---|
| S1-01 | Stack as AP Police Student Connect: Angular 22 (zoneless, signals, Vitest), Django 6.1 + DRF 3.18, PostgreSQL 17 in Docker, hand-written SCSS components, fonts bundled with `@fontsource` (OFL only, no CDN). Layout `backend/`, `frontend/`, `docs/`. | D-10 (Angular Material/CDK); pack 12 `apps/web`, `apps/api` |
| S1-02 | `/` on the main domain always shows the Eduma landing page. It has no sign-in link. | — |
| S1-03 | `/login` on the main domain is unlinked and admits only platform (System Admin) accounts. Anyone else gets the generic "Invalid login ID or password." | — |
| S1-04 | Each institution has a subdomain: `<slug>.eduma.app` (locally `<slug>.localhost:4201`). Its page links to its own `/login`, which admits only that institution's members. | Route prefix `/i/:institutionId` (04) |
| S1-05 | The API takes the institution from the request host, not from `/api/v1/institutions/{id}`. Platform routes stay under `/api/v1/platform/`. | 09 section 1 institutional base |
| S1-06 | First sign-in uses a first password set by whoever creates the login, with a forced change before anything else (MTO style). | 02 section 7 / 03 WF-ONB step 6 (single-use invitation) |
| S1-07 | System Admin may edit any institution's branding and public page at any time, audited. Institution Admin edits its own. | 02 `institution_brand.update` "System Admin during setup" |
| S1-08 | Institution creation is one atomic, idempotent request (institution + admin login + membership + starter page). The `draft` and `provisioning` states are therefore unnecessary. | 03 WF-ONB steps 3–4 |
| S1-09 | Lifecycle states in this slice: `setup`, `active`, `suspended`, `archived`. `restricted` arrives with module entitlements; `deletion_pending`/`deleted` arrive with offboarding. | 03 WF-ONB (partial) |
| S1-10 | Public pages are a fixed set of section types, editable, hideable and reorderable. This is not a free-form page builder. The Eduma main page uses the same renderer with content kept in code. | — |
| S1-11 | Lists use the Student Connect page-number paginator, not opaque cursors. | 09 section 1 lists |

## 2. Hosts, sessions and sign-in

**Configuration.** `EDUMA_BASE_URL` (default `http://localhost:4201`) gives scheme, base host and port. An institution's
URL is `scheme://<slug>.<base host>[:port]`. Production would be `https://eduma.app`, which needs wildcard DNS and a
wildcard certificate (deployment task, not this slice).

**Site resolution** (`sites.middleware.SiteMiddleware`, after Django's host validation):

| Host (port ignored) | `request.site_kind` | `request.institution` |
|---|---|---|
| equals base host | `platform` | `None` |
| `<label>.<base host>`, single label, matches an institution slug | `institution` | that institution (any state) |
| anything else (unknown slug, nested labels) | `unknown` | `None` |

**Sessions.** Cookies are host-only (no `SESSION_COOKIE_DOMAIN`), so each subdomain has its own session and CSRF
cookie. At sign-in the session stores `site = "platform"` or the institution UUID.

`sites.middleware.SessionSiteMiddleware` signs the session out on the next request when any of these is true:
- the stored site differs from the current host's site;
- a platform session's user is no longer a platform admin;
- an institution session's membership is no longer active;
- the institution is no longer in a sign-in state (`setup`, `active`).

This one rule covers cross-host replay, suspension and revocation.

**Sign-in rules** (`POST /api/v1/session/login`):
- On the platform host, only active users with `is_platform_admin`.
- On an institution host, only users with an active membership there, while the institution is `setup` or `active`.
- On an unknown host, no one.
- Every refusal returns the same `Invalid login ID or password.` (no account enumeration).
- An inactive user who knows their password is told the login is switched off, as in Student Connect.
- Throttled per client IP and per login ID.

**First password.** Every login made for someone else has `must_change_password = true`. Until it is changed, every API
call except session, logout and change-password returns 403 `password_change_required`, and the app shows only the
change-password screen. Login IDs are lowercased; passwords are checked with Django's validators.

**CSRF.** The cookie is `XSRF-TOKEN` and the header `X-XSRF-TOKEN` (Angular defaults). Login also enforces CSRF.
`CSRF_TRUSTED_ORIGINS` includes the wildcard subdomain origin.

## 3. Data model

All new tables use UUID primary keys. Mutable records carry `created_at`, `updated_at` and an integer `version`
incremented on every update; a stale `version` returns 409 `version_conflict` with `current_version`.

**`accounts.User`** (custom user model; global login identity)
- `username`: login ID; unique, lowercased, matching `^[a-z0-9][a-z0-9._-]{2,39}$`.
- `full_name`, `email` (optional), `mobile` (optional).
- `is_platform_admin`, `must_change_password`, `created_by`.
- `is_active` is the on/off switch. Nobody is deleted.

**`accounts.Membership`**
- `institution`, `user`, `role` (`INSTITUTION_ADMIN` for now), `status` (`active`/`revoked`), `created_by`, `version`.
- Unique (`institution`, `user`).
- Permissions come from a code map `ROLE_PERMISSIONS = {"INSTITUTION_ADMIN": {"institution.read",
  "institution_profile.update", "institution_brand.update"}}`. Checks call `has_perm(membership, "<resource>.<action>")`.
  Platform admins hold the platform permissions (`institution.create`, `institution.activate`, `institution.suspend`,
  `institution_brand.update`, `audit.read`) by virtue of `is_platform_admin`.

**`institutions.Institution`**
- `slug`: unique, `^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$`, not in the reserved list (`www`, `api`, `app`, `admin`,
  `console`, `login`, `static`, `media`, `mail`, `eduma`, `platform`, `help`, `support`, `status`).
- `legal_name`, `display_name`.
- `category`: `school` / `college` / `engineering_college` / `university`.
- `country_code` (default `IN`), `timezone` (IANA, default `Asia/Kolkata`), `base_currency` (default `INR`).
- `contact_email`, `contact_phone`, `address`.
- `board_affiliation_code`, `udise_code`, `aishe_code`: optional; the last two are unique when present.
- `lifecycle_status`, `status_reason`, `activated_at`.
- `creation_key`: unique; the onboarding idempotency key.
- `created_by`, `version`.
- The slug can be edited only while the institution is in `setup`.

**`sites.SiteRevision`**
- `institution`, `number` (per institution), `status` (`draft` / `published` / `superseded`).
- Theme: `primary_color`, `secondary_color` (`#RRGGBB`), `heading_font`, `body_font` (enums, section 5).
- `logo` (FK `BrandAsset`, nullable), `content` (JSON, schema in section 5).
- `created_by`, `published_by`, `published_at`, `version`.
- Partial unique indexes: at most one `draft` and one `published` per institution.

**`sites.BrandAsset`**
- `institution`, `file`, `content_type`, `width`, `height`, `byte_size`, `sha256`, `uploaded_by`, `created_at`.

**`common.AuditEvent`** (append-only; no update/delete API)
- `at`, `actor`, `institution` (nullable), `action`, `object_type`, `object_id`, `summary`, `changes` (JSON of changed
  field names with safe before/after values; never passwords).

## 4. Onboarding and lifecycle

**Wizard** (`/console/institutions/new`) has four steps and a review:
1. **Identity and type:** legal name, display name, category. Identifier fields appear only where relevant: board code
   for schools, AISHE for colleges and universities, UDISE for schools.
2. **Contacts:** email, phone, address, country, timezone, currency.
3. **Web address:** slug suggested from the display name, live availability check
   (`GET /api/v1/platform/institutions/slug-check?slug=`) and a preview of the full URL.
4. **Institution Admin:** full name, login ID (suggested `<slug>.admin`), optional email and mobile, first password
   (with show/hide).
5. **Review and create.**

On phones the stepper becomes "Step n of 5" with Back/Next. Form state stays in memory only.

**Create** is `POST /api/v1/platform/institutions` with an `Idempotency-Key` header (a UUID generated when the wizard
opens). One transaction creates:
- the `Institution` (status `setup`);
- the admin `User` (`must_change_password`);
- the `Membership`;
- a draft `SiteRevision` built from the category's starter content, with the Eduma default theme;
- `AuditEvent`s.

A retry with the same key and the same body returns 200 with the original institution. The same key with a different
body returns 409 `idempotency_mismatch` (a hash of the body is stored with the key). A taken slug or login ID returns 422
with field errors and writes nothing. The wizard then opens the new institution's detail page on the **Branding** tab.

**Transitions:** `POST /api/v1/platform/institutions/{id}/transition` `{to, reason, version, override_reason?}`.

| From → to | Rule |
|---|---|
| `setup` → `active` | Readiness checklist must pass, or `override_reason` is required and recorded. Sets `activated_at`. |
| `active` → `suspended` | Reason required. Members are signed out on their next request (section 2). |
| `suspended` → `active` | Reason required. At least one active Institution Admin membership must exist. |
| `setup`/`active`/`suspended` → `archived` | Reason required. Final in this slice. |
| anything else | 409 `invalid_transition` |

**Readiness checklist** (shown on the detail page and the platform overview):
1. An active Institution Admin who has signed in and changed their first password.
2. A published public page.
3. A contact email and phone.

**Other platform actions on the detail page:**
- Edit profile (version-checked).
- Reset the Institution Admin's password (sets a new first password and `must_change_password`; audited).
- Copy URL.
- Open the public page.

## 5. Branding and public pages

**Theme**
- `primary_color` is used for CTAs, active navigation and links. `secondary_color` is used for highlights, pills and
  tiles. Eduma defaults: `#4B5AE4` (sampled from the logo) and `#FFD43B`.
- The server derives the readable variants and returns them with every theme:
  - `primary_fill` / `secondary_fill`: the colour text sits on. It is the colour itself when white or ink `#17132B`
    reaches 4.5:1 on it. Some mid-tones (e.g. `#E0393E`) reach only about 4.3:1 with either, so they get the same hue
    darkened until white text reaches 4.5:1. The stored colour is unchanged. (Corrected after the final review: the
    first version of this spec wrongly said white or ink always reaches 4.5:1.)
  - `on_primary` / `on_secondary`: whichever of white or ink has the higher contrast on the fill.
  - `primary_text` / `secondary_text`: the colour darkened in HSL lightness steps of 2% until it reaches at least
    4.5:1 on white. Used for links and coloured text.
- Semantic colours (danger, warning, success, info) and ink are fixed.
- Soft tints for tiles are made in CSS with `color-mix()`.

**Fonts** are bundled and curated (all OFL, via `@fontsource`):
- Headings: `bricolage` (Bricolage Grotesque, default), `fredoka`, `jakarta` (Plus Jakarta Sans), `space-grotesk`,
  `fraunces`, `playfair` (Playfair Display).
- Body: `dm-sans` (default), `inter`, `nunito`, `source-sans` (Source Sans 3), `lora`.

**Logo:** shown in the public page header, the sign-in page, the in-app sidebar and as the favicon. Without a logo the
display name is used as a wordmark.

**Content** is JSON `{ "sections": [...] }`, validated by serializers. Every section has `id`, `type`, `visible`,
`eyebrow` (≤40 characters) and `title` (≤120). Each type appears at most once, and `hero` is always first and visible.

| Type | Fields (limits) | Reference look |
|---|---|---|
| `hero` | `subtitle` ≤300; `primary_cta`, `secondary_cta?` {label ≤30, href}; `images` ≤3 {asset, alt}; `badge?` {value ≤12, label ≤24}; `stickers` ≤2 (≤24 each) | Big two-line headline, pill eyebrow, tilted photo cards, round badge |
| `offerings` | `subtitle?`; `items` ≤6 {title ≤60, text ≤200, image?, tags ≤3 (≤20), cta?} | Coloured cards with image, tags, outlined button |
| `steps` | `items` ≤6 {title ≤40, text ≤160, icon from a fixed set} | Dotted path with round icons |
| `people` | `subtitle?`; `items` ≤6 {name ≤60, role ≤60, photo?, facts ≤4 (≤80)} | Portrait cards |
| `gallery` | `images` ≤8 | Photo mosaic |
| `testimonials` | `items` ≤6 {quote ≤300, name ≤60, relation ≤60, rating? 1–5, photo?} | Tilted sticky notes in soft colours |
| `feature` | `text` ≤400; `bullets` ≤5 (≤80); `image?`; `cta?` | Dark band |
| `faq` | `subtitle?`; `cta?`; `items` ≤12 {q ≤160, a ≤600} | Accordion beside a heading |

- **Links (`href`):** must be `https://`, `http://`, `mailto:`, `tel:`, `#<section-id>` or a path starting with `/`.
  Anything else is rejected (422).
- **Images:** an image field with no asset renders a brand-tinted tile with an icon.
- **Footer:** generated from the profile (name, address, phone, email), plus "Sign in" (institution only) and
  "Powered by Eduma".
- **Starter content per category:** neutral, sensible wording ("Admissions open for 2027–28" style eyebrow, programmes,
  how admission works, FAQ). It contains no invented ratings, counts or quotes; testimonials and people start hidden
  with placeholder text.

**Revisions.** Opening the editor gets or creates the single draft, copied from the published revision.

| Endpoint | Behaviour |
|---|---|
| `GET …/site/draft` | Get or create the draft. |
| `PUT …/site/draft` | Save `{version, theme fields, logo, content}`. 409 on a stale version. |
| `POST …/site/draft/publish` | `{version}`. Draft becomes published; the old published revision becomes superseded. |
| `GET …/site/revisions` | History. |
| `POST …/site/revisions/{id}/restore` | Copy that revision into the draft. |
| `POST …/site/assets` | Multipart image upload. |

`…` is `/api/v1/platform/institutions/{id}` on the platform host and `/api/v1/institution` on the institution's own
host. Both use the same views; the institution comes from the path or the host.

**Uploads.**
- PNG, JPEG or WebP; at most 5 MB and 4000×4000 px.
- Opened with Pillow, which rejects anything that is not a real image of those types.
- Re-encoded to the same format, which strips EXIF and metadata; `sha256` is recorded.
- Stored under `MEDIA_ROOT/brand/<institution>/<uuid>.<ext>`.

**Asset access.** `GET /api/v1/public/assets/{uuid}` serves the file with long cache headers when its institution is
`setup` or `active`. Branding images are public by classification (pack 10 section 3).

Shortcut: no anti-virus scanner. Re-encoding is the content check. Upgrade to a scanner adapter when uploads accept
documents or other non-image files.

**Public site API.** `GET /api/v1/public/site` (any host):

| Host | Response |
|---|---|
| Platform | `{kind:"platform", theme, content, logo_url}`. Eduma's own content comes from a Python constant. |
| Institution in `active` | `{kind:"institution", mode:"full", institution:{slug, display_name, category, contact_email, contact_phone, address}, theme, content, logo_url}` from the **published** revision. |
| Institution in `setup` | Same shape with `mode:"opening_soon"`. If nothing is published yet, the draft's theme and logo are used, and only the hero title is shown. |
| Institution in `suspended` | `{kind:"institution", mode:"unavailable", institution:{display_name}}`. |
| Archived or unknown | 404 `not_found`. |

**Theme in the app.** At start-up the app calls `/api/v1/public/site`, then:
- sets the CSS variables `--brand-primary`, `--brand-on-primary`, `--brand-primary-text`, `--brand-secondary`,
  `--brand-on-secondary`, `--brand-secondary-text`, `--font-heading` and `--font-body` on `<html>`;
- sets the favicon and the document title suffix.

Signed-in screens on an institution host use the same variables. The console uses Eduma's theme.

## 6. Screens and navigation

**Public (any host)**
- `/`: landing (Eduma or institution), or the opening-soon / unavailable page.
- `/login`: sign-in. The platform variant shows the Eduma wordmark and has no links to it from anywhere. The institution
  variant is branded.
- `/change-password`: forced or voluntary.
- Unknown host or route: neutral not-found page.

**Console** (`/console`, platform host, platform admin). Left sidebar: Overview · Institutions · Audit log; account menu
with change password and sign out.
- **Overview:** counts by lifecycle state, plus a "Needs action" list of `setup` institutions with their unmet
  readiness items, each with a link.
- **Institutions:**
  - Search as you type from 3 characters (name, slug); filters for category and state.
  - Table with name, category, state, URL, created, readiness. Phones get cards.
  - Pagination. Primary action "Add institution".
- **Onboarding wizard** (section 4).
- **Institution detail:** a header with name, state badge, URL (copy, open) and lifecycle buttons, plus three tabs:
  - Overview: profile, readiness, admin and password reset;
  - Branding: the editor;
  - Activity: that institution's audit events.
- **Audit log:** search, an action-prefix filter, pagination.

**Institution app** (`/app`, institution host, active membership). Left sidebar with the institution logo:
- **Home:** setup checklist, status, quick links.
- **Public site:** the editor.
- **Profile:** edit contacts and address, with version check.
- Account menu.

Modules not built yet are not shown.

**Site editor** (shared component)
- Left column, in order:
  - Theme: colour inputs with hex and swatch, plus the derived contrast shown as "Text on this colour: white/dark"; the
    font selects; the logo upload.
  - Sections: an expandable list with show/hide toggles and up/down buttons (no drag-only reordering). Each section has
    a typed form, add/remove for item lists, and image slots (upload or remove).
- Right column: live preview using the real renderer at a selectable desktop or phone width.
- Actions: **Save draft** (shows "Draft saved · v{n}"), **Publish**, **History** (restore). Leaving with unsaved
  changes asks first.
- On phones the columns become tabs (Edit / Preview).

**Visual language**
- **Public pages** follow the reference:
  - a canvas tinted from the primary colour, with ink `#17132B`;
  - 2 px ink borders and a hard offset shadow `4px 4px 0` on cards and buttons, with 20 px rounding;
  - pill eyebrows with borders, slightly rotated photo and testimonial cards;
  - chunky heading font at 800 weight;
  - generous spacing, a dark feature band, and a footer.
  - No gradients, glows or glass.
- **Console and app** are calmer versions of the same language: white surfaces on a light canvas, 1 px borders with the
  hard shadow kept for primary buttons and key cards, a 248 px left sidebar (drawer on phones), page header with title
  and one primary action.
- **Shared rules:**
  - status always shown as text plus colour;
  - focus rings visible;
  - controls 44 px tall;
  - reduced motion respected;
  - nothing scrolls horizontally at 360 px except labelled tables.

## 7. Errors

All API errors use RFC 9457 problem details (`application/problem+json`) with `type`
`urn:eduma:problem:<code>`, `title`, `status`, `detail`, `code` and `errors[]` (`{field, code, message}`), plus
`current_version` on conflicts.

Codes in this slice:

| Code | When |
|---|---|
| `invalid_request` | Malformed request |
| `authentication_required` | 403, no session |
| `password_change_required` | 403, first password not yet changed |
| `permission_denied` | 403 |
| `not_found` | 404, including anything from another institution |
| `version_conflict` | 409, stale version |
| `invalid_transition` | 409, lifecycle move not allowed |
| `idempotency_mismatch` | 409, same key with a different body |
| `validation_failed` | 422 |
| `rate_limited` | 429 |

The frontend shows field errors inline and others in a toast, and keeps form input after any failure.

## 8. Security checklist for this slice

- Every platform endpoint requires the platform host and a platform admin; on an institution host it returns 404.
- Every institution endpoint requires the institution host, an active membership and the permission; on the platform
  host it returns 404.
- Branding endpoints for platform admins resolve the institution from the path under `/platform/`. Assets and revisions
  are always filtered by that institution, so an asset UUID from institution A can never attach to B's revision
  (validated as 422).
- Session binding to the site (section 2), CSRF on login, throttling, host-only cookies.
- Production settings as in Student Connect:
  - HTTPS redirect, HSTS, secure cookies;
  - DEBUG refused on public hosts;
  - placeholder secret key refused;
  - Django admin off unless `DJANGO_ADMIN=1`.
- Audit for sign-in, password change, institution create/update/transition, admin password reset, site publish and
  restore.
- No passwords in audit or logs.
- The seed command refuses to run with `DEBUG=0`.

## 9. Tests and evidence

**Backend (pytest, real PostgreSQL)**
- **Host resolution:** platform, slug, unknown, nested labels, port handling.
- **Sign-in matrix:** platform admin on platform; member on own host; member on another host; platform admin on an
  institution host; non-member; inactive; setup versus suspended institution.
- **Session handling:** reuse across hosts is signed out; the forced password change is enforced.
- **Onboarding:** atomic create; idempotent retry; mismatch returns 409; slug and login-ID validation write nothing
  (TST-001).
- **Lifecycle:** every allowed and refused transition; readiness override; suspension locks members out; reactivation
  needs an admin.
- **Isolation (TST-002 subset):** platform routes from an institution host and institution routes from the platform
  host return 404; another institution's asset is rejected; another institution's revision is not found.
- **Branding:**
  - contrast maths against known WCAG pairs;
  - theme and content validation (bad hex, unknown font, `javascript:` href, too many items, duplicate type, hero not
    first);
  - save, conflict, publish, supersede, restore;
  - upload rejects a non-image, an oversize file or a disguised MIME type, and strips EXIF;
  - public site responses for each lifecycle state;
  - the asset endpoint for each state.
- **Audit:** events written for each audited action; the audit list is platform-only.

**Frontend (Vitest)**
- The site store applies theme variables.
- Guards (site kind × user).
- The renderer shows only visible sections, in order, and falls back for empty images.
- The login variant follows the site kind.
- Slug suggestion.
- The problem-detail mapper.

**Browser:**
- Click through every screen as the platform admin and as an Institution Admin.
- Check at 390 px and 1440 px.
- Keyboard pass on the wizard, the editor and sign-in.
- Results recorded in `docs/progress.md` with what was and was not checked.

## 10. Local development

**Ports:**
- PostgreSQL 17 on `5434` (db, user and password `eduma`), next to MTO on 5432 and Student Connect on 5433.
- API on `8001`.
- Angular dev server on `4201`, with `allowedHosts` set to `.localhost` and the proxy forwarding `/api` to
  `localhost:8001` with the original `Host` kept.

**Browser:** Chrome and Firefox resolve `*.localhost` to 127.0.0.1. Safari may not; use Chrome.

**`python manage.py seed_demo`** is idempotent and refuses to run with `DEBUG=0`. It creates:
- Platform admin `eduma.admin`.
- Four synthetic institutions from pack 11, each with its own colours and fonts:
  - Aster School: school, active, published.
  - Meridian College: college, active, published.
  - Vector Engineering College: engineering college, setup; its admin has not signed in yet.
  - Summit University: university, active, published.
- Admin logins `<slug>.admin`.
- Every demo login uses the password `Demo-pass-2026`.
- No photos of real people; image slots use the tinted fallback.

**Docs:**
- `README.md`: setup, run, demo logins, subdomain note, tests.
- `docs/decisions.md`: register successor to pack 14.
- `docs/progress.md`: durable progress and evidence file required by prompt.md.

## 11. Not in this slice (remaining backlog, unchanged in scope)

- **Next by build stage:**
  - BUILD-03 remainder: campuses, departments, groups, affiliation grants, custom roles and other staff roles, module
    entitlements and the `restricted` state, typed configuration revisions.
  - BUILD-04 onward: admissions (the "Apply" CTA then points to `/apply`), people, academics for all four categories,
    attendance, results, fees, communication, operational modules, reporting.
  - Platform health (SCR-008), usage (SCR-009) and support (SCR-010).
- **Security and platform:** MFA and step-up authentication, row-level security, offboarding and deletion.
- **Public pages:** custom domains, server-side rendering, editing the Eduma main page from the console.

Each later slice gets its own spec and plan.
