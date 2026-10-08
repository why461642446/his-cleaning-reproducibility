"""Evaluate an existing seed-42/rate-05 V3 output with manuscript scoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    base = Path(cfg["benchmark_parent"]).resolve()
    root = base / "HIS_Synthetic_Dataset_V1_3_REALITY_CALIBRATED"
    condition = root / "phase3_final_test" / "seed_42" / "corruption_05"
    cleaned_run = root / "phase4_results" / "final_test" / "seed_42" / "corruption_05" / "FULL_FRAMEWORK_V3"
    package = Path(__file__).resolve().parents[1]
    evaluator = package / "evaluation" / "evaluate_his_v1_3_phase4a6_final_v3_serial_attribution_fixed.py"

    required = [
        condition / "ground_truth",
        condition / "evaluation_reference" / "negative_state_sample.csv",
        cleaned_run / "cleaned",
        cleaned_run / "action_log.csv",
        evaluator,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Required paths are missing:\n" + "\n".join(missing))
    if args.output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {args.output_dir}")

    command = [
        sys.executable, str(evaluator),
        "--gt-dir", str(condition / "ground_truth"),
        "--cleaned-dir", str(cleaned_run / "cleaned"),
        "--action-log", str(cleaned_run / "action_log.csv"),
        "--negative-sample", str(condition / "evaluation_reference" / "negative_state_sample.csv"),
        "--output-dir", str(args.output_dir.resolve()),
        "--method-name", "FULL_FRAMEWORK_V3",
    ]
    completed = subprocess.run(command)
    if completed.returncode:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
