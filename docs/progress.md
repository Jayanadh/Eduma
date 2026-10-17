# Eduma — progress and evidence

The durable record that `Eduma_Build_Pack/prompt.md` asks for: what is built, how it was checked, what was not, and
what comes next. Read this first when continuing.

## Where things stand (17 October 2026)

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
