"""Settings used by pytest: development settings plus a fast password hasher, an in-memory cache and a test domain."""

import tempfile
from pathlib import Path

from .settings import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = Path(tempfile.gettempdir()) / "eduma-test-media"
# conftest clears the cache before every test, including those that use no database.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
# Tests address the platform as eduma.test and an institution as <slug>.eduma.test.
EDUMA_BASE_URL = "http://eduma.test"
ALLOWED_HOSTS = [".eduma.test", "eduma.test", "testserver"]
