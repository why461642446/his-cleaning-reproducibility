# Non-overwriting clean-directory smoke-test protocol

## Purpose

Validate that the configuration wrapper can locate data through a user-provided
base path and invoke the byte-preserved frozen V3 source without editing it.
This smoke test is not a replacement for the accepted 25-condition HELDOUT
rerun, and must not write into an existing accepted-results directory.

## Preconditions

1. A permitted synthetic benchmark copy exists under a fresh parent directory.
2. The selected `seed`/`rate` output directory does not already exist in that
   copy.
3. Python 3.10.11, NumPy 2.2.6, and pandas 2.3.3 are installed, or any
   deviations are recorded.
4. No MIMIC-IV material is needed or used.

## Procedure

1. Copy `release_wrapper/config.example.json` to a location outside the package.
2. Set `benchmark_parent`, `seed`, and `rate` to the fresh synthetic copy.
3. Run `run_frozen_v3_from_config.py --config <config>`.
4. Confirm that outputs occur only beneath the fresh copy's
   `phase4_results/final_test/.../FULL_FRAMEWORK_V3/` path.
5. Record the wrapper console log, frozen source SHA-256, input/output paths,
   action-row total, and evaluator results in a dated smoke-test record.
6. Compare metrics only if the fresh copy is intentionally identical to a
   recorded condition; otherwise state that it is a path/configuration test,
   not a result replication.

## Pass criteria

- The byte-preserved source hash equals the value in the wrapper.
- The wrapper changes only the temporary `BASE` assignment.
- No existing acceptance directory is overwritten.
- The cleaner exits successfully and produces cleaned tables, `action_log.csv`,
  and `module_summary.csv` in the fresh target location.
