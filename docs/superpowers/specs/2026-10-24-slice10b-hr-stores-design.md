# Eduma slice 10b — HR leave, payroll boundary, procurement, stock, assets and lab booking (BUILD-10, part 2)

**Date:** 24 October 2026 · **Status:** from the spec pack, fast mode. **Source:** 03 WF-OPS §11 (HR leave, payroll,
procurement, inventory/assets, lab booking); TST-029, TST-030; D-11 (payroll engine or adapter) open: Eduma prepares,
validates, approves and exports payroll inputs and results; the export is not proof of bank payment and statutory
deductions are institution-entered, not calculated by law.

## Decisions

| ID | Decision |
|---|---|
| S10B-01 | **Leave types** (code, name, days a year) set by `hr.manage`. A **leave request** (employee, type, dates, reason): draft → submitted → approved / rejected → canceled. Days are inclusive calendar days; balance = entitlement − approved days this year; no overlap with the employee's own submitted or approved leave; approval by `hr.leave_approve`, never by the employee themself; cancelling an approved request gives the days back once. |
| S10B-02 | **Staff attendance** per employee per day (present / absent / half day / on leave), recorded by `hr.manage`; an approved leave day shows as on leave. |
| S10B-03 | Every staff member with an employee record sees their own leave and balances; nobody else's without `hr.manage`. |
| S10B-04 | **Compensation** (monthly gross and named components, from a date) is visible and changeable only with `payroll.manage`; no other API or page shows it. |
| S10B-05 | **Payroll cycles** per month: prepared (lines from compensation, less leave-without-pay days pro rata) → validated → approved (by `payroll.approve`, not who prepared it) → exported (CSV, the adapter boundary). An exported cycle never changes; corrections are a later adjustment cycle. |
| S10B-06 | **Procurement rule** versions (published, immutable): up to the single-approval limit one approver, above it two different approvers (`procurement.approve`). A **requisition** records the rule revision in force when submitted and is decided by it even if the rule changes later. draft → submitted → approved → ordered → partially received / received; rejected. |
| S10B-07 | **Goods received** can't exceed what was ordered (zero tolerance); receiving adds stock. **Stock** moves (receive, issue, return, adjust) are atomic; stock never goes negative. |
| S10B-08 | **Assets** (tag, name, category, location, custodian): in use → maintenance → in use, or disposed (with reason and authority); custodian transfers and maintenance logged (`assets.manage`). |
| S10B-09 | **Lab booking**: any staff member books a bookable asset for a time; two bookings of one asset never overlap; an asset in maintenance or disposed can't be booked; `assets.manage` cancels. |
| S10B-10 | Apps `hr` and `stores`; modules `hr_payroll` and `assets` available; permissions `hr.manage`, `hr.leave_approve`, `payroll.manage`, `payroll.approve`, `procurement.manage`, `procurement.approve`, `assets.manage`; roles HR Officer, Payroll Officer, Store Keeper. |

## Tests

TST-029 (own leave only; self-approval refused; balance and overlap; cancel restores once; compensation hidden without
payroll.manage; payroll approval by another person; exported cycle frozen), TST-030 (no double booking; maintenance
blocks; a requisition over the limit needs two approvers and keeps the rule revision it was submitted under), receipt
tolerance, stock never negative, asset disposal, permissions, module gates, isolation.
