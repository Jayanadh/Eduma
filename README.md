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
| `eduma.admin` | http://localhost:4201/login | Overview; Institutions (search as you type); **Add institution**, which gives the new institution its address and its admin's first password; an institution's page, where you can edit its details and own domain, activate, suspend, archive and reset its admin's password; Audit log. Branding is left to each institution's own admin. |
| `aster.admin` | http://aster.localhost:4201/login | Home checklist; **Public site** (the same editor, for their own institution); Profile. |
| `meridian.admin`, `summit.admin` | their own address | The same for their institutions. Signing in at another institution's address is refused. |
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
- the public page in every lifecycle state.

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
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | `eduma` ×3, `localhost`, `5434` | Database |
