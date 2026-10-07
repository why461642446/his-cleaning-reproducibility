"""Configuration-driven reproduction of the restricted fairness-baseline arm.

It consumes a permitted synthetic benchmark outside the package and writes all
new outputs under a user-chosen output root. No MIMIC data are read or needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


SEEDS = [42, 142, 242, 342, 442]
RATE = 20


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(command: list[str], env: dict[str, str]) -> None:
    log_dir = Path(env["HIS_BASELINE_LOG_DIR"])
    log_dir.mkdir(parents=True, exist_ok=True)
    progress = json.loads(Path(env["HIS_BASELINE_PROGRESS_PATH"]).read_text(encoding="utf-8"))
    log_path = log_dir / f"{progress['stage']}.log"
    print("RUN", " ".join(command), "->", log_path)
    with log_path.open("ab") as log:
        completed = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--skip-frozen-v3", action="store_true", help="Use only if the five rate-20 V3 action logs already exist.")
    parser.add_argument("--resume", action="store_true", help="Continue a failed run in an existing output directory; records are retained for diagnosis.")
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    required = {"benchmark_parent", "baseline_output_root"}
    missing = required - set(cfg)
    if missing:
        raise ValueError(f"Missing config keys: {sorted(missing)}")
    benchmark_parent = Path(cfg["benchmark_parent"]).resolve()
    benchmark_root = benchmark_parent / "HIS_Synthetic_Dataset_V1_3_REALITY_CALIBRATED"
    output_root = Path(cfg["baseline_output_root"]).resolve()
    if not (benchmark_root / "phase3_final_test").is_dir():
        raise FileNotFoundError("Expected permitted synthetic phase3_final_test inputs were not found.")
    if output_root.exists() and any(output_root.iterdir()) and not args.resume:
        raise FileExistsError("baseline_output_root must be new or empty to preserve an auditable run.")
    output_root.mkdir(parents=True, exist_ok=True)

    package = Path(__file__).resolve().parents[2]
    wrapper = package / "release_wrapper" / "run_frozen_v3_from_config.py"
    scripts = Path(__file__).resolve().parent
    env = os.environ.copy()
    env["HIS_BENCHMARK_ROOT"] = str(benchmark_root)
    env["HIS_BASELINE_OUTPUT_ROOT"] = str(output_root)
    progress_path = output_root / "fair_baseline_progress.json"
    env["HIS_BASELINE_LOG_DIR"] = str(output_root / "logs")
    env["HIS_BASELINE_PROGRESS_PATH"] = str(progress_path)

    def set_progress(stage: str) -> None:
        progress_path.write_text(json.dumps({"stage": stage, "seeds": SEEDS, "rate": RATE}, indent=2), encoding="utf-8")

    if not args.skip_frozen_v3:
        set_progress("frozen_v3")
        with tempfile.TemporaryDirectory(prefix="fair_baseline_configs_") as tmp:
            for seed in SEEDS:
                one = Path(tmp) / f"frozen_v3_seed_{seed}.json"
                one.write_text(json.dumps({"benchmark_parent": str(benchmark_parent), "seed": seed, "rate": RATE}), encoding="utf-8")
                run([sys.executable, str(wrapper), "--config", str(one)], env)

    set_progress("raha_detection")
    for seed in SEEDS:
        run([sys.executable, str(scripts / "run_raha_diagnosis_detection_pilot.py"), "--seed", str(seed)], env)
    set_progress("v3_same_sample_scoring")
    run([sys.executable, str(scripts / "score_v3_on_raha_pilot_samples.py")], env)
    set_progress("direct_lookup")
    run([sys.executable, str(scripts / "run_direct_code_lookup_baseline.py")], env)
    set_progress("baran_repair")
    for seed in SEEDS:
        run([sys.executable, str(scripts / "run_baran_repair_preflight.py"), "--seed", str(seed)], env)
    set_progress("baran_aggregation")
    run([sys.executable, str(scripts / "aggregate_baran_repair_preflight.py")], env)
    set_progress("sensitivity_policies")
    run([sys.executable, str(scripts / "run_design_sensitivity_baselines.py")], env)

    results = [
        output_root / "v3_on_raha_pilot_samples_aggregate.csv",
        output_root / "direct_code_lookup_baseline_aggregate.csv",
        output_root / "baran_repair_preflight_aggregate_v1" / "baran_repair_aggregate.csv",
        output_root / "design_sensitivity_baselines_v1" / "aggregate.csv",
    ]
    missing_results = [str(p) for p in results if not p.is_file()]
    if missing_results:
        raise RuntimeError(f"Expected result files missing: {missing_results}")
    manifest = {
        "benchmark_root": str(benchmark_root),
        "output_root": str(output_root),
        "seeds": SEEDS,
        "rate": RATE,
        "frozen_v3_executed": not args.skip_frozen_v3,
        "result_sha256": {str(p.relative_to(output_root)): sha256(p) for p in results},
    }
    (output_root / "fair_baseline_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    set_progress("complete")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
