"""The fee subledger (slice 8; EX-01, TST-015, TST-016, TST-026)."""

import hashlib
import hmac
import json

import pytest

from academics.tests.conftest import enrolled_student
from admissions.tests.conftest import switch_on
from fees.models import Journal, JournalLine, Payment, Receipt
from testing import factories

F = "/api/v1/institution/fees"


@pytest.fixture
def money(world, client_for):
    switch_on(world.a, modules=("admissions", "students", "fees"))
    m = type("M", (), {})()
    m.student = enrolled_student(world.a, "2026-0001", name="Kiran Rao")
    m.accountant = client_for(world.a.slug, factories.member(world.a, role="accountant", username="cashier"))
    m.principal = client_for(world.a.slug, factories.member(world.a, role="principal", username="head"))
    m.head = m.accountant.post(f"{F}/heads", {"code": "TUITION", "name": "Tuition"}, format="json").json()
    m.invoice = m.accountant.post(
        f"{F}/students/{m.student.id}/invoices",
        {
            "due_on": "2026-11-15",
            "lines": [{"head": m.head["id"], "amount": "10000.00", "description": "Tuition 2026–27"}],
        },
        format="json",
    ).json()
    return m


def balance(client, invoice):
    return client.get(f"{F}/invoices/{invoice['id']}").json()


def trial(client):
    return {row["account"]: row["balance"] for row in client.get(f"{F}/trial-balance").json()}


def test_ex01_refund_does_not_forgive_the_charge(money):
    """TST-015: 10,000 − 1,000 concession − 6,000 paid = 3,000; refunding 1,000 makes it 4,000."""
    m = money
    assert balance(m.accountant, m.invoice)["outstanding"] == "10000.00"
    note = m.accountant.post(
        f"{F}/credit-notes",
        {"invoice": m.invoice["id"], "kind": "concession", "amount": "1000.00", "reason": "Sibling concession"},
        format="json",
    ).json()
    assert m.accountant.post(f"{F}/credit-notes/{note['id']}/approve", {}, format="json").status_code == 403
    assert m.principal.post(f"{F}/credit-notes/{note['id']}/approve", {}, format="json").json()["state"] == "posted"
    paid = m.accountant.post(
        f"{F}/payments",
        {"student": str(m.student.id), "amount": "6000.00", "channel": "cash", "reference": "Counter 1"},
        format="json",
    )
    assert paid.status_code == 201, paid.json()
    assert paid.json()["receipt"]["number"].startswith("RCT-")
    shown = balance(m.accountant, m.invoice)
    assert (
        shown["issued_charges"],
        shown["credit_notes"],
        shown["net_charges"],
        shown["net_allocated"],
        shown["outstanding"],
        shown["state"],
    ) == ("10000.00", "1000.00", "9000.00", "6000.00", "3000.00", "partially_paid")
    refund = m.accountant.post(
        f"{F}/refunds",
        {"payment": paid.json()["id"], "amount": "1000.00", "reason": "Overpaid transport"},
        format="json",
    )
    assert refund.status_code == 201, refund.json()
    assert refund.json()["impact"] == {
        "outstanding_after": "4000.00",
        "reverses": [{"invoice": m.invoice["number"], "amount": "1000.00"}],
    }
    assert m.accountant.post(f"{F}/refunds/{refund.json()['id']}/approve", {}, format="json").status_code == 403
    m.principal.post(f"{F}/refunds/{refund.json()['id']}/approve", {}, format="json")
    assert balance(m.accountant, m.invoice)["outstanding"] == "3000.00"  # nothing moves until the refund is confirmed
    done = m.accountant.post(
        f"{F}/refunds/{refund.json()['id']}/complete", {"reference": "Cash returned"}, format="json"
    )
    assert done.json()["state"] == "succeeded"
    shown = balance(m.accountant, m.invoice)
    assert (shown["net_charges"], shown["net_allocated"], shown["outstanding"]) == ("9000.00", "5000.00", "4000.00")
    assert trial(m.accountant) == {
        "receivable": "4000.00",
        "fee_income": "-10000.00",
        "concessions": "1000.00",
        "clearing": "5000.00",
        "unapplied": "0.00",
    }
    for journal in Journal.objects.all():
        lines = list(journal.lines.all())
        assert len(lines) >= 2 and sum(x.debit for x in lines) == sum(x.credit for x in lines)
    assert Receipt.objects.count() == 1


def test_refund_capacity_and_overpayment(money):
    m = money
    paid = m.accountant.post(
        f"{F}/payments",
        {"student": str(m.student.id), "amount": "12000.00", "channel": "bank_transfer", "reference": "NEFT 991"},
        format="json",
    ).json()
    statement = m.accountant.get(f"{F}/students/{m.student.id}/statement").json()
    assert (statement["outstanding"], statement["unapplied"]) == ("0.00", "2000.00")
    first = m.accountant.post(
        f"{F}/refunds", {"payment": paid["id"], "amount": "8000.00", "reason": "a"}, format="json"
    )
    assert first.status_code == 201
    over = m.accountant.post(f"{F}/refunds", {"payment": paid["id"], "amount": "4500.00", "reason": "b"}, format="json")
    assert over.status_code == 422  # 8,000 already reserved of 12,000
    assert first.json()["impact"]["reverses"] == [
        {"invoice": m.invoice["number"], "amount": "6000.00"}
    ]  # unapplied first


def test_a_credit_note_below_what_is_paid_returns_the_excess(money):
    m = money
    m.accountant.post(
        f"{F}/payments", {"student": str(m.student.id), "amount": "10000.00", "channel": "cash"}, format="json"
    )
    note = m.accountant.post(
        f"{F}/credit-notes",
        {"invoice": m.invoice["id"], "kind": "cancellation", "amount": "2500.00", "reason": "Left early"},
        format="json",
    ).json()
    m.principal.post(f"{F}/credit-notes/{note['id']}/approve", {}, format="json")
    shown = balance(m.accountant, m.invoice)
    assert (shown["net_charges"], shown["net_allocated"], shown["outstanding"]) == ("7500.00", "7500.00", "0.00")
    assert m.accountant.get(f"{F}/students/{m.student.id}/statement").json()["unapplied"] == "2500.00"


def test_an_unconfigured_provider_is_honest(money):
    """TST-026."""
    refused = money.accountant.post(f"{F}/orders", {"invoice": money.invoice["id"]}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "integration_not_configured"


def sign(secret, body):
    raw = json.dumps(body).encode()
    return raw, hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def test_provider_events_post_once(world, money, client_for):
    """TST-016: duplicate and out-of-order events change nothing twice; bad signatures and mismatches don't post."""
    m = money
    admin = client_for(world.a.slug, world.a_admin)
    admin.put(
        f"{F}/provider",
        {"provider": "sandbox", "merchant_id": "ASTER-TEST", "webhook_secret": "whsec-test-123"},
        format="json",
    )
    order = m.accountant.post(f"{F}/orders", {"invoice": m.invoice["id"]}, format="json").json()
    assert (order["state"], order["amount"]) == ("pending", "10000.00")
    hook = f"/api/v1/webhooks/payments/sandbox/{world.a.id}"
    public = client_for(None)
    event = {
        "event_id": "evt_1",
        "type": "payment.succeeded",
        "order_id": order["order_id"],
        "amount": "10000.00",
        "currency": "INR",
        "merchant_id": "ASTER-TEST",
    }
    raw, signature = sign("whsec-test-123", event)
    bad = public.post(hook, raw, content_type="application/json", HTTP_X_EDUMA_SIGNATURE="0" * 64)
    assert bad.status_code == 400 and Payment.objects.get(external_id=order["order_id"]).state == "pending"
    for _ in range(2):
        assert (
            public.post(hook, raw, content_type="application/json", HTTP_X_EDUMA_SIGNATURE=signature).status_code == 200
        )
    late_fail = {**event, "event_id": "evt_0", "type": "payment.failed"}
    raw2, sig2 = sign("whsec-test-123", late_fail)
    public.post(hook, raw2, content_type="application/json", HTTP_X_EDUMA_SIGNATURE=sig2)
    payment = Payment.objects.get(external_id=order["order_id"])
    assert payment.state == "succeeded" and Receipt.objects.filter(payment=payment).count() == 1
    assert balance(m.accountant, m.invoice)["outstanding"] == "0.00"
    assert JournalLine.objects.filter(account="clearing", debit__gt=0).count() == 1
    second = m.accountant.post(
        f"{F}/students/{m.student.id}/invoices",
        {"due_on": "2026-12-15", "lines": [{"head": m.head["id"], "amount": "500.00", "description": "Lab"}]},
        format="json",
    ).json()
    order2 = m.accountant.post(f"{F}/orders", {"invoice": second["id"]}, format="json").json()
    wrong = {**event, "event_id": "evt_2", "order_id": order2["order_id"], "amount": "50.00"}
    raw3, sig3 = sign("whsec-test-123", wrong)
    public.post(hook, raw3, content_type="application/json", HTTP_X_EDUMA_SIGNATURE=sig3)
    assert Payment.objects.get(external_id=order2["order_id"]).state == "pending"
    cases = m.accountant.get(f"{F}/cases").json()
    assert [c["discrepancy"][:15] for c in cases] == ["Amount or curre"]
    settled = m.accountant.post(
        f"{F}/settlements",
        {
            "provider": "sandbox",
            "batch_ref": "SET-1",
            "bank_ref": "UTR-1",
            "gross": "10000.00",
            "fee": "200.00",
            "net": "9800.00",
            "payments": [str(payment.id)],
        },
        format="json",
    )
    assert settled.status_code == 201, settled.json()
    tb = trial(m.accountant)
    assert (tb["clearing"], tb["bank"], tb["provider_fees"]) == ("0.00", "9800.00", "200.00")


def test_plans_and_who_sees_statements(world, money, client_for):
    m = money
    plan = m.accountant.post(
        f"{F}/plans",
        {"name": "Class 6 2026–27", "lines": [{"head": m.head["id"], "amount": "8000.00", "due_on": "2026-07-15"}]},
        format="json",
    ).json()
    plan = m.accountant.post(f"{F}/plans/{plan['id']}/publish", {"version": plan["version"]}, format="json").json()
    made = m.accountant.post(f"{F}/students/{m.student.id}/invoices", {"plan": plan["id"]}, format="json").json()
    assert (made["plan_revision"], made["issued_charges"]) == (1, "8000.00")
    revised = m.accountant.post(f"{F}/plans/{plan['id']}/revise", {}, format="json").json()
    assert revised["revision"] == 2 and balance(m.accountant, made)["issued_charges"] == "8000.00"
    teacher = client_for(world.a.slug, factories.member(world.a, role="teacher"))
    assert teacher.get(f"{F}/students/{m.student.id}/statement").status_code == 403
    switch_on(world.b, modules=("students", "fees"))
    assert client_for(world.b.slug, world.b_admin).get(f"{F}/invoices/{m.invoice['id']}").status_code == 404
