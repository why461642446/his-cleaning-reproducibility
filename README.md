# HIS Cleaning reproducibility package

This is the public code package for the frozen FULL_FRAMEWORK_V3 study. It contains code, non-patient-level aggregate results, small audit evidence, and SHA-256 inventories. It contains no MIMIC-IV data, no patient-level records, no credentials, and no raw synthetic benchmark tables.

The permitted synthetic benchmark tables are distributed separately as a
versioned Zenodo dataset: [10.5281/zenodo.23209036](https://doi.org/10.5281/zenodo.23209036).

## What this package can reproduce

1. A synthetic-data smoke test of the frozen V3 cleaner through `release_wrapper/run_frozen_v3_from_config.py`.
2. Inspection of the retained generator, evaluator, OOD utilities, and MIMIC injection/adapter code.
3. A configuration-driven reconstruction of the restricted five-seed fairness-baseline arm through `baselines/scripts/run_fair_baselines_from_config.py`.

## What this package cannot by itself reproduce

It does not contain benchmark input tables. A reproducer must independently obtain or generate the permitted synthetic benchmark inputs, configure their parent path in `release_wrapper/config.example.json`, and use the documented seed/rate. MIMIC-IV analyses require independent approved access; MIMIC data must never be copied into this repository.

## Fair-baseline reconstruction

Copy `baselines/config.example.json` to a local untracked configuration file, set the permitted synthetic benchmark parent and a new empty output directory, then run:

```text
python baselines/scripts/run_fair_baselines_from_config.py --config baselines/local_config.json
```

The runner executes the five frozen V3 20-percent conditions, then the fixed Raha, Baran, direct-lookup, no-op, and always-flag procedures. It writes a result-hash manifest in the chosen output root.

## Clean-machine smoke test

On a different Windows computer, create a new virtual environment and install `requirements-public.txt`. Place the permitted synthetic benchmark parent directory outside this package. Copy `release_wrapper/config.example.json` to a local untracked configuration file, set `benchmark_parent`, then run:

```text
python release_wrapper/run_frozen_v3_from_config.py --config local_config.json
```

Record the Python version, operating system, command, elapsed time, output SHA-256 values, and any discrepancy in a new smoke-test report. The expected seed-42 / rate-5 module action totals and eight-file SHA-256 comparison procedure are documented in `SMOKE_TEST_RESULT_20260925.md`.

## Release status and limitations

The synthetic dataset is archived at Zenodo under DOI
`10.5281/zenodo.23209036`. A clean-machine smoke test and a tagged software
release remain separate release-engineering checks; they do not change the
reported experimental results. The restricted MIMIC-IV arm cannot be
reproduced from this public package alone and requires independently approved
PhysioNet access.

## Licensing

Software in this repository is released under the MIT License. The separately
deposited synthetic benchmark is released under CC BY 4.0. MIMIC-IV remains
governed solely by its applicable PhysioNet access and data-use terms and is
not redistributed here.
