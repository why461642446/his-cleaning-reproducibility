"""Evaluate a simple frozen code-to-canonical-name lookup on the Raha samples.

The mapping is read only from V3's pre-existing canonical_reference diagnosis
table.  It never uses FINAL_TEST event truth to construct a repair candidate.
Metrics use the same 4,980 unlabelled rows per seed as the existing Raha pilot.
"""
from __future__ import annotations

from pathlib import Path
import os
import pandas as pd


SEEDS = [42, 142, 242, 342, 442]
RATE = 20
for variable in ("HIS_BENCHMARK_ROOT", "HIS_BASELINE_OUTPUT_ROOT"):
    if variable not in os.environ:
        raise RuntimeError(f"{variable} must be set by the public baseline wrapper.")
ROOT = Path(os.environ["HIS_BENCHMARK_ROOT"])
BASE = Path(os.environ["HIS_BASELINE_OUTPUT_ROOT"])


def metrics(predicted: set[str], truth: set[str]) -> dict[str, float]:
    tp, fp, fn = len(predicted & truth), len(predicted - truth), len(truth - predicted)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "Precision": p, "Recall": r, "F1": 2*p*r/(p+r) if p+r else 0.0}


def main() -> None:
    canonical = pd.read_csv(ROOT / "canonical_reference" / "diagnosis.csv", dtype=str)
    mapping = dict(zip(canonical["diagnosis_code"], canonical["diagnosis_name"]))
    if len(mapping) != 100:
        raise RuntimeError(f"Expected V3's 100-code diagnosis dictionary, observed {len(mapping)}")
    rows = []
    for seed in SEEDS:
        folder = BASE / f"seed_{seed}_rate_{RATE:02d}"
        sample = pd.read_csv(folder / "sample_manifest.csv", dtype=str)
        labels = set(pd.read_csv(folder / "labelled_tuple_manifest.csv")["raha_row_index"].astype(str))
        dirty = pd.read_csv(folder / "dirty_code_name.csv", dtype=str)
        sample["raha_row_index"] = sample["raha_row_index"].astype(str)
        scored = sample.loc[~sample["raha_row_index"].isin(labels)].copy()
        scored["dirty_name"] = dirty.loc[scored.index, "diagnosis_name"].values
        scored["canonical_name"] = scored["diagnosis_code"].map(mapping)
        if scored["canonical_name"].isna().any():
            raise RuntimeError("A scored diagnosis code is absent from the V3 dictionary")
        truth = set(scored.loc[scored["is_injected_diagnosis_name_error"].astype(int).eq(1), "diagnosis_id"])
        predicted = set(scored.loc[scored["dirty_name"] != scored["canonical_name"], "diagnosis_id"])
        result = metrics(predicted, truth)
        events = pd.read_csv(
            ROOT / "phase3_final_test" / f"seed_{seed}" / f"corruption_{RATE:02d}" / "ground_truth" / "event_gt.csv",
            usecols=["table_name", "record_id", "field_name", "canonical_target_value"], dtype=str,
        )
        events = events[(events["table_name"] == "Diagnosis") & (events["field_name"] == "diagnosis_name")]
        injected = scored[scored["diagnosis_id"].isin(truth)].merge(
            events[["record_id", "canonical_target_value"]], left_on="diagnosis_id", right_on="record_id", how="left", validate="one_to_one"
        )
        repaired = (injected["canonical_name"] == injected["canonical_target_value"]).sum()
        result.update({
            "method": "Direct V3 canonical code-to-name lookup",
            "seed": seed,
            "rate": RATE,
            "dictionary_entries": len(mapping),
            "scored_unlabelled_rows": len(scored),
            "truth_error_rows": len(truth),
            "predicted_changed_rows": len(predicted),
            "injected_rows_with_dictionary_output": int(repaired),
            "warning": "This baseline applies a deterministic canonical lookup whenever the current name differs. It is not a general lexical inference method and does not establish that all source-native representation changes should be overwritten.",
        })
        rows.append(result)
    result = pd.DataFrame(rows)
    result.to_csv(BASE / "direct_code_lookup_baseline_all_seeds.csv", index=False)
    summary = result[["Precision", "Recall", "F1", "TP", "FP", "FN"]].agg(["mean", "std"]).T.reset_index().rename(columns={"index": "metric"})
    summary.to_csv(BASE / "direct_code_lookup_baseline_aggregate.csv", index=False)
    print(result.to_string(index=False))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
