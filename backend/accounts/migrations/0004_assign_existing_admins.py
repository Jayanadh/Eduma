from zoneinfo import ZoneInfo

from django.db import migrations


def assign_admins(apps, schema_editor):
    """Every membership so far was an Institution Admin's: it becomes that role over the whole institution."""
    Membership = apps.get_model("accounts", "Membership")
    RoleAssignment = apps.get_model("accounts", "RoleAssignment")
    for membership in Membership.objects.filter(assignments__isnull=True):
        RoleAssignment.objects.create(
            membership=membership,
            institution_id=membership.institution_id,
            role_key="institution_admin",
            scope_type="institution",
            # The institution's own calendar day, as everywhere else that starts or ends a role.
            starts_on=membership.created_at.astimezone(ZoneInfo(membership.institution.timezone)).date(),
            status="ended" if membership.status == "revoked" else "active",
            created_by_id=membership.created_by_id,
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_roles_assignments")]

    operations = [migrations.RunPython(assign_admins, migrations.RunPython.noop)]
