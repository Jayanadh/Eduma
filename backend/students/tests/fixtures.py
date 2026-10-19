"""Fixtures for student tests that start from a real enrollment."""

import pytest

from admissions.tests.test_enrollment import FIRST
from admissions.tests.test_review import act


@pytest.fixture
def enrolled(world, cycle, accepted, registrar):
    """The student enrolled from asha.parent's application, with its proposed link to her."""
    from students.models import Student

    act(registrar, accepted, "enroll", password=FIRST)
    return Student.objects.get()
