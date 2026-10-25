"""Prints the cutover reconciliation for one institution as JSON, to compare with the source system's own totals."""

import json

from django.core.management.base import BaseCommand, CommandError

from institutions.models import Institution
from operations.reconcile import cutover_report


class Command(BaseCommand):
    help = "Counts, money and checksums to reconcile with the source system before go-live."

    def add_arguments(self, parser):
        parser.add_argument("slug")

    def handle(self, *args, **options):
        institution = Institution.objects.filter(slug=options["slug"]).first()
        if institution is None:
            raise CommandError(f"No institution {options['slug']}.")
        self.stdout.write(json.dumps(cutover_report(institution), indent=2))
