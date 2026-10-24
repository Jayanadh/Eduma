"""Leave, staff attendance and the payroll boundary (slice 10b; TST-029)."""

import datetime as dt

import pytest

from accounts.models import Employee, Membership
from accounts.permissions import today_for
from admissions.tests.conftest import switch_on
from testing import factories

H = "/api/v1/institution/hr"


def employ(institution, role, username, number, full_name):
    user = factories.member(institution, role=role, username=username, full_name=full_name)
    Employee.objects.create(
        institution=institution, membership=Membership.objects.get(user=user), employee_number=number
    )
    return user


@pytest.fixture
def h(world, client_for):
    switch_on(world.a, modules=("hr_payroll",))
    ns = type("H", (), {})()
    ns.year = today_for(world.a).year
    ns.admin = client_for(world.a.slug, world.a_admin)
    ns.teacher = client_for(world.a.slug, employ(world.a, "teacher", "maths.teacher", "AST-101", "Kavya Nair"))
    ns.other = client_for(world.a.slug, employ(world.a, "teacher", "science.teacher", "AST-102", "Arjun Das"))
    ns.hr = client_for(world.a.slug, employ(world.a, "hr_officer", "hr.office", "AST-103", "Leela Menon"))
    ns.payroll = client_for(world.a.slug, employ(world.a, "payroll_officer", "pay.office", "AST-104", "Rahul Shah"))
    ns.principal = client_for(world.a.slug, employ(world.a, "principal", "principal", "AST-105", "Dr. Iyer"))
    kinds = (
        {"code": "CL", "name": "Casual leave", "days_per_year": 12},
        {"code": "LWP", "name": "Leave without pay", "days_per_year": 30, "paid": False},
    )
    ns.casual, ns.unpaid = (ns.hr.post(f"{H}/leave-types", body, format="json").json() for body in kinds)
    return ns


def on(h, month, day):
    return dt.date(h.year, month, day).isoformat()


def ask(client, kind, start, end):
    body = {"leave_type": kind["id"], "starts_on": start, "ends_on": end, "reason": "Family function"}
    return client.post(f"{H}/leave", body, format="json")


def act(client, leave, action):
    return client.post(f"{H}/leave/{leave['id']}/{action}", {}, format="json")


def pay(h, number="AST-101", gross="62000.00"):
    employee = Employee.objects.get(employee_number=number)
    body = {
        "monthly_gross": gross,
        "components": {"basic": "40000.00", "hra": "22000.00"},
        "deductions": {"pf": "1800.00"},
        "effective_from": on(h, 1, 1),
    }
    return f"{H}/employees/{employee.id}/compensation", body


def test_tst029_balance_overlap_self_approval_and_cancel(h):
    made = ask(h.teacher, h.casual, on(h, 3, 2), on(h, 3, 6))
    assert made.status_code == 201, made.json()
    leave = made.json()
    assert (leave["days"], leave["state"]) == (5, "submitted")
    clash = ask(h.teacher, h.casual, on(h, 3, 6), on(h, 3, 7))
    assert clash.status_code == 422 and clash.json()["errors"][0]["field"] == "starts_on"
    too_many = ask(h.teacher, h.casual, on(h, 4, 1), on(h, 4, 8))  # 5 waiting + 8 > 12
    assert too_many.status_code == 422 and too_many.json()["errors"][0]["field"] == "ends_on"
    own = ask(h.hr, h.casual, on(h, 5, 4), on(h, 5, 4)).json()
    assert act(h.hr, own, "approve").status_code == 403  # nobody approves their own leave
    assert act(h.teacher, leave, "approve").status_code == 403
    assert act(h.hr, leave, "approve").json()["state"] == "approved"
    assert h.teacher.get(f"{H}/leave").json()["balances"][0] == {
        "code": "CL",
        "name": "Casual leave",
        "entitled": 12,
        "taken": 5,
        "waiting": 0,
        "left": 7,
    }
    assert act(h.teacher, leave, "cancel").json()["state"] == "canceled"
    assert act(h.teacher, leave, "cancel").status_code == 409
    assert h.teacher.get(f"{H}/leave").json()["balances"][0]["left"] == 12


def test_tst029_people_see_only_their_own_leave(world, h, client_for):
    leave = ask(h.teacher, h.casual, on(h, 3, 2), on(h, 3, 3)).json()
    assert h.other.get(f"{H}/leave").json()["requests"] == []
    assert h.other.get(f"{H}/leave", {"all": "1"}).status_code == 403
    assert act(h.other, leave, "cancel").status_code == 404
    everyone = h.hr.get(f"{H}/leave", {"all": "1"}).json()["requests"]
    assert [(r["employee"]["number"], r["employee"]["name"]) for r in everyone] == [("AST-101", "Kavya Nair")]
    switch_on(world.b, modules=("hr_payroll",))
    assert act(client_for(world.b.slug, world.b_admin), leave, "approve").status_code == 404


def test_tst029_pay_is_seen_only_with_payroll_manage(h):
    url, body = pay(h)
    assert h.hr.post(url, body, format="json").status_code == 403
    assert h.payroll.post(url, body, format="json").status_code == 201
    for client in (h.hr, h.teacher, h.principal):
        assert client.get(url).status_code == 403
    assert h.payroll.get(url).json()[0]["monthly_gross"] == "62000.00"
    hr_view = {row["number"]: row for row in h.hr.get(f"{H}/employees").json()}
    pay_view = {row["number"]: row for row in h.payroll.get(f"{H}/employees").json()}
    assert "pay" not in hr_view["AST-101"] and pay_view["AST-101"]["pay"] == "62000.00"
    assert h.teacher.get(f"{H}/employees").status_code == 403


def test_tst029_payroll_needs_another_approver_and_freezes_on_export(h):
    url, body = pay(h)
    h.payroll.post(url, body, format="json")
    unpaid = ask(h.teacher, h.unpaid, on(h, 3, 9), on(h, 3, 11)).json()
    act(h.hr, unpaid, "approve")
    made = h.admin.post(f"{H}/payroll", {"month": on(h, 3, 1)}, format="json")
    assert made.status_code == 201, made.json()
    cycle = made.json()
    line = cycle["lines"][0]
    assert (line["employee"]["number"], line["gross"], line["unpaid_days"], line["unpaid_deduction"]) == (
        "AST-101",
        "62000.00",
        3,
        "6000.00",
    )
    assert (line["deductions"], line["net"]) == ("1800.00", "54200.00")
    assert h.admin.post(f"{H}/payroll", {"month": on(h, 3, 1)}, format="json").status_code == 409
    step = f"{H}/payroll/{cycle['id']}"
    assert h.principal.post(f"{step}/approve", {}, format="json").status_code == 409  # not validated yet
    assert h.payroll.post(f"{step}/validate", {}, format="json").json()["state"] == "validated"
    assert h.admin.post(f"{step}/approve", {}, format="json").status_code == 403  # prepared it
    assert h.payroll.post(f"{step}/approve", {}, format="json").status_code == 403
    assert h.principal.post(f"{step}/approve", {}, format="json").json()["state"] == "approved"
    exported = h.payroll.post(f"{step}/export", {}, format="json")
    assert exported.status_code == 200 and exported["Content-Type"].startswith("text/csv")
    assert exported.content.decode().splitlines() == [
        "employee_number,name,gross,unpaid_days,unpaid_deduction,deductions,net",
        "AST-101,Kavya Nair,62000.00,3,6000.00,1800.00,54200.00",
    ]
    assert h.payroll.post(f"{step}/validate", {}, format="json").status_code == 409
    assert h.payroll.post(f"{step}/export", {}, format="json").content == exported.content  # the same file again


def test_staff_attendance_shows_approved_leave(h):
    leave = ask(h.teacher, h.casual, on(h, 3, 2), on(h, 3, 3)).json()
    act(h.hr, leave, "approve")
    other = Employee.objects.get(employee_number="AST-102")
    marks = {"date": on(h, 3, 2), "marks": [{"employee": str(other.id), "status": "present"}]}
    assert h.hr.post(f"{H}/attendance", marks, format="json").status_code == 200
    day = {row["number"]: row["status"] for row in h.hr.get(f"{H}/attendance", {"date": on(h, 3, 2)}).json()}
    assert (day["AST-101"], day["AST-102"], day["AST-103"]) == ("on_leave", "present", None)
    assert h.teacher.post(f"{H}/attendance", marks, format="json").status_code == 403


def test_module_gate(world, h):
    switch_on(world.a, modules=("students",))
    assert h.teacher.get(f"{H}/leave").status_code == 404
