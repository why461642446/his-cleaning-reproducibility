# K1 Frozen Coverage and Transformation Audit v1

## Purpose and scope

This read-only audit documents the boundary between the frozen `FULL_FRAMEWORK_V3` rules, the corruption transformations, and the reported evaluation endpoints. It does not modify any cleaner rule, threshold, dictionary, corruption event, ground-truth record, or reported result.

The purpose is disclosure, not retrospective relabeling. An event remains a false negative when the predeclared endpoint was not met, including the two unsupported internal HELDOUT variants.

## Evidence base

- Frozen internal HELDOUT: six variants, five corruption rates, five seeds, 25 conditions.
- External MIMIC-IV Demo HELDOUT: 15 applicable variants, five rates, 75 conditions, 626,723 injected events.
- OOD diagnosis-alias stress test: 19 clinically reviewed aliases absent from the diagnosis-name dictionary, 1,900 injected events.
- Retained frozen V3 code, condition manifests, event truth, action logs, evaluator outputs, and the independent 75-condition reproduction record.

### Retained-source identity record

| Artifact | SHA-256 |
|---|---|
| Internal HELDOUT generator `generate_phase3f4_heldout_final_test_all_conditions_v1_3.py` | `1278379E0946D25B1BD093508494AA5E982F5921D722F6FD52F0B4C042E73F43` |
| Internal evaluator `evaluate_his_v1_3_phase4a6_final_v3_fixed.py` | `48A785DE8D17FE1BF6419AB44476ED4B3BCD34E0FE44E4128C691D810B133874` |
| Frozen MIMIC adapter `run_frozen_v3_mimic_path_adapter_v1_3_medlex_na.py` | `D278C793A38AD79660A4600D30B00A00F15D150E967517672A84AC9266ADB43F` |
| MIMIC materializer `materialize_mimic_debug_condition.py` | `F4394688B4C2F4812D86DA6145529A20E4347888D61EDB690AFDB7E428034347` |
| MIMIC evaluator `evaluate_mimic_injected_condition.py` | `8646BBE7FE59DC1AC0923C1378DA131F574F531EF93B818FAA78C1F99B81E5E2` |
| OOD alias manifest `OOD_LEX_ALIAS_01_frozen_manifest.csv` | `00FF39C27407A91FF61A91A741471C642F458788BACAC5836963074D613CBA5F` |

These hashes identify the retained local evidence used for this audit. They are not a substitute for a public, path-independent archival release.

## A. Internal HELDOUT coverage map

| Variant | Corruption operation | Frozen evidence available to V3 | Predeclared endpoint | Coverage status | Observed result | Interpretation |
|---|---|---|---|---|---|---|
| `CORR_LEX_02` | Diagnosis-name single-character perturbation | Diagnosis code-to-canonical-name mapping and lexical normalization | `CORRECT` | Covered | 1.0000 recall | Tests code-supported canonical restoration for a controlled character-edit family. |
| `CORR_UNIT_02` | Numeric-unit scale inconsistency through unit relabeling or a numeric scaling operation | Frozen laboratory unit map and numeric/unit consistency rules | Detection or standardization, as recorded by the evaluator | Covered | >0.9999 recall | Tests the specific internal numeric-unit configurations; it is not evidence for arbitrary real-world unit recovery. |
| `CORR_TIME_02` | Laboratory timestamp moved outside its linked encounter window | Visit linkage and temporal window rule | `FLAG_ONLY` | Covered | 1.0000 recall | Tests an explicitly rule-violating out-of-window timestamp. |
| `CORR_REL_03` | Medication patient identifier conflicts with linked visit | Medication-to-visit dependency | `CORRECT` | Covered | 1.0000 recall | Tests one specified cross-table dependency. |
| `CORR_MISS_02` | Medication dose value and dose unit jointly blanked | No unique deterministic replacement rule | Recovery endpoint retained in denominator | Intentionally unsupported | 0.0000 recall | The framework does not infer a unique dose/unit pair. This is a limitation, not an unobservable event removed from scoring. |
| `CORR_DUP_02` | Laboratory near-duplicate with a small result-value difference | Exact-duplicate key only; no near-duplicate similarity rule | Duplicate recovery endpoint retained in denominator | Unsupported | 0.0000 recall | M7 supports exact duplicates, not this near-duplicate transformation. |

The six variants had approximately equal event budgets. Consequently, the aggregate internal recall of about 0.6667 is a weighted property of this frozen mixture: four covered variants were recovered/detected and two unsupported variants were not. It must not be interpreted as a mechanism-independent estimate of HIS cleaning recall.

## B. Boundary test outside the internal HELDOUT representation family

| Condition | Difference from internal HELDOUT | Dictionary membership | Available evidence | Events | Result | What the result does and does not show |
|---|---|---|---|---:|---|---|
| `OOD_LEX_ALIAS_01` | Replaces a diagnosis display name with a pre-specified clinically equivalent alias, rather than a controlled one-character perturbation | All 19 aliases had no exact normalized match in the diagnosis-name dictionary | Diagnosis code remained available | 1,900 | 1,900 recovered | V3 can restore these aliases when paired diagnosis-code evidence identifies the canonical title. It does not demonstrate name-only alias generalization. |
| `OOD_LEX_ALIAS_CODE_MASKED_01` | Same aliases, but the paired diagnosis code is unavailable to the cleaner | All 19 aliases outside dictionary | No code-to-name evidence | 1,900 | 0 recovered | Confirms that the successful OOD alias result depends on the paired code, rather than an undisclosed alias dictionary or general fuzzy-name resolver. |

This is a useful held-out representation test, but it is not an independent error generator and does not establish broad out-of-distribution robustness. The planned multi-character lexical and timestamp-representation conditions remain unexecuted and must not be claimed as completed.

## C. MIMIC-IV Demo taxonomy and comparability boundary

All 15 externally tested MIMIC identifiers belong to the original synthetic taxonomy. Six identifiers (`MISS_02`, `LEX_02`, `UNIT_02`, `TIME_02`, `DUP_02`, `REL_03`) were also present in the internal HELDOUT panel; the remaining nine derive from broader development mechanism families. Thus, MIMIC is an external-data and external-schema stress test, not an independent test of wholly new corruption families.

| Comparison class | Variants | Permitted interpretation |
|---|---|---|
| Direct or close correction comparison | `LEX_02`, `REL_03` | Same broad operation and correction objective; schema and eligibility still differ. |
| Detection-oriented partial comparison | `TIME_02`, `MISS_02`, `DUP_02` | Similar broad corruption but different action semantics or endpoint; do not compare recovery rates as a common task. |
| Not directly comparable despite shared name | `UNIT_02` | Internal operation may relabel a unit or scale a value; MIMIC retains numeric value and changes the paired unit label, with flag-or-abstain scoring only. |
| External-only or development-family variants | All other MIMIC variants | Report only as MIMIC mechanism-specific results, not as held-out internal generalization. |

## D. What this audit resolves and what remains open

### Resolved by retained evidence

1. The principal internal result has a documented mechanism mixture and known coverage boundary.
2. Unsupported missingness and near-duplicate variants remain visible in strict recall; they were not removed through observability relabeling.
3. The OOD alias result has a falsification control: it disappears when code evidence is masked.
4. External MIMIC results are no longer presented as direct numerical replicas of same-named synthetic variants where operations or endpoints differ.

### Still open before claiming K1 fully resolved

1. The internal generator, taxonomy, and frozen rule set were designed within the same research program. This audit documents the risk but cannot independently eliminate it.
2. A complete rule/dictionary coverage inventory needs stable source-level references and hashes for every internal transformation operator.
3. At least one additional predeclared held-out operator should be executed without altering V3. The strongest next candidate is `OOD_LEX_MULTI_01` (multiple or keyboard-adjacent character edits) with correction-only scoring. A timestamp-representation test may be added separately, but it should assess parsing preservation rather than call equivalent timestamps erroneous.
4. A publicly released, path-independent materializer/evaluator package is still required for independent reproduction.

## Reporting restriction for the manuscript

Use the phrase: “The internal HELDOUT panel evaluates a frozen mixture of covered and explicitly unsupported mechanisms. Its aggregate recall is mixture-dependent; mechanism-level and held-out representation results define the supported boundary.”

Do not use: “The held-out results establish general HIS error-detection recall,” “MIMIC validates all synthetic mechanisms,” or “OOD aliases demonstrate dictionary-free lexical generalization.”
