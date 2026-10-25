"""Records a backup taken by ops/backup.sh from its manifest, so the health page knows how old the last backup is."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from operations.models import BackupRecord


class Command(BaseCommand):
    help = "Record the backup described by a manifest written by ops/backup.sh."

    def add_arguments(self, parser):
        parser.add_argument("manifest")

    def handle(self, *args, **options):
        try:
            with open(options["manifest"]) as handle:
                m = json.load(handle)
        except (OSError, ValueError) as error:
            raise CommandError(f"Can't read the manifest: {error}") from error
        made = BackupRecord.objects.create(
            taken_at=parse_datetime(m["taken_at"]),
            database_file=m["database"]["file"],
            database_sha256=m["database"]["sha256"],
            media_file=m["media"]["file"],
            media_sha256=m["media"]["sha256"],
            size_bytes=m["database"]["bytes"] + m["media"]["bytes"],
        )
        self.stdout.write(f"Recorded backup {made.id} taken at {made.taken_at:%Y-%m-%d %H:%M}")
