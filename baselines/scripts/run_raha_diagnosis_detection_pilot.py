"""Run a predeclared Raha detection-only pilot on one frozen HIS condition.

The full clean reference is supplied solely because Raha's stock implementation
uses it to simulate a fixed number of human tuple labels.  Detection metrics
exclude those labelled tuples, so the held-out score is not calculated on
training annotations.  This is a label-budget simulation, not a claim of
manual clinical labelling or a whole-framework ranking.
"""

from __future__ import annotations

import json
import itertools
import os
from pathlib import Path
import random
import pickle
import argparse

import numpy as np
import pandas as pd
import raha


DEFAULT_SEED = 42
RATE = 20
SAMPLE_ROWS = 5_000
SAMPLE_RANDOM_STATE = 20260928
LABEL_BUDGET = 20

for variable in ("HIS_BENCHMARK_ROOT", "HIS_BASELINE_OUTPUT_ROOT"):
    if variable not in os.environ:
        raise RuntimeError(f"{variable} must be set by the public baseline wrapper.")
ROOT = Path(os.environ["HIS_BENCHMARK_ROOT"])
OUT = Path(os.environ["HIS_BASELINE_OUTPUT_ROOT"])


class WindowsSerialRaha(raha.Detection):
    """Raha's unmodified strategies, executed serially to avoid Windows locks."""

    def run_strategies(self, d):
        profiles_dir = os.path.join(d.results_folder, "strategy-profiling")
        if os.path.exists(profiles_dir):
            d.strategy_profiles = [
                pickle.load(open(os.path.join(profiles_dir, name), "rb"))
                for name in os.listdir(profiles_dir)
            ]
            return
        if self.SAVE_RESULTS:
            os.mkdir(profiles_dir)
        jobs = []
        for algorithm in self.ERROR_DETECTION_ALGORITHMS:
            if algorithm == "OD":
                configs = [list(x) for x in itertools.product(
                    ["histogram"], ["0.1", "0.3", "0.5", "0.7", "0.9"],
                    ["0.1", "0.3", "0.5", "0.7", "0.9"]
                )] + [list(x) for x in itertools.product(
                    ["gaussian"], ["1.0", "1.3", "1.5", "1.7", "2.0", "2.3", "2.5", "2.7", "3.0"]
                )]
            elif algorithm == "PVD":
                configs = []
                for attribute in d.dataframe.columns:
                    for character in set("".join(d.dataframe[attribute].tolist())):
                        configs.append([attribute, character])
            elif algorithm == "RVD":
                configs = [[a, b] for a, b in itertools.product(d.dataframe.columns, repeat=2) if a != b]
            elif algorithm == "KBVD":
                kb = os.path.join(os.path.dirname(raha.__file__), "tools", "KATARA", "knowledge-base")
                configs = [os.path.join(kb, name) for name in os.listdir(kb)]
            else:
                raise RuntimeError(f"Unsupported Raha strategy: {algorithm}")
            jobs.extend([[d, algorithm, config] for config in configs])
        random.shuffle(jobs)
        d.strategy_profiles = [self._strategy_runner_process(job) for job in jobs]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    seed = args.seed
    random.seed(SAMPLE_RANDOM_STATE + seed)
    np.random.seed(SAMPLE_RANDOM_STATE + seed)
    
    condition = ROOT / "phase3_final_test" / f"seed_{seed}" / f"corruption_{RATE:02d}"
    out = OUT / f"seed_{seed}_rate_{RATE:02d}"
    out.mkdir(parents=True, exist_ok=True)
    dirty = pd.read_csv(condition / "operational_input" / "diagnosis.csv", dtype=str)
    events = pd.read_csv(
        condition / "ground_truth" / "event_gt.csv",
        usecols=["table_name", "record_id", "field_name", "pre_corruption_value", "variant_id"],
        dtype=str,
    )
    events = events[(events["table_name"] == "Diagnosis") & (events["field_name"] == "diagnosis_name")]
    if events["record_id"].duplicated().any():
        raise RuntimeError("Expected one diagnosis-name event per record in this scoped condition.")

    dirty = dirty.merge(
        events[["record_id", "pre_corruption_value", "variant_id"]],
        left_on="diagnosis_id",
        right_on="record_id",
        how="left",
        validate="one_to_one",
    )
    dirty["is_injected_diagnosis_name_error"] = dirty["pre_corruption_value"].notna()
    sample = dirty.sample(n=SAMPLE_ROWS, random_state=SAMPLE_RANDOM_STATE).copy().reset_index(drop=True)
    clean_name = sample["diagnosis_name"].where(
        ~sample["is_injected_diagnosis_name_error"], sample["pre_corruption_value"]
    )

    # Raha receives only the two predeclared common fields; no project dictionary
    # or V3 action log is available to it.
    dirty_raha = sample[["diagnosis_code", "diagnosis_name"]].copy()
    clean_raha = dirty_raha.copy()
    clean_raha["diagnosis_name"] = clean_name
    dirty_path = out / "dirty_code_name.csv"
    clean_path = out / "clean_code_name_for_label_budget_simulation.csv"
    dirty_raha.to_csv(dirty_path, index=False)
    clean_raha.to_csv(clean_path, index=False)

    manifest = pd.DataFrame(
        {
            "raha_row_index": range(len(sample)),
            "diagnosis_id": sample["diagnosis_id"],
            "diagnosis_code": sample["diagnosis_code"],
            "is_injected_diagnosis_name_error": sample["is_injected_diagnosis_name_error"].astype(int),
            "variant_id": sample["variant_id"].fillna("CLEAN"),
        }
    )
    manifest.to_csv(out / "sample_manifest.csv", index=False)

    detector = WindowsSerialRaha()
    detector.LABELING_BUDGET = LABEL_BUDGET
    detector.USER_LABELING_ACCURACY = 1.0
    detector.VERBOSE = True
    detector.SAVE_RESULTS = True
    # The predeclared text code--name scope has no numeric attribute for OD and
    # no relevant hospital diagnosis knowledge base for the bundled city KBVD.
    # Retain Raha's native pattern-violation and relation-violation strategies.
    detector.ERROR_DETECTION_ALGORITHMS = ["PVD", "RVD"]
    # Avoid process-spawn instability on Windows for the first reproducibility run.
    detected = detector.run(
        {
            "name": f"his_finaltest_seed{seed}_rate{RATE:02d}_diagnosis_code_name_pvd_rvd_v2",
            "path": str(dirty_path),
            "clean_path": str(clean_path),
        }
    )

    results_dir = out / f"raha-baran-results-his_finaltest_seed{seed}_rate{RATE:02d}_diagnosis_code_name_pvd_rvd_v2" / "error-detection"
    dataset_pickle = results_dir / "detection.dataset"
    if not dataset_pickle.exists():
        raise RuntimeError(f"Raha did not write its dataset artifact: {dataset_pickle}")

    import pickle
    with dataset_pickle.open("rb") as handle:
        state = pickle.load(handle)
    labelled_rows = sorted(int(x) for x in state.labeled_tuples)
    pd.DataFrame({"raha_row_index": labelled_rows}).merge(manifest, on="raha_row_index", how="left").to_csv(
        out / "labelled_tuple_manifest.csv", index=False
    )

    # Raha reports all detected cells. Score only the diagnosis_name column (index 1)
    # and only rows that were not used for simulated annotations.
    predicted = {int(row) for (row, col) in detected if int(col) == 1}
    labelled = set(labelled_rows)
    scored = manifest[~manifest["raha_row_index"].isin(labelled)].copy()
    truth = set(scored.loc[scored["is_injected_diagnosis_name_error"] == 1, "raha_row_index"])
    predicted &= set(scored["raha_row_index"])
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    summary = {
        "experiment": "Raha detection-only pilot; simulated fixed label budget",
        "condition": {"stage": "FINAL_TEST", "seed": seed, "corruption_rate_pct": RATE},
        "scope": "Diagnosis diagnosis_code and diagnosis_name only; score diagnosis_name only",
        "sample_rows": SAMPLE_ROWS,
        "sample_random_state": SAMPLE_RANDOM_STATE,
        "label_budget": LABEL_BUDGET,
        "label_accuracy_simulated": 1.0,
        "scored_unlabelled_rows": len(scored),
        "truth_error_rows": len(truth),
        "predicted_error_rows": len(predicted),
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
        "warning": "The clean reference was used only to simulate the predeclared annotation budget. Metrics exclude annotated tuples. This is not a general ranking of full cleaning systems.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.DataFrame([summary]).to_csv(out / "summary.csv", index=False)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
