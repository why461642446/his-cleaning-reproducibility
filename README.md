# HIS Cleaning reproducibility release candidate

This is the public code package for the frozen FULL_FRAMEWORK_V3 study. It contains code, non-patient-level aggregate results, small audit evidence, and SHA-256 inventories. It contains no MIMIC-IV data, no patient-level records, no credentials, and no raw synthetic benchmark tables.

The permitted synthetic benchmark tables are distributed separately as a
versioned Zenodo dataset. Add its DOI here before the first public release:
`ZENODO_DATASET_DOI_TO_BE_ADDED`.

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

## Release limitations

Before public release, complete a clean-machine smoke test, verify the public
manifest, replace all DOI/URL placeholders, create a tagged GitHub release,
and archive the software release through Zenodo. The synthetic dataset should
be deposited as a separate Zenodo dataset record.

## Licensing

Software in this repository is released under the MIT License. The separately
deposited synthetic benchmark is intended for CC BY 4.0 after upstream-license
confirmation. MIMIC-IV remains governed solely by its applicable PhysioNet
access and data-use terms and is not redistributed here.
