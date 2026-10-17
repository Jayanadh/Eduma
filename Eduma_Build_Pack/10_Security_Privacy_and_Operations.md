# 10 — Security, Privacy and Operations

**Prepared:** 12 October 2026  
**Status:** Proposed engineering and operating requirements; not a security audit, legal opinion, compliance certification or production readiness claim.  
**Requirement families:** REQ-TEN, REQ-ACL, REQ-OPS, REQ-COM, REQ-FIN, REQ-INT.  
**Related:** [permissions](02_Roles_Tenancy_and_Permissions.md), [architecture](07_Architecture_and_Decisions.md), [data model](08_Data_Model_and_Dictionary.md), [tests](11_Test_UAT_and_Migration.md), [decisions](14_Decisions_and_Assumptions.md).

## 1. Operating responsibilities

Eduma operates the shared platform and institution provisioning. Each institution owns its academic policy, staff delegation and purposes of institutional processing. Legal roles must be assessed by processing purpose: Eduma's service telemetry, institution-held learner records and an external media provider may involve different responsibilities. Contracts must name instruction authority, subprocessors, incident contacts, data location, retention and exit assistance.

System Admin needs actionable service health, usage and lifecycle controls; that does not require unrestricted access to student records. Platform Operations receives redacted diagnostics. Institution Admin receives institution-specific operational status and authorized business metrics. Infrastructure configuration, secrets and privileged database operations belong in controlled operating systems, not an unrestricted browser SQL or shell console.

Assign named owners before production: platform engineering, security/incident response, institution privacy contact, academic records, finance, support and recovery. A small team may combine jobs, but high-risk self-approval restrictions must remain explicit.

## 2. India legal baseline and verification

As of 12 October 2026, the November 2025 DPDP commencement notification stages provisions at publication, one year and eighteen months. Core processing duties are in the later group; do not describe the entire Act as already operational. Record the Gazette publication basis and recheck subsequent notifications when setting deadlines. The omission of IT Act section 43A is also in the later commencement group. [Official commencement notification](https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf)

The DPDP Rules also commence in stages. Their education-related exceptions are conditional and do not authorize all ERP processing or commercial profiling. Plan notices, appropriate consent evidence, child-related safeguards, correction/erasure workflows and processor controls now, with counsel mapping each obligation to purpose and commencement. Future log/security retention rules must be reconciled with existing schedules. [DPDP Rules 2025](https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf)

During transition, assess current IT Act/SPDI applicability and the distinction between directly collected information and contractual processing. No universal exemption should be assumed merely because the customer is an educational institution. [Government SPDI clarification](https://www.pib.gov.in/newsite/erelcontent.aspx?lang=2&reg=48&relid=74990)

For covered entities and specified incidents, CERT-In directions include reporting within six hours of noticing or being informed, synchronized clocks, a designated contact and rolling 180-day ICT log retention within India. Counsel/security owners must confirm applicability and reporting responsibility. This is distinct from future/applicable DPDP notifications and customer notices. [CERT-In directions](https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf)

Maintain a legal applicability register: jurisdiction, processing purpose, provision, commencement, responsible entity, technical control, evidence owner and next review. Government identifiers and APIs require specific authorized access; Eduma must remain usable without pretending that every institution can connect to APAAR, DigiLocker, UDISE+, AISHE or other systems. International expansion requires a new country review before selling country-specific compliance.

## 3. Privacy by purpose

Classify data before collection: public branding; internal operational records; confidential identity, academic, HR and finance records; and tightly restricted health, disability, safeguarding, identity-document or biometric information. A sensitive classification does not automatically require collecting the field. Use optional fields with a defined purpose where possible; do not make Aadhaar a universal admission requirement.

Notices state purpose, data categories, recipients, retention, contact and relevant choices. Consent is versioned evidence with subject/guardian, purpose, notice revision, channel, time, status and withdrawal event; a generic admission checkbox is insufficient for every future use. Distinguish compulsory institutional records from optional media publication or recording. Consent withdrawal triggers purpose-specific cessation/review while legitimate retention requirements are separately documented.

Guardian verification and adult student delegation follow [permissions](02_Roles_Tenancy_and_Permissions.md). Parent access is never inferred from payment or matching contact information. Do not expose a student's full contact details to other class participants. Private chat/call content is unavailable to general admin dashboards; reported content enters a separately authorized review workflow. Recordings default off, with purpose, audience, access expiry and retention approved before enablement.

Privacy requests use identity verification, scope clarification, legal-hold review, assigned ownership and a logged response. Exports minimize third-party data and use secure delivery. No marketing use of student records or AI model training is included in the baseline. New analytics or AI processing requires its own purpose, provider and data review.

## 4. Threat scenarios and required controls

This is a focused planning table, not an exhaustive threat model or penetration test.

| Scenario | Required design | Verification evidence |
|---|---|---|
| Tenant ID or object URL substitution | Server membership checks, scoped queries, tenant-safe foreign keys, private storage | Cross-tenant API/file/job/socket tests |
| Pooled connection retains previous tenant | Transaction-scoped context, reset/fail-closed behavior, non-bypass service role | Concurrent reuse and rollback tests |
| Compromised admin escalates authority | Strong authentication, grant ceilings, sensitive-action step-up, approval separation | Role-escalation and self-approval denials |
| Payment webhook forged, replayed or out of order | Signature verification over required payload, provider event identity, idempotency, state machine | Duplicate/reorder/refund reconciliation suite |
| Malicious attachment or spreadsheet | Type/size validation, quarantine and malware scan, safe rendering, formula-injection controls | Unsafe file, disguised MIME and CSV fixtures |
| Forwarded class link or harassment | Server roster checks, short-lived scoped tokens, waiting room, host removal, reporting | Unauthorized join, revocation and abuse tests |
| Logs leak secrets or children’s data | Allowlisted structured fields, redaction, restricted access, sampled diagnostics | Log-content inspection and access tests |
| Bulk export misused | Separate export permission, field filtering, recipient checks, expiry, download audit | Revoked recipient and excessive-scope tests |
| Destructive migration or ransomware | Least privilege, protected backups, restore drills, immutable audit copy where required | Measured restore and reconciliation evidence |
| One institution exhausts workers/storage | Tenant quotas, fair queues, concurrency/rate limits and metering | Mixed-tenant load and noisy-tenant tests |

Baseline application controls include TLS, secure cookie/session settings, CSRF defenses for cookie authentication, safe output encoding, parameterized database queries, input schemas, restrictive file handling, dependency scanning and authentication throttling. Restrict outbound integration destinations to prevent server-side request abuse. Service accounts have purpose-specific permissions and short-lived credentials where supported. Password resets and invitations are single-use, expiring and revocable; account recovery must not bypass institutional authority checks.

## 5. Encryption, secrets and audit

Use managed key storage or an equivalently controlled secrets system. Never place production credentials in source control, browser bundles, logs or institution-editable settings. Store integration references and masked status in the UI, while secret values remain backend-only. Define rotation, revocation, emergency replacement and provider credential ownership. Backups must be encrypted with recoverable, independently protected keys; a backup without accessible keys is not a recovery plan.

Separate production, staging and development identities, databases, buckets and provider accounts. Use synthetic or approved anonymized data outside production. Deployment identities cannot casually browse learner records. Record privileged access and periodically review inactive accounts, grants and secret age.

Audit fields: event UUID, timestamp, actor and effective actor, institution, action, object identifiers, changed field names, safe prior/new values or references, reason, grant/approval ID, request correlation ID and outcome. Exclude secrets and unnecessary message bodies. Protect audit records from ordinary edits/deletion, restrict readers and maintain independent retention controls where required. “Append-only to application users” must not be marketed as mathematically tamper-proof.

## 6. Retention and deletion register

Durations below are named policy variables to be populated by accountable owners; blank values are unresolved production decisions, not infinite retention. The register must store approved duration, start event, jurisdiction/basis, version and approver.

| Category | Owner and policy variable | Trigger | Deletion/hold handling |
|---|---|---|---|
| Applicant records/documents | Admissions + privacy; `RET_APPLICATION` | Final decision/withdrawal | Remove rejected drafts after approved period; hold disputes separately |
| Enrollment, transcript and award history | Registrar; `RET_ACADEMIC` | Departure/award or prescribed event | Preserve mandated records; minimize unrelated attachments |
| Charges, receipts, refunds and reconciliation | Finance + legal; `RET_FINANCE` | Financial period closure | Immutable corrections; tax/dispute holds verified |
| Employee/payroll | HR + legal; `RET_HR` | Separation/financial closure | Restricted archive and statutory record review |
| Messages and attachments | Institution communications owner; `RET_MESSAGE` | Message/conversation event | Delete body, attachment derivatives and indexes coherently |
| Call metadata / recordings | Privacy + academic owner; `RET_CALL_META`, `RET_RECORDING` | Call/session end | Independent schedules; recording disabled until approved |
| Health/safeguarding | Designated restricted-record owner; `RET_RESTRICTED` | Case closure or applicable event | Restricted hold and reviewed access, not ordinary class export |
| Security/ICT logs | Security + legal; `RET_SECURITY_LOG` | Event time | Meet applicable CERT-In baseline and other effective duties |
| Backups | Operations + privacy; `RET_BACKUP` | Backup creation | Fixed expiry; legal constraints and recovery needs reconciled |
| Report exports/import staging | Data operations; `RET_EXPORT`, `RET_IMPORT_STAGE` | Completion or failure | Expire private objects and delivery tokens; preserve minimal provenance |

A retention job supports preview, approval for exceptional purges, batch limits and evidence. Legal holds name an authority, scope, reason and review date. Deletion covers primary data, objects, thumbnails, search, cache and processors. Backups expire through their approved schedule; after restore, replay deletion/hold records before allowing user access. Publicly issued academic verification documents may require a different retention policy from portal profile data.

## 7. Health dashboard and alerting

Every widget shows measurement time, scope, source and stale/unknown state. Missing telemetry must not appear green. Business correctness metrics accompany infrastructure metrics.

| Signal | Proposed starting alert / budget | Action and owner |
|---|---|---|
| Core API availability | Draft 99.9% monthly SLO; eligible requests defined separately | Burn-rate alert; incident lead reviews failing journeys |
| API latency/errors | Candidate p95 ordinary read under 800 ms, write under 2 seconds at agreed load | Trace slow paths; distinguish provider and database delay |
| Database | Connection use above 80% for 10 min; sustained locks/replication lag | Operations investigates pool, queries and capacity |
| Worker queues | Oldest time-critical task over 60 seconds for 5 min | Inspect failures; throttle heavy imports; route retries |
| Payment reconciliation | Any unexplained settled-versus-ledger mismatch | Finance/engineering investigate; do not auto-invent entries |
| Message/call service | Rising delivery failures, join failures or stale provider status | Show degraded service; retry safely and notify support |
| Storage/cost | Tenant budget at 80% warning, 100% policy action | Institution/Admin sees usage; avoid deleting data automatically |
| Backups and audit | Backup overdue, restore check failed, audit sink unavailable | Operations/security escalates; preserve local protected buffers |

These thresholds are hypotheses to tune with measured pilot traffic. Define numerator, denominator and exclusions for SLOs; planned maintenance and dependency treatment require agreement. A 99.9% availability target does not prove capacity or imply a contractual SLA. Monitor fleet summaries without placing unbounded tenant/user IDs into high-cardinality metric labels. Keep audit, security, application and business event purposes distinct.

## 8. Recovery, incidents and releases

Provisional recovery targets are **RPO ≤15 minutes** and **RTO ≤4 hours** for an agreed database/platform failure scenario. They are not validated promises. Specify whether a regional failure, key loss, object deletion or provider outage is included. Back up PostgreSQL with point-in-time recovery capability, object data/version history as appropriate, configuration and necessary key recovery material. Inventory dependencies and test them together.

Whole-platform restore occurs in an isolated environment, checks application/database compatibility, validates objects and keys, reapplies holds/deletions, reconciles finance, then restores access. Individual-tenant recovery in a shared database restores a separate copy, extracts only that tenant, reconciles intervening events and applies controlled corrections. Never rewind every institution to repair one. External settlements and notifications cannot be undone by restoring a database; replay and reconciliation are mandatory.

Incident sequence: detect and timestamp; assign lead/severity; contain with minimum necessary disruption; preserve evidence; assess data/service impact; activate applicable reporting and customer-notification clocks; restore and validate; review causes and corrective work. Do not wait for a complete investigation before an applicable reporting deadline. Keep runbooks for database saturation, compromised account, media outage, payment backlog, tenant suspension and failed deployment.

Use reviewed changes, reproducible builds, dependency inventory, migration previews and staged releases. Prefer backward-compatible database expansion followed by later removal. A rollback plan must cover data written by the new version; reverting an executable alone may be unsafe. Production readiness requires restore evidence, incident ownership, secret inventory, tested access boundaries and approved service/retention commitments. No such evidence is claimed by this planning file.
