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
            f"{TODAY} Sees staff and their roles, and student records.",
            "membership.read",
            "student.read",
        ),
        _role(
            "head_of_department",
            "Head of Department",
            f"{TODAY} Sees the department's staff. Academic permissions arrive with the Academics module.",
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
        ),
        _role("teacher", "Teacher / Faculty", f"{TODAY} Teaching permissions arrive with Academics and Attendance."),
        _role(
            "admissions_officer",
            "Admissions Officer",
            "Reviews applications: checks documents, asks for information, marks eligible or rejects.",
            "application.review",
        ),
        _role("accountant", "Accountant / Cashier", f"{TODAY} Fee permissions arrive with the Fees module."),
        _role(
            "exam_officer",
            "Examination Officer",
            f"{TODAY} Examination permissions arrive with Assessment and results.",
        ),
    )
}


def powerful(perms: Iterable[str]) -> bool:
    """A role that can change the institution or its staff: anything beyond seeing staff. These wait for approval while
    the institution requires it."""
    return bool(set(perms) - {"membership.read"})


def institution_only(perms: Iterable[str]) -> list[str]:
    return sorted(name for name in perms if name in PERMISSIONS and PERMISSIONS[name].institution_only)
