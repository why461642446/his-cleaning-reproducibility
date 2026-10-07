# K2 Synthetic and MIMIC-IV Demo Comparability Crosswalk v1

## Decision

The MIMIC-IV Demo arm should be described as an **external-schema, external-data substrate stress test with injected and known truth**, not as evidence that the synthetic benchmark reproduces the prevalence, clinical case mix, or natural error distribution of real hospitals.

The comparison is useful for defining transfer boundaries. It does not validate population realism.

## Table-level mapping

| Synthetic table | MIMIC-IV Demo mapped table | Common analytical unit | Comparable properties | Material non-comparability | Permitted manuscript use |
|---|---|---|---|---|---|
| Patient | Patient | One patient | Sex and age availability; patient-level record counts | Synthetic birth date, blood type, insurance type, and home region have no equivalent mapped fields; MIMIC age is de-identified and anchored | Describe cohort structure and available demographic fields only. |
| Visit | Visit/admission | One hospital encounter | Encounter linkage, admission/discharge ordering, visit-level missingness | Synthetic includes outpatient-style short encounters and department; MIMIC Demo is admission-centric with ED and discharge attributes | Compare temporal-field availability and encounter density; do not compare utilization prevalence. |
| Diagnosis | Diagnosis | One diagnosis assigned to an encounter | Code, title, ICD version, diagnosis-to-visit linkage | MIMIC diagnoses are discharge coding records; synthetic diagnosis timing and department are not directly comparable | Support code-title dictionary and linkage stress tests only. |
| Laboratory | Laboratory | One laboratory event | Result value, unit, reference interval, abnormal flag, timestamp, and optional encounter linkage | MIMIC has structural non-admission-linked events and text/numeric result separation; item vocabularies and unit systems differ | Compare missingness and linkage patterns; do not pool unit distributions without a common concept vocabulary. |
| Medication | Medication/prescription | One prescription row | Drug name, route, dose fields, start/stop time, patient/visit linkage | MIMIC prescription rows are order/prescription information rather than direct administration events; `pharmacy_id` is not a row key | Support temporal and relationship stress tests with native source anomalies excluded from denominators. |
| Examination | None | One examination event | None | No direct mapped MIMIC Demo counterpart in this protocol | Exclude from all synthetic--MIMIC comparison claims. |

## Quantitative interpretation of the completed structural audit

| Feature | Synthetic reference | MIMIC-IV Demo | Correct interpretation |
|---|---:|---:|---|
| Patients | 20,000 | 100 | Different scale; counts are not prevalence estimates. |
| Visits per patient, median | 4 | 1 | Synthetic benchmark has more encounters per patient in this reference slice. |
| Diagnoses per visit, median | 2 | 14 | Diagnosis-record density differs substantially. |
| Laboratory rows per linked visit, median | 7 | 178 | MIMIC laboratory documentation density is much higher. |
| Medication rows per linked visit, median | 3 | 53 | MIMIC prescription documentation density is much higher. |
| Visit duration, median hours | 2.12 | 116.47 | Encounter definitions and care settings differ; duration distributions must not be treated as matched. |
| Laboratory records lacking a visit link | 0.0000% | 26.3815% | MIMIC's hospital-wide event model contains legitimate non-admission-linked laboratories. |
| Laboratory unit missingness | 8.4471% | 15.3555% | Missingness differs and is not a natural-error prevalence comparison. |

## Required reporting boundaries

1. The synthetic benchmark evaluates known injected events against a clean reference and is a controlled **verification** setting.
2. The MIMIC Demo manual audit evaluates whether mapping and selected native source structures were interpreted safely. It is not an adjudicated natural-error gold standard.
3. The MIMIC Demo injected-event arm evaluates transfer of frozen rules onto a real-data schema. It does not estimate the natural frequency of errors in MIMIC-IV or any hospital.
4. Native MIMIC structural missingness, non-admission linkage, duplicated pharmacy identifiers, source prescription time inversions, and abnormal-but-plausible clinical values must be excluded from injected-event denominators.
5. No paper claim may use this comparison to say that the synthetic data are representative of all hospitals, that the reported 5--40% corruption rates are realistic prevalence rates, or that MIMIC results establish clinical effectiveness.

## Manuscript-ready paragraph for the methods section

> The external arm used MIMIC-IV Demo as a real-data substrate after schema mapping, not as a natural-error gold standard. The synthetic reference and mapped MIMIC tables differ materially in cohort scale, encounter definition, diagnosis density, laboratory and prescription documentation density, visit-link completeness, and unit representation. We therefore used the comparison to define which frozen rules could be evaluated after mapping and to identify native source characteristics that must not be relabeled as injected errors. The external experiments retained event-level truth only for predeclared artificial perturbations; they do not estimate the prevalence of natural MIMIC data errors or establish that the synthetic corruption mixture is representative of hospital practice.

## Manuscript-ready limitation sentence

> MIMIC-IV Demo provides a heterogeneous real-EHR schema and a useful transfer substrate, but its 100-patient sample, admission-centered design, de-identification conventions, and non-equivalent local concept systems do not validate the population realism of the synthetic generator.

## Remaining K2 work

The structural comparison and crosswalk are complete. Two tasks remain before K2 can be considered substantially addressed:

1. Add a literature-grounded error-pattern table using only defensible, source-specific claims; it must not convert heterogeneous published quality findings into a false common prevalence scale.
2. Add the crosswalk and structural comparison to the manuscript, and cite the MIMIC-IV source and EHR data-quality frameworks appropriately.
