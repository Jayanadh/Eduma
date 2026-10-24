# Eduma slice 8 — fees, payments and reconciliation (BUILD-08)

**Date:** 24 October 2026 · **Status:** from the spec pack, fast mode. **Source:** 03 WF-FIN §9; 08 §6 fee subledger
(entities, posting table, balance formulas); 05 API §4.4 (invoice balance, refunds); EX-01; TST-015, TST-016, TST-026;
BUILD-08. D-11 (accounting engine) and D-12 (payment provider) are open: Eduma keeps a balanced fee subledger with an
export boundary, and the only online provider is a clearly labelled **test-mode sandbox** with signed webhooks — an
institution without a configured provider gets 409 `integration_not_configured`, never a fake success.

## Decisions

| ID | Decision |
|---|---|
| S8-01 | **Fee heads** and **fee plans** (draft → published, immutable; a change is a revision): lines of head, amount and due date. Invoices issued from a plan record its revision. Exact decimals, INR. |
| S8-02 | **Student accounts** (one per student and currency) hold **invoices** (numbered, issued lines immutable). Balance per invoice: net charges = lines − posted credit notes; net allocated = allocations − reversals; outstanding = net charges − net allocated; 0 ≤ net allocated ≤ net charges. |
| S8-03 | **Credit notes** (concession or cancellation) are requested with a reason and approved by someone else (`fees.approve`); posting one that takes charges below what is allocated moves the excess back to unapplied funds in the same transaction. |
| S8-04 | **Payments**: office collections (cash, cheque, bank transfer) are recorded by `fees.collect` as received; online payments start `pending` and only a verified provider event makes them `succeeded`. A receipt (numbered atomically, never reused) is issued once per succeeded payment. Money is allocated to chosen invoices (default: oldest due first) up to their outstanding; the rest stays as visible unapplied credit. |
| S8-05 | **Refunds**: requested with an amount and reason against a payment (capacity reserved under lock: requested + approved + succeeded ≤ the payment), approved by someone else, then completed on confirmation (office) or a provider event. Completion reverses allocations (newest first) and posts the cash out; a failed refund releases its reservation. A refund never reduces the charge. |
| S8-06 | **Journals**: every financial step posts a balanced journal (≥ 2 lines, one positive side each, debits = credits) under a unique posting key, append-only; accounts per the pack's posting table (receivable, fee income, concessions, provider clearing/cash, unapplied funds, bank, provider fees). A trial balance and a CSV journal export are the accounting boundary. |
| S8-07 | **Provider events** are stored and de-duplicated by provider and event id before any effect; signatures are verified (HMAC-SHA256 of the body with the institution's webhook secret); amount, currency and merchant must match the order, else a **reconciliation case** quarantines it. Out-of-order events never undo a terminal state. |
| S8-08 | **Settlements** (provider batch: gross, fee, net, bank reference, payments) move clearing to bank and record fees; a mismatch with the payments opens a reconciliation case. |
| S8-09 | **Who sees what**: staff with `fees.read`; a student their own statement; a guardian a child's when the record is shared. Online pay shows "confirmation pending" until the provider confirms. |
| S8-10 | New app `fees`; module `fees` (needs students) available; permissions `fees.read`, `fees.manage`, `fees.collect`, `fees.approve`, `fees.reconcile`; Accountant gets read/manage/collect/reconcile, Principal read/approve. |

## Tests

TST-015 / EX-01 (3,000 → 4,000 after a 1,000 refund; ledger balances; settlement separate), TST-016 (duplicate and
out-of-order events → one posting; invalid signature rejected; amount mismatch quarantined), TST-026 (unconfigured
provider is honest), approval separation, refund capacity, credit note below allocation, overpayment as unapplied,
plan revision kept on issued invoices, family/student visibility, isolation.
