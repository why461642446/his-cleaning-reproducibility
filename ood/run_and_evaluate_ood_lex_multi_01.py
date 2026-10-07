"""Run and independently evaluate the frozen OOD_LEX_MULTI_01 condition."""

from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
def execute(command: list[str], label: str, log_path: Path) -> None:
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(f"\n--- {label} ---\n")
        stream.flush()
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed: exit={result.returncode}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--condition-dir", required=True, type=Path)
    args = parser.parse_args()
    benchmark_root = args.benchmark_root.resolve()
    condition = args.condition_dir.resolve()
    log = condition / "run.log"
    output = condition / "v3_output"
    evaluation = condition / "evaluation"
    if output.exists() or evaluation.exists():
        raise FileExistsError("Refusing to overwrite existing OOD output or evaluation.")
    execute([
        sys.executable, str(ROOT / "run_frozen_v3_isolated.py"),
        "--input-dir", str(condition / "operational_input"),
        "--canonical-dir", str(benchmark_root / "canonical_reference"),
        "--output-dir", str(output),
        "--run-label", "OOD_LEX_MULTI_01",
    ], "frozen_v3", log)
    execute([
        sys.executable, str(ROOT / "evaluate_v3_ood_isolated.py"),
        "--gt-dir", str(condition / "ground_truth"),
        "--cleaned-dir", str(output / "cleaned"),
        "--action-log", str(output / "action_log.csv"),
        "--negative-sample", str(condition / "evaluation_reference_negative_state_sample.csv"),
        "--output-dir", str(evaluation),
        # The frozen cleaner records this canonical method name in every action
        # log.  The condition identity is carried by the isolated directory and
        # protocol manifest, rather than changing evaluator identity metadata.
        "--method-name", "FULL_FRAMEWORK_V3",
        "--benchmark-root", str(benchmark_root),
    ], "independent_evaluation", log)
    (condition / "COMPLETE").write_text("completed\n", encoding="utf-8")


if __name__ == "__main__":
    main()
