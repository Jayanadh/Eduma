"""The report catalogue (BUILD-11 S11-01, S11-02). Reports are code, never admin-written queries; rows come only from
what the viewer may read, and each result says where it came from."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable

from django.db.models import Count
from django.utils import timezone

from accounts.permissions import perms_anywhere, today_for
from configuration.gates import module_on
from students.views import visible_students

SMALL = 5  # confidential groups smaller than this show as "<5"


@dataclass(frozen=True)
class Report:
    key: str
    title: str
    module: str
    perms: tuple[str, ...]  # any one of them runs the report
    columns: tuple[str, ...]
    rows: Callable  # (actor, institution) -> list[list]


def _students_by_class(actor, institution):
    counts = Counter()
    for e in _enrollments(actor, institution).filter(status="active"):
        counts[e.place_label] += 1
    withdrawn = Counter(e.place_label for e in _enrollments(actor, institution).exclude(status="active"))
    return [[place, counts[place], withdrawn[place]] for place in sorted(set(counts) | set(withdrawn))]


def _enrollments(actor, institution):
    from students.models import Enrollment

    return Enrollment.objects.filter(student__in=visible_students(actor, institution))


def _attendance(actor, institution):
    from attendance.models import AttendanceMark, AttendanceSession
    from attendance.services import label

    marks = AttendanceMark.objects.filter(
        session__institution=institution,
        session__state__in=[AttendanceSession.State.SUBMITTED, AttendanceSession.State.LOCKED],
        enrollment__in=_enrollments(actor, institution),
    ).select_related("session__section", "session__offering__course")
    by = defaultdict(lambda: {"sessions": set(), "present": 0, "absent": 0, "total": 0})
    for m in marks:
        target = m.session.section or m.session.offering
        row = by[label(target)]
        row["sessions"].add(m.session_id)
        row["total"] += 1
        row["present"] += m.code in ("present", "late")
        row["absent"] += m.code == "absent"
    return [
        [name, len(r["sessions"]), r["present"], r["absent"], f"{100 * r['present'] / r['total']:.1f}"]
        for name, r in sorted(by.items())
    ]


def _fees(actor, institution):
    from fees.models import Invoice
    from fees.services import balances

    rows = defaultdict(lambda: [0, 0, 0])
    invoices = Invoice.objects.filter(
        account__institution=institution, account__student__in=visible_students(actor, institution)
    ).select_related("account__student__person")
    # shortcut: balances() per invoice is a few queries each; fine to a few thousand invoices, then aggregate in SQL
    for invoice in invoices:
        b, student = balances(invoice), invoice.account.student
        row = rows[(student.number, student.person.full_name)]
        row[0] += b["net_charges"]
        row[1] += b["net_allocated"]
        row[2] += b["outstanding"]
    return [[n, name, str(c), str(p), str(o)] for (n, name), (c, p, o) in sorted(rows.items()) if o > 0]


def _results(actor, institution):
    from results.models import Assessment, ResultVersion

    out = []
    for a in Assessment.objects.filter(institution=institution).order_by("title"):
        current = ResultVersion.objects.filter(
            candidate__assessment=a,
            superseded_at__isnull=True,
            candidate__enrollment__in=_enrollments(actor, institution),
        )
        outcomes = Counter(current.values_list("outcome", flat=True))
        out.append(
            [
                a.title,
                a.get_state_display(),
                sum(outcomes.values()),
                outcomes["passed"],
                outcomes["failed"],
                outcomes["absent"],
            ]
        )
    return out


def _library(actor, institution):
    from campus.models import Loan

    today = today_for(institution)
    loans = Loan.objects.filter(
        copy__title__institution=institution, status=Loan.Status.ACTIVE, due_on__lt=today
    ).select_related("copy__title", "student__person", "staff__user")
    return [
        [
            x.copy.accession,
            x.copy.title.title,
            x.student.person.full_name if x.student_id else x.staff.user.full_name,
            x.due_on.isoformat(),
            (today - x.due_on).days,
        ]
        for x in loans.order_by("due_on")
    ]


def _placements(actor, institution):
    from development.services import report

    return [
        [r["opportunity"], r["employer"], r["kind"], r["applied"], r["offers"], r["accepted"]]
        for r in report(institution)
    ]


def _cases(actor, institution):
    from cases.models import ServiceCase

    rows = (
        ServiceCase.objects.filter(institution=institution)
        .values("case_type", "confidential", "state")
        .annotate(n=Count("id"))
        .order_by("case_type", "state")
    )
    labels, states = dict(ServiceCase.Type.choices), dict(ServiceCase.State.choices)
    return [
        [labels[r["case_type"]], states[r["state"]], f"<{SMALL}" if r["confidential"] and r["n"] < SMALL else r["n"]]
        for r in rows
    ]


def _leave(actor, institution):
    from hr.models import LeaveRequest

    year = today_for(institution).year
    taken = LeaveRequest.objects.filter(
        employee__institution=institution, state=LeaveRequest.State.APPROVED, starts_on__year=year
    ).select_related("employee__membership__user", "leave_type")
    days = defaultdict(int)
    for r in taken:
        days[(r.employee.employee_number, r.employee.membership.user.full_name, r.leave_type.name)] += r.days
    return [[n, name, kind, d] for (n, name, kind), d in sorted(days.items())]


REPORTS = {
    r.key: r
    for r in (
        Report(
            "students_by_class",
            "Students by class or program",
            "students",
            ("student.read",),
            ("Class or program", "Active", "Left"),
            _students_by_class,
        ),
        Report(
            "attendance_by_class",
            "Attendance by class",
            "attendance",
            ("attendance.manage",),
            ("Class", "Sessions", "Present or late", "Absent", "Present %"),
            _attendance,
        ),
        Report(
            "fees_outstanding",
            "Fees outstanding",
            "fees",
            ("fees.read",),
            ("Student number", "Name", "Charged", "Paid", "Outstanding"),
            _fees,
        ),
        Report(
            "results_by_assessment",
            "Results by assessment",
            "exams",
            ("results.publish", "results.moderate"),
            ("Assessment", "State", "Results", "Passed", "Failed", "Absent"),
            _results,
        ),
        Report(
            "library_overdue",
            "Overdue library loans",
            "library",
            ("library.manage",),
            ("Accession", "Title", "Borrower", "Due", "Days overdue"),
            _library,
        ),
        Report(
            "placement_outcomes",
            "Placement outcomes",
            "placements",
            ("placement.manage",),
            ("Opportunity", "Employer", "Kind", "Applied", "Offers", "Accepted"),
            _placements,
        ),
        Report(
            "cases_by_type",
            "Cases by type and state",
            "services",
            ("service_case.assign",),
            ("Type", "State", "Cases"),
            _cases,
        ),
        Report(
            "leave_taken",
            "Leave taken this year",
            "hr_payroll",
            ("hr.manage",),
            ("Employee number", "Name", "Leave type", "Days"),
            _leave,
        ),
    )
}


def runnable(actor, institution) -> list[Report]:
    held = perms_anywhere(actor, institution)
    return [r for r in REPORTS.values() if module_on(institution, r.module) and held & set(r.perms)]


def may_run(actor, institution, report: Report) -> bool:
    return report in runnable(actor, institution)


def run(actor, institution, report: Report) -> dict:
    rows = report.rows(actor, institution)
    return {
        "key": report.key,
        "title": report.title,
        "columns": list(report.columns),
        "rows": rows,
        "provenance": {
            "generated_at": timezone.now().isoformat(),
            "source": f"Eduma live records, {institution.display_name}",
            "scope": "Only records you may read",
            "filters": {},
            "row_count": len(rows),
        },
    }
