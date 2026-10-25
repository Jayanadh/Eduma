"""Procurement, stock, assets and lab booking (slice 10b; TST-030)."""

import datetime as dt

import pytest
from django.utils import timezone

from accounts.models import Membership
from admissions.tests.conftest import switch_on
from testing import factories

S = "/api/v1/institution/stores"


@pytest.fixture
def s(world, client_for):
    switch_on(world.a, modules=("assets",))
    ns = type("S", (), {})()
    ns.admin = client_for(world.a.slug, world.a_admin)
    ns.keeper = client_for(world.a.slug, factories.member(world.a, role="store_keeper", username="stores"))
    ns.principal = client_for(world.a.slug, factories.member(world.a, role="principal", username="principal"))
    ns.teacher = client_for(
        world.a.slug, factories.member(world.a, role="teacher", username="lab.teacher", full_name="Kavya Nair")
    )
    ns.rule = ns.admin.post(f"{S}/rules", {"single_approval_limit": "50000.00"}, format="json").json()
    item = {"code": "MIC-01", "name": "Compound microscope", "unit": "each"}
    ns.item = ns.keeper.post(f"{S}/items", item, format="json").json()
    return ns


def requisition(s, quantity, cost, client=None):
    body = {"title": "Biology lab", "lines": [{"item": s.item["id"], "quantity": str(quantity), "unit_cost": cost}]}
    return (client or s.keeper).post(f"{S}/requisitions", body, format="json")


def post(client, url, body=None):
    return client.post(url, body or {}, format="json")


def test_tst030_approval_follows_the_rule_revision_it_was_submitted_under(s):
    made = requisition(s, 4, "20000.00")
    assert made.status_code == 201, made.json()
    big = made.json()
    assert (big["total"], big["rule_revision"], big["approvals_needed"]) == ("80000.00", 1, 2)
    post(s.admin, f"{S}/rules", {"single_approval_limit": "100000.00"})
    small = requisition(s, 1, "20000.00").json()
    assert (small["rule_revision"], small["approvals_needed"]) == (2, 1)
    url = f"{S}/requisitions/{big['id']}"
    assert post(s.keeper, f"{url}/approve").status_code == 403
    assert post(s.principal, f"{url}/approve").json()["state"] == "submitted"  # one of two
    assert post(s.principal, f"{url}/approve").status_code == 409
    assert post(s.admin, f"{url}/approve").json()["state"] == "approved"
    own = requisition(s, 1, "100.00", client=s.admin).json()
    assert post(s.admin, f"{S}/requisitions/{own['id']}/approve").status_code == 403  # raised it


def test_receipt_never_exceeds_the_order_and_stock_never_goes_negative(s):
    req = requisition(s, 10, "1500.00").json()
    url, line = f"{S}/requisitions/{req['id']}", req["lines"][0]["id"]
    receive = f"{url}/receive"
    assert post(s.keeper, receive, {"lines": [{"line": line, "quantity": "1"}]}).status_code == 409  # not ordered
    post(s.principal, f"{url}/approve")
    supplier = post(s.keeper, f"{S}/suppliers", {"name": "Lab Supplies Co"}).json()
    assert post(s.keeper, f"{url}/order", {"supplier": supplier["id"]}).json()["state"] == "ordered"
    assert post(s.keeper, receive, {"lines": [{"line": line, "quantity": "11"}]}).status_code == 422
    assert post(s.keeper, receive, {"lines": [{"line": line, "quantity": "6"}]}).json()["state"] == (
        "partially_received"
    )
    assert post(s.keeper, receive, {"lines": [{"line": line, "quantity": "5"}]}).status_code == 422
    assert post(s.keeper, receive, {"lines": [{"line": line, "quantity": "4"}]}).json()["state"] == "received"
    assert s.keeper.get(f"{S}/items").json()[0]["on_hand"] == "10.00"
    out = {"item": s.item["id"], "kind": "issue", "quantity": "7", "reference": "Biology lab"}
    assert post(s.keeper, f"{S}/stock", out).status_code == 201
    short = post(s.keeper, f"{S}/stock", {**out, "quantity": "4"})
    assert short.status_code == 409 and short.json()["code"] == "insufficient_stock"
    assert s.keeper.get(f"{S}/items").json()[0]["on_hand"] == "3.00"


def test_tst030_no_double_booking_and_maintenance_blocks_booking(s):
    lab = {"tag": "LAB-PHY-1", "name": "Physics lab", "category": "Laboratory", "bookable": True}
    asset = post(s.keeper, f"{S}/assets", lab).json()
    day = (timezone.now() + dt.timedelta(days=7)).replace(hour=4, minute=0, second=0, microsecond=0)

    def book(client, start, hours):
        body = {
            "asset": asset["id"],
            "starts_at": (day + dt.timedelta(hours=start)).isoformat(),
            "ends_at": (day + dt.timedelta(hours=start + hours)).isoformat(),
            "purpose": "Practical",
        }
        return post(client, f"{S}/bookings", body)

    first = book(s.teacher, 0, 2)
    assert first.status_code == 201, first.json()
    assert [b["mine"] for b in s.teacher.get(f"{S}/bookings").json()] == [True]
    clash = book(s.keeper, 1.5, 1)
    assert clash.status_code == 409 and clash.json()["code"] == "booking_conflict"
    assert book(s.keeper, 2, 1).status_code == 201  # back to back is fine
    assert book(s.teacher, -24 * 30, 1).status_code == 422  # in the past
    post(s.keeper, f"{S}/assets/{asset['id']}/maintenance", {"note": "Bench wiring"})
    blocked = book(s.teacher, 5, 1)
    assert blocked.status_code == 409 and blocked.json()["code"] == "asset_unavailable"
    assert post(s.principal, f"{S}/bookings/{first.json()['id']}/cancel").status_code == 403
    assert post(s.teacher, f"{S}/bookings/{first.json()['id']}/cancel").json()["canceled"] is True
    post(s.keeper, f"{S}/assets/{asset['id']}/back")
    assert book(s.teacher, 0, 1).status_code == 201


def test_asset_custody_and_disposal(s):
    asset = post(s.keeper, f"{S}/assets", {"tag": "PRJ-7", "name": "Projector"}).json()
    url = f"{S}/assets/{asset['id']}"
    custodian = Membership.objects.get(user__username="lab.teacher")
    assert post(s.keeper, f"{url}/transfer", {"username": "nobody"}).status_code == 422
    moved = post(s.keeper, f"{url}/transfer", {"username": "Lab.Teacher", "note": "Physics lab"}).json()
    assert moved["custodian"] == {"id": str(custodian.id), "name": "Kavya Nair"}
    assert post(s.keeper, f"{url}/dispose").status_code == 422  # needs the reason
    gone = post(s.keeper, f"{url}/dispose", {"reason": "Beyond repair, committee minute 3/2026"}).json()
    assert gone["status"] == "disposed"
    assert post(s.keeper, f"{url}/maintenance", {"note": "Try again"}).status_code == 409
    assert [e["kind"] for e in s.keeper.get(url).json()["events"]] == ["transferred", "disposed"]
    assert post(s.teacher, f"{S}/assets", {"tag": "X-1", "name": "Chair"}).status_code == 403


def test_module_gate_and_isolation(world, s, client_for):
    req = requisition(s, 1, "100.00").json()
    switch_on(world.b, modules=("assets",))
    outsider = client_for(world.b.slug, world.b_admin)
    assert post(outsider, f"{S}/requisitions/{req['id']}/approve").status_code == 404
    switch_on(world.a, modules=("students",))
    assert s.keeper.get(f"{S}/items").status_code == 404
