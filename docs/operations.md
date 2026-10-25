# Eduma — operations runbook

What an operator runs, what the console's **Health** page means, and what to do when a tile goes red. Health tiles and
alerts link here by section. Targets are the pack's provisional ones (RPO 15 minutes, RTO 4 hours; D-14 is open) and
are not promises until agreed and tested in the production environment.

## Processes

| Process | Command | How often |
|---|---|---|
| API | `backend/.venv/bin/python backend/manage.py runserver 8001` (development); a WSGI server in production | always |
| Worker | `backend/.venv/bin/python backend/manage.py run_jobs` | every minute from cron or a systemd timer; `--loop` in development |
| Backup | `ops/backup.sh` | daily (cron `15 2 * * *`) |
| Restore drill | `ops/restore-drill.sh` | monthly, and after any change to backups |

Each worker pass records a heartbeat, builds queued exports, runs due scheduled tasks (expire exports hourly,
overdue-case reminders daily) and evaluates alerts. Every run is in **Jobs** on the console.

## Health tiles and alerts

Tiles: ok, warning, failing, unknown (no telemetry yet, never shown as healthy) or not configured. A failing or warning
tile opens one alert. The alert refreshes while the problem lasts and resolves itself when the tile is ok again.
Acknowledging an alert makes you its owner; the history stays.

### database

The API couldn't run `SELECT 1`, or the round trip took over 200 ms.

1. `docker compose ps`.
2. `docker compose logs db --tail 100`.
3. Check the disk space on the database host.
4. Restart the container only after reading the logs.
5. If the data is damaged, see [restore](#restore).

### worker

No heartbeat for 5 minutes: the worker isn't running. A stopped worker can't raise its own alert, so point an outside
uptime monitor at `/api/v1/health/ready`. It answers 200 when the database, worker and storage are healthy, and 503
naming what isn't. Each probe, and each view of the console's Health page, also opens or resolves alerts.

1. Check the cron entry or systemd timer.
2. Run `manage.py run_jobs` by hand and read its output.
3. A task that fails is recorded with its error in **Jobs**.

Exports wait while the worker is down; nothing is lost.

### exports

The oldest queued export has waited more than 10 minutes (warning) or 30 minutes (failing).

1. Check the [worker](#worker) first.
2. A failed export shows its error to the person who asked for it, who can request it again.

### storage

Private media (applicants' documents, imports, evidence, exports) isn't writable.

1. Check the disk space.
2. Check the ownership of `DJANGO_PRIVATE_MEDIA_ROOT`.

Uploads fail cleanly while this lasts; nothing half-written is kept.

### backup

No backup in 26 hours, or none recorded at all (unknown).

1. Run `ops/backup.sh` by hand.
2. It needs `docker compose` access to the `db` service.
3. It writes `backups/<timestamp>/` with `eduma.dump`, `private_media.tar` and `manifest.json` (SHA-256s), then records itself.

Development keeps backups on this machine, unencrypted. Production must:

- encrypt them with independently held keys;
- keep them off the database host;
- add point-in-time recovery (WAL archiving) to meet a 15-minute RPO.

None of that is set up yet.

### restore

No passing drill in 35 days, or a drill failed.

`ops/restore-drill.sh` does the following:

1. Checks the latest dump against its manifest.
2. Restores it into a scratch database `eduma_drill`; the live database is never touched.
3. Unpacks the media into a scratch folder.
4. Runs `manage.py restore_check`, which compares every table's row count and each institution's fee trial balance with the live database. Operations telemetry and sessions are expected to differ, so they are skipped.
5. Records the measured duration and the result.

A failed drill lists the tables that differ.

**A real restore** (after damage, decided by whoever owns the incident):

1. Stop the API and the worker.
2. Restore the chosen dump into a new database.
3. Run `restore_check` against the last known-good counts.
4. Point `POSTGRES_DB` at the restored database.
5. Unpack `private_media.tar`.
6. Start the API, then the worker.
7. Reconcile fees: check the trial balance and provider settlements since the backup.

### providers

Calls and classes run only on the test-mode sandbox (D-12). Payments run only on the sandbox. Both tiles say so; they
never report a live connection that isn't there.

## Cutover

The spec pack's sequence:

1. Source-owner sign-off.
2. Mapping and a dry run (**Data transfer**, then Check).
3. Resolve the flagged rows.
4. Freeze the source.
5. `ops/backup.sh`.
6. Commit.
7. Reconcile.
8. Verify users and roles.
9. Institution acceptance.

`manage.py cutover_report <slug>` prints what to compare with the source system's own totals:

- students by status, active enrollments and guardian links;
- imported records by type;
- fees: charged, credit notes, received, refunded, and the trial balance net, which must be 0.00;
- courses and attempts by outcome;
- issued documents with a checksum;
- anything unresolved: import rows with errors, imports not committed, open reconciliation cases.

Go live only with zero unexplained differences in counts and money. Importing the same file again creates nobody (TST-025), so a retried import doesn't move the numbers.

## Release gates

Run these before a release:

- `pytest` (the everyday suite);
- `pytest -m adversarial`: the cross-tenant sweep, and every route answering an empty request without a 5xx (about 10 minutes);
- `npm test` and `npm run check:a11y`;
- `ng build`;
- `manage.py check --deploy` with production settings;
- `ops/backup.sh` and `ops/restore-drill.sh`.

## Measured evidence

| Date | What | Result |
|---|---|---|
| 25 Oct 2026 | `ops/backup.sh` then `ops/restore-drill.sh` on the development machine (PostgreSQL 17 in Docker, demo data) | Passed: 150 tables and 1,472 rows matched; 5 trial-balance lines matched; restore 1.0 s. This is demo scale only; repeat with production-sized data before agreeing an RTO. |
| 25 Oct 2026 | `manage.py measure_workload --clients 8 --rounds 20` on demo data | 2,080 reads in 16.9 s, zero errors, worst p95 148.5 ms (report "students by class"); the planning target is 800 ms. In-process, demo scale. |
| 25 Oct 2026 | `manage.py cutover_report aster` on demo data | 8 active students; 6 imported; fees charged 10,000.00, credit notes 1,000.00, received 6,000.00; trial balance net 0.00; 1 import still uncommitted, with 1 row in error (shown as unresolved). |
