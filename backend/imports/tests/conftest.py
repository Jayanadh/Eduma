"""Admissions and student fixtures for import tests (files go to config.settings_test's private folder)."""

from admissions.tests.conftest import cycle, main, on  # noqa: F401
from admissions.tests.test_enrollment import accepted, registrar  # noqa: F401
from students.tests.fixtures import enrolled  # noqa: F401
