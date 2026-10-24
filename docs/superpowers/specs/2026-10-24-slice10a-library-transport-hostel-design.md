# Eduma slice 10a — library, transport and hostel (BUILD-10, part 1)

**Date:** 24 October 2026 · **Status:** from the spec pack, fast mode. **Source:** 03 WF-OPS §11 (library, transport,
hostel); TST-027, TST-028; BUILD-10 ("each selected module needs its own end-to-end demonstration and error/permission
tests"). Not selected here: GPS tracking (no authorised adapter), the mess (meal plans), hostel deposits.

## Decisions

| ID | Decision |
|---|---|
| S10A-01 | **Library**: titles (title, author, ISBN, subject) and copies (accession number; available / issued / reserved / lost / damaged / withdrawn), managed by `library.manage` (new role Librarian). |
| S10A-02 | **Loans**: the copy is locked while issuing, so two people can't take the last copy (one active loan per copy, enforced by the database too); borrowers are active students or staff, within their limit (students 3, staff 5) and with nothing overdue; due in 14 days; up to 2 renewals, not when someone is waiting. Returning twice changes nothing the second time. |
| S10A-03 | **Reservations** queue per title; a returned copy is held for the first in the queue for 3 days. |
| S10A-04 | **Fines** (overdue days × ₹2, or the replacement cost for a lost copy) are recorded on the loan; when Fees is on and the borrower is a student, the fine is an invoice on their fee account (approved finance posting); a waiver keeps the fine and records who waived it and why. Lost is its own state, not a return. |
| S10A-05 | **Transport**: vehicles (capacity), routes with ordered stops, rider assignments (student, route, stop, from–to dates); a route's riders on any overlapping dates can't exceed its vehicle's capacity; a student has one assignment at a time. |
| S10A-06 | **Trips** (route, date, direction, vehicle, driver, attendant): planned → dispatched → in_progress → completed / canceled. The trip's driver or attendant (or `transport.manage`) records boarding once per rider (duplicates refused) and drop-off, which needs one of the student's **approved pickup** people (guardians with an active link, or named people added by `transport.manage`). |
| S10A-07 | **Visibility**: a guardian sees their child's route, stop and today's trip status (no other riders, no vehicle location — tracking isn't selected); a student sees their own. |
| S10A-08 | **Hostel**: hostels, rooms, beds; allocations requested → approved → allocated → checked out, never two active allocations of a bed or of a student over overlapping dates; transfer ends one and starts the other atomically; occupancy per hostel. Managed by `hostel.manage` (new role Warden). |
| S10A-09 | **Out-passes**: a resident student asks (from–to, reason); the warden approves or rejects; return is recorded. |
| S10A-10 | App `campus`; modules `library`, `transport`, `hostel` marked available (they still need to be in an institution's plan and switched on). |

## Tests

TST-027 (two threads, last copy → one loan; return twice; fine waiver keeps history; lost distinct), TST-028 (route
capacity over overlapping dates; bed overlap; one allocation per student; approved pickup only; duplicate boarding),
borrower limits and overdue block, renewal blocked by a reservation, out-pass flow, guardian sees own child only,
permissions, module gates, isolation.
