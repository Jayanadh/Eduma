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
| `cd backend && pytest` | 163 passed |
| `ruff check --select F,E,W,I --line-length 120 --exclude '.venv,*/migrations' .` and `ruff format --check` | clean |
| `DJANGO_DEBUG=0 … manage.py check --deploy` | no issues (2 silenced on purpose: HSTS subdomains/preload) |
| `manage.py makemigrations --check` | no changes |
| `cd frontend && npx ng test --watch=false` | 82 passed (21 files) |
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
