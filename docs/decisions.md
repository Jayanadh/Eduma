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
| S1-07 | Branding (logo, colours, fonts, public page) is the Institution Admin's alone; the System Admin only onboards the institution and activates it once its checklist is done. *Changed by the user on 18 Oct 2026; was: the System Admin could edit any institution's branding.* | 02 `institution_brand.update` ("System Admin during setup") |
| S1-08 | Creating an institution is one atomic, idempotent request (institution, admin login, membership, starter page). | 03 WF-ONB `draft`/`provisioning` steps |
| S1-09 | Lifecycle states now: `setup`, `active`, `suspended`, `archived`. `restricted` comes with module entitlements; `deletion_pending`/`deleted` with offboarding. | 03 WF-ONB (in part) |
| S1-10 | Public pages are a fixed set of section types that can be edited, hidden and reordered (not a free-form builder). The Eduma page uses the same renderer with its content kept in code. | — |
| S1-11 | Lists use page-number pagination, as in Student Connect, 5 rows a page (the user's rule: any list over 5 records gets pages). | 09 §1 cursors |
| S1-12 | An institution may have its own domain (e.g. `www.dps.edu.in`) as well as `<slug>.<base host>`, set by the System Admin in its details at any time. Its links use the own domain; the Eduma address keeps working. On a server `DJANGO_ALLOWED_HOSTS=*`, since Eduma serves only its base host, its subdomains and recorded domains. | — |
| S1-13 | Country, time zone and currency are chosen from lists taken from the browser's Intl data (ISO countries, current ISO 4217 currencies, IANA zones). | — |

## Slice 2 (organization, staff roles, modules, restricted state)

Full table and reasons: `docs/superpowers/specs/2026-10-18-slice2-organization-staff-modules-design.md` §2.

| ID | Decision |
|---|---|
| S2-01 | Authority comes from role assignments (role + whole institution, campus or department + start/end dates), not a single role on the membership. |
| S2-02, S2-03 | Built-in roles and the permission registry live in code; institutions add custom roles from the registry. Only permissions for built features are registered. |
| S2-04 | Seeing the institution's home comes with membership itself. |
| S2-05 | Staff logins get a first password with a forced change; a login ID is never reused across institutions. |
| S2-06, S2-07 | Grant ceiling: nobody gives what they don't hold, changes their own roles, or removes the last Institution Admin. |
| S2-08 | Role changes take effect at once, audited; approval routing comes with the configuration engine. |
| S2-09 | The platform records each institution's modules; none is built yet, so each says it arrives in a later release. |
| S2-10 | `restricted`: members can sign in and read; every change is refused with the reason. |
| S2-11 | Every institution has a Main campus. |
| S2-12 | Deferred: typed configuration engine, groups and affiliation grants, guardian grants, invitations, support access, approvals. |
| S2-13 | New permission names `organization.manage` and `membership.read`. |

## Pack defaults accepted for local development

Accepted by the user for local development on 12 Oct 2026 (pack 14 §3) and used in slice 1: D-02 (full catalogue kept,
built in order), D-07 (one institution = one tenant, `institution_id` boundary), D-08 (institution logo and validated
theme colours; semantic colours fixed), D-13 (recording off), D-15 (typed, versioned configuration with history),
D-18 (one complete theme first; no dark mode yet).

## Still open (carried forward, unchanged)

D-01 pilot boards and regulations · D-03 capacity targets · D-05 launch languages · D-06 team, budget and dates ·
D-12 providers (payment, email/SMS, storage, media) · D-14 residency, retention and recovery commitments ·
D-16 import formats · D-17 support coverage · D-21 hosting and region · D-22 mobile framework.

## Slice 3 (configuration engine, module enablement, approvals)

Full table and reasons: `docs/superpowers/specs/2026-10-19-slice3-configuration-approvals-design.md` §2.

| ID | Decision |
|---|---|
| S3-01, S3-02 | Settings are defined in code; institutions hold revisions: draft → waiting for approval → published → replaced, or returned / withdrawn. Published revisions are never edited. |
| S3-03 | A change starts on a chosen day (today or later); the value on any day is the latest published one that has started; a newer change cancels a not-yet-started one; restore puts an old value in a new draft. |
| S3-04, S3-05 | Changes that need approval are approved by someone else holding `configuration.publish`; `configuration.edit` drafts and sends. |
| S3-06, S3-07 | First settings: modules switched on (within the plan), approval for powerful roles (needs two whole-institution assigners), academic year start month. Modules in force = plan ∩ switched on. |
| S3-08 | While approval is on, a role beyond "see staff" waits until someone else who could give it approves. |
| S3-09 | No campus overrides yet. |
| S3-10 | Workspace menu grouped: Home · People · Administration. |
| S3-11 | Support access → BUILD-11; groups and affiliation grants → BUILD-05; guardian grants → BUILD-04; invitations and recovery wait for D-12. |
