"""Create deterministic, non-mutating MIMIC Demo DEBUG injection plans.

The script reads only mapped clean references and the frozen v1.1 protocol.
It creates one plan per catalog variant/rate; plans never mix variants, so a
single condition has a single known corruption mechanism.  It does not alter
any table and intentionally has no --execute mode.
"""

from __future__ import annotations

from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path
import re

import pandas as pd


RATES = (5, 10, 20, 30, 40)
DEBUG_SALT = "MIMIC_DEBUG_INJECTION_V1_1_20260923"
HELDOUT_SALT = "MIMIC_HELDOUT_INJECTION_V1_4_20260924"
NOT_APPLICABLE_V12 = {"CORR_SEM_02", "CORR_LEX_01"}
SINGLE_NUMBER = re.compile(r"^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*$")
UNIT_PAIRS = {
    "mg/dL": "g/dL", "g/dL": "mg/dL", "mg/L": "g/L", "g/L": "mg/L",
    "ug/mL": "mg/mL", "mg/mL": "ug/mL", "ng/mL": "ug/mL",
    "ug/L": "mg/L", "mmol/L": "umol/L", "umol/L": "mmol/L",
}
ROW_ID = {"Patient": "patient_id", "Visit": "visit_id", "Diagnosis": "diagnosis_id", "Laboratory": "lab_id", "Medication": "medication_event_id"}


def select(mask: pd.Series, frame: pd.DataFrame, row_id: str, variant: str, rate: int, salt: str) -> pd.DataFrame:
    eligible = frame.loc[mask].copy()
    n = max(1, round(len(eligible) * rate / 100)) if len(eligible) else 0
    eligible["selection_hash"] = eligible[row_id].astype(str).map(
        lambda value: sha256(f"{salt}:{variant}:{rate}:{value}".encode("utf-8")).hexdigest()
    )
    return eligible.sort_values(["selection_hash", row_id], kind="stable").head(n)


def masks(tables: dict[str, pd.DataFrame]) -> dict[str, tuple[str, pd.Series]]:
    lab, med, visit, diag = (tables[key] for key in ("Laboratory", "Medication", "Visit", "Diagnosis"))
    lab_num = pd.to_numeric(lab["result_value"], errors="coerce")
    lab_unit = lab["unit"].astype("string").str.strip().replace("", pd.NA)
    start = pd.to_datetime(med["start_time"], errors="coerce")
    stop = pd.to_datetime(med["stop_time"], errors="coerce")
    bounds = visit.set_index("visit_id")[["admission_time", "discharge_time"]].copy()
    bounds["admission_time"] = pd.to_datetime(bounds["admission_time"], errors="coerce")
    bounds["discharge_time"] = pd.to_datetime(bounds["discharge_time"], errors="coerce")
    linked = lab["visit_id"].map(bounds["discharge_time"])
    lab_time = pd.to_datetime(lab["lab_time"], errors="coerce")
    dose_ok = med["dose_value"].astype("string").fillna("").map(lambda x: bool(SINGLE_NUMBER.match(x)))
    return {
        "CORR_MISS_01": ("Laboratory", lab_num.notna() & lab_unit.notna()),
        "CORR_LEX_01": ("Medication", med["drug_name"].notna()),
        "CORR_LEX_03": ("Diagnosis", diag["diagnosis_code"].notna()),
        "CORR_SEM_01": ("Diagnosis", diag["diagnosis_code"].notna() & diag["diagnosis_name"].notna()),
        "CORR_SEM_02": ("Visit", visit["visit_type"].notna()),
        "CORR_UNIT_01": ("Laboratory", lab_num.notna() & lab_unit.notna()),
        "CORR_NUM_01": ("Laboratory", lab_num.notna() & pd.to_numeric(lab["reference_lower"], errors="coerce").notna() & pd.to_numeric(lab["reference_upper"], errors="coerce").notna()),
        "CORR_NUM_02": ("Medication", dose_ok),
        "CORR_TIME_01": ("Medication", start.notna() & stop.notna() & (stop > start)),
        "CORR_DUP_01": ("Laboratory", pd.Series(True, index=lab.index)),
        "CORR_REL_01": ("Laboratory", lab["visit_id"].notna()),
        "CORR_MISS_02": ("Medication", med["dose_value"].notna() & med["dose_unit"].notna()),
        "CORR_LEX_02": ("Diagnosis", diag["diagnosis_name"].astype("string").str.len().ge(4)),
        "CORR_UNIT_02": ("Laboratory", lab_num.notna() & lab_unit.isin(UNIT_PAIRS)),
        "CORR_TIME_02": ("Laboratory", lab["visit_id"].notna() & linked.notna() & lab_time.notna()),
        "CORR_DUP_02": ("Laboratory", lab_num.notna()),
        "CORR_REL_03": ("Medication", med["visit_id"].notna()),
    }


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--partition", choices=["DEBUG", "HELDOUT"], default="DEBUG")
    args = parser.parse_args()
    mapped, protocol = args.base / "mapped", args.base / "protocol"
    partition = pd.read_csv(protocol / "mimic_demo_patient_partition_v1_1.csv")
    target_ids = set(partition.loc[partition["partition"].eq(args.partition), "patient_id"].astype(int))
    salt = DEBUG_SALT if args.partition == "DEBUG" else HELDOUT_SALT
    catalog = pd.read_csv(protocol / "mimic_external_corruption_catalog_v1_1.csv")
    catalog = catalog.loc[
        catalog["status"].astype(str).str.startswith("INCLUDE")
        & ~catalog["variant_id"].isin(NOT_APPLICABLE_V12)
    ].copy()
    files = {"Patient": "patient", "Visit": "visit", "Diagnosis": "diagnosis", "Laboratory": "laboratory", "Medication": "medication"}
    tables = {name: pd.read_csv(mapped / f"mimic_{stem}_clean_reference.csv", low_memory=False) for name, stem in files.items()}
    tables["Medication"].insert(0, "medication_event_id", [f"MIMICMED_{i:08d}" for i in range(1, len(tables["Medication"]) + 1)])
    for table in tables.values():
        table["__target_partition__"] = table["patient_id"].isin(target_ids)
    eligible_masks = masks(tables)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for entry in catalog.itertuples(index=False):
        domain, mask = eligible_masks[entry.variant_id]
        frame = tables[domain]
        mask = mask & frame["__target_partition__"]
        for rate in RATES:
            planned = select(mask, frame, ROW_ID[domain], entry.variant_id, rate, salt)
            keep = [ROW_ID[domain], "patient_id", "selection_hash"]
            planned.loc[:, keep].assign(variant_id=entry.variant_id, rate_pct=rate).to_csv(
                args.output_dir / f"{entry.variant_id}_{args.partition.lower()}_rate{rate:02d}_plan.csv", index=False, encoding="utf-8-sig"
            )
            manifest_rows.append({"variant_id": entry.variant_id, "arm": entry.arm, "domain": domain, "partition": args.partition, "rate_pct": rate, "eligible_partition_rows": int(mask.sum()), "planned_events": len(planned), "plan_sha256": sha256(planned[keep].to_csv(index=False).encode("utf-8")).hexdigest()})
    pd.DataFrame(manifest_rows).to_csv(args.output_dir / f"{args.partition.lower()}_injection_plan_manifest.csv", index=False, encoding="utf-8-sig")
    print(f"Created {len(manifest_rows)} non-mutating {args.partition} plans in {args.output_dir}")


if __name__ == "__main__":
    main()
