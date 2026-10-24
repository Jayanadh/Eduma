# Eduma

Eduma is a multi-institution education ERP for schools, colleges, engineering colleges and universities, India first.
The Eduma team onboards each institution. Each institution gets its own web address (`<slug>.eduma.app`), its own
public page with its logo, colours, fonts, words and photos, and a workspace for its people with the same branding.

This repository is being built in slices. **Slice 1 (this one)** covers:
- the platform console;
- onboarding and the institution lifecycle (set up, activate, suspend, archive);
- institution subdomains;
- sign-in (platform and per institution);
- the branded public pages;
- the site editor;
- the institution's own workspace.

What comes next is in [`docs/progress.md`](docs/progress.md). The full specification is in `Eduma_Build_Pack/`.

Built with Angular (screens), Django REST Framework (API) and PostgreSQL (database), the same stack as AP Police
Student Connect.

## What you need installed

- **Docker** (runs the PostgreSQL 17 database)
- **Python 3.12**
- **Node 24 or newer** (comes with npm)
- **Chrome or Firefox** for local testing. They send `*.localhost` addresses to your own computer; Safari may not.

## First-time setup

Run these once, from this folder (the one with `docker-compose.yml`).

```bash
# 1. Start the database (on port 5434, so it can run next to the MTO and Student Connect databases)
docker compose up -d db

# 2. Backend: Python environment, tables and demo data
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_demo
cd ..

# 3. Frontend: install packages
cd frontend
npm install
cd ..
```

`seed_demo` creates the platform admin and four made-up institutions, one per category, each with its own colours and
fonts. It is safe to run again: it never duplicates anything and it puts the demo passwords back. It refuses to run with
`DJANGO_DEBUG=0`.

## Running the app

Open two terminal windows.

**Terminal 1: the backend (API on port 8001)**

```bash
cd backend
source .venv/bin/activate
python manage.py runserver 8001
```

**Terminal 2: the frontend (screens on port 4201)**

```bash
cd frontend
npm start
```

The frontend forwards every `/api` request to the backend, keeping the address you typed, so the backend knows which
site you are on (see `frontend/proxy.conf.json`).

## Addresses

| Address | What it is |
|---|---|
| http://localhost:4201 | The Eduma landing page. It has no sign-in link. |
| http://localhost:4201/login | Platform sign-in. It is not linked from anywhere and only admits Eduma platform admins. |
| http://aster.localhost:4201 | Aster School's public page, with its own **Sign in** for its members |
| http://www.meridiancollege.localhost:4201 | Meridian College, on a domain of its own (its http://meridian.localhost:4201 address works too) |
| http://summit.localhost:4201 | Summit University |
| http://vector.localhost:4201 | Vector Engineering College: still being set up, so its page says "Opening soon" |

In production the same pattern runs on `eduma.app` and `<slug>.eduma.app`. That needs a wildcard DNS record and a
wildcard certificate for `*.eduma.app`.

## Demo logins

Every demo login uses the password **`Demo-pass-2026`**.

| Login ID | Sign in at | Things to try |
|---|---|---|
| `eduma.admin` | http://localhost:4201/login | Overview; Institutions (search as you type); **Add institution**, which gives the new institution its address, its modules and its admin's first password; an institution's page, where you can edit its details, own domain and modules, activate, restrict, suspend, archive and reset its admin's password; Audit log. Branding and staff are left to each institution's own admin. |
| `aster.admin` | http://aster.localhost:4201/login | Home checklist and modules; **Staff** (add people with a first password, give and end roles for the whole school, a campus or a department); **Roles** (built-in roles and your own custom roles); **Organization** (campuses and departments); **Settings** (modules switched on, approval for powerful roles, academic year: drafted, previewed, published from a chosen day, with history and restore); **Public site**; **Data transfer** (import students from a spreadsheet: try `backend/imports/fixtures/aster-students-sample.csv` — a dry run, then Import; download the errors; undo a fresh import); Profile. |
| `aster.principal` | http://aster.localhost:4201/login | A Principal for the whole school: sees all staff and their roles, changes nothing. |
| `aster.campus` | http://aster.localhost:4201/login | Campus Admin for City campus: sees and adds staff at City only; cannot make anyone an Institution Admin. |
| `aster.teacher`, `aster.office` | http://aster.localhost:4201/login | A Science teacher: **My classes** (6A this year as class teacher and Science; 6A next year with Arjun) and each class list. A custom "Front office" role at City (sees City staff). |
| `aster.deputy` | http://aster.localhost:4201/login | A second Institution Admin. With two admins, try **Settings → Approval for powerful roles**: one admin sends it, the other approves it from Home. Then a Campus Admin's request to give a powerful role waits for an admin's approval. |
| `aster.admissions` | http://aster.localhost:4201/login | Admissions Officer: **Enquiries** (questions from the Apply page and walk-ins: follow up, assign, link to an application, close) and **Applications** — check documents, ask the family for more, mark eligible or decline. Cannot offer places. |
| `aster.registrar` | http://aster.localhost:4201/login | Registrar: offers places (within the seats left), enrolls accepted applicants with the student's first password; **Academics**: academic setup (years and terms, grades, subjects) and **Sections** (place students, assign teachers, move a section up to next year); and keeps **Students** (search and filter by status, open a record, correct details, **Guardians**: add, verify with evidence and access, revoke; **Withdraw** and **Reinstate**; **History**). |
| `aster.parent` | http://aster.localhost:4201/login | Arjun Demo's verified guardian: lands on **Your children** (Arjun's number and class) and keeps **Applications** (Meera Demo, Class 1, submitted). New families make their own account from **Apply** on the school's page (http://aster.localhost:4201/apply). |
| `aster.grandparent` | http://aster.localhost:4201/login | Arjun's grandmother, a verified guardian with nothing shared: sees Arjun listed with "Your school has not shared this record with you". |
| `aster.2027-0001` | http://aster.localhost:4201/login | Arjun Demo, the enrolled student: their own record (student number and class). A new student's login is `<school>.<student number>`, with the first password the registrar chose. |
| `meridian.admin` | http://meridian.localhost:4201/login | A college: **Programs** (B.Sc Physics and its regulation R2026 — a synthetic regulation for development, not any real university's — with courses by semester and prerequisites; draft, publish, retire, **New revision**), **Courses**, **Offerings** (PHY101-A with its lab PHY101L-A1; open, cancel, assign teachers), **Sections** as batches (BSC-PHY 2026 A), and each student's **Program and regulation**. |
| `meridian.faculty` | http://meridian.localhost:4201/login | A Physics teacher: **My classes** shows batch BSC-PHY 2026 A (as class teacher, with its class list) and the PHY101-A offering. |
| `summit.admin` | http://summit.localhost:4201/login | The same as `aster.admin` for Summit University. Signing in at another institution's address is refused. |
| `vector.admin` | http://vector.localhost:4201/login | A first sign-in: the app asks for a new password before anything else. |

## Tests

```bash
# Backend (the database container must be running)
cd backend
source .venv/bin/activate
pytest

# Frontend
cd frontend
npx ng test --watch=false
npx ng build
```

The backend tests cover:
- host routing;
- who may sign in where;
- sessions that are reused on another address, or whose institution is suspended;
- onboarding retries;
- lifecycle rules;
- colour contrast;
- page content validation;
- drafts, publishing and edit conflicts;
- image upload checks;
- the public page in every lifecycle state;
- admissions: cycles, applying, documents, review, seats, offers, enrollment and who may see what;
- student records and the student's own record;
- academics: years, sections, placement, move-up, programs, regulations, courses, offerings, batches and pinning.

## Settings

The backend reads these environment variables. Every one has a development default, so none are needed on a laptop.
`backend/.env.example` lists them for reference; nothing loads that file, so export them in your shell or process
manager.

| Variable | Development default | Purpose |
|---|---|---|
| `EDUMA_BASE_URL` | `http://localhost:4201` | The Eduma main site; institutions are served at `<slug>.<its host>`, and at their own domain once one is set |
| `EDUMA_CONTACT_EMAIL` | `hello@eduma.example` | Where the landing page's "Talk to us" sends email |
| `DJANGO_SECRET_KEY` | a development key | Must be set when `DJANGO_DEBUG=0` |
| `DJANGO_DEBUG` | `1` | `0` on a server |
| `DJANGO_ALLOWED_HOSTS` | `localhost,.localhost,127.0.0.1` | On a server: `*`, so institutions' own domains reach Eduma; it serves only its base host, `<slug>.<base host>` and domains recorded on an institution |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `http://localhost:4201,http://*.localhost:4201` | On a server: `https://eduma.app,https://*.eduma.app` |
| `DJANGO_PROXY_COUNT` | `0` | Number of reverse proxies in front of Django |
| `DJANGO_MEDIA_ROOT` | `backend/media` | Where uploaded brand images are kept |
| `DJANGO_PRIVATE_MEDIA_ROOT` | `backend/private_media` | Where admission documents are kept; never served as public files |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | `eduma` ×3, `localhost`, `5434` | Database |
