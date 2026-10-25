# Eduma BUILD-11 — reports, exports, jobs, health, alerts, usage, backup and restore

**Date:** 25 October 2026 · **Status:** from the spec pack, fast mode. **Source:** 05 BUILD-11; 04 SCR-004, SCR-008,
SCR-009, SCR-041, SCR-042; 08 ExportJob; 09 `report.export`; 10 monitoring, backup and recovery (RPO 15 min / RTO 4 h
are provisional targets, D-14 open). **Completion evidence asked for:** a service failure produces a useful alert;
reports cannot bypass record permissions; recovery has measured evidence.

## Decisions

| ID | Decision |
|---|---|
| S11-01 | **Reports** are defined in code (no admin-written queries). Each has a key, title, module, permission and columns. Rows come only from what the viewer may read: student-based reports start from `visible_students` (campus-scoped readers see their campuses only). Every result carries provenance: generated at, filters, source, row count. Eight reports: students by class or program; attendance by class; fees outstanding; results by assessment; overdue library loans; placement outcomes; cases by type and state; leave taken. Module `reports` is available; the Reports page lists only the reports the viewer can run. |
| S11-02 | **Group aggregates:** for confidential case types, counts under 5 show as "<5" so small groups can't identify anyone. |
| S11-03 | **Exports** (`report.export`, plus the report's own permission): an ExportJob records the requester, report, filter snapshot and state (queued → running → done / failed). The worker writes a CSV with formula-looking cells neutralised. Downloads go to the requester only, rechecking both permissions; files expire after 7 days (410), and an hourly job deletes expired files. |
| S11-04 | **Jobs:** `manage.py run_jobs` (cron or systemd every minute; `--loop` for development) records a heartbeat, runs queued exports, and runs due scheduled tasks: expire exports (hourly), remind officers of overdue cases (daily) and evaluate alerts (every run). Each run is a JobRun row (task, started, finished, status, detail). |
| S11-05 | **Health** (SCR-008, platform admins): database (round trip), worker heartbeat, export queue age, import failures in the last day, private storage writable, last backup age, last restore drill, and media and payment providers. Each tile has a status (ok / warning / failing / unknown / not configured), the observation time, threshold, source and a runbook reference. A heartbeat never seen is unknown, never healthy; a stale one is failing, with its age. No secrets, hostnames or student data. |
| S11-06 | **Alerts:** each failing or warning check opens (or refreshes) one alert per check. Recovery resolves it automatically. Platform admins acknowledge and take ownership; the history is kept. The console overview shows open alerts. |
| S11-07 | **Usage** (SCR-009, read only): per institution, members by kind, active students, exports this month, messages this month, open cases and private storage bytes. Plans, quotas and billing aren't built (no commercial decision yet). |
| S11-08 | **Backup and restore:** `ops/backup.sh` writes a `pg_dump` custom-format dump from the database container plus a tar of private media, and a manifest with SHA-256s. `manage.py record_backup` stores the manifest so health knows the backup age. `ops/restore-drill.sh` restores the latest dump into a scratch database, runs `manage.py restore_check` (row counts per table and the fee trial balance against the live database) and records the measured duration and result as a RestoreDrill. The first drill runs here on the development machine; production must use encrypted, off-machine storage and point-in-time recovery (recorded as a limitation). |
| S11-09 | App `operations`; permission `report.export`; the Accountant and Principal roles get `report.export`. |

## Tests

- Reports return rows only within the viewer's scope (a campus-scoped reader never sees another campus).
- A report the viewer may not run → 403; module off → 404.
- Small confidential counts are suppressed.
- Exports: requester-only download, permission rechecked at download (revoked → 403), expiry → 410, formula cells neutralised.
- `run_jobs` processes the queue and records a heartbeat.
- A stale heartbeat makes health failing and opens an alert, which resolves once the worker recovers.
- No heartbeat at all is unknown.
- Acknowledging an alert works.
- Usage counts are correct.
- `restore_check` reports matching counts, and the trial balance matches.
