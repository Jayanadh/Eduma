"""Employee numbers and dates on staff (slice 4b S4B-10)."""

from accounts.models import Employee, Membership
from accounts.permissions import today_for
from testing import factories

STAFF = "/api/v1/institution/staff"
FIRST = "Welcome-2027-pass"


def add(client, username, **changes):
    body = {
        "full_name": username.title(),
        "username": username,
        "password": FIRST,
        "role": "teacher",
        "scope_type": "institution",
        **changes,
    }
    return client.post(STAFF, body, format="json")


def test_add_staff_with_employee_number(world, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    made = add(admin, "new.teacher", employee_number="AST-010", joined_on="2026-06-01")
    assert made.status_code == 201, made.json()
    assert made.json()["employee"] == {"number": "AST-010", "joined_on": "2026-06-01", "left_on": None}
    listed = admin.get(STAFF, {"search": "new.teacher"}).json()["results"][0]
    assert listed["employee"]["number"] == "AST-010"


def test_duplicate_employee_number_422(world, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    assert add(admin, "first.teacher", employee_number="AST-010").status_code == 201
    taken = add(admin, "second.teacher", employee_number="AST-010")
    assert taken.status_code == 422 and taken.json()["errors"][0]["field"] == "employee_number"
    other = add(admin, "third.teacher").json()
    patched = admin.patch(
        f"{STAFF}/{other['id']}", {"version": other["version"], "employee_number": "AST-010"}, format="json"
    )
    assert patched.status_code == 422 and patched.json()["errors"][0]["field"] == "employee_number"
    assert add(admin, "fourth.teacher").status_code == 201  # blank numbers repeat freely


def test_only_a_manager_edits_employee_details(world, client_for):
    city = factories.campus(world.a, code="CITY", name="City campus")
    campus_admin = client_for(world.a.slug, factories.member(world.a, role="campus_admin", scope=city))
    registrar = Membership.objects.get(user=factories.member(world.a, role="registrar", scope=city))
    refused = campus_admin.patch(
        f"{STAFF}/{registrar.id}", {"version": registrar.version, "employee_number": "X-1"}, format="json"
    )
    assert refused.status_code == 403
    assert not Employee.objects.filter(membership=registrar, employee_number="X-1").exists()


def test_remove_sets_left_on_and_restore_clears_it(world, client_for):
    admin = client_for(world.a.slug, world.a_admin)
    person = add(admin, "leaving.teacher", employee_number="AST-020").json()
    removed = admin.post(
        f"{STAFF}/{person['id']}/remove", {"version": person["version"], "reason": "Moved"}, format="json"
    )
    assert removed.status_code == 200
    assert removed.json()["employee"]["left_on"] == str(today_for(world.a))
    back = admin.post(f"{STAFF}/{person['id']}/restore", {"version": removed.json()["version"]}, format="json")
    assert back.status_code == 200 and back.json()["employee"]["left_on"] is None
