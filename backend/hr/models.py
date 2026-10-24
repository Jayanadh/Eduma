"""Leave, staff attendance and the payroll boundary (slice 10b S10B-01..05)."""

import uuid

from django.conf import settings
from django.db import models

Money = {"max_digits": 12, "decimal_places": 2}


def _id():
    return models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class LeaveType(models.Model):
    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=60)
    days_per_year = models.PositiveSmallIntegerField()
    paid = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_leave_type")]


class LeaveRequest(models.Model):
    class State(models.TextChoices):
        SUBMITTED = "submitted", "Waiting for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELED = "canceled", "Canceled"

    id = _id()
    employee = models.ForeignKey("accounts.Employee", on_delete=models.PROTECT, related_name="leave")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="+")
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.CharField(max_length=300)
    state = models.CharField(max_length=10, choices=State.choices, default=State.SUBMITTED)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_on"]

    @property
    def days(self) -> int:
        return (self.ends_on - self.starts_on).days + 1


class StaffAttendance(models.Model):
    id = _id()
    employee = models.ForeignKey("accounts.Employee", on_delete=models.PROTECT, related_name="attendance")
    date = models.DateField()
    status = models.CharField(max_length=10)  # present / absent / half_day / on_leave
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "date"], name="one_staff_mark_per_day")]


class Compensation(models.Model):
    """Protected: only payroll.manage reads or writes it (S10B-04)."""

    id = _id()
    employee = models.ForeignKey("accounts.Employee", on_delete=models.PROTECT, related_name="compensation")
    monthly_gross = models.DecimalField(**Money)
    components = models.JSONField(default=dict)  # {"basic": "30000.00", "hra": "12000.00", …}
    deductions = models.JSONField(default=dict)  # institution-entered, e.g. {"pf": "1800.00"}
    effective_from = models.DateField()

    class Meta:
        ordering = ["-effective_from"]


class PayrollCycle(models.Model):
    class State(models.TextChoices):
        PREPARED = "prepared", "Prepared"
        VALIDATED = "validated", "Validated"
        APPROVED = "approved", "Approved"
        EXPORTED = "exported", "Exported"

    id = _id()
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="+")
    month = models.DateField()  # the first day of the month
    state = models.CharField(max_length=10, choices=State.choices, default=State.PREPARED)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    exported_at = models.DateTimeField(null=True, blank=True)
    inputs_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-month"]
        constraints = [models.UniqueConstraint(fields=["institution", "month"], name="one_payroll_per_month")]


class PayrollLine(models.Model):
    id = _id()
    cycle = models.ForeignKey(PayrollCycle, on_delete=models.CASCADE, related_name="lines")
    employee = models.ForeignKey("accounts.Employee", on_delete=models.PROTECT, related_name="+")
    gross = models.DecimalField(**Money)
    unpaid_days = models.PositiveSmallIntegerField(default=0)
    unpaid_deduction = models.DecimalField(default=0, **Money)
    deductions = models.DecimalField(default=0, **Money)
    net = models.DecimalField(**Money)
