"""The fee subledger (slice 8 S8-01..08; pack 08 §6). Money is exact decimal INR; posted records are never edited —
corrections are new records (credit notes, reversals, refunds)."""

import uuid

from django.conf import settings
from django.db import models

from common.models import VersionedModel

Money = {"max_digits": 12, "decimal_places": 2}


def _id():
    return models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class FeeHead(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_fee_head")]


class FeePlan(VersionedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    family = models.UUIDField(default=uuid.uuid4)
    revision = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    lines = models.JSONField(default=list)  # [{"head": id, "amount": "10000.00", "due_on": "2026-07-15"}]

    class Meta:
        ordering = ["name", "-revision"]
        constraints = [models.UniqueConstraint(fields=["family", "revision"], name="unique_plan_revision")]


class StudentAccount(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="fee_accounts")
    currency = models.CharField(max_length=3, default="INR")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["institution", "student", "currency"], name="one_account")]


class Invoice(models.Model):
    id = _id()
    account = models.ForeignKey(StudentAccount, on_delete=models.PROTECT, related_name="invoices")
    number = models.CharField(max_length=30)
    issued_on = models.DateField()
    due_on = models.DateField()
    plan = models.ForeignKey(FeePlan, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    plan_revision = models.PositiveSmallIntegerField(null=True, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["due_on", "number"]


class InvoiceLine(models.Model):
    id = _id()
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="lines")
    head = models.ForeignKey(FeeHead, on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=150)
    amount = models.DecimalField(**Money)


class CreditNote(models.Model):
    class State(models.TextChoices):
        REQUESTED = "requested", "Waiting for approval"
        POSTED = "posted", "Approved and posted"
        REJECTED = "rejected", "Rejected"

    id = _id()
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="credit_notes")
    kind = models.CharField(max_length=12, choices=[("concession", "Concession"), ("cancellation", "Cancellation")])
    amount = models.DecimalField(**Money)
    reason = models.CharField(max_length=300)
    state = models.CharField(max_length=10, choices=State.choices, default=State.REQUESTED)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)


class Payment(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Confirmation pending"
        SUCCEEDED = "succeeded", "Received"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    id = _id()
    account = models.ForeignKey(StudentAccount, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(**Money)
    currency = models.CharField(max_length=3, default="INR")
    channel = models.CharField(max_length=14)  # cash, cheque, bank_transfer, online
    provider = models.CharField(max_length=20, default="office")
    external_id = models.CharField(max_length=80)
    invoice = models.ForeignKey(
        Invoice, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )  # online order
    state = models.CharField(max_length=10, choices=State.choices)
    reference = models.CharField(max_length=120, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    succeeded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "external_id"], name="unique_provider_payment")]


class Receipt(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="receipt")
    number = models.CharField(max_length=30)
    issued_at = models.DateTimeField(auto_now_add=True)
    content_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["institution", "number"], name="unique_receipt_number")]


class Allocation(models.Model):
    id = _id()
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(**Money)
    posted_at = models.DateTimeField(auto_now_add=True)


class Refund(models.Model):
    class State(models.TextChoices):
        REQUESTED = "requested", "Waiting for approval"
        APPROVED = "approved", "Approved, waiting for confirmation"
        SUCCEEDED = "succeeded", "Refunded"
        FAILED = "failed", "Failed"
        REJECTED = "rejected", "Rejected"

    RESERVED = ("requested", "approved", "succeeded")

    id = _id()
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(**Money)
    reason = models.CharField(max_length=300)
    state = models.CharField(max_length=10, choices=State.choices, default=State.REQUESTED)
    provider_ref = models.CharField(max_length=80, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    completed_at = models.DateTimeField(null=True, blank=True)


class AllocationReversal(models.Model):
    id = _id()
    allocation = models.ForeignKey(Allocation, on_delete=models.PROTECT, related_name="reversals")
    amount = models.DecimalField(**Money)
    reason = models.CharField(max_length=60)  # refund / credit_note
    refund = models.ForeignKey(Refund, null=True, blank=True, on_delete=models.PROTECT, related_name="reversals")
    credit_note = models.ForeignKey(
        CreditNote, null=True, blank=True, on_delete=models.PROTECT, related_name="reversals"
    )
    posted_at = models.DateTimeField(auto_now_add=True)


class Journal(models.Model):
    """A balanced posting; append-only. The posting key makes repeating a step harmless."""

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    posting_key = models.CharField(max_length=120)
    source = models.CharField(max_length=40)
    date = models.DateField()
    memo = models.CharField(max_length=200)
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["posted_at"]
        constraints = [models.UniqueConstraint(fields=["institution", "posting_key"], name="unique_posting_key")]


class JournalLine(models.Model):
    ACCOUNTS = ("receivable", "fee_income", "concessions", "clearing", "unapplied", "bank", "provider_fees")

    id = _id()
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name="lines")
    account = models.CharField(max_length=16)
    debit = models.DecimalField(default=0, **Money)
    credit = models.DecimalField(default=0, **Money)
    student = models.ForeignKey("students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0, credit=0) | models.Q(debit=0, credit__gt=0)), name="one_positive_side"
            )
        ]


class ProviderConfig(models.Model):
    """An institution's payment provider. Only the test-mode sandbox exists until a real provider is chosen (D-12)."""

    id = _id()
    institution = models.OneToOneField("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    provider = models.CharField(max_length=20)
    mode = models.CharField(max_length=6, default="test")
    merchant_id = models.CharField(max_length=60)
    webhook_secret = models.CharField(max_length=80)


class ProviderEvent(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    provider = models.CharField(max_length=20)
    event_id = models.CharField(max_length=80)
    kind = models.CharField(max_length=40)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    outcome = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="unique_provider_event")]


class Settlement(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    provider = models.CharField(max_length=20)
    batch_ref = models.CharField(max_length=80)
    bank_ref = models.CharField(max_length=80)
    gross = models.DecimalField(**Money)
    fee = models.DecimalField(**Money)
    net = models.DecimalField(**Money)
    payments = models.ManyToManyField(Payment, related_name="settlements")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "batch_ref"], name="unique_settlement")]


class ReconciliationCase(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    source = models.CharField(max_length=120)
    expected = models.DecimalField(null=True, blank=True, **Money)
    observed = models.DecimalField(null=True, blank=True, **Money)
    discrepancy = models.CharField(max_length=300)
    state = models.CharField(max_length=10, choices=State.choices, default=State.OPEN)
    resolution = models.CharField(max_length=300, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    opened_at = models.DateTimeField(auto_now_add=True)
