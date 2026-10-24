"""What a teacher's own assignments open to them (slice 5a S5A-05): a relationship, not a campus permission."""

from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.models import AcademicYear, CourseOffering, EnrollmentPeriod, Section, TeachingAssignment
from accounts.models import Membership
from accounts.permissions import active_membership, today_for
from configuration.gates import require_module


def assignments(user, institution):
    """The teacher's assignments in effect today, in years that are not closed, of offerings not cancelled."""
    membership = active_membership(user, institution)
    if membership is None or membership.kind != Membership.Kind.STAFF:
        return TeachingAssignment.objects.none()
    today = today_for(institution)
    rows = TeachingAssignment.objects.filter(membership=membership, starts_on__lte=today)
    rows = rows.exclude(ends_on__lt=today).exclude(section__year__status=AcademicYear.Status.CLOSED)
    rows = rows.exclude(offering__term__year__status=AcademicYear.Status.CLOSED)
    rows = rows.exclude(offering__status=CourseOffering.Status.CANCELLED)
    return rows.select_related("section__year", "section__grade", "subject", "offering__course", "offering__term__year")


def teaches(user, section: Section) -> bool:
    return assignments(user, section.institution).filter(section=section).exists()


class TeachingView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        membership = (
            active_membership(request.user, request.institution) if request.site_kind == "institution" else None
        )
        if membership is None or membership.kind != Membership.Kind.STAFF:
            raise NotFound()
        require_module(request.institution, "academics")


class Classes(TeachingView):
    def get(self, request):
        found: dict = {}
        rows = assignments(request.user, request.institution).order_by(
            "section__year__starts_on", "section__code", "offering__course__code", "offering__code"
        )
        for row in rows:
            entry = found.setdefault(
                row.section or row.offering, {**_target(row), "subjects": [], "class_teacher": False}
            )
            if row.offering_id:
                continue
            entry["class_teacher"] = entry["class_teacher"] or row.subject_id is None
            if row.subject_id and row.subject.name not in entry["subjects"]:
                entry["subjects"].append(row.subject.name)
        return Response(list(found.values()))


def _target(row: TeachingAssignment) -> dict:
    if row.offering_id:
        offering = row.offering
        return {
            "offering": {
                "id": str(offering.id),
                "course": offering.course.code,
                "title": offering.course.title,
                "code": offering.code,
                "term": offering.term.name,
                "year": offering.term.year.code,
            }
        }
    section = row.section
    return {
        "section": {"id": str(section.id), "code": section.code, "grade": section.grade.name, "year": section.year.code}
    }


class ClassRoster(TeachingView):
    """Number, name and status only: what taking a register needs, nothing else of the record."""

    def get(self, request, section):
        found = Section.objects.filter(institution=request.institution, pk=section).first()
        if found is None or not teaches(request.user, found):
            raise NotFound()
        rows = found.placements.filter(state=EnrollmentPeriod.State.ACTIVE).select_related(
            "enrollment__student__person"
        )
        return Response(
            [
                {
                    "number": row.enrollment.student.number,
                    "full_name": row.enrollment.student.person.full_name,
                    "status": row.enrollment.student.status,
                }
                for row in rows.order_by("enrollment__student__number")
            ]
        )
