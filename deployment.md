# Eduma deployment (without Docker)

This guide deploys the repository under **`/home/policebza/eduma/`** on a Linux server. The application code, Python environment, frontend build, uploaded files, and local backup staging directory stay inside that folder. PostgreSQL, Nginx, and systemd are host services; PostgreSQL keeps its database files in its system-managed data directory.

The commands assume a Debian/Ubuntu-style server and a login with `sudo`. Replace `eduma.app` with the real base domain throughout, and set up DNS and certificates before enabling HTTPS. Run shell commands on the **server**, not on a laptop.

## 1. Prerequisites

- Python 3.12 with `venv`, a C compiler and Python build headers.
- PostgreSQL 17 with its client tools (`psql`, `pg_dump`, `pg_restore`).
- Node.js 24 LTS (24.15 or later) and npm, for building the Angular frontend. Node is not needed to serve the built site.
- Nginx, systemd, Git, and a TLS certificate covering the base domain and its wildcard subdomains. A wildcard certificate requires DNS validation. Each institution's separate custom domain needs its own certificate and Nginx host configuration.
- DNS records for `eduma.app` and `*.eduma.app` pointing to this server.

Check installed versions before continuing:

```bash
python3.12 --version
psql --version
node --version
npm --version
nginx -v
```

## 2. Put the project in the requested folder

Run as the `policebza` account (or create it and grant it ownership of this folder). If the folder is empty:

```bash
sudo install -d -o policebza -g policebza /home/policebza/eduma
sudo -u policebza git clone https://github.com/Jayanadh/Eduma.git /home/policebza/eduma
cd /home/policebza/eduma
```

If the folder already contains this Git checkout, run `git -C /home/policebza/eduma pull --ff-only origin main` instead. Do not copy a laptop's `.venv`, `node_modules`, or `dist` into the server; build those for the server below. Keep any existing `backend/media`, `backend/private_media`, `.env.production`, and `backups` when updating.

## 3. Create the PostgreSQL database

Use the local PostgreSQL service. These commands prompt for the database user's password. Generate a shell-safe password, for example with `python3.12 -c 'import secrets; print(secrets.token_hex(24))'`, and enter it at the prompt:

```bash
sudo -u postgres createuser --pwprompt eduma
sudo -u postgres createdb --owner=eduma eduma
```

If either role or database already exists, keep it and do not recreate it. The password entered here must match `POSTGRES_PASSWORD` in the production environment file. PostgreSQL should listen only on localhost unless a separate database host is intentionally configured.

## 4. Configure production settings

Create `/home/policebza/eduma/backend/.env.production` as `policebza`. Generate a new secret with `python3.12 -c 'import secrets; print(secrets.token_urlsafe(64))'`. Fill in the actual domain, contact address, secret, and database password:

```ini
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=REPLACE_WITH_A_NEW_RANDOM_SECRET
DJANGO_ALLOWED_HOSTS=*
DJANGO_CSRF_TRUSTED_ORIGINS=https://eduma.app,https://*.eduma.app
DJANGO_PROXY_COUNT=1
DJANGO_SSL_REDIRECT=1
DJANGO_HSTS_SECONDS=31536000
DJANGO_ADMIN=0
EDUMA_BASE_URL=https://eduma.app
EDUMA_CONTACT_EMAIL=hello@eduma.app
DJANGO_MEDIA_ROOT=/home/policebza/eduma/backend/media
DJANGO_PRIVATE_MEDIA_ROOT=/home/policebza/eduma/backend/private_media
POSTGRES_DB=eduma
POSTGRES_USER=eduma
POSTGRES_PASSWORD=REPLACE_WITH_DATABASE_PASSWORD
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

`DJANGO_ALLOWED_HOSTS=*` is needed if institution custom domains can be added without editing this file each time; Eduma's host router accepts only its base host, institution subdomains, and custom domains recorded for an institution. Restrict inbound traffic to Nginx and bind Gunicorn to `127.0.0.1`. If custom domains are not used, you can list only `eduma.app,.eduma.app` here. If another trusted proxy sits in front of Nginx, review `DJANGO_PROXY_COUNT` and forwarded-header handling for that topology.

```bash
cd /home/policebza/eduma
chmod 600 backend/.env.production
mkdir -p backend/media backend/private_media backend/staticfiles backups
chmod 700 backend/private_media backups
```

The environment file is read by systemd, not automatically by Django. Keep it out of Git and backups sent to people without access to production secrets. Never run `seed_demo` in production: it is development data with known passwords and refuses to run when `DJANGO_DEBUG=0`.

## 5. Install and build the application

Run as `policebza`:

```bash
cd /home/policebza/eduma/backend
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

cd /home/policebza/eduma/frontend
npm ci
npm run build
test -f /home/policebza/eduma/frontend/dist/frontend/browser/index.html

cd /home/policebza/eduma/backend
set -a
. ./.env.production
set +a
.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
```

The production frontend is served from `/home/policebza/eduma/frontend/dist/frontend/browser/`. The API is served separately by Gunicorn. Do not use `runserver` or `ng serve` as production services.

For a fresh database, create the first platform login interactively, then mark it as a platform admin:

```bash
cd /home/policebza/eduma/backend
set -a; . ./.env.production; set +a
.venv/bin/python manage.py createsuperuser --username eduma.admin
.venv/bin/python manage.py shell -c "from accounts.models import User; User.objects.filter(username='eduma.admin').update(is_platform_admin=True)"
```

Choose a unique, strong password when prompted. The platform login is at `https://eduma.app/login`. Do this only once; for an existing database, retain its users and data.

## 6. Run the API and worker with systemd

Create `/etc/systemd/system/eduma-api.service`:

```ini
[Unit]
Description=Eduma API
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
User=policebza
Group=policebza
WorkingDirectory=/home/policebza/eduma/backend
EnvironmentFile=/home/policebza/eduma/backend/.env.production
ExecStart=/home/policebza/eduma/backend/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 3 --timeout 120 --access-logfile - --error-logfile -
Restart=always
RestartSec=5
UMask=0077

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/eduma-worker.service`:

```ini
[Unit]
Description=Eduma jobs worker
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
User=policebza
Group=policebza
WorkingDirectory=/home/policebza/eduma/backend
EnvironmentFile=/home/policebza/eduma/backend/.env.production
ExecStart=/home/policebza/eduma/backend/.venv/bin/python manage.py run_jobs --loop
Restart=always
RestartSec=5
UMask=0077

[Install]
WantedBy=multi-user.target
```

Start and inspect them:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now eduma-api eduma-worker
sudo systemctl status eduma-api eduma-worker
sudo journalctl -u eduma-api -u eduma-worker -n 100 --no-pager
```

The worker processes exports and scheduled jobs every minute. Keep exactly one looping worker unless the job runner is explicitly made safe for multiple concurrent workers.

## 7. Serve HTTPS with Nginx

Create `/etc/nginx/sites-available/eduma` after the certificate exists. Replace the certificate paths with the paths supplied by your certificate provider:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name eduma.app *.eduma.app;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name eduma.app *.eduma.app;

    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;
    client_max_body_size 8m;

    root /home/policebza/eduma/frontend/dist/frontend/browser;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /static/ {
        alias /home/policebza/eduma/backend/staticfiles/;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Do **not** add a public Nginx alias for `backend/private_media/`; private files are returned only through authorized API views. The same applies to `backend/media/` unless a specific, reviewed public route is added. Give the Nginx user read and directory traversal access to the frontend build and `backend/staticfiles` while keeping `.env.production`, private media, and backups inaccessible. On systems where `/home/policebza` blocks traversal, grant narrowly scoped ACLs to the Nginx user for those public directories.

```bash
sudo ln -s /etc/nginx/sites-available/eduma /etc/nginx/sites-enabled/eduma
sudo nginx -t
sudo systemctl reload nginx
```

For each institution custom domain, point its DNS at this server and add an HTTPS Nginx server block with a certificate for that domain and the same `root`, `/api/` proxy, and `/static/` location. The domain must also be saved on that institution in Eduma. If you restrict `DJANGO_ALLOWED_HOSTS`, add the custom domain there too.

## 8. Verify the deployment

```bash
curl -fsS https://eduma.app/api/v1/health
curl -fsS https://eduma.app/api/v1/health/ready
curl -I https://eduma.app/
```

`/api/v1/health` checks the API process. `/api/v1/health/ready` checks the database, worker, and storage, and may report `503` until the worker's first pass completes. Open `https://eduma.app/login`, sign in with the platform admin, then check an institution subdomain after one is created. Confirm that login and uploads work over HTTPS.

## 9. Updates and backups

For an update, first take a tested database and media backup. Then run as `policebza`:

```bash
cd /home/policebza/eduma
git pull --ff-only origin main
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build
cd ../backend
set -a; . ./.env.production; set +a
.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart eduma-api eduma-worker
sudo nginx -t && sudo systemctl reload nginx
```

The repository's current `ops/backup.sh` and `ops/restore-drill.sh` are development scripts tied to the container database. For this native installation, a basic manual backup is:

```bash
cd /home/policebza/eduma
set -a; . backend/.env.production; set +a
stamp=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -m 700 "backups/$stamp"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "backups/$stamp/eduma.dump"
tar -C backend -cf "backups/$stamp/media.tar" media private_media
sha256sum "backups/$stamp/eduma.dump" "backups/$stamp/media.tar" > "backups/$stamp/SHA256SUMS"
```

This does not replace an automated backup and restore drill. Encrypt backups, copy them off this server, retain a tested restore procedure, and arrange PostgreSQL WAL archiving if a short recovery point is required. Keep temporary backup files under `/home/policebza/eduma/backups/` with mode `700`; do not rely on that local directory as the only backup. The console's backup tile requires backups to be recorded with `manage.py record_backup`; this manual example does not do that. Schedule `manage.py run_jobs` through the service above, not an additional cron job.

For troubleshooting, see `sudo journalctl -u eduma-api -u eduma-worker -f`, `sudo journalctl -u nginx -f`, and [`docs/operations.md`](docs/operations.md). A failed code release can be rolled back to a known Git commit and rebuilt, but database migrations may require a separate restore plan; check migration compatibility before rolling back.
