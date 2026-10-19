"""Guardian links are proposed only by enrollment or by staff (slice 4b S4B-02)."""

from admissions.tests.conftest import APPS, applicant, complete
from admissions.tests.test_applicant import attach_documents, start
from admissions.tests.test_enrollment import FIRST
from admissions.tests.test_review import act
from common.models import AuditEvent
from students.guardians import propose
from students.models import GuardianLink, Student


def test_enrollment_proposes_one_link_to_the_owner(world, cycle, accepted, registrar):
    assert act(registrar, accepted, "enroll", password=FIRST).status_code == 200
    act(registrar, accepted, "enroll", password=FIRST)
    link = GuardianLink.objects.get()
    student = Student.objects.get()
    assert (link.status, link.source, link.relationship) == ("proposed", "enrollment", "Mother")
    assert link.user.username == "asha.parent" and link.student == student
    assert (link.adult.full_name, link.adult.phone, link.adult.email) == (
        "Asha Rao",
        "+91 90000 12345",
        "asha@example.com",
    )
    assert not (link.access_record or link.access_fees or link.access_messages)
    on_student = AuditEvent.objects.filter(object_type="student", object_id=str(student.id))
    assert set(on_student.values_list("action", flat=True)) == {"student.enrolled", "student.guardian_proposed"}


def test_matching_phone_never_links(world, cycle, accepted, registrar, client_for):
    ravi = applicant(world.a, "ravi.parent")
    family = client_for(world.a.slug, ravi)
    draft = start(family, cycle).json()
    saved = family.patch(f"{APPS}/{draft['id']}", complete(draft), format="json").json()  # the same phone and name
    attach_documents(draft["id"])
    family.post(f"{APPS}/{draft['id']}/submit", {"version": saved["version"]}, format="json")
    act(registrar, accepted, "enroll", password=FIRST)
    assert GuardianLink.objects.count() == 1
    assert not GuardianLink.objects.filter(user=ravi).exists()


def test_staff_propose_needs_no_login(world, cycle, accepted, registrar):
    act(registrar, accepted, "enroll", password=FIRST)
    student = Student.objects.get()
    adult = {"full_name": "Lakshmi Rao", "phone": "+91 90000 55555", "email": ""}
    link = propose(world.a_admin, student, adult, "Grandmother")
    assert (link.status, link.source, link.user, link.proposed_by) == ("proposed", "staff", None, world.a_admin)
    assert link.adult.institution == world.a and link.adult.full_name == "Lakshmi Rao"
    event = AuditEvent.objects.get(action="student.guardian_proposed", changes__link=str(link.id))
    assert event.changes == {
        "link": str(link.id),
        "adult": "Lakshmi Rao",
        "relationship": "Grandmother",
        "status": "proposed",
    }
