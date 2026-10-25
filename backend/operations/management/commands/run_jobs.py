"""The worker: run it every minute from cron or systemd (`manage.py run_jobs`), or keep it running in development with
`--loop`. Each pass records a heartbeat, so a stopped worker shows as failing on the health page."""

import time

from django.core.management.base import BaseCommand

from operations.services import run_jobs


class Command(BaseCommand):
    help = "Run queued exports and due scheduled tasks once (or every minute with --loop)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep running, one pass a minute.")

    def handle(self, *args, **options):
        while True:
            for run in run_jobs():
                self.stdout.write(f"{run.task}: {run.status} {run.detail}")
            if not options["loop"]:
                return
            time.sleep(60)
