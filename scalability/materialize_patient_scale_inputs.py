"""Materialize relationship-preserving V3 scalability inputs without changing source data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


TABLES = ("patient", "visit", "diagnosis", "laboratory", "medication", "examination")
FRACTIONS = {"S10": 0.10, "S25": 0.25, "S50": 0.50}
REPLICATE_SEEDS = {1: 20260924, 2: 20260925, 3: 20260926}


def write_subset(source_dir: Path, table: str, patient_ids: set[str], visit_ids: set[str], destination: Path) -> int:
    source = source_dir / f"{table}.csv"
    target = destination / f"{table}.csv"
    rows = 0
    first = True
    for chunk in pd.read_csv(source, chunksize=100_000, low_memory=False):
        if table == "patient":
            keep = chunk["patient_id"].astype(str).isin(patient_ids)
        elif table == "visit":
            keep = chunk["patient_id"].astype(str).isin(patient_ids)
        else:
            keep = chunk["patient_id"].astype(str).isin(patient_ids)
            if "visit_id" in chunk.columns:
                keep |= chunk["visit_id"].astype(str).isin(visit_ids)
        selected = chunk.loc[keep]
        rows += len(selected)
        selected.to_csv(target, mode="w" if first else "a", header=first, index=False, encoding="utf-8")
        first = False
    return rows


def materialize(dataset: Path, output_root: Path, scale: str, replicate: int) -> None:
    if scale not in FRACTIONS:
        raise ValueError(f"Unsupported scale: {scale}")
    source = dataset / "phase3_final_test" / "seed_42" / "corruption_20" / "operational_input"
    output = output_root / "inputs" / f"{scale}_R{replicate}" / "operational_input"
    if output.exists() and any(output.glob("*.csv")):
        raise FileExistsError(f"Refusing to overwrite existing scale input: {output}")
    output.mkdir(parents=True, exist_ok=False)

    patients = pd.read_csv(source / "patient.csv", usecols=["patient_id"], dtype=str)
    n = int(round(len(patients) * FRACTIONS[scale]))
    selected_patients = patients.sample(n=n, random_state=REPLICATE_SEEDS[replicate])["patient_id"].astype(str)
    patient_ids = set(selected_patients)
    visits = pd.read_csv(source / "visit.csv", usecols=["visit_id", "patient_id"], dtype=str)
    visit_ids = set(visits.loc[visits["patient_id"].astype(str).isin(patient_ids), "visit_id"].astype(str))

    counts = {table: write_subset(source, table, patient_ids, visit_ids, output) for table in TABLES}
    manifest = {
        "source_condition": "phase3_final_test/seed_42/corruption_20",
        "scale": scale,
        "replicate": replicate,
        "patient_fraction": FRACTIONS[scale],
        "patient_sampling_random_state": REPLICATE_SEEDS[replicate],
        "patients": len(patient_ids),
        "visits": len(visit_ids),
        "row_counts": counts,
        "total_rows": sum(counts.values()),
        "relationship_policy": "patient-selected; all rows linked by retained patient_id or visit_id retained",
        "source_data_modified": False,
    }
    (output.parent / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--scale", required=True, choices=sorted(FRACTIONS))
    parser.add_argument("--replicate", required=True, type=int, choices=sorted(REPLICATE_SEEDS))
    args = parser.parse_args()
    materialize(args.benchmark_root.resolve(), args.output_root.resolve(), args.scale, args.replicate)


if __name__ == "__main__":
    main()
