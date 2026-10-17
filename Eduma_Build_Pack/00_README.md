# Eduma — Predevelopment Specification Pack

**Pack version:** 1.1  
**Prepared:** 12 October 2026  
**Status:** Specifications prepared; five responsive visual previews now available for review. The Angular/Django/PostgreSQL application has not been generated.

**Latest handoff:** The user supplied the Eduma logo and accepted the selected stack and documented defaults for local development. See 14 for the current decision record. The separate `Eduma_UI_Preview` folder/ZIP contains the interactive prototype and ten desktop/mobile screenshots. Review the prototype before authorizing the conditional application implementation; older research/design-status statements describe the initial document-only baseline.

This pack consolidates the Eduma requirements already supplied in the conversation and develops them into product, design and engineering specifications. It supports the requested flow: **review the documents → supply the logo → review concrete screens → approve the relevant decisions → build and verify connected stages**. A single enormous generation step would make errors and missing modules harder to detect; the supplied prompt instead maintains the complete agreed scope while guiding staged implementation.

## 1. Confirmed product direction

Eduma is a centralized, multi-institution education ERP for **India first**, with international expansion planned. **Schools, general colleges, engineering colleges and universities are all initial institution categories.** Groups, campuses and affiliated colleges are included through explicit authority and controlled data sharing.

The Eduma System Admin onboards institutions, uploads their initial details/images, invites Institution Admins, controls activation and platform entitlements, and monitors the platform. Institution Admins own institutional operations, users, academics, branding and available feature settings. Teacher–parent and authorized staff messages/calls are included; students join teacher-conducted online classes under institution policy.

Angular + Django + PostgreSQL remains the working stack recommendation, with alternatives and mobile implications documented. Web comes first; Android/iOS come later. Configurability means validated, versioned rules and workflows with history and delegated authority.

## 2. File manifest and review order

The folder contains **17 Markdown files**: 16 numbered specification/reference files plus the future-session prompt. Individual document revision numbers may differ from the pack version; every approval/evidence status remains explicit.

| File | Purpose | Suggested reviewer |
|---|---|---|
| [00_README.md](00_README.md) | Navigation, usage, precedence and actual status | Everyone |
| [01_PRD_and_Release_Scope.md](01_PRD_and_Release_Scope.md) | Product objectives, requirement families and complete scope | Product owner, institution representatives |
| [02_Roles_Tenancy_and_Permissions.md](02_Roles_Tenancy_and_Permissions.md) | Admin boundaries, roles, canonical action permissions and isolation | Product, security, backend |
| [03_Workflows_and_Business_Rules.md](03_Workflows_and_Business_Rules.md) | State transitions, exceptions and worked academic/financial examples | Academic, finance, operations |
| [04_Navigation_and_Screen_Catalog.md](04_Navigation_and_Screen_Catalog.md) | 49 screen identifiers, role navigation and device expectations | Product and design |
| [05_Design_System_and_Responsive_UX.md](05_Design_System_and_Responsive_UX.md) | Proposed tokens, components, responsive behavior and accessibility | Design and frontend |
| [06_Screen_Specs_and_Prototype_Review.md](06_Screen_Specs_and_Prototype_Review.md) | Representative layouts, actions, validations, states and review scenarios | Product, design, institution users |
| [07_Architecture_and_Decisions.md](07_Architecture_and_Decisions.md) | Stack tradeoffs, modular architecture, tenancy and mobile strategy | Technical lead, operations |
| [08_Data_Model_and_Dictionary.md](08_Data_Model_and_Dictionary.md) | Entities, relationships, constraints, history and fee subledger | Backend, academic, finance |
| [09_API_Events_and_Integrations.md](09_API_Events_and_Integrations.md) | Interface conventions, routes, events, callbacks and provider boundaries | Backend, frontend, integration owners |
| [10_Security_Privacy_and_Operations.md](10_Security_Privacy_and_Operations.md) | Privacy planning, access, India obligations, monitoring and recovery | Security, operations, legal/contract owners |
| [11_Test_UAT_and_Migration.md](11_Test_UAT_and_Migration.md) | Synthetic fixtures, acceptance scenarios, migration and release evidence | QA, institution owners, engineering |
| [12_Delivery_Backlog_and_Build_Readiness.md](12_Delivery_Backlog_and_Build_Readiness.md) | 13 dependency-ordered build stages, readiness and completion criteria | Product owner, delivery lead |
| [13_Traceability.md](13_Traceability.md) | Requirements → workflows/screens/contracts/tests/build stages | Product, QA, technical lead |
| [14_Decisions_and_Assumptions.md](14_Decisions_and_Assumptions.md) | Confirmed decisions, proposed defaults and unresolved choices | Product owner first |
| [15_Research_Baseline.md](15_Research_Baseline.md) | Source-linked enterprise ERP knowledge document | All reviewers as needed |
| [prompt.md](prompt.md) | Portable instructions for the next review/build session | The future implementation assistant |

For the first review, read **00 → 14 → 01 → 02 → 03 → 04–06**. Review **07–11** with technical/operational owners, then **12–13** for delivery coverage. Consult 15 for research and definitions rather than treating its earlier high-level proposals as accepted implementation decisions.

## 3. How to transfer this work

Three equivalent ways to carry the specifications forward:

1. **Chat attachments:** attach `Eduma_All_Specifications.md`, this folder's `prompt.md`, and the logo when available. The merged document contains 00–15 with source-file markers; no need to attach the separate copies too.
2. **Repository workspace:** copy this folder into a documentation directory, preserve filenames, and ask the assistant to read 00 and prompt before implementation. The future project layout is proposed in 12; no project is created by this pack.
3. **Archive:** extract `Eduma_Build_Pack.zip` and use all 17 files. Some interfaces cannot read a ZIP directly, so extraction or the merged Markdown is more reliable.

The prompt defaults to **review** unless the user explicitly requests implementation. It also respects already approved decisions and requires honest evidence for actual progress. Attaching the files alone is not approval of every proposal. If an interface truncates or cannot access a document, the assistant must identify the missing input before relying on it.

## 4. Authority and conflict rules

Apply current explicit user instructions first, then accepted decisions recorded with evidence, then the confirmed requirements in 14. Detailed reviewed specifications govern their subject. Unapproved defaults remain proposals; source research informs decisions but does not approve them. External laws, institutional regulations and contracts must be checked for actual applicability and cannot be inferred from a generic example.

The user explicitly replaced the earlier school-first direction with all four institution categories at launch. **L1/L2 are proposed build order, not approval to omit categories or abandon operational modules.** L3 contains later mobile/international work or explicitly selected advanced scope. A smaller release needs a recorded scope decision.

If two documents conflict on permissions, tenancy, money, official results or release breadth, resolve the conflict and update affected files before implementing the dependent behavior. Do not silently choose the easier or more permissive interpretation. Prefer canonical permission names in 02 and data/interface conventions in 08/09.

The earlier standalone knowledge document and predevelopment plan are historical planning artifacts. This pack is the consolidated handoff; 15 preserves the research baseline. Keep user decisions and evidence in 14 or a clearly linked successor as the project develops.

## 5. Current readiness and next concrete work

| Area | Current state / next step |
|---|---|
| Requirements and written specifications | Prepared for review; proposals are labeled |
| Logo and visual direction | Logo supplied; five actual responsive previews created; user visual approval pending |
| Institution rules | Obtain sample academic, fee, receipt, transcript and approval rules for representative institutions; use labeled synthetic examples for development |
| Stack and tenant choices | Working recommendations are recorded; resolve consequential choices before their implementation |
| Providers | Payment, messaging, media, hosting and external-education access remain unselected/unverified where noted |
| Capacity, operating budget and commitments | Establish actual forecast, support ownership and recovery/service targets before contractual promises |
| Application, database and native apps | Not generated |
| Runtime tests and prototype/UAT evidence | 40 prototype checks passed; application/backend, accessibility-conformance and human UAT evidence remain unverified |

No additional planning files need to be invented just to delay useful work. The next review should resolve the decisions that affect the first design/build slice. During implementation, create executable subsystem plans, actual OpenAPI/event schemas, migration files, runbooks and evidence records when the corresponding code and environment make those artifacts meaningful.

## 6. Document quality checks

Preparation includes checks for the complete file manifest, internal file links, stable screen/test/build identifiers, valid JSON examples and balanced Markdown code fences; independent arithmetic checks cover the worked fee, marks, GPA and attendance examples. A consistency review checks all four institution categories, administrator boundaries, lifecycle terminology, applicant/case access and the distinction between proposals and evidence.

**Checked on 12 October 2026:** 17 Markdown files, 85 internal file links, 49 screen IDs, 35 acceptance-scenario IDs, 13 build stages, 14 requirement families, 80 tables and 6 JSON examples. The document checks found no missing file references, undefined catalog IDs, inconsistent table widths or invalid JSON examples. Worked arithmetic and the eight declared color-contrast pairs were independently recalculated. All 35 application acceptance scenarios remain **Not run**.

These are **document checks only**. They do not establish application security, WCAG conformance, financial correctness in code, successful external integrations, mobile background calling, legal compliance, recovery time or measured capacity. Those require the evidence described in 10–12. The research baseline links primary sources; changing legal/provider/version facts require revalidation when implementation or launch depends on them.

## 7. Recommended message for the next session

> Review the attached Eduma specification pack and follow prompt.md in review mode. Preserve the confirmed requirements for all four institution categories. Identify only material decisions needed next and prepare a concrete review of representative screens using my logo. Do not generate application code yet.

After the documents and visual direction are reviewed, use the implementation message at the end of [prompt.md](prompt.md). Build connected, verified stages and keep progress against 12/13; a scaffold or dashboard alone is not the requested enterprise ERP.
