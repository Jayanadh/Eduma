"""Library, transport and hostel (slice 10a S10A-01..09)."""

import uuid

from django.conf import settings
from django.db import models

Money = {"max_digits": 10, "decimal_places": 2}


def _id():
    return models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


# Library


class Title(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=80, blank=True)
    replacement_cost = models.DecimalField(default=500, **Money)

    class Meta:
        ordering = ["title"]


class Copy(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ISSUED = "issued", "Issued"
        RESERVED = "reserved", "Held for a reservation"
        LOST = "lost", "Lost"
        DAMAGED = "damaged", "Damaged"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = _id()
    title = models.ForeignKey(Title, on_delete=models.PROTECT, related_name="copies")
    accession = models.CharField(max_length=30)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AVAILABLE)
    held_for = models.ForeignKey("Reservation", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    held_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["accession"]
        constraints = [models.UniqueConstraint(fields=["title", "accession"], name="unique_accession")]


class Loan(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "On loan"
        RETURNED = "returned", "Returned"
        LOST = "lost", "Lost"

    id = _id()
    copy = models.ForeignKey(Copy, on_delete=models.PROTECT, related_name="loans")
    # A borrower is a student (with or without a login) or a member of staff.
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="loans"
    )
    staff = models.ForeignKey(
        "accounts.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="loans"
    )
    issued_on = models.DateField()
    due_on = models.DateField()
    renewals = models.PositiveSmallIntegerField(default=0)
    returned_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-issued_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["copy"], condition=models.Q(status="active"), name="one_active_loan_per_copy"
            )
        ]


class Reservation(models.Model):
    id = _id()
    title = models.ForeignKey(Title, on_delete=models.PROTECT, related_name="reservations")
    student = models.ForeignKey("students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    staff = models.ForeignKey("accounts.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    placed_at = models.DateTimeField(auto_now_add=True)
    fulfilled = models.BooleanField(default=False)
    canceled = models.BooleanField(default=False)

    class Meta:
        ordering = ["placed_at"]


class Fine(models.Model):
    id = _id()
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="fines")
    amount = models.DecimalField(**Money)
    reason = models.CharField(max_length=120)
    invoice = models.ForeignKey("fees.Invoice", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    waived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    waived_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# Transport


class Vehicle(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    registration = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField()


class Route(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=80)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="routes")
    stops = models.JSONField(default=list)  # [{"name": "Lake Road", "time": "07:40"}, …] in order


class Rider(models.Model):
    id = _id()
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="riders")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="rides")
    stop = models.CharField(max_length=80)
    starts_on = models.DateField()
    ends_on = models.DateField()


class Pickup(models.Model):
    """Someone named by the office as allowed to collect a student at the stop (besides guardians with a link)."""

    id = _id()
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="pickups")
    full_name = models.CharField(max_length=120)
    relationship = models.CharField(max_length=40)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")


class Trip(models.Model):
    class State(models.TextChoices):
        PLANNED = "planned", "Planned"
        DISPATCHED = "dispatched", "Dispatched"
        IN_PROGRESS = "in_progress", "On the way"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    id = _id()
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="trips")
    date = models.DateField()
    direction = models.CharField(max_length=8)  # to_school / home
    driver = models.ForeignKey("accounts.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    attendant = models.ForeignKey(
        "accounts.Membership", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    state = models.CharField(max_length=12, choices=State.choices, default=State.PLANNED)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["route", "date", "direction"], name="one_trip")]


class Boarding(models.Model):
    id = _id()
    trip = models.ForeignKey(Trip, on_delete=models.PROTECT, related_name="boardings")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="+")
    boarded_at = models.DateTimeField()
    dropped_at = models.DateTimeField(null=True, blank=True)
    handed_to = models.CharField(max_length=120, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["trip", "student"], name="one_boarding")]


# Hostel


class Hostel(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=80)


class Bed(models.Model):
    id = _id()
    hostel = models.ForeignKey(Hostel, on_delete=models.PROTECT, related_name="beds")
    room = models.CharField(max_length=20)
    label = models.CharField(max_length=10)

    class Meta:
        ordering = ["room", "label"]
        constraints = [models.UniqueConstraint(fields=["hostel", "room", "label"], name="unique_bed")]


class Allocation(models.Model):
    class State(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        ALLOCATED = "allocated", "In residence"
        CHECKED_OUT = "checked_out", "Checked out"
        REJECTED = "rejected", "Rejected"

    HOLDING = ("approved", "allocated")

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="hostel_allocations")
    bed = models.ForeignKey(Bed, null=True, blank=True, on_delete=models.PROTECT, related_name="allocations")
    starts_on = models.DateField()
    ends_on = models.DateField()
    state = models.CharField(max_length=12, choices=State.choices, default=State.REQUESTED)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )


class OutPass(models.Model):
    class State(models.TextChoices):
        REQUESTED = "requested", "Waiting for the warden"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", "Back"

    id = _id()
    allocation = models.ForeignKey(Allocation, on_delete=models.PROTECT, related_name="out_passes")
    leaves_at = models.DateTimeField()
    returns_at = models.DateTimeField()
    reason = models.CharField(max_length=200)
    state = models.CharField(max_length=10, choices=State.choices, default=State.REQUESTED)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    returned_at = models.DateTimeField(null=True, blank=True)
