# Eduma — decision register

Successor to `Eduma_Build_Pack/14_Decisions_and_Assumptions.md` for the implementation. Earlier entries in the pack
stay as they were; anything here that differs supersedes them. Never record an approval that was not given.

## Slice 1 decisions (17 October 2026)

Evidence: the user's answers in the build session of 17 Oct 2026 ("approved", "native, go ahead") and the approved
spec `docs/superpowers/specs/2026-10-17-foundation-onboarding-branding-design.md`.

| ID | Decision | Supersedes |
|---|---|---|
| S1-01 | Stack as AP Police Student Connect: Angular 22 (zoneless, signals, Vitest), Django 6.1 + DRF 3.18, PostgreSQL 17 in Docker, hand-written SCSS, fonts bundled with `@fontsource` (OFL only, no CDN). Layout `backend/`, `frontend/`, `docs/`. | D-10 (Angular Material/CDK); pack 12 repository layout |
| S1-02 | `/` on the main domain always shows the Eduma landing page, with no sign-in link. | — |
| S1-03 | `/login` on the main domain is unlinked and admits only platform (System Admin) accounts; everyone else gets "Invalid login ID or password." | — |
| S1-04 | Each institution has a subdomain: `<slug>.eduma.app` (locally `<slug>.localhost:4201`). Its page links to its own `/login`, for its members only. | Route prefix `/i/:institutionId` (04) |
| S1-05 | The API takes the institution from the request host. Platform routes stay under `/api/v1/platform/`. | 09 §1 institutional base |
| S1-06 | First sign-in uses a first password set by whoever creates the login, with a forced change before anything else. | 02 §7 and 03 WF-ONB step 6 (invitations) |
| S1-07 | The System Admin may edit any institution's branding and public page at any time, audited; the Institution Admin edits its own. | 02 `institution_brand.update` ("System Admin during setup") |
| S1-08 | Creating an institution is one atomic, idempotent request (institution, admin login, membership, starter page). | 03 WF-ONB `draft`/`provisioning` steps |
| S1-09 | Lifecycle states now: `setup`, `active`, `suspended`, `archived`. `restricted` comes with module entitlements; `deletion_pending`/`deleted` with offboarding. | 03 WF-ONB (in part) |
| S1-10 | Public pages are a fixed set of section types that can be edited, hidden and reordered (not a free-form builder). The Eduma page uses the same renderer with its content kept in code. | — |
| S1-11 | Lists use page-number pagination, as in Student Connect. | 09 §1 cursors |

## Pack defaults accepted for local development

Accepted by the user for local development on 12 Oct 2026 (pack 14 §3) and used in slice 1: D-02 (full catalogue kept,
built in order), D-07 (one institution = one tenant, `institution_id` boundary), D-08 (institution logo and validated
theme colours; semantic colours fixed), D-13 (recording off), D-15 (typed, versioned configuration with history),
D-18 (one complete theme first; no dark mode yet).

## Still open (carried forward, unchanged)

D-01 pilot boards and regulations · D-03 capacity targets · D-05 launch languages · D-06 team, budget and dates ·
D-12 providers (payment, email/SMS, storage, media) · D-14 residency, retention and recovery commitments ·
D-16 import formats · D-17 support coverage · D-21 hosting and region · D-22 mobile framework.
