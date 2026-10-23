"""What a teacher's own assignments open to them (slice 5a S5A-05): a relationship, not a campus permission."""

from academics.models import AcademicYear, Section, TeachingAssignment
from accounts.models import Membership
from accounts.permissions import active_membership, today_for


def assignments(user, institution):
    """The teacher's assignments in effect today, in years that are not closed."""
    membership = active_membership(user, institution)
    if membership is None or membership.kind != Membership.Kind.STAFF:
        return TeachingAssignment.objects.none()
    today = today_for(institution)
    rows = TeachingAssignment.objects.filter(membership=membership, starts_on__lte=today)
    rows = rows.exclude(ends_on__lt=today).exclude(section__year__status=AcademicYear.Status.CLOSED)
    return rows.select_related("section__year", "section__grade", "subject")


def teaches(user, section: Section) -> bool:
    return assignments(user, section.institution).filter(section=section).exists()
