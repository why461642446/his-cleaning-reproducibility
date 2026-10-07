"""Independent materializer for a predeclared multi-character lexical OOD condition."""

from __future__ import annotations

import json
import argparse
from pathlib import Path
import shutil

import numpy as np
import pandas as pd


WORK = Path(__file__).resolve().parent
N_EVENTS = 1900
RANDOM_STATE = 20260925
TABLES = ("patient", "visit", "diagnosis", "laboratory", "medication", "examination")


def multi_typo(value: str) -> str:
    """Apply exactly two textual operations: one adjacent swap and one deletion."""
    chars = list(value)
    alpha = [i for i, char in enumerate(chars) if char.isalpha()]
    if len(alpha) < 4:
        raise ValueError(f"Insufficient alphabetic characters: {value!r}")
    left = alpha[1]
    right = left + 1
    while right >= len(chars) or not chars[right].isalpha():
        left += 1
        right = left + 1
    chars[left], chars[right] = chars[right], chars[left]
    delete = alpha[-2]
    if delete in {left, right}:
        delete = alpha[-3]
    del chars[delete]
    result = "".join(chars)
    if result == value:
        raise RuntimeError("Multi-character operation did not change the value.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    canonical = args.benchmark_root.resolve() / "canonical_reference"
    out = args.output_dir.resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing OOD condition: {out}")
    input_dir = out / "operational_input"
    gt_dir = out / "ground_truth"
    input_dir.mkdir(parents=True)
    gt_dir.mkdir()
    for table in TABLES:
        shutil.copy2(canonical / f"{table}.csv", input_dir / f"{table}.csv")

    diagnosis_path = input_dir / "diagnosis.csv"
    diagnosis = pd.read_csv(diagnosis_path, dtype=str, keep_default_na=False)
    eligible = diagnosis.loc[
        diagnosis["diagnosis_name"].map(lambda x: len([c for c in str(x) if c.isalpha()]) >= 4)
    ].copy()
    selected_ids = eligible.sample(n=N_EVENTS, random_state=RANDOM_STATE)["diagnosis_id"].tolist()
    selected = diagnosis[diagnosis["diagnosis_id"].isin(selected_ids)].copy().sort_values("diagnosis_id")
    if len(selected) != N_EVENTS:
        raise RuntimeError("Selected record count mismatch.")

    event_rows = []
    state_rows = []
    mapping = {}
    for number, row in enumerate(selected.itertuples(index=False), start=1):
        before = str(row.diagnosis_name)
        after = multi_typo(before)
        event_id = f"OODLEXMULTI_{number:07d}"
        mapping[str(row.diagnosis_id)] = after
        event_rows.append({
            "corruption_event_id": event_id,
            "variant_id": "OOD_LEX_MULTI_01",
            "category": "LEXICAL_OOD",
            "table_name": "Diagnosis",
            "record_id": str(row.diagnosis_id),
            "secondary_record_id": "",
            "field_name": "diagnosis_name",
            "secondary_field_name": "",
            "pre_corruption_value": before,
            "post_corruption_value": after,
            "source_valid_value": before,
            "canonical_target_value": before,
            "expected_action": "CORRECT",
            "event_group_id": event_id,
        })
        state_rows.append({
            "table_name": "Diagnosis",
            "record_id": str(row.diagnosis_id),
            "field_name": "diagnosis_name",
            "source_valid_value": before,
            "canonical_target_value": before,
            "expected_action": "CORRECT",
            "event_group_id": event_id,
            "variant_id": "OOD_LEX_MULTI_01",
        })
    diagnosis.loc[diagnosis["diagnosis_id"].isin(mapping), "diagnosis_name"] = diagnosis.loc[
        diagnosis["diagnosis_id"].isin(mapping), "diagnosis_id"
    ].map(mapping)
    diagnosis.to_csv(diagnosis_path, index=False, encoding="utf-8")
    pd.DataFrame(event_rows).to_csv(gt_dir / "event_gt.csv", index=False, encoding="utf-8")
    pd.DataFrame(state_rows).to_csv(gt_dir / "state_gt.csv", index=False, encoding="utf-8")
    shutil.copy2(
        WORK / "OOD_LEX_ALIAS_01" / "evaluation_reference_negative_state_sample.csv",
        out / "evaluation_reference_negative_state_sample.csv",
    )
    protocol = {
        "variant_id": "OOD_LEX_MULTI_01",
        "purpose": "Held-out lexical transformation operator test; separately reported from internal HELDOUT.",
        "source": "canonical_reference copied into an isolated condition",
        "events": N_EVENTS,
        "selection_random_state": RANDOM_STATE,
        "operator": "one adjacent alphabetic-character transposition plus one distinct alphabetic-character deletion",
        "expected_action": "CORRECT",
        "code_retained": True,
        "interpretation": "Tests code-supported recovery under an unseen multi-character typo operator. It does not test dictionary-free name-only generalization.",
        "frozen_v3_modified": False,
        "original_heldout_modified": False,
    }
    (OUT / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    print(json.dumps(protocol, ensure_ascii=False))


if __name__ == "__main__":
    main()
