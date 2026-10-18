from django.db import migrations


def add_main_campus(apps, schema_editor):
    Campus = apps.get_model("organization", "Campus")
    Institution = apps.get_model("institutions", "Institution")
    for institution in Institution.objects.exclude(campuses__code="MAIN"):
        Campus.objects.create(institution=institution, code="MAIN", name="Main campus")


class Migration(migrations.Migration):
    dependencies = [("organization", "0001_initial")]

    operations = [migrations.RunPython(add_main_campus, migrations.RunPython.noop)]
