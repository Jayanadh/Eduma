# Eduma — Decisions, Assumptions and Review Status

**Version/date:** 1.1 / 12 October 2026  
**Status:** Authoritative planning register for this pack. “Proposed” never means user-approved. This replaces the earlier standalone decision register for the purpose of this portable handoff.

**Latest user direction:** The user supplied `logo_eduma.png`, explicitly selected Angular + Django REST Framework + PostgreSQL, and accepted documented proposed defaults for local development. They authorized a concrete desktop/mobile preview of System Admin, Institution Admin, teacher attendance, parent and student screens. Actual application implementation remains conditional on their visual approval. This update supersedes the initial “logo not supplied” and stack-selection status in older baseline documents. Prototype files and review evidence are distributed separately in `Eduma_UI_Preview`; they are not the production application.

## 1. Confirmed requirements

| ID | Confirmed from the user |
|---|---|
| C-01 | The product is named Eduma |
| C-02 | Initial market is India, with international expansion |
| C-03 | Schools, colleges, engineering colleges and universities are all initial institution categories |
| C-04 | Support institution groups, multiple campuses and affiliated colleges |
| C-05 | System Admin onboards institutions, uploads initial institution images/details and primary admin information, activates/deactivates institutions and manages platform health/metrics |
| C-06 | Institution Admin controls institutional operations, users, branding and feature settings within platform availability |
| C-07 | Teacher–parent and staff messaging/calling; students participate in teacher-conducted online classes under institution policy |
| C-08 | Angular + Django REST Framework + PostgreSQL is explicitly selected; later Android/iOS are intended |
| C-09 | Planning and visual review precede application implementation; the logo has now been supplied |
| C-10 | Generate the required Markdown documents and `prompt.md` for attachment to a later build session |
| C-11 | Use the prior conversation/application context and review it through the requested Superpowers planning workflow before implementation |
| C-12 | Use documented defaults for local development; first create the five requested responsive previews, then implement after visual approval |

The user authorized this document pack and the interactive visual preview. The preview has been created for review; user visual approval and production approval have not been received.

## 2. Decision classes

- **Foundation decision:** resolve before dependent architecture or irreversible implementation choices.
- **Design decision:** resolve before representing a visual direction as approved; independent domain specification may continue.
- **Integration decision:** resolve before claiming that provider capability works; unrelated local work can continue.
- **Production decision:** resolve before using real institutional rules/data or making operational/legal promises.

Routine reversible choices can use clearly recorded proposed defaults once the user authorizes building with those defaults. Ask only for missing choices that materially affect the next work; do not re-ask confirmed requirements.

## 3. Decisions and suggested defaults

The table below preserves the original decision inventory. Proposed defaults in D-02, D-07, D-08, D-10, D-11, D-13, D-15 and D-18 are now accepted for local development by the latest user instruction, with application work starting after design approval. This does not select unconfigured providers, approve production rules/SLAs, choose a future native framework or approve the visual direction. D-19 is now **preview authorized; implementation conditional on visual approval**. D-20 is **logo supplied; visual review pending**. D-21's primary stack is accepted; exact compatible versions and hosting remain implementation choices.

| ID | Question | Proposed default or required evidence | Class / status |
|---|---|---|---|
| D-01 | Which real boards, programs and university regulations define the pilots? | One representative case per confirmed category; use explicitly synthetic rules only for development until institutional rules are supplied | Production; open |
| D-02 | What first-release breadth is approved? | Preserve full web catalog; build L1 operational core then L2 breadth. A smaller launch requires explicit scope approval | Foundation; proposed |
| D-03 | What is the capacity target? | Use the illustrative test scenario in 11 for engineering discussion, never as approved forecast/SLA | Production/cost; open |
| D-04 | Which visual direction is approved? | Calm neutral surfaces, restrained indigo accent, task-focused layouts; review representative screens in 06 | Design; proposed |
| D-05 | Which languages and devices are required? | English draft with Unicode/localization architecture and phone/tablet/desktop coverage; actual launch language set needs confirmation | Design/production; open |
| D-06 | What team, budget and deadline are available? | Estimate after release breadth and external dependencies are known; no invented schedule | Delivery/cost; open |
| D-07 | Which organizations are separate tenants? | One independently governed institution per `institution_id`; campuses within it; groups/affiliations connect via explicit grants | Foundation; proposed |
| D-08 | What institution branding is editable? | Institution logo and validated accent/theme tokens; preserve semantics/accessibility/security | Design; proposed |
| D-09 | One mobile app or per-institution apps? | One Eduma application with authorized institution/role switching; native implementation later | Future mobile; proposed |
| D-10 | Which Angular UI foundation? | Angular Material/CDK plus shared Eduma tokens; assess specialized grid need separately | Design/technical; proposed |
| D-11 | What accounting/payroll depth is in scope? | Fee subledger is core; clearly scoped adapters or separately reviewed engines for full accounting/statutory payroll | Foundation/integration; proposed |
| D-12 | Which external providers/accounts are usable? | Select payment, mail/SMS, storage and WebRTC providers by contract/capability; explicit unconfigured state until configured | Integration; open |
| D-13 | Is call/class recording needed? | Off. Enable only after purpose, notice/consent, access, retention, provider and jurisdiction review | Privacy/integration; proposed |
| D-14 | What residency, retention, RPO/RTO commitments apply? | Category-specific responsibilities; operational targets in 10 remain provisional until tested and agreed | Production; open |
| D-15 | What may admins configure? | Typed versioned fields/rules/workflows, impact preview and historical preservation; no arbitrary code or security bypass | Foundation; proposed |
| D-16 | Which source documents/import formats must be supported? | Collect blank/redacted samples; use deterministic synthetic fixture set in 11 during development | Workflow/production; open |
| D-17 | What support coverage and service tier are promised? | Assign owners, response channels and incident coverage before contracts | Production; open |
| D-18 | Is dark mode included? | Deliver one complete accessible theme first; second theme only if explicitly included | Design/scope; proposed |
| D-19 | Is the next session review or build? | Default to reviewing the pack and missing consequential choices. A direct instruction to build is authorization after applicable design/readiness review | Start gate; open until that session |
| D-20 | Where is the logo and has branding been reviewed? | Logo not supplied. Request the promised asset when needed; a text wordmark requires user acceptance as a provisional alternative | Design; open |
| D-21 | Which stack and deployment versions? | Supported compatible stable versions selected/locked at implementation; no mandatory cloud vendor chosen | Technical; open |
| D-22 | Which mobile framework? | Evaluate Ionic/Capacitor against native-calling requirements; retain Angular web and backend if another mobile client is selected | Future mobile; open |

## 4. Proposed defaults connecting the documents

These defaults reduce contradiction while remaining reviewable:

1. `institution_id` is the initial data boundary; it is not interchangeable with group/campus.
2. UUID record IDs, server-verified membership, integer record version and UTC instants.
3. Exact money and explicit currency; synthetic fees/marks/credits in 03 and 11 are test expectations only.
4. Angular/TypeScript + proposed Material/CDK; Django/DRF modular monolith; PostgreSQL; Channels; Celery/RabbitMQ; separate Redis purposes; private object storage.
5. First-party web sessions with CSRF. Mobile authentication is a later reviewed client design.
6. Managed WebRTC transport is proposed; provider is not selected. Persistent chat is a separate durable domain.
7. Teacher-supervised student meetings, no unrestricted student direct communication, recording off.
8. Library/transport/hostel/HR/assets/service/placement/quality/research web capabilities remain tracked even when delivered after core workflows.
9. No currently unavailable integration is silently represented by fabricated success.
10. Technical operations show healthy/degraded/unavailable/unknown based on evidence, not constant green indicators.

## 5. Evidence and design-review status

| Item | Actual status |
|---|---|
| Research baseline | Written with linked sources; changing legal/provider facts need revalidation before use |
| Detailed Markdown specifications | Written as proposed/review-ready requirements |
| Internal document checks | To be recorded in 00 when performed; not application testing |
| Brand/logo | Supplied as `logo_eduma.png`; used unchanged in the preview |
| Rendered wireframes or clickable prototype | Five interactive responsive role previews created in `Eduma_UI_Preview`; visual approval pending |
| User visual approval | Not obtained |
| Implemented application or database | Not generated |
| Integration credentials/partnerships | Not provided/verified by this task |
| Runtime, isolation, performance, media/device tests | Application/backend/native tests not run; 40 prototype layout/interaction checks passed separately |
| Legal sign-off and institution-specific rule approval | Not obtained |
| Production deployment | Not performed |

## 6. Handling open items in a future session

Read this register first. State the current mode and identify only the unresolved decisions that affect the next action. Present a concrete default/alternative and consequence. Continue independent authorized work while awaiting a genuinely required answer.

Do not make a production-rule guess to hide a missing regulation. Use labeled synthetic examples for development. Do not let a missing live provider secret prevent designing its interface, but do not call that integration delivered.

When the user approves a decision, record the option, date/message evidence, affected documents and reconsideration condition. Keep prior decisions as superseded. Merely attaching this pack does not approve every proposed default; a clear instruction to proceed with the documented defaults can do so for their stated development scope.

## 7. Change record

| Version | Change | Authority |
|---|---|---|
| 1.0, 12 October 2026 | Consolidated existing user requirements; produced full specification pack and future-session prompt | User requested Markdown preparation, not code generation |
| 1.1, 12 October 2026 | Logo received; stack/defaults accepted for local development; five responsive previews prepared with synthetic data and browser evidence | User explicitly requested preview first and application implementation after visual approval |

Future implementation sessions add actual decision and evidence records here or in a repository-linked successor. Never fill approval/date fields with fictional reviewers or assumed consent.
