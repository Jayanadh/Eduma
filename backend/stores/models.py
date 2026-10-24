"""Procurement, stock, assets and lab booking (slice 10b S10B-06..09)."""

import uuid

from django.conf import settings
from django.db import models

Money = {"max_digits": 12, "decimal_places": 2}


def _id():
    return models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class ProcurementRule(models.Model):
    """Who must approve a purchase, by revision; published revisions never change (S10B-06)."""

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    revision = models.PositiveSmallIntegerField()
    single_approval_limit = models.DecimalField(**Money)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revision"]
        constraints = [models.UniqueConstraint(fields=["institution", "revision"], name="unique_rule_revision")]


class Supplier(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=120)
    contact = models.CharField(max_length=120, blank=True)


class Item(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=20, default="each")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_item_code")]


class Requisition(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Waiting for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ORDERED = "ordered", "Ordered"
        PARTIAL = "partially_received", "Partly received"
        RECEIVED = "received", "Received"

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=150)
    state = models.CharField(max_length=20, choices=State.choices, default=State.SUBMITTED)
    rule = models.ForeignKey(ProcurementRule, on_delete=models.PROTECT, related_name="+")
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RequisitionLine(models.Model):
    id = _id()
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(**Money)
    received = models.DecimalField(max_digits=10, decimal_places=2, default=0)


class Approval(models.Model):
    id = _id()
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["requisition", "approver"], name="one_approval_each")]


class StockMovement(models.Model):
    id = _id()
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="movements")
    quantity = models.DecimalField(max_digits=10, decimal_places=2)  # + in, − out
    kind = models.CharField(max_length=10)  # receive / issue / return / adjust
    reference = models.CharField(max_length=150, blank=True)
    moved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    moved_at = models.DateTimeField(auto_now_add=True)


class Asset(models.Model):
    class Status(models.TextChoices):
        IN_USE = "in_use", "In use"
        MAINTENANCE = "maintenance", "In maintenance"
        DISPOSED = "disposed", "Disposed"

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    tag = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=60, blank=True)
    location = models.CharField(max_length=80, blank=True)
    custodian = models.ForeignKey(
        "accounts.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    bookable = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_USE)
    disposal_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["institution", "tag"], name="unique_asset_tag")]


class AssetEvent(models.Model):
    id = _id()
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=20)  # transferred / maintenance / back_in_use / disposed
    note = models.CharField(max_length=200)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    at = models.DateTimeField(auto_now_add=True)


class Booking(models.Model):
    id = _id()
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="bookings")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    purpose = models.CharField(max_length=150)
    booked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    canceled = models.BooleanField(default=False)

    class Meta:
        ordering = ["starts_at"]
