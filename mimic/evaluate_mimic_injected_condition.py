"""Evaluate one materialized MIMIC injected-event condition without natural-error assumptions."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json

import pandas as pd


OUTPUT_FILE = {"Patient": "patient.csv", "Visit": "visit.csv", "Diagnosis": "diagnosis.csv", "Laboratory": "laboratory.csv", "Medication": "medication.csv"}
ROW_ID = {"Patient": "patient_id", "Visit": "visit_id", "Diagnosis": "diagnosis_id", "Laboratory": "lab_id", "Medication": "medication_event_id"}


def norm(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def matching_actions(actions: pd.DataFrame, event: pd.Series) -> pd.DataFrame:
    subset = actions.loc[actions["table_name"].astype(str).eq(str(event.table_name))].copy()
    ids = {str(event.record_id)}
    if norm(event.secondary_record_id):
        ids.add(str(event.secondary_record_id))
    return subset.loc[subset["record_id"].astype(str).isin(ids) | subset["secondary_record_id"].astype(str).isin(ids)]


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--condition-dir", type=Path, required=True)
    parser.add_argument("--cleaned-dir", type=Path, required=True)
    parser.add_argument("--action-log", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    truth = pd.read_csv(args.condition_dir / "ground_truth" / "injected_event_truth.csv", dtype=str).fillna("")
    actions = pd.read_csv(args.action_log, dtype=str).fillna("")
    cleaned = {domain: pd.read_csv(args.cleaned_dir / filename, dtype=str).fillna("") for domain, filename in OUTPUT_FILE.items()}
    rows = []
    for event in truth.itertuples(index=False):
        before = json.loads(event.before_json)
        after = json.loads(event.after_json)
        action_rows = matching_actions(actions, pd.Series(event._asdict()))
        action_types = set(action_rows["action_type"].astype(str))
        outcome = "UNASSESSED"
        success = False

        if event.expected_behavior == "CORRECT":
            table, key = cleaned[event.table_name], ROW_ID[event.table_name]
            record = table.loc[table[key].astype(str).eq(str(event.record_id))]
            restored = len(record) == 1 and all(norm(record.iloc[0].get(field, "")) == norm(value) for field, value in before.items())
            success, outcome = restored, "RESTORED" if restored else "NOT_RESTORED"
        elif event.expected_behavior == "REMOVE_DUPLICATE":
            table, key = cleaned[event.table_name], ROW_ID[event.table_name]
            removed = not table[key].astype(str).eq(str(event.secondary_record_id)).any()
            success, outcome = removed, "REMOVED" if removed else "NOT_REMOVED"
        elif event.expected_behavior == "FLAG_OR_ABSTAIN":
            detected = bool(action_types.intersection({"FLAG", "ABSTAIN"}))
            success, outcome = detected, "DETECTED" if detected else "NOT_DETECTED"
        elif event.expected_behavior == "STRESS_TEST_ONLY":
            outcome = "OBSERVED_DETECTION" if action_types.intersection({"FLAG", "ABSTAIN", "REMOVE_DUPLICATE"}) else "NO_OBSERVED_DETECTION"
        rows.append({"event_id": event.event_id, "variant_id": event.variant_id, "table_name": event.table_name, "record_id": event.record_id, "expected_behavior": event.expected_behavior, "outcome": outcome, "success": success, "matched_action_rows": len(action_rows)})

    event_results = pd.DataFrame(rows)
    summary = event_results.loc[event_results["expected_behavior"].ne("STRESS_TEST_ONLY")].groupby(["variant_id", "expected_behavior"], as_index=False).agg(events=("event_id", "size"), successful_events=("success", "sum"))
    summary["event_recall"] = summary["successful_events"] / summary["events"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    event_results.to_csv(args.output_dir / "event_level_results.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(args.output_dir / "condition_metric_summary.csv", index=False, encoding="utf-8-sig")
    (args.output_dir / "evaluation_manifest.json").write_text(json.dumps({"truth_events": len(truth), "action_rows": len(actions), "natural_error_assumptions": False}, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
