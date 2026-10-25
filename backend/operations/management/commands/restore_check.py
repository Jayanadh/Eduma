"""Compares a restored database with the live one: row counts in every table and each institution's fee trial
balance. Run by ops/restore-drill.sh, which records the outcome and its measured duration as a RestoreDrill."""

import json

import psycopg
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from operations.models import BackupRecord, RestoreDrill

SKIP = ("operations_", "django_session")


def _snapshot(database: str) -> dict:
    """Read straight through psycopg: the restored database is not one Django is configured for."""
    params = {**connection.get_connection_params(), "dbname": database}
    params.pop("database", None)
    counts = {}
    with psycopg.connect(**params) as raw, raw.cursor() as cursor:
        for model in apps.get_models():
            table = model._meta.db_table
            # Operations telemetry and sessions are written after the dump is taken (the backup record itself), so
            # they are expected to differ; everything else must match exactly.
            if model._meta.managed and not model._meta.proxy and not table.startswith(SKIP):
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')  # table names come from the models, not input
                counts[table] = cursor.fetchone()[0]
        cursor.execute(
            "SELECT j.institution_id, l.account, SUM(l.debit) - SUM(l.credit) FROM fees_journalline l "
            "JOIN fees_journal j ON j.id = l.journal_id GROUP BY 1, 2 ORDER BY 1, 2"
        )
        balances = [[str(i), a, str(b)] for i, a, b in cursor.fetchall()]
    return {"counts": counts, "trial_balances": balances}


class Command(BaseCommand):
    help = "Compare the restored database (--restored NAME) with the live one and record the drill."

    def add_arguments(self, parser):
        parser.add_argument("--restored", required=True, help="Name of the database the backup was restored into.")
        parser.add_argument("--seconds", type=float, required=True, help="Measured restore time.")

    def handle(self, *args, **options):
        live, restored = _snapshot(connection.settings_dict["NAME"]), _snapshot(options["restored"])
        different = {
            t: [live["counts"][t], restored["counts"].get(t)]
            for t in live["counts"]
            if live["counts"][t] != restored["counts"].get(t)
        }
        passed = not different and live["trial_balances"] == restored["trial_balances"]
        backup = BackupRecord.objects.first()
        detail = {
            "tables": len(live["counts"]),
            "rows": sum(live["counts"].values()),
            "different_tables": different,
            "trial_balances_match": live["trial_balances"] == restored["trial_balances"],
            "trial_balance_lines": len(live["trial_balances"]),
        }
        if backup is not None:
            RestoreDrill.objects.create(
                backup=backup, ran_at=timezone.now(), seconds=round(options["seconds"], 1), passed=passed, detail=detail
            )
        self.stdout.write(json.dumps({"passed": passed, **detail}, indent=2))
