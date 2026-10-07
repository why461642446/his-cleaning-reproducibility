# Configuration-wrapper smoke-test result

Date: 2026-09-25

## Test design

An isolated benchmark root was created separately from the accepted results.
Its `canonical_reference` and `phase3_final_test` inputs were read-only
junctions to the retained synthetic data. The test selected seed 42 at 5%
corruption, and all outputs were written under the isolated root.

The wrapper first verified the byte-preserved frozen V3 source SHA-256, then
modified only the `BASE` assignment in a temporary source copy. The provenance
source under `frozen_v3/` was not modified.

## Wrapper correction found by the test

The initial wrapper failed before execution because its text anchor represented
two backslashes while the retained source contains one. The anchor was corrected
to match exactly once. This was a wrapper path-matching defect only; it did not
alter the frozen cleaner, thresholds, inputs, or accepted results.

## Result

The wrapper exited successfully and produced all expected artifacts:

- six cleaned CSV tables;
- `action_log.csv`;
- `module_summary.csv`.

The isolated outputs were compared with the accepted seed-42 / 5% outputs by
SHA-256. All eight corresponding files were byte-identical:

| Artifact group | Files compared | Result |
|---|---:|---|
| Cleaned tables | 6 | all byte-identical |
| Action log | 1 | byte-identical |
| Module summary | 1 | byte-identical |
| Total | 8 | 8/8 identical |

The common module-action totals were M1=97,957, M2=22,615, M3=0,
M4=35,389, M5=26,675, M6=26,674, and M7=1.

## Scope limitation

This is a path-configuration and result-replication test on the same computing
environment, with isolated output. It is not a clean-machine or cross-platform
reproduction claim. A fresh-environment test and a fully specified dependency
lockfile remain required before a public release can claim path-independent
reproducibility.
