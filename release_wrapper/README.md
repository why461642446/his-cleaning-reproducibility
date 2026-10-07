# Configuration wrapper

The source under `../frozen_v3/` is an exact historical artifact. Do not edit
it. Copy `config.example.json` outside the package, set the parent directory
that contains `HIS_Synthetic_Dataset_V1_3_REALITY_CALIBRATED`, then run:

```text
python run_frozen_v3_from_config.py --config <your-config.json>
```

The wrapper verifies the recorded SHA-256 value, creates a temporary configured
copy, and changes only `BASE`. It does not alter thresholds, dictionaries,
algorithm code, seed/rate validity constraints, or the retained frozen source.

This wrapper still needs a documented clean-machine smoke test and dependency
lockfile before public release.
