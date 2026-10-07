# Baseline reproducibility status

The package contains the exact baseline scripts and non-patient-level aggregate results used in the manuscript for no-op, always-flag, direct lookup, Raha 1.26, and Baran 1.26. `baselines/scripts/run_fair_baselines_from_config.py` is a configuration-driven runner that recreates the five deterministic samples from independently supplied permitted synthetic FINAL_TEST inputs, runs the five frozen V3 rate-20 conditions, then runs and hashes all baseline outputs.

No raw synthetic tables are included in this candidate package. A clean-machine user must supply permitted synthetic benchmark inputs outside the package. MIMIC-IV is neither required nor permitted for this baseline runner.
