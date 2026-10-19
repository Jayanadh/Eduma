"""The family portal (slice 4b S4B-08): a guardian's children with an active, in-effect link at this institution, and
only what each link shares. The student id in a URL is never trusted on its own."""

from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Membership
from accounts.permissions import active_membership, today_for
from configuration.gates import module_on
from students.models import GuardianLink, Student
from students.serializers import enrollment_item


def child_item(student: Student, shared: bool) -> dict:
    item = {"id": str(student.id), "full_name": student.person.full_name, "shared": shared}
    if shared:
        current = student.enrollments.select_related("campus").first()  # the latest, ended or not
        item.update(
            number=student.number,
            status=student.status,
            left_on=student.left_on,
            enrollment=enrollment_item(current),
        )
    return item


class FamilyView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        membership = (
            active_membership(request.user, request.institution) if request.site_kind == "institution" else None
        )
        if membership is None or membership.kind != Membership.Kind.GUARDIAN:
            raise NotFound()

    def children(self) -> dict[Student, bool]:
        """{student: shared} for every child this login may see today."""
        institution = self.request.institution
        if not module_on(institution, "students"):
            return {}
        today = today_for(institution)
        links = (
            GuardianLink.objects.filter(
                institution=institution,
                student__institution=institution,
                user=self.request.user,
                status=GuardianLink.Status.ACTIVE,
                starts_on__lte=today,
            )
            .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
            .select_related("student__person")
            .order_by("student__number")
        )
        found: dict[Student, bool] = {}
        for link in links:
            found[link.student] = found.get(link.student, False) or link.access_record
        return found


class Children(FamilyView):
    def get(self, request):
        return Response([child_item(student, shared) for student, shared in self.children().items()])


class Child(FamilyView):
    def get(self, request, pk):
        for student, shared in self.children().items():
            if student.pk == pk:
                return Response(child_item(student, shared))
        raise NotFound()
