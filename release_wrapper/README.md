# Configuration wrapper

The source under `../frozen_v3/` is an exact historical artifact. Do not edit
it. Copy `config.example.json` outside the package, set the parent directory
that contains `HIS_Synthetic_Dataset_V1_3_REALITY_CALIBRATED`, then run:

```text
python run_frozen_v3_from_config.py --config <your-config.json>
```

The wrapper verifies the recorded byte-level SHA-256 value, creates a temporary configured
copy, and changes only `BASE`. It does not alter thresholds, dictionaries,
algorithm code, seed/rate validity constraints, or the retained frozen source.

The repository `.gitattributes` marks the historical cleaner as `-text`, so Git
must preserve its CRLF bytes and the recorded SHA-256 across checkout. The
clean-machine acceptance evidence is documented separately in the release
evidence and does not imply that every output file is byte-identical.

To evaluate an already generated seed-42/rate-05 output with the corrected
manuscript scoring, choose a new output directory and run:

```text
python evaluate_existing_seed42_rate05.py --config <your-config.json> --output-dir <new-evaluation-directory>
```
