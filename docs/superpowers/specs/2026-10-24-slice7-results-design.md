# Eduma slice 7 — assessments, results and awards (BUILD-07)

**Date:** 24 October 2026 · **Status:** from the spec pack, fast mode. **Source:** 03 WF-EXM §8; 08 Assessment /
Component / Mark, ResultVersion / PublicationBatch, OutcomeMapping / AttainmentRun, Award / Transcript; EX-02, EX-03;
TST-012, TST-013, TST-014, TST-031; BUILD-07. D-01 open: schemes, grade bands and award rules are institution-entered
and typed; demo content is synthetic.

## Decisions

| ID | Decision |
|---|---|
| S7-01 | **Scheme** (draft → published → retired; a change is a new revision): components (name, maximum, weight, optional minimum %), overall pass %, grade bands (minimum %, grade, grade point), display decimals. Publishing checks weights total 100, at least one component, bands present. |
| S7-02 | **Assessment** for a section + subject or an offering in a term, pinned to a published scheme revision, with a roster snapshot taken when it is created (placed / registered students). |
| S7-03 | **Marks** per candidate and component: a score within 0…maximum, or `absent`, `exempt`, `withheld`; no row = missing. Never converted to zero. |
| S7-04 | **States** draft → submitted (evaluator: the assigned teacher or `assessment.manage`) → moderated (`results.moderate`, not the submitter; may return to draft with a reason) → published (`results.publish`). Publishing needs every mark present; it is one atomic batch; marks are frozen after. |
| S7-05 | **Calculation** (EX-02): total = Σ score ÷ maximum × weight, exact, rounded only for display at the scheme's decimals; an exempt component is left out and the rest scaled to 100; any absent → outcome `absent`, any withheld → `withheld` (no total); passed = total ≥ pass % and every component minimum met (a component failure fails the result); grade and grade point from the bands (failed → the lowest band). |
| S7-06 | **Result versions**: immutable; inputs (marks, scheme revision) hashed and kept; a correction is a new revision superseding the old, which stays readable. |
| S7-07 | Publishing an **offering's** assessment writes each registered student's attempt outcome (passed/failed with grade point, absent, withheld), so degree progress and SGPA follow published results. |
| S7-08 | **Revaluation**: a case with a reason and corrected marks, raised by `results.moderate` or `results.publish`, approved by someone else with `results.publish` → new result revision (and attempt). |
| S7-09 | **Promotion decisions** for school students per year (promote / repeat / hold, with reason) by `results.publish`. |
| S7-10 | **Issued documents** — report card (school, per term: subjects, grades, attendance, promotion), transcript (college: attempts, SGPA/CGPA), award (qualification once accepted credits meet the regulation, or by an authorised exception with reason) — each a numbered snapshot with a content hash and a verification token; reissue supersedes; revoke with a reason. A university issues awards to affiliated students from its current accepted records (S5E). |
| S7-11 | **Public verification** shows only institution, document type, number, issue date, the holder's initials and status (current / superseded / revoked). |
| S7-12 | **Course outcomes** (engineering): outcomes per course, components mapped to outcomes, an attainment run per published assessment (share of candidates at or above a threshold on the mapped components), stored with method and inputs. Not a claim of accreditation. |
| S7-13 | New app `results`; modules `exams` (needs academics) and `report_cards` (needs exams) available, `outcomes` available; permissions `assessment.manage`, `results.moderate`, `results.publish` (Examination Officer all three; Registrar `assessment.manage` and `results.publish`). |

## Tests

TST-012 (77/100; component minimum fails a 77; absent/withheld/missing not zero; exempt rescales), TST-013 via
attempts, TST-014 (maker can't publish; published mark edit refused; revaluation → approved revision with the old one
reproducible), moderation separation, publish blocked by missing marks, report card / transcript / award issue,
reissue supersedes, public verification minimal, attainment, isolation.
