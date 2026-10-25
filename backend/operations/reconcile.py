"""The cutover reconciliation (BUILD-12; spec pack 11 cutover sequence): the numbers to compare with the source system
before an institution goes live — counts by status, fee totals, academic counts, document checksums and anything
still unresolved. Zero unexplained differences in critical counts and money, or no go-live."""

import hashlib
from collections import Counter
from decimal import Decimal

from django.db.models import Sum

ZERO = Decimal("0.00")


def _total(queryset, field="amount") -> str:
    return str(queryset.aggregate(t=Sum(field))["t"] or ZERO)


def cutover_report(institution) -> dict:
    from academics.models import Course, CourseAttempt
    from fees.models import CreditNote, InvoiceLine, Payment, ReconciliationCase, Refund
    from fees.services import trial_balance
    from imports.models import ImportedRecord, ImportJob, ImportRow
    from results.models import IssuedDocument
    from students.models import Enrollment, GuardianLink

    documents = IssuedDocument.objects.filter(institution=institution).order_by("number")
    balances = trial_balance(institution)
    return {
        "institution": institution.slug,
        "students": dict(Counter(institution.students.values_list("status", flat=True))),
        "active_enrollments": Enrollment.objects.filter(institution=institution, status="active").count(),
        "guardian_links": dict(
            Counter(GuardianLink.objects.filter(student__institution=institution).values_list("status", flat=True))
        ),
        "imported_records": dict(
            Counter(ImportedRecord.objects.filter(institution=institution).values_list("entity_type", flat=True))
        ),
        "fees": {
            "charged": _total(InvoiceLine.objects.filter(invoice__account__institution=institution)),
            "credit_notes": _total(
                CreditNote.objects.filter(invoice__account__institution=institution, state="posted")
            ),
            "received": _total(Payment.objects.filter(account__institution=institution, state="succeeded")),
            "refunded": _total(Refund.objects.filter(payment__account__institution=institution, state="succeeded")),
            "trial_balance_net": str(sum((Decimal(b["balance"]) for b in balances), ZERO)),
        },
        "academics": {
            "courses": Course.objects.filter(institution=institution).count(),
            "attempts": dict(
                Counter(CourseAttempt.objects.filter(institution=institution).values_list("outcome", flat=True))
            ),
        },
        "documents": {
            "count": documents.count(),
            "checksum": hashlib.sha256("".join(documents.values_list("content_hash", flat=True)).encode()).hexdigest(),
        },
        "unresolved": {
            "import_rows_with_errors": ImportRow.objects.filter(
                job__institution=institution, job__status=ImportJob.Status.VALIDATED, state=ImportRow.State.ERROR
            ).count(),
            "imports_not_committed": ImportJob.objects.filter(
                institution=institution, status=ImportJob.Status.VALIDATED
            ).count(),
            "reconciliation_cases": ReconciliationCase.objects.filter(institution=institution, state="open").count(),
        },
    }
