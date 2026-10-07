# Frozen HELDOUT Generator Specification and Integrity Audit v1

## Scope

This audit describes the frozen final-test generator used for five held-out seeds (42, 142, 242, 342, and 442) and five corruption rates (5%, 10%, 20%, 30%, and 40%). The panel contains 25 conditions and 16,805,125 event-level injected corruptions in total. Every condition passed all seven retained generator validation checks.

## Frozen held-out mechanism specification

| Variant | Target table and field(s) | Eligibility | Transformation | Predeclared endpoint | Coverage status |
|---|---|---|---|---|---|
| `CORR_MISS_02` | Medication: `dose_value`, `dose_unit` | Both values present | Jointly set both fields to missing | `CORRECT` | Unsupported for unique automatic recovery; retained in FN denominator |
| `CORR_LEX_02` | Diagnosis: `diagnosis_name` | Non-missing title | One-character typo via frozen operator | `CORRECT` | Covered, code-supported canonical restoration |
| `CORR_UNIT_02` | Laboratory: `result_value`, `unit` | Numeric value and non-missing unit | Frozen numeric-unit scale mismatch; value and/or unit may change | `CORRECT` | Covered only for frozen numeric-unit configurations |
| `CORR_TIME_02` | Laboratory: timestamp | Linked visit with non-missing admission and discharge | Move timestamp 1--72 h before admission or after discharge, selected with equal branch probability | `FLAG_ONLY` | Covered, explicit visit-window violation |
| `CORR_DUP_02` | Laboratory row | Numeric result available | Add a second row with a new technical ID and result increased by 1% of absolute value, or 0.001 when original value is zero | `REMOVE_DUPLICATE` | Unsupported near-duplicate recovery; retained in FN denominator |
| `CORR_REL_03` | Medication: `patient_id` | Visit identifier links to a patient | Replace patient ID with a sampled patient different from both linked-visit patient and original value | `CORRECT` | Covered, explicit cross-table dependency violation |

Each rate allocates approximately one sixth of its event budget to each variant. This equal allocation is a deliberate generator design feature and explains why aggregate recall is mixture-dependent.

## Ground-truth and collision safeguards

For each condition, the generator records event-level before/after values, target table, primary and secondary record identifiers where applicable, expected behavior, seed, rate, and variant ID. It also emits state-level ground truth for scalar/row evaluation.

The retained validation suite verifies:

1. event count equals the requested condition budget;
2. exactly six held-out variants are present;
3. no development-only variant appears in the HELDOUT panel;
4. corruption event identifiers are unique;
5. state-level ground truth is present;
6. fields designated ground-truth-sensitive are hidden from the cleaning pipeline; and
7. added near-duplicate laboratory rows equal the `CORR_DUP_02` budget, so inserted records are accounted for rather than silently colliding with source rows.

All seven checks passed in all 25 frozen conditions. This confirms internal bookkeeping and event-truth integrity. It does not prove that the chosen mechanism mixture represents natural hospital-error prevalence.

## Required manuscript interpretation

> The final test used five unseen random seeds and a fixed six-variant error mixture. Every generated condition passed event-count, variant-membership, event-identifier, ground-truth, exposure, and near-duplicate accounting checks. These checks establish experimental integrity, whereas the mixture itself remains a designed evaluation distribution rather than an estimate of natural EHR error prevalence.

## Remaining limitation

The generator and cleaning rules remain products of the same research program. The OOD alias stress test and code-masked control provide a partial boundary check, but independent public reproduction still requires the staging package to be converted into a path-independent release and at least one further predeclared transformation family to be evaluated without V3 retuning.
