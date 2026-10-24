"""Django settings for Eduma.

Every value that differs between a laptop and a server comes from an environment
variable with a development default, so `python manage.py runserver 8001` works with no setup.
"""

import ipaddress
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


DEVELOPMENT_SECRET_KEY = "dev-only-insecure-key-change-me"
# The built-in default and the placeholder in backend/.env.example are both public, so neither may sign a real server.
PLACEHOLDER_SECRET_KEYS = {DEVELOPMENT_SECRET_KEY, "change-me"}
SECRET_KEY = env("DJANGO_SECRET_KEY", DEVELOPMENT_SECRET_KEY)
DEBUG = env("DJANGO_DEBUG", "1") == "1"
if not DEBUG and SECRET_KEY in PLACEHOLDER_SECRET_KEYS:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG=0.")
# A leading dot matches every subdomain: each institution is served at <slug>.<base host>.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,.localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:4201,http://*.localhost:4201")


def is_local_host(host: str) -> bool:
    """This machine or the local network, where a development server may run with DEBUG on."""
    host = host.lstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return address.is_loopback or address.is_private


# DEBUG shows code and settings in error pages: never on a server that the public can reach.
if DEBUG and (public_hosts := [host for host in ALLOWED_HOSTS if not is_local_host(host)]):
    raise ImproperlyConfigured(
        f"DJANGO_DEBUG=1 is for development; set DJANGO_DEBUG=0 to serve {', '.join(public_hosts)}."
    )

# Behind a reverse proxy (such as nginx), set DJANGO_PROXY_COUNT to the number of proxies in front of Django: the
# client's address (for login throttling) is then read from X-Forwarded-For and HTTPS from X-Forwarded-Proto. With 0,
# the default, both come from the connection itself, so a client cannot fake them.
PROXY_COUNT = int(env("DJANGO_PROXY_COUNT", "0"))
if PROXY_COUNT:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Production is HTTPS only: plain HTTP is redirected, and browsers are told to use HTTPS for a year.
SECURE_SSL_REDIRECT = not DEBUG and env("DJANGO_SSL_REDIRECT", "1") == "1"
SECURE_HSTS_SECONDS = 0 if DEBUG else int(env("DJANGO_HSTS_SECONDS", str(60 * 60 * 24 * 365)))
# HSTS stays on each host only; preloading cannot be undone quickly. `check --deploy` would otherwise flag both.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]

# The Django admin is a second way in with full powers: off in production unless DJANGO_ADMIN=1.
ADMIN_ENABLED = env("DJANGO_ADMIN", "1" if DEBUG else "0") == "1"

# The Eduma main site. Institutions are served at <slug>.<host of this URL>, with the same scheme and port.
EDUMA_BASE_URL = env("EDUMA_BASE_URL", "http://localhost:4201")
# Where the "Talk to us" button on the Eduma landing page sends email.
EDUMA_CONTACT_EMAIL = env("EDUMA_CONTACT_EMAIL", "hello@eduma.example")

LOCAL_APPS = [
    "common",
    "accounts",
    "institutions",
    "organization",
    "configuration",
    "admissions",
    "students",
    "academics",
    "affiliations",
    "attendance",
    "results",
    "fees",
    "communication",
    "imports",
    "sites",
]

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    *LOCAL_APPS,
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "sites.middleware.SiteMiddleware",
    "sites.middleware.RestrictedMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "sites.middleware.SessionSiteMiddleware",
    "accounts.middleware.PasswordChangeRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "eduma"),
        "USER": env("POSTGRES_USER", "eduma"),
        "PASSWORD": env("POSTGRES_PASSWORD", "eduma"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5434"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))
# Applicants' documents: never under MEDIA_ROOT or any public URL; served only through checked views.
PRIVATE_MEDIA_ROOT = Path(env("DJANGO_PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media")))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Session-cookie login. Cookies are host-only (no SESSION_COOKIE_DOMAIN), so every institution's subdomain has its own
# session. The CSRF cookie and header names match Angular HttpClient's defaults, so the frontend sends the token
# automatically on every POST, PUT and PATCH.
CSRF_COOKIE_NAME = "XSRF-TOKEN"
CSRF_HEADER_NAME = "HTTP_X_XSRF_TOKEN"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Login throttling counts attempts in the cache, which every gunicorn worker must share: a cache in each
# worker would let each one allow the full number. So it lives in the database; a migration makes its table.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "eduma_cache",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "common.exceptions.problem_handler",
    # Sign-in attempts: per client address, and per login ID however many addresses the attempts come from.
    "DEFAULT_THROTTLE_RATES": {"login": "10/min", "login_id": "20/hour", "public": "120/min", "enquiry": "10/hour"},
    "NUM_PROXIES": PROXY_COUNT,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# Brand images may be up to 5 MB; Django keeps bigger request bodies out of memory.
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
