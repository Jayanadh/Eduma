from django.db import migrations

from institutions.modules import default_modules


def fill_defaults(apps, schema_editor):
    Institution = apps.get_model("institutions", "Institution")
    for institution in Institution.objects.filter(modules=[]):
        institution.modules = default_modules(institution.category)
        institution.save(update_fields=["modules"])


class Migration(migrations.Migration):
    dependencies = [("institutions", "0003_modules")]

    operations = [migrations.RunPython(fill_defaults, migrations.RunPython.noop)]
