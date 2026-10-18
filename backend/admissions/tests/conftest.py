import datetime as dt

import pytest

from accounts.permissions import today_for
from configuration.models import SettingRevision
from testing import factories

CYCLES = "/api/v1/institution/admissions/cycles"


def switch_on(institution, modules=("admissions", "students")):
    institution.modules = sorted(set(institution.modules) | set(modules))
    institution.save()
    SettingRevision.objects.create(
        institution=institution,
        key="modules.enabled",
        number=SettingRevision.objects.filter(institution=institution, key="modules.enabled").count() + 1,
        value=sorted(modules),
        status="published",
        effective_from=today_for(institution),
    )


@pytest.fixture
def on(world):
    switch_on(world.a)
    return world.a


@pytest.fixture
def main(world):
    return factories.campus(world.a, code="MAIN", name="Main campus")


def cycle_body(main, **changes):
    today = today_for(main.institution)
    body = {
        "name": "Admissions 2027–28",
        "entry_year": today.year + 1,
        "opens_on": str(today),
        "closes_on": str(today + dt.timedelta(days=60)),
        "instructions": "Apply before the closing date.",
        "places": [
            {"code": "C1", "label": "Class 1", "campus": str(main.id), "seats": 40},
            {"code": "C6", "label": "Class 6", "campus": str(main.id), "seats": 10},
        ],
        "questions": [
            {"code": "LANG", "label": "Home language", "help": "", "kind": "text", "options": [], "required": True},
            {
                "code": "BUS",
                "label": "Needs the school bus?",
                "help": "",
                "kind": "yes_no",
                "options": [],
                "required": True,
            },
            {
                "code": "STREAM",
                "label": "Preferred second language",
                "help": "",
                "kind": "choice",
                "options": ["Hindi", "Telugu"],
                "required": False,
            },
        ],
        "documents": [
            {"code": "BIRTH", "label": "Birth certificate", "help": "", "required": True},
            {"code": "PHOTO", "label": "Recent photo", "help": "", "required": True},
        ],
    }
    body.update(changes)
    return body


APPS = "/api/v1/applicant/applications"


def applicant(institution, username):
    from accounts.models import Membership

    person = factories.user(username=username, full_name=username.replace(".", " ").title())
    Membership.objects.create(institution=institution, user=person, kind="applicant")
    return person


@pytest.fixture
def cycle(world, on, main, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    draft = admin.post(CYCLES, cycle_body(main), format="json").json()
    return admin.post(f"{CYCLES}/{draft['id']}/publish", {"version": draft["version"]}, format="json").json()


def complete(application: dict) -> dict:
    """The core fields and answers a submittable application needs (documents are uploaded separately)."""
    return {
        "version": application["version"],
        "learner_name": "Meera Rao",
        "date_of_birth": "2020-05-17",
        "guardian_name": "Asha Rao",
        "guardian_relationship": "Mother",
        "guardian_phone": "+91 90000 12345",
        "guardian_email": "asha@example.com",
        "address": "4 Lake Road, Vijayawada",
        "previous_school": "",
        "answers": {"LANG": "Telugu", "BUS": True, "STREAM": "Hindi"},
    }
