import pytest

from accounts.models import Membership
from accounts.roles import BUILTIN_ROLES
from common.models import AuditEvent
from testing import factories

ROLES = "/api/v1/institution/roles"


@pytest.fixture
def admin(world, client_for):
    return client_for(world.a.slug, world.a_admin)


def membership(user, institution):
    return Membership.objects.get(user=user, institution=institution)


def test_lists_builtin_then_custom_with_counts(world, admin):
    role = factories.custom_role(world.a, permissions=["membership.read"], name="Front office")
    factories.member(world.a, custom_role=role)
    factories.member(world.a, custom_role=role)
    items = admin.get(ROLES, {"page_size": 200}).json()["results"]
    assert [i["id"] for i in items[:13]] == list(BUILTIN_ROLES)
    assert all(i["builtin"] for i in items[:13])
    assert items[0]["label"] == "Institution Admin" and items[0]["assigned_count"] == 1
    assert items[13] == {
        "id": str(role.id),
        "builtin": False,
        "label": "Front office",
        "description": "",
        "permissions": ["membership.read"],
        "assigned_count": 2,
        "is_active": True,
        "version": role.version,
    }
    assert admin.get(ROLES).json()["count"] == 14 and len(admin.get(ROLES).json()["results"]) == 5


def test_create_custom_role_within_ceiling(world, admin):
    created = admin.post(ROLES, {"name": "Front office", "permissions": ["membership.read"]}, format="json")
    assert created.status_code == 201
    assert AuditEvent.objects.filter(action="role.created", institution=world.a).exists()
    for bad in (["membership.read", "nope"], ["institution.read"]):
        response = admin.post(ROLES, {"name": "Other", "permissions": bad}, format="json")
        assert response.status_code == 422, bad
        assert response.json()["errors"][0]["field"] == "permissions"
    assert "nope" in admin.post(ROLES, {"name": "X", "permissions": ["nope"]}, format="json").json()["detail"]


def test_editor_cannot_exceed_own_permissions(world, client_for):
    manager_role = factories.custom_role(world.a, permissions=["role.manage", "membership.read"])
    manager = client_for(world.a.slug, factories.member(world.a, custom_role=manager_role))
    response = manager.post(ROLES, {"name": "Org", "permissions": ["organization.manage"]}, format="json")
    assert response.status_code == 422
    assert response.json()["detail"] == "You can only give permissions you hold yourself."
    branded = factories.custom_role(world.a, permissions=["institution_brand.update"])
    patch = manager.patch(f"{ROLES}/{branded.id}", {"version": branded.version, "name": "Renamed"}, format="json")
    assert patch.status_code == 403


def test_institution_only_permission_refused_when_role_given_narrowly(world, admin):
    city = factories.campus(world.a, code="CITY", name="City campus")
    role = factories.custom_role(world.a, permissions=["membership.read"])
    factories.member(world.a, custom_role=role, scope=city)
    body = {"version": role.version, "permissions": ["membership.read", "organization.manage"]}
    response = admin.patch(f"{ROLES}/{role.id}", body, format="json")
    assert response.status_code == 422
    assert "1 person has this role at a campus or department" in response.json()["detail"]


def test_names_unique_case_insensitively_among_active(world, admin):
    old = factories.custom_role(world.a, name="Front Office")
    assert admin.post(ROLES, {"name": "front office", "permissions": []}, format="json").status_code == 422
    old.is_active = False
    old.save()
    assert admin.post(ROLES, {"name": "front office", "permissions": []}, format="json").status_code == 201


def test_archive_refused_while_assigned(world, admin):
    role = factories.custom_role(world.a, permissions=["membership.read"])
    factories.member(world.a, custom_role=role)
    response = admin.patch(f"{ROLES}/{role.id}", {"version": role.version, "is_active": False}, format="json")
    assert response.status_code == 409 and response.json()["code"] == "in_use"
    unused = factories.custom_role(world.a)
    archived = admin.patch(f"{ROLES}/{unused.id}", {"version": unused.version, "is_active": False}, format="json")
    assert archived.status_code == 200
    assert AuditEvent.objects.filter(action="role.archived").exists()


def test_stale_version_409(world, admin):
    role = factories.custom_role(world.a)
    admin.patch(f"{ROLES}/{role.id}", {"version": role.version, "name": "One"}, format="json")
    stale = admin.patch(f"{ROLES}/{role.id}", {"version": role.version, "name": "Two"}, format="json")
    assert stale.status_code == 409


def test_assignable_filter(world, client_for):
    city = factories.campus(world.a, code="CITY", name="City campus")
    factories.custom_role(world.a, permissions=["role.manage"], name="Role makers")
    factories.custom_role(world.a, permissions=["membership.read"], name="Readers")
    boss = client_for(world.a.slug, factories.member(world.a, role="campus_admin", scope=city))
    labels = [i["label"] for i in boss.get(ROLES, {"assignable": "1", "page_size": 200}).json()["results"]]
    assert "Teacher / Faculty" in labels and "Readers" in labels
    assert "Institution Admin" not in labels and "Role makers" not in labels
    assert "Campus Admin" in labels  # it holds only what the Campus Admin holds, at the campus


def test_registry_and_who_may_read(world, admin, client_for):
    groups = admin.get("/api/v1/institution/permissions").json()
    assert [g["group"] for g in groups] == [
        "Institution",
        "Organization",
        "Staff",
        "Settings",
        "Admissions",
        "Academics",
        "Results",
        "Fees",
        "Communication",
        "Campus services",
        "Students",
    ]
    assert groups[2]["permissions"][0] == {
        "name": "membership.read",
        "label": "See staff and their roles",
        "institution_only": False,
    }
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.get(ROLES).status_code == 403
    assert teacher.get("/api/v1/institution/permissions").status_code == 403


def test_roles_not_on_other_hosts(world, client_for):
    role = factories.custom_role(world.a)
    assert client_for(world.b.slug, world.b_admin).get(f"{ROLES}/{role.id}").status_code == 404
    assert client_for(None, world.platform_admin).get(ROLES).status_code == 404


def test_active_role_names_are_unique_in_the_database_too(world):
    """Two creates at the same instant cannot both pass the name check (final review #6)."""
    from django.db import IntegrityError, transaction

    factories.custom_role(world.a, name="Front office")
    with pytest.raises(IntegrityError), transaction.atomic():
        factories.custom_role(world.a, name="FRONT OFFICE")
    factories.custom_role(world.a, name="Front office", is_active=False)


def test_restoring_an_archived_role_checks_its_name(world, admin):
    """Final review #5."""
    old = factories.custom_role(world.a, name="Office", is_active=False)
    factories.custom_role(world.a, name="office")
    response = admin.patch(f"{ROLES}/{old.id}", {"version": old.version, "is_active": True}, format="json")
    assert response.status_code == 422 and response.json()["errors"][0]["field"] == "name"


def test_roles_list_searches_from_three_letters(world, admin):
    """Final review #15: every list is searchable."""
    factories.custom_role(world.a, name="Front office")
    assert [r["label"] for r in admin.get(ROLES, {"search": "fro"}).json()["results"]] == ["Front office"]
    assert admin.get(ROLES, {"search": "fr"}).json()["count"] == 14
