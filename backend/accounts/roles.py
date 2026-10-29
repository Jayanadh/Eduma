"""The permission registry and the built-in roles (spec pack 02 §3–4). Only permissions for features that exist are
registered; each later slice adds its own and gives them to the built-in roles that should hold them."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    name: str
    group: str
    label: str
    # Applies only to the whole institution: a role holding it cannot be given at a campus or department.
    institution_only: bool


PERMISSIONS: dict[str, Permission] = {
    p.name: p
    for p in (
        Permission("institution_profile.update", "Institution", "Edit the institution's contact details", True),
        Permission("institution_brand.update", "Institution", "Edit the logo, colours and public page", True),
        Permission("organization.manage", "Organization", "Add and change campuses and departments", True),
        Permission("membership.read", "Staff", "See staff and their roles", False),
        Permission(
            "membership.assign",
            "Staff",
            "Add staff, give and end roles, reset staff passwords and remove staff",
            False,
        ),
        Permission("role.manage", "Staff", "Create and change custom roles", True),
        Permission("configuration.edit", "Settings", "Draft changes to settings and send them for approval", True),
        Permission("configuration.publish", "Settings", "Publish and approve changes to settings", True),
        Permission("admission_cycle.manage", "Admissions", "Set up admission cycles, their places and forms", True),
        Permission(
            "application.review",
            "Admissions",
            "Review applications: check documents, ask for information, mark eligible or reject",
            False,
        ),
        Permission("admission.approve", "Admissions", "Offer places and enroll accepted applicants", False),
        Permission(
            "enquiry.manage",
            "Admissions",
            "Answer enquiries: record, assign, follow up, link to applications and close",
            False,
        ),
        Permission("data.import", "Settings", "Import students from a spreadsheet", True),
        Permission(
            "academic_structure.manage",
            "Academics",
            "Set up years, grades, subjects and sections, place students and assign teachers",
            False,
        ),
        Permission(
            "registration.manage",
            "Academics",
            "Open registration windows, register students, approve, drop and withdraw registrations, and place holds",
            False,
        ),
        Permission("registration.override", "Academics", "Let a student past a failed registration check", False),
        Permission(
            "academic_record.manage",
            "Academics",
            "Record course outcomes and decide transfer credit",
            False,
        ),
        Permission(
            "affiliation.submit",
            "Academics",
            "Build and submit result batches to an affiliating university",
            True,
        ),
        Permission(
            "affiliation.review",
            "Academics",
            "Review result batches from affiliated colleges",
            True,
        ),
        Permission(
            "attendance.manage",
            "Academics",
            "See every class's attendance, approve corrections and lock sessions",
            False,
        ),
        Permission("assessment.manage", "Results", "Set up assessment schemes and assessments, and enter marks", False),
        Permission("results.moderate", "Results", "Moderate submitted marks and raise revaluations", False),
        Permission(
            "results.publish",
            "Results",
            "Publish results, approve revaluations, decide promotion and issue report cards, transcripts and awards",
            False,
        ),
        Permission("fees.read", "Fees", "See fee accounts, invoices, payments and receipts", False),
        Permission("fees.manage", "Fees", "Set up fee heads and plans, issue invoices and request credit notes", False),
        Permission("fees.collect", "Fees", "Record payments at the office, allocate them and request refunds", False),
        Permission("fees.approve", "Fees", "Approve credit notes and refunds someone else requested", False),
        Permission(
            "fees.reconcile",
            "Fees",
            "Set up the payment provider, record settlements, resolve reconciliation cases and export journals",
            True,
        ),
        Permission(
            "communication.manage",
            "Communication",
            "Set the communication policy and the media provider, and message any student's family",
            True,
        ),
        Permission(
            "library.manage",
            "Campus services",
            "Run the library: catalogue, loans, returns, reservations and fines",
            False,
        ),
        Permission(
            "transport.manage", "Campus services", "Run transport: vehicles, routes, riders, trips and pickups", False
        ),
        Permission(
            "hostel.manage", "Campus services", "Run hostels: beds, allocations, transfers and out-passes", False
        ),
        Permission(
            "hr.manage", "Staff services", "Set leave types, see everyone's leave and record staff attendance", False
        ),
        Permission("hr.leave_approve", "Staff services", "Approve or reject other people's leave", False),
        Permission("payroll.manage", "Staff services", "See and change pay, and prepare payroll", True),
        Permission("payroll.approve", "Staff services", "Approve payroll someone else prepared", True),
        Permission(
            "procurement.manage", "Staff services", "Raise requisitions, order, receive goods and move stock", False
        ),
        Permission("procurement.approve", "Staff services", "Approve requisitions under the procurement rule", False),
        Permission(
            "assets.manage", "Staff services", "Keep the asset register, maintenance, disposal and bookings", False
        ),
        Permission("service_case.assign", "Student services", "See the case queue and assign cases", False),
        Permission(
            "service_case.confidential",
            "Student services",
            "Be assigned grievance, counselling and safeguarding cases",
            True,
        ),
        Permission("placement.manage", "Student services", "Run placements, internships and the alumni list", False),
        Permission(
            "research.manage", "Student services", "Run research scholars, supervision and ethics records", False
        ),
        Permission(
            "quality_evidence.manage", "Student services", "Run quality review cycles and accept evidence", False
        ),
        Permission("report.export", "Reports", "Export the reports you can see as files", False),
        Permission("student.read", "Students", "See student records", False),
        Permission("student.update", "Students", "Correct student details", False),
        Permission(
            "guardian_link.manage",
            "Students",
            "Verify and revoke guardian links, and read custody notes and verification evidence",
            False,
        ),
    )
}

# Every active member holds this through their membership; it is not given by roles.
IMPLICIT = "institution.read"


@dataclass(frozen=True)
class BuiltinRole:
    key: str
    label: str
    description: str
    permissions: frozenset[str]


def _role(key: str, label: str, description: str, *permissions: str) -> BuiltinRole:
    return BuiltinRole(key, label, description, frozenset(permissions))


TODAY = "Signs in and sees the institution's home."
BUILTIN_ROLES: dict[str, BuiltinRole] = {
    r.key: r
    for r in (
        _role(
            "institution_admin",
            "Institution Admin",
            "Runs the institution's setup: its details, page, campuses, staff and roles.",
            *PERMISSIONS,
        ),
        _role(
            "campus_admin",
            "Campus Admin",
            "Adds staff and gives them roles within the campus or department it is given for.",
            "membership.read",
            "membership.assign",
        ),
        _role(
            "principal",
            "Principal / Director",
            f"{TODAY} Sees staff, their roles and student records; approves fee credit notes and refunds, leave, "
            "payroll and purchases; exports reports.",
            "membership.read",
            "student.read",
            "fees.read",
            "fees.approve",
            "communication.manage",
            "hr.leave_approve",
            "payroll.approve",
            "procurement.approve",
            "report.export",
        ),
        _role(
            "head_of_department",
            "Head of Department",
            f"{TODAY} Sees the department's staff and their roles.",
            "membership.read",
        ),
        _role(
            "registrar",
            "Registrar",
            "Offers places, enrolls accepted applicants, keeps student records and verifies guardians.",
            "admission.approve",
            "application.review",
            "student.read",
            "student.update",
            "guardian_link.manage",
            "enquiry.manage",
            "academic_structure.manage",
            "registration.manage",
            "registration.override",
            "academic_record.manage",
            "attendance.manage",
            "assessment.manage",
            "results.publish",
        ),
        _role(
            "academic_adviser",
            "Academic Adviser",
            "Advises students on registration: registers them, approves requests and lets them past checks.",
            "student.read",
            "registration.manage",
            "registration.override",
        ),
        _role(
            "teacher",
            "Teacher / Faculty",
            f"{TODAY} Teaches the classes and courses assigned to them: attendance, assignments and marks.",
        ),
        _role(
            "admissions_officer",
            "Admissions Officer",
            "Answers enquiries and reviews applications: checks documents, asks for information, marks eligible or "
            "rejects.",
            "application.review",
            "enquiry.manage",
        ),
        _role("librarian", "Librarian", "Runs the library.", "library.manage"),
        _role(
            "student_services",
            "Student Services Officer",
            "Takes in service requests and grievances and assigns each to who handles it.",
            "service_case.assign",
        ),
        _role(
            "grievance_officer",
            "Grievance Officer",
            "Assigns cases and handles confidential grievance, counselling and safeguarding cases given to them.",
            "service_case.assign",
            "service_case.confidential",
        ),
        _role(
            "placement_officer",
            "Placement Officer",
            "Runs placements, internships and alumni.",
            "placement.manage",
            "student.read",
        ),
        _role(
            "research_coordinator",
            "Research Coordinator",
            "Runs research scholars and supervision.",
            "research.manage",
            "student.read",
        ),
        _role(
            "iqac_coordinator",
            "IQAC Coordinator",
            "Runs quality review cycles and evidence.",
            "quality_evidence.manage",
            "membership.read",
        ),
        _role(
            "hr_officer",
            "HR Officer",
            "Runs leave and staff attendance.",
            "membership.read",
            "hr.manage",
            "hr.leave_approve",
        ),
        _role("payroll_officer", "Payroll Officer", "Keeps pay and prepares payroll.", "payroll.manage"),
        _role(
            "store_keeper",
            "Store Keeper",
            "Runs purchasing, stores and the asset register.",
            "procurement.manage",
            "assets.manage",
        ),
        _role(
            "transport_officer",
            "Transport Officer",
            "Runs buses, routes and riders.",
            "transport.manage",
            "student.read",
        ),
        _role("warden", "Warden", "Runs the hostel.", "hostel.manage", "student.read"),
        _role(
            "accountant",
            "Accountant / Cashier",
            "Runs fees: plans, invoices, collections, receipts, refunds requested, settlements and reconciliation.",
            "student.read",
            "fees.read",
            "fees.manage",
            "fees.collect",
            "fees.reconcile",
            "report.export",
        ),
        _role(
            "exam_officer",
            "Examination Officer",
            "Runs assessments: schemes, marks, moderation, publication, revaluation and documents.",
            "student.read",
            "academic_record.manage",
            "assessment.manage",
            "results.moderate",
            "results.publish",
        ),
    )
}


def powerful(perms: Iterable[str]) -> bool:
    """A role that can change the institution or its staff: anything beyond seeing staff. These wait for approval while
    the institution requires it."""
    return bool(set(perms) - {"membership.read"})


def institution_only(perms: Iterable[str]) -> list[str]:
    return sorted(name for name in perms if name in PERMISSIONS and PERMISSIONS[name].institution_only)
