"""Run prespecified no-op and always-flag baselines on the saved Raha samples.

These comparators make no use of V3 actions, thresholds, dictionaries, or
event truth while predicting.  The same 20 labelled tuples per seed are
excluded as in the Raha and direct-lookup reports.
"""
from __future__ import annotations

from pathlib import Path
import os

import pandas as pd


SEEDS = [42, 142, 242, 342, 442]
RATE = 20
if "HIS_BASELINE_OUTPUT_ROOT" not in os.environ:
    raise RuntimeError("HIS_BASELINE_OUTPUT_ROOT must be set by the public baseline wrapper.")
BASE = Path(os.environ["HIS_BASELINE_OUTPUT_ROOT"])


def score(predicted: set[str], truth: set[str]) -> dict[str, float]:
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "Precision": precision, "Recall": recall, "F1": f1}


def main() -> None:
    rows = []
    for seed in SEEDS:
        folder = BASE / f"seed_{seed}_rate_{RATE:02d}"
        sample = pd.read_csv(folder / "sample_manifest.csv", dtype=str)
        labels = set(pd.read_csv(folder / "labelled_tuple_manifest.csv")["raha_row_index"].astype(str))
        sample["raha_row_index"] = sample["raha_row_index"].astype(str)
        scored = sample.loc[~sample["raha_row_index"].isin(labels)].copy()
        truth = set(scored.loc[scored["is_injected_diagnosis_name_error"].astype(int).eq(1), "diagnosis_id"])
        all_rows = set(scored["diagnosis_id"])
        for method, predicted in [("No-op", set()), ("Always-flag", all_rows)]:
            result = score(predicted, truth)
            result.update({
                "method": method,
                "seed": seed,
                "rate": RATE,
                "scored_unlabelled_rows": len(scored),
                "truth_error_rows": len(truth),
                "predicted_flagged_rows": len(predicted),
                "review_burden_per_1000_rows": len(predicted) / len(scored) * 1000,
                "repair_attempts": 0,
                "protocol": "Same 4,980 unseen rows and excluded 20 label tuples as Raha/direct lookup",
            })
            rows.append(result)

    per_seed = pd.DataFrame(rows).sort_values(["method", "seed"])
    aggregate = (per_seed.groupby("method", as_index=False)
                 .agg(Precision_mean=("Precision", "mean"), Precision_sd=("Precision", "std"),
                      Recall_mean=("Recall", "mean"), Recall_sd=("Recall", "std"),
                      F1_mean=("F1", "mean"), F1_sd=("F1", "std"),
                      review_burden_per_1000_mean=("review_burden_per_1000_rows", "mean"),
                      review_burden_per_1000_sd=("review_burden_per_1000_rows", "std")))
    out = BASE / "design_sensitivity_baselines_v1"
    out.mkdir(parents=True, exist_ok=True)
    per_seed.to_csv(out / "per_seed.csv", index=False, encoding="utf-8-sig")
    aggregate.to_csv(out / "aggregate.csv", index=False, encoding="utf-8-sig")
    (out / "README.md").write_text(
        "# Design-sensitivity baselines\n\n"
        "No-op predicts no errors. Always-flag predicts every scored diagnosis row as an error. "
        "Both are detection-only reference policies on the same five saved 5,000-row samples, after "
        "excluding the same 20 labelled tuples per seed used by the Raha comparator. Neither uses V3 "
        "rules, event truth, or a candidate dictionary while making predictions. They do not repair values.\n",
        encoding="utf-8",
    )
    print(per_seed.to_string(index=False))
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
