import pytest
from django.core.management import CommandError, call_command

from accounts.models import RoleAssignment, User
from institutions.models import Institution
from institutions.modules import default_modules
from sites.models import SiteRevision


def test_seed_runs_twice_without_duplicates(db, settings):
    settings.DEBUG = True
    call_command("seed_demo")
    User.objects.filter(username="aster.admin").update(full_name="Changed")
    call_command("seed_demo")
    assert Institution.objects.count() == 4
    assert User.objects.count() == 16  # with aster.grandparent and meridian.faculty
    assert SiteRevision.objects.filter(status="published").count() == 3
    states = dict(Institution.objects.values_list("slug", "lifecycle_status"))
    assert states == {"aster": "active", "meridian": "active", "vector": "setup", "summit": "active"}
    aster = SiteRevision.objects.get(institution__slug="aster", status="published")
    assert (aster.primary_color, aster.heading_font, aster.body_font) == ("#5B3FD9", "fredoka", "nunito")
    admin = User.objects.get(username="aster.admin")
    assert admin.check_password("Demo-pass-2026") and not admin.must_change_password
    vector = User.objects.get(username="vector.admin")
    assert vector.must_change_password and vector.last_login is None
    assert User.objects.get(username="eduma.admin").is_platform_admin
    assert Institution.objects.get(slug="meridian").custom_domain == "www.meridiancollege.localhost"
    aster_inst = Institution.objects.get(slug="aster")
    assert set(aster_inst.campuses.values_list("code", flat=True)) == {"MAIN", "CITY"}
    assert set(aster_inst.departments.values_list("code", flat=True)) == {"SCI", "PHY", "LANG"}
    assert aster_inst.departments.get(code="PHY").parent.code == "SCI"
    for username in ("aster.principal", "aster.campus", "aster.teacher", "aster.office"):
        person = User.objects.get(username=username)
        assert person.check_password("Demo-pass-2026") and not person.must_change_password
    from accounts.models import Employee, Membership
    from students.models import GuardianLink

    links = GuardianLink.objects.filter(student__application__learner_name="Arjun Demo").order_by("created_at")
    assert [(link.user.username, link.status, link.access_record) for link in links] == [
        ("aster.parent", "active", True),
        ("aster.grandparent", "active", False),
    ]
    assert Membership.objects.get(user__username="aster.parent").kind == "guardian"
    assert Employee.objects.get(membership__user__username="aster.admin").employee_number == "AST-001"
    from admissions.models import Enquiry

    assert sorted(Enquiry.objects.values_list("source", "status")) == [("walk_in", "following_up"), ("website", "open")]
    from academics.models import EnrollmentPeriod, Section

    assert sorted(Section.objects.filter(institution=aster_inst).values_list("year__code", "code")) == [
        ("2026–27", "6A"),
        ("2026–27", "6B"),
        ("2027–28", "6A"),
        ("2027–28", "7A"),
    ]
    arjun = EnrollmentPeriod.objects.get(enrollment__student__application__learner_name="Arjun Demo")
    assert (arjun.year.code, arjun.section.code) == ("2027–28", "6A")
    office = RoleAssignment.objects.get(membership__user__username="aster.office")
    assert (office.custom_role.name, office.custom_role.permissions, office.campus.code) == (
        "Front office",
        ["membership.read"],
        "CITY",
    )
    for institution in Institution.objects.all():
        assert institution.modules == default_modules(institution.category)
    from configuration.models import SettingRevision
    from configuration.registry import setting

    assert setting(aster_inst, "modules.enabled") == ["academics", "admissions", "students"]
    assert SettingRevision.objects.filter(institution=aster_inst, key="modules.enabled").count() == 1
    assert setting(aster_inst, "access.role_approval") is False
    deputy = User.objects.get(username="aster.deputy")
    assert deputy.full_name == "Aster Deputy Admin" and deputy.check_password("Demo-pass-2026")
    from admissions.models import AdmissionCycle, Application
    from students.models import Student

    cycle = AdmissionCycle.objects.get(institution=aster_inst)
    assert cycle.status == "published" and [p.label for p in cycle.places.all()] == ["Class 1", "Class 6"]
    stages = sorted(Application.objects.filter(owner__username="aster.parent").values_list("stage", flat=True))
    assert stages == ["enrolled", "submitted"]
    student = Student.objects.get(institution=aster_inst)
    assert student.user.check_password("Demo-pass-2026") and not student.user.must_change_password
    for username in ("aster.admissions", "aster.registrar", "aster.parent"):
        assert User.objects.get(username=username).check_password("Demo-pass-2026")
    from academics.models import CourseOffering, CurriculumVersion

    meridian = Institution.objects.get(slug="meridian")
    assert setting(meridian, "modules.enabled") == ["academics", "admissions", "students"]
    regulation = CurriculumVersion.objects.get(program__institution=meridian)
    assert (str(regulation), regulation.status, regulation.courses.count()) == ("R2026 rev 1", "published", 4)
    lab = CourseOffering.objects.get(institution=meridian, code="A1")
    assert (str(lab), str(lab.linked_to)) == ("PHY101L-A1", "PHY101-A")
    assert lab.linked_to.teaching.get().membership.user.username == "meridian.faculty"
    batch = Section.objects.get(institution=meridian)
    assert (batch.code, batch.program.code, batch.placements.count()) == ("BSC-PHY 2026 A", "BSC-PHY", 1)
    pins = sorted(meridian.students.values_list("enrollments__curriculum__regulation", flat=True), key=str)
    assert pins == [None, "R2026"]


def test_seed_refuses_without_debug(db, settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_demo")
