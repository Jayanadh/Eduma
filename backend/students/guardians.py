"""Guardian links (slice 4b §2): proposed by enrollment or by staff, never inferred from matching names or phones;
verified or revoked by staff with guardian_link.manage. Audit lines go on the student, without notes or evidence."""

from common import audit
from students.models import GuardianLink, Person, Student


def log_link(actor, link: GuardianLink, action: str, summary: str):
    changes = {
        "link": str(link.id),
        "adult": link.adult.full_name,
        "relationship": link.relationship,
        "status": link.status,
    }
    return audit.log(actor, action, link.student, summary, institution=link.student.institution, changes=changes)


def _new(actor, student: Student, adult: Person, relationship: str, source: str, user=None) -> GuardianLink:
    link = GuardianLink.objects.create(
        institution=student.institution,
        student=student,
        adult=adult,
        user=user,
        relationship=relationship,
        source=source,
        proposed_by=actor,
    )
    log_link(
        actor, link, "student.guardian_proposed", f"{adult.full_name} proposed as {relationship} of {student.number}"
    )
    return link


def propose_from_application(actor, student: Student, application) -> GuardianLink:
    """The adult who applied, waiting for staff to check their authority. Call inside enrollment's transaction."""
    existing = student.guardian_links.filter(user=application.owner).exclude(status=GuardianLink.Status.REVOKED)
    if (found := existing.first()) is not None:
        return found
    adult = Person.objects.create(
        institution=student.institution,
        full_name=application.guardian_name,
        phone=application.guardian_phone,
        email=application.guardian_email,
        address=application.address,
    )
    relationship = application.guardian_relationship
    return _new(actor, student, adult, relationship, GuardianLink.Source.ENROLLMENT, user=application.owner)


def propose(actor, student: Student, adult: dict, relationship: str) -> GuardianLink:
    """Another adult named by staff; no login until verification makes one."""
    person = Person.objects.create(
        institution=student.institution,
        full_name=adult["full_name"],
        phone=adult.get("phone", ""),
        email=adult.get("email", ""),
    )
    return _new(actor, student, person, relationship, GuardianLink.Source.STAFF)
