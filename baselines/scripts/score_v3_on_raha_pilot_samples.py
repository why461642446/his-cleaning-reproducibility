"""Extract frozen V3 diagnosis-name detection on the predeclared Raha samples.

This does not rerun V3 and does not alter any action log.  A diagnosis record is
counted as detected when the frozen V3 action log contains any action on its
diagnosis_name field.  To match the Raha score, Raha's 20 simulated-label rows
are excluded here too.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


SEEDS = [42, 142, 242, 342, 442]
RATE = 20
for variable in ("HIS_BENCHMARK_ROOT", "HIS_BASELINE_OUTPUT_ROOT"):
    if variable not in os.environ:
        raise RuntimeError(f"{variable} must be set by the public baseline wrapper.")
BASELINE = Path(os.environ["HIS_BASELINE_OUTPUT_ROOT"])
V3ROOT = Path(os.environ["HIS_BENCHMARK_ROOT"]) / "phase4_results" / "final_test"


def score(seed: int) -> dict:
    folder = BASELINE / f"seed_{seed}_rate_{RATE:02d}"
    manifest = pd.read_csv(folder / "sample_manifest.csv", dtype={"diagnosis_id": str})
    labelled = set(pd.read_csv(folder / "labelled_tuple_manifest.csv")["raha_row_index"])
    action_path = V3ROOT / f"seed_{seed}" / f"corruption_{RATE:02d}" / "FULL_FRAMEWORK_V3" / "action_log.csv"
    usecols = ["table_name", "record_id", "field_name", "action_type"]
    actions = pd.read_csv(action_path, usecols=usecols, dtype=str)
    flagged = set(actions.loc[
        (actions["table_name"] == "Diagnosis") & (actions["field_name"] == "diagnosis_name"), "record_id"
    ])
    scored = manifest[~manifest["raha_row_index"].isin(labelled)].copy()
    truth = set(scored.loc[scored["is_injected_diagnosis_name_error"] == 1, "diagnosis_id"])
    predicted = set(scored.loc[scored["diagnosis_id"].isin(flagged), "diagnosis_id"])
    tp, fp, fn = len(predicted & truth), len(predicted - truth), len(truth - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "method": "Frozen FULL_FRAMEWORK_V3 (action-log extraction)", "seed": seed,
        "rate": RATE, "scored_unlabelled_rows": len(scored), "truth_error_rows": len(truth),
        "predicted_error_rows": len(predicted), "TP": tp, "FP": fp, "FN": fn,
        "Precision": precision, "Recall": recall, "F1": f1,
    }


def main() -> None:
    rows = [score(seed) for seed in SEEDS]
    result = pd.DataFrame(rows)
    result.to_csv(BASELINE / "v3_on_raha_pilot_samples_all_seeds.csv", index=False)
    aggregate = result[["Precision", "Recall", "F1"]].agg(["mean", "std"]).T.reset_index().rename(columns={"index": "metric"})
    aggregate.to_csv(BASELINE / "v3_on_raha_pilot_samples_aggregate.csv", index=False)
    print(result.to_string(index=False))
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
