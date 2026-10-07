"""One-seed Baran repair preflight on the frozen diagnosis code-name sample.

Baran receives the same two data fields as Raha and no V3 dictionary. Its clean
reference is accessed only for Baran's fixed 20-tuple oracle-label simulation.
Labelled tuples are excluded from evaluation. A serial predictor calls Baran's
own feature and prediction function without Windows multiprocessing.
"""
from __future__ import annotations

import itertools
import json
import pickle
import random
import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import raha


DEFAULT_SEED = 42
RATE = 20
LABEL_BUDGET = 20
for variable in ("HIS_BENCHMARK_ROOT", "HIS_BASELINE_OUTPUT_ROOT"):
    if variable not in os.environ:
        raise RuntimeError(f"{variable} must be set by the public baseline wrapper.")
ROOT = Path(os.environ["HIS_BENCHMARK_ROOT"])
BASE = Path(os.environ["HIS_BASELINE_OUTPUT_ROOT"])


class WindowsSerialBaran(raha.Correction):
    """Execute Baran's existing per-chunk predictor serially on Windows."""

    def predict_correction_multicore(self, classification_model, used_cells_test, d, all_zeros, all_ones):
        for start in range(0, len(used_cells_test), self.CHUNK_SIZE):
            cells = used_cells_test[start:start + self.CHUNK_SIZE]
            d.corrected_cells.update(
                self._prediction_process(cells, all_ones, all_zeros, dataset=d, cls_model=classification_model)
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, choices=[42, 142, 242, 342, 442])
    args = parser.parse_args()
    seed = args.seed
    random_seed = 20260928 + seed
    random.seed(random_seed)
    np.random.seed(random_seed)
    folder = BASE / f"seed_{seed}_rate_{RATE:02d}"
    out = folder / "baran_repair_preflight_v1"
    out.mkdir(parents=True, exist_ok=True)
    detection_pickle = folder / f"raha-baran-results-his_finaltest_seed{seed}_rate20_diagnosis_code_name_pvd_rvd_v2" / "error-detection" / "detection.dataset"
    with detection_pickle.open("rb") as handle:
        dataset = pickle.load(handle)

    # Retain Raha's detection output but start Baran with its own fixed label budget.
    dataset.name = f"his_finaltest_seed{seed}_rate20_diagnosis_code_name_baran_preflight_v1"
    dataset.labeled_tuples = {}
    dataset.labeled_cells = {}
    dataset.corrected_cells = {}

    baran = WindowsSerialBaran()
    baran.LABELING_BUDGET = LABEL_BUDGET
    baran.SAVE_RESULTS = True
    baran.VERBOSE = True
    baran.NUM_WORKERS = 1
    corrected = baran.run(dataset)

    manifest = pd.read_csv(folder / "sample_manifest.csv", dtype={"diagnosis_id": str})
    labelled = set(int(x) for x in dataset.labeled_tuples)
    scored = manifest[~manifest["raha_row_index"].isin(labelled)].copy()
    truth = set(scored.loc[scored["is_injected_diagnosis_name_error"].astype(int).eq(1), "raha_row_index"])
    diagnosis_name_col = list(dataset.dataframe.columns).index("diagnosis_name")
    predictions = {int(row): value for (row, col), value in corrected.items() if int(col) == diagnosis_name_col and int(row) in set(scored["raha_row_index"])}
    predicted_rows = set(predictions)
    events = pd.read_csv(
        ROOT / "phase3_final_test" / f"seed_{seed}" / f"corruption_{RATE:02d}" / "ground_truth" / "event_gt.csv",
        usecols=["table_name", "record_id", "field_name", "canonical_target_value"], dtype=str,
    )
    events = events[(events["table_name"] == "Diagnosis") & (events["field_name"] == "diagnosis_name")]
    lookup = dict(zip(manifest["diagnosis_id"], manifest["raha_row_index"]))
    target = {lookup[row.record_id]: row.canonical_target_value for row in events.itertuples(index=False) if row.record_id in lookup}
    tp_detect = predicted_rows & truth
    repaired_correct = {row for row in tp_detect if predictions[row] == target.get(row)}
    tp, fp, fn = len(tp_detect), len(predicted_rows - truth), len(truth - predicted_rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    repair_precision = len(repaired_correct) / len(predicted_rows) if predicted_rows else 0.0
    repair_recall = len(repaired_correct) / len(truth) if truth else 0.0
    pd.DataFrame(
        [{"raha_row_index": row, "predicted_value": predictions[row], "is_injected_error": int(row in truth), "canonical_target": target.get(row), "correct_repair": int(row in repaired_correct)} for row in sorted(predictions)]
    ).to_csv(out / "baran_predicted_diagnosis_name_repairs.csv", index=False)
    pd.DataFrame({"raha_row_index": sorted(labelled)}).merge(manifest, on="raha_row_index", how="left").to_csv(out / "baran_labelled_tuple_manifest.csv", index=False)
    summary = {
        "method": "Baran standard semi-supervised repair preflight (no V3 dictionary)",
        "seed": seed, "rate": RATE, "label_budget": LABEL_BUDGET,
        "labelled_injected_errors": int(pd.read_csv(out / "baran_labelled_tuple_manifest.csv")["is_injected_diagnosis_name_error"].sum()),
        "scored_unlabelled_rows": len(scored), "truth_error_rows": len(truth),
        "predicted_repairs": len(predicted_rows), "TP_detection": tp, "FP_detection": fp, "FN_detection": fn,
        "detection_precision": precision, "detection_recall": recall, "detection_F1": f1,
        "correct_repairs": len(repaired_correct), "repair_precision_all_predictions": repair_precision,
        "repair_recall_truth_errors": repair_recall,
        "warning": "Baran received no V3 dictionary. The clean reference is used only for the fixed oracle-label budget; metrics exclude labelled tuples.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
