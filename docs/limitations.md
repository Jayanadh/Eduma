# Eduma — remaining limitations, provider dependencies and support ownership

BUILD-12's record of what this release does not do, what it waits on, and who looks after what. Nothing below is
hidden behind a working-looking screen: each item is either absent from the interface or shown as not configured.

## Not part of web completion

- **BUILD-13: native mobile apps and international expansion.** The spec pack keeps these out of web completion unless re-scoped (D-09, D-22). That covers:
  - push notifications;
  - locked-screen and background calling (TST-032);
  - app-store releases;
  - country-specific rules.

  The web app works on phone widths, but it is not a native app.

## Built, with known limits

| Area | Limit | Upgrade when |
|---|---|---|
| Payroll | One cycle per month. There are no adjustment cycles: an exported month can't be redone in Eduma. Statutory deductions are entered, not calculated (D-11). | A payroll engine or adapter is chosen (D-11). |
| Procurement | Requisitions double as orders: there are no separate purchase-order documents, quotations or depreciation. | Finance asks for them. |
| Hostel | No mess, meal plans or deposits. | Those are scoped. |
| Transport | No GPS tracking. | A tracking provider is chosen. |
| Placements | No employer or recruiter logins, and no CV builder. The placement office works on employers' behalf. | Employer access is approved, with its consent rules. |
| Research | No grants, disbursements or publication lists (they need an accounting boundary, D-11). | They are scoped. |
| Quality evidence | Generic criteria and evidence; no framework-specific report formats. A frozen cycle is an evidence record, not an accreditation claim. | A framework's format is supplied. |
| Cases | Overdue cases are flagged and their officers reminded daily; there are no multi-step escalation rules. | The institution approves escalation rules. |
| Notifications and alerts | In-app only. There is no email or SMS (D-12), and console alerts are not sent anywhere else. | A mail or SMS provider is contracted. |
| Usage | Read-only counts. There are no plans, quotas or billing (D-06). | The commercial model is decided. |
| Support | No support-access sessions (SCR-010). Support uses the audit log and the institution's own admin. | A support model is agreed (D-17). |
| Service status | Institution users see no service-status banner. Platform health is console-only. | Needed for incidents. |
| Imports | Synchronous, up to the file size limit. A heavy import by one tenant isn't queued or rate-shared (TST-024 not exercised). | Real import sizes are known (D-16). |
| Attachments | Uploads are checked by content type (PDF, PNG, JPEG) and size, but not virus-scanned. Quarantine (TST-021) exists only for payment events. | A scanning service is chosen. |
| Retention and deletion | No retention schedules, legal holds or erasure workflow (TST-022). Records are archived, not erased. | Retention rules are agreed (D-14). |
| Restore | Whole-database restore only. No single-tenant restore (TST-023) and no point-in-time recovery; backups are local and unencrypted on the development machine. | Before production: encrypted off-site backups, WAL archiving, a single-tenant runbook. |
| Language | English only (D-05). The interface text is not yet extracted for translation. | Launch languages are confirmed. |
| Theme | One light theme (D-18). | A second theme is approved. |

## Waiting on providers or decisions

| Dependency | State in Eduma | Decision |
|---|---|---|
| Online payments | Test-mode sandbox with signed webhooks, deduplication and reconciliation; no live gateway | D-12 |
| Calls and online classes (media) | Test-mode sandbox issues tokens but carries no audio or video; screens say so | D-12; recording off, D-13 |
| Email and SMS | None | D-12 |
| Payroll engine and statutory rules | Export file boundary only | D-11 |
| Real academic rules per category | Synthetic demo rules only (school, college, engineering, university) | D-01 |
| Hosting, residency, RPO/RTO | Development machine; provisional targets only | D-14, D-21 |
| Capacity target | Measured only at demo scale (see below) | D-03 |
| Logo and branding review | Text wordmark | D-20 |

## Verification still to do

- **UAT for all four institution categories, with approved real rules.** This needs the pilot institutions and D-01.
- **Human accessibility review** with a keyboard and screen readers. There is a static check (`npm run check:a11y`) and labelled controls throughout, but no claim of WCAG 2.2 AA is made.
- **Workload at real scale.** `manage.py measure_workload` on demo data: 8 concurrent clients, 2,080 everyday reads, worst p95 148.5 ms (target 800 ms). It measured the application and database in-process, not the network or a production server.
- **Writes under load.** Not measured.
- **External security review.** The internal review found `check --deploy` clean and logs free of tokens. The cross-tenant sweep `pytest -m adversarial` calls every id-taking route with another institution's ids: no leaks, nothing changed. Dependency audits on 25 Oct 2026: `pip-audit` and `npm audit` both report 0 known vulnerabilities, after the fixes in progress.md. No penetration test has been done.
- **Recovery at real scale.** The restore drill passed on demo data in 1.0 s. That is not an RTO.

## Support ownership

| What | Owner |
|---|---|
| Platform: hosting, health alerts, backups, restore drills, the worker, provider accounts | Eduma platform operations (the platform admin role) |
| An institution's setup, staff, roles, modules and settings | That institution's Institution Admin |
| Each office's records (fees, library, HR, cases and the rest) | The office's role holders, within their permissions |
| Confidential cases | The assigned Grievance Officer; assignment is audited |
| Import exceptions and cutover sign-off | The institution's data owner, using `manage.py cutover_report <slug>` and the source system's totals |
| Incidents | Whoever acknowledges the alert on the console; the runbook is `docs/operations.md` |

Response times and coverage hours are not promised yet (D-17).
