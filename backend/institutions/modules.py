"""The modules an institution's plan can include (spec pack 01 §6, slice 2 spec §6). The platform records which ones
each institution has (Institution.modules); none is built yet, so each says it arrives in a later release."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError

ALL = frozenset({"school", "college", "engineering_college", "university"})
HIGHER = frozenset({"college", "engineering_college", "university"})


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    group: str  # "core" or "operations"
    depends_on: tuple[str, ...] = ()
    default_for: frozenset[str] = frozenset()
    available: bool = False


def _core(key, label, *depends_on, default_for=ALL, available=False) -> Module:
    return Module(key, label, "core", depends_on, default_for, available)


def _operations(key, label) -> Module:
    return Module(key, label, "operations")


MODULES: dict[str, Module] = {
    m.key: m
    for m in (
        _core("admissions", "Admissions and enrollment", "students", available=True),
        _core("students", "Students and guardians", available=True),
        _core("academics", "Academic structure and timetable", available=True),
        _core("attendance", "Attendance", "academics", available=True),
        _core("exams", "Assessment and results", "academics", available=True),
        _core(
            "report_cards",
            "Grades, sections, report cards and promotion",
            "exams",
            default_for=frozenset({"school"}),
            available=True,
        ),
        _core("course_registration", "Course registration, credits and degree audit", "academics", default_for=HIGHER),
        _core(
            "outcomes",
            "Lab batches, projects and outcome evidence",
            "exams",
            default_for=frozenset({"engineering_college", "university"}),
            available=True,
        ),
        _core(
            "affiliations",
            "Affiliated colleges and central examinations",
            "exams",
            default_for=frozenset({"university"}),
        ),
        _core("fees", "Fees", "students", available=True),
        _core("communication", "Messages, calls and online classes", "students", available=True),
        _core("reports", "Reports"),
        _operations("library", "Library"),
        _operations("transport", "Transport"),
        _operations("hostel", "Hostel and mess"),
        _operations("hr_payroll", "HR and payroll"),
        _operations("assets", "Assets, purchasing and labs"),
        _operations("services", "Student services and cases"),
        _operations("placements", "Placements, internships and alumni"),
        _operations("quality", "Quality, accreditation and research"),
    )
}


def default_modules(category: str) -> list[str]:
    return sorted(key for key, module in MODULES.items() if category in module.default_for)


def check_modules(keys: list[str]) -> list[str]:
    """The list sorted and without repeats; refused if a key is unknown or a module's dependency is missing."""
    chosen = sorted(set(keys))
    for key in chosen:
        if key not in MODULES:
            raise ValidationError(f"Unknown module: {key}.")
    for key in chosen:
        for needed in MODULES[key].depends_on:
            if needed not in chosen:
                raise ValidationError(f"{MODULES[key].label} needs {MODULES[needed].label}.")
    return chosen
