"""The library (slice 10a S10A-01..04): copies are locked while issuing, so the last copy goes to one borrower;
returning twice does nothing the second time; fines are kept even when waived."""

import datetime as dt
from decimal import Decimal

from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Membership
from accounts.permissions import has_perm, today_for
from campus.models import Copy, Fine, Loan, Reservation, Title
from common import audit
from common.exceptions import Problem
from configuration.gates import module_on

MANAGE = "library.manage"
LOAN_DAYS, HOLD_DAYS, RENEWALS = 14, 3, 2
LIMIT = {"student": 3, "staff": 5}
DAILY_FINE = Decimal("2.00")


def require(actor, institution) -> None:
    if not has_perm(actor, institution, MANAGE):
        raise PermissionDenied("Only the library can do this.")


def add_title(actor, institution, data: dict) -> Title:
    require(actor, institution)
    copies = data.pop("copies", [])
    with transaction.atomic():
        made = Title.objects.create(institution=institution, **data)
        for accession in copies:
            Copy.objects.create(title=made, accession=accession)
        return made


def _who(student=None, staff=None) -> dict:
    return {"student": student} if student is not None else {"staff": staff}


def _check_borrower(institution, student=None, staff=None) -> None:
    who = _who(student, staff)
    if student is not None and (student.institution_id != institution.id or student.status != "active"):
        raise ValidationError({"student": ["Only an active student of this institution borrows."]})
    if staff is not None and (staff.institution_id != institution.id or staff.status != Membership.Status.ACTIVE):
        raise ValidationError({"staff": ["Only active staff borrow."]})
    active = Loan.objects.filter(status=Loan.Status.ACTIVE, **who)
    if active.filter(due_on__lt=today_for(institution)).exists():
        raise ValidationError({"borrower": ["Something is overdue; return it first."]})
    limit = LIMIT["student" if student is not None else "staff"]
    if active.count() >= limit:
        raise ValidationError({"borrower": [f"Already {limit} books out."]})


def issue(actor, institution, accession: str, student=None, staff=None) -> Loan:
    require(actor, institution)
    _check_borrower(institution, student, staff)
    today = today_for(institution)
    try:
        with transaction.atomic():
            copy = Copy.objects.select_for_update().filter(title__institution=institution, accession=accession).first()
            if copy is None:
                raise ValidationError({"accession": ["No copy has this accession number."]})
            holder = copy.held_for
            mine = (
                holder is not None
                and holder.student_id == (student.id if student else None)
                and holder.staff_id == (staff.id if staff else None)
            )
            if copy.status == Copy.Status.RESERVED and not mine and (copy.held_until or today) >= today:
                raise Problem(409, "copy_unavailable", f"{accession} is held for someone who reserved it.")
            if copy.status not in (Copy.Status.AVAILABLE, Copy.Status.RESERVED):
                raise Problem(409, "copy_unavailable", f"{accession} is {copy.get_status_display().lower()}.")
            loan = Loan.objects.create(
                copy=copy,
                issued_on=today,
                due_on=today + dt.timedelta(days=LOAN_DAYS),
                issued_by=actor,
                **_who(student, staff),
            )
            if holder is not None:
                holder.fulfilled = True
                holder.save(update_fields=["fulfilled"])
            copy.status, copy.held_for, copy.held_until = Copy.Status.ISSUED, None, None
            copy.save()
            return loan
    except IntegrityError as error:  # the database's one-active-loan rule caught a race the lock didn't
        raise Problem(409, "copy_unavailable", f"{accession} has just been issued.") from error


def _fine(loan: Loan, amount: Decimal, reason: str, actor) -> Fine:
    fine = Fine.objects.create(loan=loan, amount=amount, reason=reason)
    institution = loan.copy.title.institution
    if loan.student_id and module_on(institution, "fees"):
        from fees import services as fees

        head = fees.head_for(institution, "LIBFINE", "Library fine")
        fine.invoice = fees.create_invoice(
            actor,
            loan.student,
            [{"head": head, "amount": amount, "description": f"Library: {reason}"}],
            today_for(institution),
        )
        fine.save(update_fields=["invoice"])
    return fine


def give_back(actor, loan: Loan) -> Loan:
    institution = loan.copy.title.institution
    require(actor, institution)
    with transaction.atomic():
        loan = Loan.objects.select_for_update().select_related("copy__title").get(pk=loan.pk)
        if loan.status != Loan.Status.ACTIVE:
            return loan  # returned (or lost) already: a second return changes nothing
        today = today_for(institution)
        loan.status, loan.returned_on = Loan.Status.RETURNED, today
        loan.save()
        late = (today - loan.due_on).days
        if late > 0:
            _fine(loan, DAILY_FINE * late, f"{late} days late", actor)
        copy = loan.copy
        waiting = Reservation.objects.filter(title=copy.title, fulfilled=False, canceled=False).first()
        if waiting is not None:
            copy.status, copy.held_for, copy.held_until = (
                Copy.Status.RESERVED,
                waiting,
                today + dt.timedelta(days=HOLD_DAYS),
            )
        else:
            copy.status = Copy.Status.AVAILABLE
        copy.save()
        return loan


def renew(actor, loan: Loan) -> Loan:
    institution = loan.copy.title.institution
    require(actor, institution)
    if loan.status != Loan.Status.ACTIVE:
        raise Problem(409, "invalid_transition", "Only a book on loan is renewed.")
    if loan.renewals >= RENEWALS:
        raise Problem(409, "renewal_limit", f"Renewed {RENEWALS} times already.")
    if Reservation.objects.filter(title=loan.copy.title, fulfilled=False, canceled=False).exists():
        raise Problem(409, "reserved", "Someone is waiting for this title.")
    loan.renewals += 1
    loan.due_on = today_for(institution) + dt.timedelta(days=LOAN_DAYS)
    loan.save()
    return loan


def lose(actor, loan: Loan) -> Loan:
    institution = loan.copy.title.institution
    require(actor, institution)
    with transaction.atomic():
        loan = Loan.objects.select_for_update().select_related("copy__title").get(pk=loan.pk)
        if loan.status != Loan.Status.ACTIVE:
            raise Problem(409, "invalid_transition", "Only a book on loan is marked lost.")
        loan.status = Loan.Status.LOST
        loan.save()
        loan.copy.status = Copy.Status.LOST
        loan.copy.save()
        _fine(loan, loan.copy.title.replacement_cost, "Lost: replacement cost", actor)
        audit.log(actor, "library.lost", loan.copy.title, f"{loan.copy.accession} lost", institution=institution)
        return loan


def reserve(actor, institution, title: Title, student=None, staff=None) -> Reservation:
    require(actor, institution)
    return Reservation.objects.create(title=title, **_who(student, staff))


def waive(actor, fine: Fine, reason: str) -> Fine:
    require(actor, fine.loan.copy.title.institution)
    if not reason.strip():
        raise ValidationError({"reason": ["Say why."]})
    fine.waived_by, fine.waived_reason = actor, reason.strip()
    fine.save()
    return fine


def loan_item(loan: Loan) -> dict:
    who = loan.student.person.full_name if loan.student_id else loan.staff.user.full_name
    return {
        "id": str(loan.id),
        "title": loan.copy.title.title,
        "accession": loan.copy.accession,
        "borrower": who,
        "issued_on": loan.issued_on,
        "due_on": loan.due_on,
        "returned_on": loan.returned_on,
        "renewals": loan.renewals,
        "status": loan.status,
        "fines": [
            {
                "id": str(f.id),
                "amount": str(f.amount),
                "reason": f.reason,
                "waived_reason": f.waived_reason,
                "invoiced": f.invoice_id is not None,
            }
            for f in loan.fines.order_by("created_at")
        ],
    }


def title_item(title: Title) -> dict:
    copies = list(title.copies.all())
    return {
        "id": str(title.id),
        "title": title.title,
        "author": title.author,
        "isbn": title.isbn,
        "subject": title.subject,
        "copies": [{"accession": c.accession, "status": c.status} for c in copies],
        "available": sum(c.status == Copy.Status.AVAILABLE for c in copies),
        "waiting": title.reservations.filter(fulfilled=False, canceled=False).count(),
    }
