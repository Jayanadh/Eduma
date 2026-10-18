"""Where an institution works: its campuses, and departments that may sit at a campus and nest under each other.
Both are scopes inside the institution (spec pack 02 §1), never separate tenants."""

import re

from django.core.exceptions import ValidationError
from django.db import models

from common.models import VersionedModel

CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,19}$")


def validate_code(value: str) -> str:
    code = value.strip().upper()
    if not CODE_RE.match(code):
        raise ValidationError("Use 2–20 letters, digits or dashes.")
    return code


class Campus(VersionedModel):
    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="campuses")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_active", "name"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_campus_code")]

    def __str__(self) -> str:
        return self.name


class Department(VersionedModel):
    """With a parent, its campus is always the parent's (the API sets it)."""

    institution = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT, related_name="departments")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    campus = models.ForeignKey(Campus, null=True, blank=True, on_delete=models.PROTECT, related_name="departments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_active", "name"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="unique_department_code")]

    def __str__(self) -> str:
        return self.name

    def descendant_ids(self) -> set:
        """Every department below this one, at any depth, from one query over the institution's departments."""
        children: dict = {}
        rows = Department.objects.filter(institution_id=self.institution_id).values_list("id", "parent_id")
        for pk, parent_id in rows:
            children.setdefault(parent_id, []).append(pk)
        found, todo = set(), [self.id]
        while todo:
            for child in children.get(todo.pop(), []):
                if child not in found:
                    found.add(child)
                    todo.append(child)
        return found
