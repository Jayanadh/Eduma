from accounts.models import Membership
from accounts.permissions import has_perm
from accounts.roles import BUILTIN_ROLES
from testing import factories

from .test_auth import host, login

ADMISSIONS = {"admission_cycle.manage", "application.review", "admission.approve", "student.read", "student.update"}


def test_applicant_and_student_memberships_get_no_workspace(world):
    applicant = factories.user(username="a.parent")
    Membership.objects.create(institution=world.a, user=applicant, kind="applicant")
    assert not has_perm(applicant, world.a, "institution.read")
    client = host(world.a.slug)
    me = login(client, "a.parent").json()["user"]["membership"]
    assert me == {
        "category": world.a.category,
        "kind": "applicant",
        "modules_enabled": [],
        "roles": [],
        "permissions": [],
        "restricted": False,
        "status_reason": "",
    }
    assert client.get("/api/v1/institution").status_code == 403


def test_staff_keep_their_workspace(world):
    client = host(world.a.slug)
    me = login(client, world.a_admin.username).json()["user"]["membership"]
    assert me["kind"] == "staff" and "institution.read" in me["permissions"]


def test_builtin_roles_gain_admissions_permissions():
    assert ADMISSIONS <= BUILTIN_ROLES["institution_admin"].permissions
    assert {"admission.approve", "application.review", "student.read", "student.update"} <= BUILTIN_ROLES[
        "registrar"
    ].permissions
    assert "application.review" in BUILTIN_ROLES["admissions_officer"].permissions
    assert "student.read" in BUILTIN_ROLES["principal"].permissions


def test_modules_admissions_and_students_are_available():
    from institutions.modules import MODULES

    assert MODULES["admissions"].available and MODULES["students"].available
    assert not MODULES["placements"].available


def test_me_says_which_modules_are_on(world):
    from admissions.tests.conftest import switch_on

    client = host(world.a.slug)
    assert login(client, world.a_admin.username).json()["user"]["membership"]["modules_enabled"] == []
    switch_on(world.a)
    me = client.get("/api/v1/session").json()["user"]["membership"]
    assert me["modules_enabled"] == ["admissions", "students"]


def test_registrar_holds_guardian_link_manage():
    from accounts.roles import PERMISSIONS

    assert "guardian_link.manage" in BUILTIN_ROLES["registrar"].permissions
    assert "guardian_link.manage" in BUILTIN_ROLES["institution_admin"].permissions
    assert PERMISSIONS["guardian_link.manage"].institution_only is False
    assert Membership.Kind.GUARDIAN == "guardian"


def test_enquiry_and_import_permissions():
    from accounts.roles import PERMISSIONS

    assert "enquiry.manage" in BUILTIN_ROLES["registrar"].permissions
    assert "enquiry.manage" in BUILTIN_ROLES["admissions_officer"].permissions
    assert PERMISSIONS["enquiry.manage"].institution_only is False
    assert PERMISSIONS["data.import"].institution_only is True
    assert "data.import" not in BUILTIN_ROLES["registrar"].permissions
    assert "data.import" in BUILTIN_ROLES["institution_admin"].permissions
