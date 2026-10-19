"""Admissions fixtures, so student tests can start from a real enrollment."""

from admissions.tests.conftest import cycle, main, on  # noqa: F401
from admissions.tests.test_enrollment import accepted, registrar  # noqa: F401
