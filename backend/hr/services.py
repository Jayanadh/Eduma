"""Leave, staff attendance and the payroll boundary (slice 10b S10B-01..05). Payroll stops at an approved, exported
file: Eduma doesn't pay anyone, and statutory deductions are entered by the institution, not worked out here."""

import csv
import datetime as dt
import hashlib
import io
import json
from calendar import monthrange
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Employee, Membership
from accounts.permissions import has_perm
from common import audit
from common.exceptions import Problem
from hr.models import Compensation, LeaveRequest, LeaveType, PayrollCycle, PayrollLine, StaffAttendance
from imports.services import _safe

CENT = Decimal("0.01")
State = LeaveRequest.State
LIVE = (State.SUBMITTED, State.APPROVED)
MARKS = ("present", "absent", "half_day")
COLUMNS = ["employee_number", "name", "gross", "unpaid_days", "unpaid_deduction", "deductions", "net"]


def require(actor, institution, perm: str, message: str) -> None:
    if not has_perm(actor, institution, perm):
        raise PermissionDenied(message)


def employee_of(user, institution, create=False) -> Employee | None:
    membership = Membership.objects.filter(user=user, institution=institution, kind=Membership.Kind.STAFF).first()
    if membership is None:
        return None
    if create:
        return Employee.objects.get_or_create(institution=institution, membership=membership)[0]
    return Employee.objects.filter(membership=membership).first()


def person(employee: Employee) -> dict:
    return {"id": str(employee.id), "number": employee.employee_number, "name": employee.membership.user.full_name}


# Leave


def add_type(actor, institution, data: dict) -> LeaveType:
    require(actor, institution, "hr.manage", "Only HR sets leave types.")
    code = data["code"].strip().upper()
    if LeaveType.objects.filter(institution=institution, code=code).exists():
        raise ValidationError({"code": ["That code is taken."]})
    return LeaveType.objects.create(institution=institution, **{**data, "code": code})


def _days(rows, first=None, last=None) -> int:
    """Calendar days of `rows`, counting only those between first and last when given."""
    return sum((min(r.ends_on, last or r.ends_on) - max(r.starts_on, first or r.starts_on)).days + 1 for r in rows)


def balances(employee: Employee, year: int) -> list[dict]:
    rows = list(LeaveRequest.objects.filter(employee=employee, starts_on__year=year, state__in=LIVE))
    out = []
    for kind in LeaveType.objects.filter(institution=employee.institution).order_by("code"):
        taken = _days(r for r in rows if r.leave_type_id == kind.id and r.state == State.APPROVED)
        waiting = _days(r for r in rows if r.leave_type_id == kind.id and r.state == State.SUBMITTED)
        entitled = kind.days_per_year
        out.append(
            {"code": kind.code, "name": kind.name, "entitled": entitled, "taken": taken, "waiting": waiting,
             "left": entitled - taken}
        )  # fmt: skip
    return out


def request_leave(actor, institution, kind: LeaveType, starts_on, ends_on, reason: str) -> LeaveRequest:
    employee = employee_of(actor, institution, create=True)
    if employee is None:
        raise PermissionDenied("Only staff ask for leave.")
    if ends_on < starts_on:
        raise ValidationError({"ends_on": ["Leave can't end before it starts."]})
    if starts_on.year != ends_on.year:
        raise ValidationError({"ends_on": ["Split leave across the year end into two requests."]})
    days = (ends_on - starts_on).days + 1
    with transaction.atomic():
        Employee.objects.select_for_update().get(pk=employee.pk)  # one request at a time per person
        live = LeaveRequest.objects.filter(employee=employee, state__in=LIVE)
        if live.filter(starts_on__lte=ends_on, ends_on__gte=starts_on).exists():
            raise ValidationError({"starts_on": ["You already have leave on some of these days."]})
        used = _days(live.filter(leave_type=kind, starts_on__year=starts_on.year))
        if used + days > kind.days_per_year:
            left = max(kind.days_per_year - used, 0)
            raise ValidationError({"ends_on": [f"{left} days of {kind.name.lower()} left this year."]})
        made = LeaveRequest.objects.create(
            employee=employee, leave_type=kind, starts_on=starts_on, ends_on=ends_on, reason=reason
        )
    audit.log(actor, "leave.requested", made, f"Asked for {days} days of {kind.name}", institution=institution)
    return made


def _move(leave: LeaveRequest, allowed: tuple, to: str, **fields) -> LeaveRequest:
    with transaction.atomic():
        leave = LeaveRequest.objects.select_for_update().get(pk=leave.pk)
        if leave.state not in allowed:
            raise Problem(409, "invalid_transition", f"This request is already {leave.get_state_display().lower()}.")
        leave.state = to
        for key, value in fields.items():
            setattr(leave, key, value)
        leave.save()
    return leave


def decide(actor, institution, leave: LeaveRequest, approve: bool) -> LeaveRequest:
    require(actor, institution, "hr.leave_approve", "You can't approve leave.")
    if leave.employee.membership.user_id == actor.id:
        raise PermissionDenied("Someone else decides your own leave.")
    done = _move(leave, (State.SUBMITTED,), State.APPROVED if approve else State.REJECTED, decided_by=actor)
    audit.log(actor, f"leave.{done.state}", done, f"{done.get_state_display()} leave", institution=institution)
    return done


def cancel(actor, institution, leave: LeaveRequest) -> LeaveRequest:
    """The days come back by themselves: balances count only submitted and approved requests."""
    if leave.employee.membership.user_id != actor.id:
        require(actor, institution, "hr.manage", "Only the person or HR cancels leave.")
    done = _move(leave, LIVE, State.CANCELED)
    audit.log(actor, "leave.canceled", done, "Canceled leave", institution=institution)
    return done


def leave_item(r: LeaveRequest) -> dict:
    kind = r.leave_type
    return {
        "id": str(r.id),
        "employee": person(r.employee),
        "leave_type": {"id": str(kind.id), "code": kind.code, "name": kind.name, "paid": kind.paid},
        "starts_on": r.starts_on.isoformat(),
        "ends_on": r.ends_on.isoformat(),
        "days": r.days,
        "reason": r.reason,
        "state": r.state,
        "decided_by": r.decided_by.full_name if r.decided_by_id else None,
    }


# Staff attendance


def staff(institution):
    return (
        Employee.objects.filter(institution=institution, membership__status=Membership.Status.ACTIVE)
        .select_related("membership__user")
        .order_by("employee_number", "membership__user__full_name")
    )


def day_sheet(institution, date: dt.date) -> list[dict]:
    marks = dict(
        StaffAttendance.objects.filter(employee__institution=institution, date=date).values_list(
            "employee_id", "status"
        )
    )
    away = set(
        LeaveRequest.objects.filter(
            employee__institution=institution, state=State.APPROVED, starts_on__lte=date, ends_on__gte=date
        ).values_list("employee_id", flat=True)
    )
    return [{**person(e), "status": "on_leave" if e.id in away else marks.get(e.id)} for e in staff(institution)]


def record_day(actor, institution, date: dt.date, marks: list[dict]) -> None:
    require(actor, institution, "hr.manage", "Only HR records staff attendance.")
    people = {str(e.id): e for e in staff(institution)}
    for mark in marks:
        if str(mark["employee"]) not in people or mark["status"] not in MARKS:
            raise ValidationError({"marks": [f"Can't record {mark['status']} for {mark['employee']}."]})
    with transaction.atomic():
        for mark in marks:
            StaffAttendance.objects.update_or_create(
                employee=people[str(mark["employee"])],
                date=date,
                defaults={"status": mark["status"], "recorded_by": actor},
            )
    audit.log(actor, "staff_attendance.recorded", institution, f"Staff attendance for {date}")


# Pay (S10B-04): every read and write checks payroll.manage


def set_pay(actor, institution, employee: Employee, data: dict) -> Compensation:
    require(actor, institution, "payroll.manage", "Only payroll sees or changes pay.")
    made = Compensation.objects.create(
        employee=employee,
        monthly_gross=data["monthly_gross"],
        components={k: str(v) for k, v in data.get("components", {}).items()},
        deductions={k: str(v) for k, v in data.get("deductions", {}).items()},
        effective_from=data["effective_from"],
    )
    audit.log(actor, "pay.changed", employee, f"Pay from {made.effective_from}", institution=institution)
    return made


def pay_history(actor, institution, employee: Employee) -> list[dict]:
    require(actor, institution, "payroll.manage", "Only payroll sees or changes pay.")
    return [
        {
            "id": str(c.id),
            "monthly_gross": str(c.monthly_gross),
            "components": c.components,
            "deductions": c.deductions,
            "effective_from": c.effective_from.isoformat(),
        }
        for c in employee.compensation.all()
    ]


def directory(actor, institution) -> list[dict]:
    """Staff with their numbers; pay appears only for payroll.manage."""
    sees_pay = has_perm(actor, institution, "payroll.manage")
    if not (sees_pay or has_perm(actor, institution, "hr.manage")):
        raise PermissionDenied("Only HR and payroll see the staff list.")
    rows = [person(e) for e in staff(institution)]
    if sees_pay:
        current = {}
        today = timezone.localdate()
        for c in Compensation.objects.filter(employee__institution=institution, effective_from__lte=today).order_by(
            "employee_id", "-effective_from"
        ):
            current.setdefault(str(c.employee_id), str(c.monthly_gross))
        rows = [{**row, "pay": current.get(row["id"])} for row in rows]
    return rows


# Payroll (S10B-05)


def _lines(institution, first: dt.date, last: dt.date) -> list[PayrollLine]:
    pays = {}
    for c in Compensation.objects.filter(employee__institution=institution, effective_from__lte=last).order_by(
        "employee_id", "-effective_from"
    ):
        pays.setdefault(c.employee_id, c)
    unpaid = defaultdict(list)
    for r in LeaveRequest.objects.filter(
        employee__institution=institution,
        state=State.APPROVED,
        leave_type__paid=False,
        starts_on__lte=last,
        ends_on__gte=first,
    ):
        unpaid[r.employee_id].append(r)
    lines = []
    for e in Employee.objects.filter(institution=institution, id__in=pays).select_related("membership__user"):
        if (e.left_on and e.left_on < first) or (e.joined_on and e.joined_on > last):
            continue
        pay, days = pays[e.id], _days(unpaid[e.id], first, last)
        cut = (pay.monthly_gross * days / last.day).quantize(CENT, ROUND_HALF_UP)
        deductions = sum((Decimal(v) for v in pay.deductions.values()), Decimal("0.00"))
        lines.append(
            PayrollLine(
                employee=e,
                gross=pay.monthly_gross,
                unpaid_days=days,
                unpaid_deduction=cut,
                deductions=deductions,
                net=pay.monthly_gross - cut - deductions,
            )
        )
    return lines


def prepare(actor, institution, month: dt.date) -> PayrollCycle:
    require(actor, institution, "payroll.manage", "Only payroll prepares payroll.")
    first = month.replace(day=1)
    last = first.replace(day=monthrange(first.year, first.month)[1])
    lines = _lines(institution, first, last)
    snapshot = [[str(x.employee_id), str(x.gross), x.unpaid_days, str(x.deductions)] for x in lines]
    try:
        with transaction.atomic():
            cycle = PayrollCycle.objects.create(
                institution=institution,
                month=first,
                prepared_by=actor,
                inputs_hash=hashlib.sha256(json.dumps(snapshot).encode()).hexdigest(),
            )
            for line in lines:
                line.cycle = cycle
            PayrollLine.objects.bulk_create(lines)
    except IntegrityError:
        raise Problem(409, "cycle_exists", f"Payroll for {first:%B %Y} already exists.") from None
    audit.log(actor, "payroll.prepared", cycle, f"Prepared payroll for {first:%B %Y}", institution=institution)
    return cycle


def _step(cycle: PayrollCycle, allowed: str, to: str, **fields) -> PayrollCycle:
    with transaction.atomic():
        cycle = PayrollCycle.objects.select_for_update().get(pk=cycle.pk)
        if cycle.state != allowed:
            raise Problem(409, "invalid_transition", f"This payroll is {cycle.get_state_display().lower()}.")
        cycle.state = to
        for key, value in fields.items():
            setattr(cycle, key, value)
        cycle.save()
    return cycle


def validate(actor, institution, cycle: PayrollCycle) -> PayrollCycle:
    require(actor, institution, "payroll.manage", "Only payroll validates payroll.")
    lines = list(cycle.lines.select_related("employee"))
    if not lines:
        raise ValidationError({"lines": ["Nobody has pay set for this month."]})
    if negative := [x.employee.employee_number for x in lines if x.net < 0]:
        raise ValidationError({"lines": [f"Net pay below zero for {', '.join(negative)}."]})
    done = _step(cycle, PayrollCycle.State.PREPARED, PayrollCycle.State.VALIDATED)
    audit.log(actor, "payroll.validated", done, "Validated payroll", institution=institution)
    return done


def approve(actor, institution, cycle: PayrollCycle) -> PayrollCycle:
    require(actor, institution, "payroll.approve", "You can't approve payroll.")
    if cycle.prepared_by_id == actor.id:
        raise PermissionDenied("Someone other than who prepared it approves payroll.")
    done = _step(cycle, PayrollCycle.State.VALIDATED, PayrollCycle.State.APPROVED, approved_by=actor)
    audit.log(actor, "payroll.approved", done, "Approved payroll", institution=institution)
    return done


def export(actor, institution, cycle: PayrollCycle) -> PayrollCycle:
    """Hands the approved cycle to the payroll or bank system; from here it never changes."""
    require(actor, institution, "payroll.manage", "Only payroll exports payroll.")
    done = _step(cycle, PayrollCycle.State.APPROVED, PayrollCycle.State.EXPORTED, exported_at=timezone.now())
    audit.log(actor, "payroll.exported", done, "Exported payroll", institution=institution)
    return done


def export_file(actor, institution, cycle: PayrollCycle) -> str:
    """The exported cycle's file: the same every time it is downloaded."""
    require(actor, institution, "payroll.manage", "Only payroll downloads payroll.")
    if cycle.state != PayrollCycle.State.EXPORTED:
        raise Problem(409, "invalid_transition", "Export the payroll first.")
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for x in cycle.lines.select_related("employee__membership__user").order_by("employee__employee_number"):
        e = x.employee
        writer.writerow(
            [_safe(e.employee_number), _safe(e.membership.user.full_name), x.gross, x.unpaid_days,
             x.unpaid_deduction, x.deductions, x.net]
        )  # fmt: skip
    return out.getvalue()


def cycle_item(cycle: PayrollCycle, lines=False) -> dict:
    rows = list(cycle.lines.select_related("employee__membership__user").order_by("employee__employee_number"))
    item = {
        "id": str(cycle.id),
        "month": cycle.month.isoformat(),
        "state": cycle.state,
        "prepared_by": cycle.prepared_by.full_name,
        "approved_by": cycle.approved_by.full_name if cycle.approved_by_id else None,
        "exported_at": cycle.exported_at.isoformat() if cycle.exported_at else None,
        "people": len(rows),
        "net": str(sum((x.net for x in rows), Decimal("0.00"))),
    }
    if lines:
        item["lines"] = [
            {
                "employee": person(x.employee),
                "gross": str(x.gross),
                "unpaid_days": x.unpaid_days,
                "unpaid_deduction": str(x.unpaid_deduction),
                "deductions": str(x.deductions),
                "net": str(x.net),
            }
            for x in rows
        ]
    return item
