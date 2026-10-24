"""The fee subledger (slice 8 S8-01..09; pack 08 §6, WF-FIN §9, EX-01).

Every financial step posts one balanced journal under a unique posting key (repeating a step posts nothing new).
Balances are worked out from posted records, never stored:
net charges = lines − posted credit notes; net allocated = allocations − reversals;
outstanding = net charges − net allocated. A refund returns money; it never forgives a charge."""

import hashlib
import hmac
import json
import secrets
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.permissions import has_perm, today_for
from common import audit
from common.exceptions import Problem
from fees.models import (
    Allocation,
    AllocationReversal,
    CreditNote,
    FeeHead,
    FeePlan,
    Invoice,
    InvoiceLine,
    Journal,
    JournalLine,
    Payment,
    ProviderConfig,
    ProviderEvent,
    Receipt,
    ReconciliationCase,
    Refund,
    Settlement,
    StudentAccount,
)
from students.models import Student

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def money(value) -> str:
    return str(Decimal(value).quantize(CENT))


def _require(actor, institution, perm: str, student: Student | None = None) -> None:
    scope = student.scope if student is not None else ("institution", None)
    if not has_perm(actor, institution, perm, scope):
        raise PermissionDenied("Your role does not allow this.")


# Journals (S8-06)


def post(institution, key: str, source: str, memo: str, lines: list[tuple]) -> Journal:
    """lines: (account, debit, credit, student, invoice). Balanced or refused; the same key twice posts once."""
    if found := Journal.objects.filter(institution=institution, posting_key=key).first():
        return found
    if len(lines) < 2:
        raise ValueError("A journal needs at least two lines.")
    debits = sum((Decimal(d) for _, d, _, _, _ in lines), ZERO)
    credits = sum((Decimal(c) for _, _, c, _, _ in lines), ZERO)
    if debits != credits or any((Decimal(d) > 0) == (Decimal(c) > 0) for _, d, c, _, _ in lines):
        raise ValueError(f"Unbalanced journal {key}: {debits} ≠ {credits}.")
    journal = Journal.objects.create(
        institution=institution, posting_key=key, source=source, date=today_for(institution), memo=memo
    )
    for account, debit, credit, student, invoice in lines:
        JournalLine.objects.create(
            journal=journal, account=account, debit=debit, credit=credit, student=student, invoice=invoice
        )
    return journal


def trial_balance(institution) -> list[dict]:
    rows = (
        JournalLine.objects.filter(journal__institution=institution)
        .values("account")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
        .order_by("account")
    )
    return [{"account": r["account"], "balance": money(r["debit"] - r["credit"])} for r in rows]


# Accounts, plans and invoices (S8-01, S8-02)


def account_of(student: Student) -> StudentAccount:
    found, _ = StudentAccount.objects.get_or_create(institution=student.institution, student=student, currency="INR")
    return found


def _number(institution, model, prefix: str) -> str:
    from institutions.models import Institution

    Institution.objects.select_for_update().get(pk=institution.pk)  # numbers one at a time, never reused
    stem = f"{prefix}-{timezone.now().year}-"
    field = "account__institution" if model is Invoice else "institution"
    taken = model.objects.filter(**{field: institution}, number__startswith=stem).values_list("number", flat=True)
    return f"{stem}{max((int(n[len(stem) :]) for n in taken), default=0) + 1:05d}"


def save_head(actor, institution, data: dict) -> FeeHead:
    _require(actor, institution, "fees.manage")
    if FeeHead.objects.filter(institution=institution, code=data["code"]).exists():
        raise ValidationError({"code": ["Another fee head has this code."]})
    return FeeHead.objects.create(institution=institution, **data)


def _lines(institution, lines: list[dict]) -> list[dict]:
    heads = {str(h.id): h for h in FeeHead.objects.filter(institution=institution)}
    if not lines or any(str(line["head"]) not in heads for line in lines):
        raise ValidationError({"lines": ["Give at least one line with one of this institution's fee heads."]})
    return [{**line, "head": heads[str(line["head"])]} for line in lines]


def save_plan(actor, institution, data: dict) -> FeePlan:
    _require(actor, institution, "fees.manage")
    lines = _lines(institution, data["lines"])
    stored = [{"head": str(x["head"].id), "amount": money(x["amount"]), "due_on": str(x["due_on"])} for x in lines]
    return FeePlan.objects.create(institution=institution, name=data["name"], lines=stored)


def publish_plan(actor, plan: FeePlan, version: int) -> FeePlan:
    _require(actor, plan.institution, "fees.manage")
    with transaction.atomic():
        plan = FeePlan.objects.select_for_update().get(pk=plan.pk)
        plan.check_version(version)
        if plan.status != FeePlan.Status.DRAFT:
            raise Problem(409, "invalid_transition", "Only a draft plan is published.")
        plan.status = FeePlan.Status.PUBLISHED
        plan.save()
        return plan


def revise_plan(actor, plan: FeePlan) -> FeePlan:
    _require(actor, plan.institution, "fees.manage")
    latest = FeePlan.objects.filter(family=plan.family).order_by("-revision").first()
    if latest.status == FeePlan.Status.DRAFT:
        return latest
    return FeePlan.objects.create(
        institution=plan.institution, family=plan.family, revision=latest.revision + 1, name=plan.name, lines=plan.lines
    )


def issue_invoice(actor, student: Student, data: dict) -> Invoice:
    institution = student.institution
    _require(actor, institution, "fees.manage", student)
    plan = None
    if data.get("plan"):
        plan = FeePlan.objects.filter(institution=institution, pk=data["plan"], status=FeePlan.Status.PUBLISHED).first()
        if plan is None:
            raise ValidationError({"plan": ["Choose a published fee plan."]})
        heads = {str(h.id): h for h in FeeHead.objects.filter(institution=institution)}
        lines = [
            {"head": heads[x["head"]], "amount": Decimal(x["amount"]), "description": heads[x["head"]].name}
            for x in plan.lines
        ]
        due_on = min(x["due_on"] for x in plan.lines)
    else:
        lines = _lines(institution, data.get("lines", []))
        due_on = data.get("due_on")
        if not due_on:
            raise ValidationError({"due_on": ["Give the due date."]})
    return create_invoice(actor, student, lines, due_on, plan)


def create_invoice(actor, student: Student, lines: list[dict], due_on, plan: FeePlan | None = None) -> Invoice:
    """Issue and post an invoice. Callers check authority: fees staff through issue_invoice, other services (library
    fines) for their own approved charges."""
    institution = student.institution
    with transaction.atomic():
        invoice = Invoice.objects.create(
            account=account_of(student),
            number=_number(institution, Invoice, "INV"),
            issued_on=today_for(institution),
            due_on=due_on,
            plan=plan,
            plan_revision=plan.revision if plan else None,
            issued_by=actor,
        )
        total = ZERO
        for line in lines:
            InvoiceLine.objects.create(
                invoice=invoice,
                head=line["head"],
                description=line.get("description") or line["head"].name,
                amount=line["amount"],
            )
            total += Decimal(line["amount"])
        post(
            institution,
            f"invoice:{invoice.id}",
            "invoice",
            f"Invoice {invoice.number}",
            [("receivable", total, 0, student, invoice), ("fee_income", 0, total, student, invoice)],
        )
        audit.log(
            actor,
            "fees.invoice_issued",
            student,
            f"Invoice {invoice.number} for {money(total)}",
            institution=institution,
        )
        return invoice


def balances(invoice: Invoice) -> dict:
    issued = invoice.lines.aggregate(t=Sum("amount"))["t"] or ZERO
    credited = invoice.credit_notes.filter(state=CreditNote.State.POSTED).aggregate(t=Sum("amount"))["t"] or ZERO
    allocated = invoice.allocations.aggregate(t=Sum("amount"))["t"] or ZERO
    reversed_ = AllocationReversal.objects.filter(allocation__invoice=invoice).aggregate(t=Sum("amount"))["t"] or ZERO
    net_charges, net_allocated = issued - credited, allocated - reversed_
    outstanding = net_charges - net_allocated
    state = "paid" if outstanding == 0 and net_charges > 0 else "partially_paid" if net_allocated > 0 else "issued"
    if net_charges == 0:
        state = "cancelled"
    return {
        "issued_charges": issued,
        "credit_notes": credited,
        "net_charges": net_charges,
        "net_allocated": net_allocated,
        "outstanding": outstanding,
        "state": state,
    }


def _allocation_left(allocation: Allocation) -> Decimal:
    return allocation.amount - (allocation.reversals.aggregate(t=Sum("amount"))["t"] or ZERO)


# Credit notes (S8-03)


def request_credit(actor, invoice: Invoice, data: dict) -> CreditNote:
    student = invoice.account.student
    _require(actor, student.institution, "fees.manage", student)
    if data["amount"] <= 0 or data["amount"] > balances(invoice)["net_charges"]:
        raise ValidationError({"amount": ["A credit note is more than 0 and at most what is still charged."]})
    return CreditNote.objects.create(invoice=invoice, requested_by=actor, **data)


def decide_credit(actor, note: CreditNote, approve: bool) -> CreditNote:
    invoice = note.invoice
    student = invoice.account.student
    _require(actor, student.institution, "fees.approve", student)
    if note.requested_by_id == actor.id:
        raise PermissionDenied("Someone other than who asked approves a credit note.")
    with transaction.atomic():
        note = CreditNote.objects.select_for_update().get(pk=note.pk)
        if note.state != CreditNote.State.REQUESTED:
            raise Problem(409, "invalid_transition", "This credit note has been decided.")
        note.state = CreditNote.State.POSTED if approve else CreditNote.State.REJECTED
        note.decided_by, note.decided_at = actor, timezone.now()
        note.save()
        if approve:
            institution = student.institution
            post(
                institution,
                f"credit:{note.id}",
                "credit_note",
                f"{note.get_kind_display()} on {invoice.number}",
                [("concessions", note.amount, 0, student, invoice), ("receivable", 0, note.amount, student, invoice)],
            )
            excess = -balances(invoice)["outstanding"]
            if excess > 0:  # charged less than is already paid: the excess goes back to unapplied funds
                _reverse(invoice.allocations.order_by("-posted_at"), excess, "credit_note", credit_note=note)
                post(
                    institution,
                    f"credit-excess:{note.id}",
                    "credit_note",
                    f"Excess paid on {invoice.number} back to credit",
                    [("receivable", excess, 0, student, invoice), ("unapplied", 0, excess, student, invoice)],
                )
            audit.log(
                actor,
                "fees.credit_posted",
                student,
                f"{note.get_kind_display()} {money(note.amount)} on {invoice.number}",
                institution=institution,
            )
        return note


def _reverse(allocations, amount: Decimal, reason: str, refund=None, credit_note=None) -> list[tuple]:
    left, done = amount, []
    for allocation in allocations:
        if left <= 0:
            break
        take = min(_allocation_left(allocation), left)
        if take > 0:
            AllocationReversal.objects.create(
                allocation=allocation, amount=take, reason=reason, refund=refund, credit_note=credit_note
            )
            done.append((allocation.invoice, take))
            left -= take
    return done


# Payments, receipts and allocation (S8-04)


def unapplied_of(payment: Payment) -> Decimal:
    if payment.state != Payment.State.SUCCEEDED:
        return ZERO
    allocated = sum((_allocation_left(a) for a in payment.allocations.all()), ZERO)
    refunded = payment.refunds.filter(state=Refund.State.SUCCEEDED).aggregate(t=Sum("amount"))["t"] or ZERO
    return payment.amount - allocated - refunded


def _succeed(payment: Payment) -> Payment:
    """A confirmed payment: receipt, cash in, then allocation to its order's invoice or the oldest dues."""
    account = payment.account
    student, institution = account.student, account.institution
    payment.state, payment.succeeded_at = Payment.State.SUCCEEDED, timezone.now()
    payment.save()
    body = json.dumps(
        {"payment": str(payment.id), "amount": money(payment.amount), "student": student.number}, sort_keys=True
    )
    Receipt.objects.create(
        institution=institution,
        payment=payment,
        number=_number(institution, Receipt, "RCT"),
        content_hash=hashlib.sha256(body.encode()).hexdigest(),
    )
    post(
        institution,
        f"payment:{payment.id}",
        "payment",
        f"{payment.channel} received from {student.number}",
        [("clearing", payment.amount, 0, student, None), ("unapplied", 0, payment.amount, student, None)],
    )
    return payment


def allocate(
    actor, payment: Payment, invoices: list[Invoice] | None = None, amounts: dict | None = None
) -> list[Allocation]:
    """Allocate the payment's unapplied money: to the given invoices (and amounts), else oldest due first."""
    account = payment.account
    student = account.student
    targets = invoices if invoices is not None else list(account.invoices.order_by("due_on", "number"))
    made = []
    for invoice in targets:
        left = unapplied_of(payment)
        if left <= 0:
            break
        due = balances(invoice)["outstanding"]
        take = min(left, due, Decimal(amounts[str(invoice.id)]) if amounts and str(invoice.id) in amounts else due)
        if take <= 0:
            continue
        allocation = Allocation.objects.create(payment=payment, invoice=invoice, amount=take)
        post(
            account.institution,
            f"allocation:{allocation.id}",
            "allocation",
            f"{payment.channel} to {invoice.number}",
            [("unapplied", take, 0, student, invoice), ("receivable", 0, take, student, invoice)],
        )
        made.append(allocation)
    return made


def collect(actor, student: Student, data: dict) -> Payment:
    """An office collection (cash, cheque, bank transfer): received when the cashier records it."""
    institution = student.institution
    _require(actor, institution, "fees.collect", student)
    if data["amount"] <= 0:
        raise ValidationError({"amount": ["Give an amount above 0."]})
    with transaction.atomic():
        payment = Payment.objects.create(
            account=account_of(student),
            amount=data["amount"],
            channel=data["channel"],
            provider="office",
            external_id=f"office-{secrets.token_hex(8)}",
            state=Payment.State.PENDING,
            reference=data.get("reference", ""),
            recorded_by=actor,
        )
        _succeed(payment)
        targets = None
        if data.get("allocations"):
            ids = [x["invoice"] for x in data["allocations"]]
            targets = list(Invoice.objects.filter(account=payment.account, pk__in=ids))
            allocate(actor, payment, targets, {str(x["invoice"]): x["amount"] for x in data["allocations"]})
        else:
            allocate(actor, payment)
        audit.log(
            actor,
            "fees.payment_received",
            student,
            f"{money(payment.amount)} by {payment.channel}",
            institution=institution,
        )
        return payment


# Refunds (S8-05)


def _plan_refund(payment: Payment, amount: Decimal) -> list[tuple]:
    """Unapplied money first, then the payment's allocations newest first: [(invoice, amount reversed)]."""
    from_allocations = max(amount - unapplied_of(payment), ZERO)
    plan, left = [], from_allocations
    for allocation in payment.allocations.order_by("-posted_at"):
        take = min(_allocation_left(allocation), left)
        if take > 0:
            plan.append((allocation.invoice, take))
            left -= take
    return plan


def request_refund(actor, payment: Payment, amount: Decimal, reason: str) -> tuple[Refund, dict]:
    student = payment.account.student
    _require(actor, student.institution, "fees.collect", student)
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.state != Payment.State.SUCCEEDED:
            raise Problem(409, "invalid_transition", "Only a received payment is refunded.")
        reserved = payment.refunds.filter(state__in=Refund.RESERVED).aggregate(t=Sum("amount"))["t"] or ZERO
        if amount <= 0 or reserved + amount > payment.amount:
            raise ValidationError(
                {"amount": [f"At most {money(payment.amount - reserved)} can still be refunded from this payment."]}
            )
        refund = Refund.objects.create(payment=payment, amount=amount, reason=reason, requested_by=actor)
        return refund, impact(refund)


def impact(refund: Refund) -> dict:
    plan = _plan_refund(refund.payment, refund.amount)
    invoices = {i for i, _ in plan}
    after = sum((balances(i)["outstanding"] + sum(a for j, a in plan if j == i) for i in invoices), ZERO)
    return {
        "outstanding_after": money(after) if invoices else None,
        "reverses": [{"invoice": i.number, "amount": money(a)} for i, a in plan],
    }


def approve_refund(actor, refund: Refund) -> Refund:
    student = refund.payment.account.student
    _require(actor, student.institution, "fees.approve", student)
    if refund.requested_by_id == actor.id:
        raise PermissionDenied("Someone other than who asked approves a refund.")
    with transaction.atomic():
        refund = Refund.objects.select_for_update().get(pk=refund.pk)
        if refund.state != Refund.State.REQUESTED:
            raise Problem(409, "invalid_transition", "This refund has been decided.")
        refund.state, refund.approved_by = Refund.State.APPROVED, actor
        refund.save()
        return refund


def reject_refund(actor, refund: Refund) -> Refund:
    student = refund.payment.account.student
    _require(actor, student.institution, "fees.approve", student)
    if refund.state != Refund.State.REQUESTED:
        raise Problem(409, "invalid_transition", "This refund has been decided.")
    refund.state = Refund.State.REJECTED
    refund.save()
    return refund


def complete_refund(actor, refund: Refund, reference: str = "", failed: bool = False) -> Refund:
    """Money actually returned (office confirmation or a provider event): reverse allocations, then cash out."""
    payment = refund.payment
    student, institution = payment.account.student, payment.account.institution
    if actor is not None:
        _require(actor, institution, "fees.collect", student)
    with transaction.atomic():
        refund = Refund.objects.select_for_update().get(pk=refund.pk)
        if refund.state != Refund.State.APPROVED:
            if refund.state in (Refund.State.SUCCEEDED, Refund.State.FAILED):
                return refund  # a repeated confirmation changes nothing
            raise Problem(409, "invalid_transition", "Only an approved refund is completed.")
        if failed:
            refund.state = Refund.State.FAILED  # the reservation is released with it
            refund.save()
            return refund
        for invoice, amount in _plan_refund(payment, refund.amount):
            _reverse(
                payment.allocations.filter(invoice=invoice).order_by("-posted_at"), amount, "refund", refund=refund
            )
            post(
                institution,
                f"refund-reversal:{refund.id}:{invoice.id}",
                "refund",
                f"Refund reopens {invoice.number}",
                [("receivable", amount, 0, student, invoice), ("unapplied", 0, amount, student, invoice)],
            )
        refund.state, refund.completed_at, refund.provider_ref = Refund.State.SUCCEEDED, timezone.now(), reference
        refund.save()
        post(
            institution,
            f"refund:{refund.id}",
            "refund",
            f"Refund to {student.number}",
            [("unapplied", refund.amount, 0, student, None), ("clearing", 0, refund.amount, student, None)],
        )
        audit.log(
            actor,
            "fees.refunded",
            student,
            f"{money(refund.amount)} refunded: {refund.reason}",
            institution=institution,
        )
        return refund


# Provider, orders, events and settlement (S8-07, S8-08)


def configure(actor, institution, data: dict) -> ProviderConfig:
    _require(actor, institution, "fees.reconcile")
    if data["provider"] != "sandbox":
        raise ValidationError({"provider": ["Only the test-mode sandbox exists until a provider is chosen."]})
    found, _ = ProviderConfig.objects.update_or_create(institution=institution, defaults={**data, "mode": "test"})
    audit.log(
        actor,
        "fees.provider_configured",
        institution,
        "Payment provider set to the test-mode sandbox",
        institution=institution,
    )
    return found


def create_order(student: Student, invoice: Invoice, actor) -> Payment:
    config = ProviderConfig.objects.filter(institution=student.institution).first()
    if config is None:
        raise Problem(409, "integration_not_configured", "Online payment isn't set up here; pay at the office.")
    due = balances(invoice)["outstanding"]
    if due <= 0:
        raise ValidationError({"invoice": ["Nothing is outstanding on this invoice."]})
    return Payment.objects.create(
        account=invoice.account,
        amount=due,
        channel="online",
        provider=config.provider,
        invoice=invoice,
        external_id=f"ord_{secrets.token_hex(10)}",
        state=Payment.State.PENDING,
        recorded_by=actor,
    )


def handle_event(institution, provider: str, raw: bytes, signature: str) -> tuple[int, str]:
    config = ProviderConfig.objects.filter(institution=institution, provider=provider).first()
    if config is None:
        raise NotFound()
    expected = hmac.new(config.webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        return 400, "invalid_signature"
    try:
        event = json.loads(raw)
        event_id, kind = str(event["event_id"]), str(event["type"])
    except (ValueError, KeyError, TypeError):
        return 400, "malformed"
    with transaction.atomic():
        stored, made = ProviderEvent.objects.get_or_create(
            provider=provider, event_id=event_id, defaults={"institution": institution, "kind": kind, "payload": event}
        )
        if not made:
            return 200, "duplicate"
        stored.outcome = _apply(institution, config, provider, event_id, kind, event)
        stored.save(update_fields=["outcome"])
        return 200, stored.outcome


def _quarantine(institution, source: str, expected, observed, why: str) -> str:
    ReconciliationCase.objects.create(
        institution=institution, source=source, expected=expected, observed=observed, discrepancy=why
    )
    return "quarantined"


def _apply(institution, config, provider, event_id, kind, event) -> str:
    source = f"{provider} event {event_id}"
    if kind.startswith("payment."):
        payment = (
            Payment.objects.select_for_update()
            .filter(provider=provider, external_id=event.get("order_id"), account__institution=institution)
            .first()
        )
        if payment is None:
            return _quarantine(institution, source, None, None, "Event for an order Eduma didn't create.")
        if payment.state != Payment.State.PENDING:
            return f"ignored: payment already {payment.state}"  # out of order or late: never undo a final state
        if kind == "payment.failed":
            payment.state = Payment.State.FAILED
            payment.save()
            return "failed"
        try:
            observed = Decimal(str(event.get("amount")))
        except ArithmeticError:
            observed = None
        if (
            observed != payment.amount
            or event.get("currency") != payment.currency
            or event.get("merchant_id") != config.merchant_id
        ):
            return _quarantine(
                institution, source, payment.amount, observed, "Amount or currency or merchant doesn't match the order."
            )
        _succeed(payment)
        allocate(None, payment, [payment.invoice] if payment.invoice_id else None)
        allocate(None, payment)  # anything left goes to other dues, oldest first
        return "succeeded"
    if kind in ("refund.succeeded", "refund.failed"):
        refund = Refund.objects.filter(pk=event.get("refund_id"), payment__account__institution=institution).first()
        if refund is None:
            return _quarantine(institution, source, None, None, "Refund event Eduma can't match.")
        complete_refund(None, refund, reference=event_id, failed=kind == "refund.failed")
        return kind.split(".")[1]
    return "ignored: unknown type"


def settle(actor, institution, data: dict) -> Settlement:
    _require(actor, institution, "fees.reconcile")
    if data["gross"] - data["fee"] != data["net"]:
        raise ValidationError({"net": ["Net is gross less fees."]})
    payments = list(
        Payment.objects.filter(
            account__institution=institution,
            pk__in=data["payments"],
            state=Payment.State.SUCCEEDED,
            provider=data["provider"],
        )
    )
    if len(payments) != len(set(data["payments"])):
        raise ValidationError({"payments": ["Choose received online payments of this provider."]})
    with transaction.atomic():
        if Settlement.objects.filter(provider=data["provider"], batch_ref=data["batch_ref"]).exists():
            raise ValidationError({"batch_ref": ["This settlement batch is already recorded."]})
        settlement = Settlement.objects.create(
            institution=institution,
            provider=data["provider"],
            batch_ref=data["batch_ref"],
            bank_ref=data["bank_ref"],
            gross=data["gross"],
            fee=data["fee"],
            net=data["net"],
            recorded_by=actor,
        )
        settlement.payments.set(payments)
        lines = [("bank", data["net"], 0, None, None), ("clearing", 0, data["gross"], None, None)]
        if data["fee"] > 0:
            lines.insert(1, ("provider_fees", data["fee"], 0, None, None))
        post(institution, f"settlement:{settlement.id}", "settlement", f"Settlement {settlement.batch_ref}", lines)
        expected = sum((p.amount for p in payments), ZERO)
        if expected != data["gross"]:
            _quarantine(
                institution,
                f"settlement {settlement.batch_ref}",
                expected,
                data["gross"],
                "Settlement gross differs from its payments.",
            )
        return settlement


def resolve(actor, case: ReconciliationCase, resolution: str) -> ReconciliationCase:
    _require(actor, case.institution, "fees.reconcile")
    if not resolution.strip():
        raise ValidationError({"resolution": ["Say how it was resolved."]})
    case.state, case.resolution, case.resolved_by = ReconciliationCase.State.RESOLVED, resolution.strip(), actor
    case.save()
    return case


# Items


def invoice_item(invoice: Invoice) -> dict:
    b = balances(invoice)
    return {
        "id": str(invoice.id),
        "number": invoice.number,
        "issued_on": invoice.issued_on,
        "due_on": invoice.due_on,
        "plan_revision": invoice.plan_revision,
        "lines": [
            {"head": x.head.code, "description": x.description, "amount": money(x.amount)}
            for x in invoice.lines.select_related("head")
        ],
        **{k: (money(v) if isinstance(v, Decimal) else v) for k, v in b.items()},
        "credit_notes_list": [
            {"id": str(n.id), "kind": n.kind, "amount": money(n.amount), "reason": n.reason, "state": n.state}
            for n in invoice.credit_notes.all()
        ],
    }


def payment_item(payment: Payment) -> dict:
    receipt = getattr(payment, "receipt", None)
    return {
        "id": str(payment.id),
        "amount": money(payment.amount),
        "channel": payment.channel,
        "state": payment.state,
        "state_label": payment.get_state_display(),
        "reference": payment.reference,
        "order_id": payment.external_id if payment.provider != "office" else None,
        "created_at": payment.created_at,
        "receipt": {"number": receipt.number, "issued_at": receipt.issued_at} if receipt else None,
        "unapplied": money(unapplied_of(payment)),
        "refunds": [
            {"id": str(r.id), "amount": money(r.amount), "state": r.state, "reason": r.reason}
            for r in payment.refunds.all()
        ],
    }


def statement(student: Student) -> dict:
    account = account_of(student)
    invoices = [invoice_item(i) for i in account.invoices.all()]
    payments = list(account.payments.select_related("receipt"))
    return {
        "student": {"id": str(student.id), "number": student.number, "full_name": student.person.full_name},
        "currency": account.currency,
        "invoices": invoices,
        "payments": [payment_item(p) for p in payments],
        "outstanding": money(sum((Decimal(i["outstanding"]) for i in invoices), ZERO)),
        "unapplied": money(sum((unapplied_of(p) for p in payments), ZERO)),
        "online": ProviderConfig.objects.filter(institution=student.institution).exists(),
    }


def head_for(institution, code: str, name: str) -> FeeHead:
    found, _ = FeeHead.objects.get_or_create(institution=institution, code=code, defaults={"name": name})
    return found
