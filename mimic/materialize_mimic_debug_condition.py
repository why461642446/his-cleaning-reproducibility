"""Materialize one v1.2 MIMIC DEBUG corruption condition.

No write occurs unless --execute is supplied.  The input plan must have been
created by plan_mimic_debug_injections.py; the materializer never selects rows
on its own.  It writes separate clean-reference, operational-input, and
event-level ground-truth folders, preserving the mapped source tables.
"""

from __future__ import annotations

from argparse import ArgumentParser
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json

import pandas as pd


TABLE_FILES = {
    "Patient": "patient", "Visit": "visit", "Diagnosis": "diagnosis",
    "Laboratory": "laboratory", "Medication": "medication",
}
ROW_ID = {"Patient": "patient_id", "Visit": "visit_id", "Diagnosis": "diagnosis_id", "Laboratory": "lab_id", "Medication": "medication_event_id"}
VARIANT_DOMAIN = {
    "CORR_MISS_01": "Laboratory", "CORR_MISS_02": "Medication",
    "CORR_LEX_02": "Diagnosis", "CORR_LEX_03": "Diagnosis",
    "CORR_SEM_01": "Diagnosis", "CORR_UNIT_01": "Laboratory",
    "CORR_UNIT_02": "Laboratory", "CORR_NUM_01": "Laboratory",
    "CORR_NUM_02": "Medication", "CORR_TIME_01": "Medication",
    "CORR_TIME_02": "Laboratory", "CORR_DUP_01": "Laboratory",
    "CORR_DUP_02": "Laboratory", "CORR_REL_01": "Laboratory",
    "CORR_REL_03": "Medication",
}
EXPECTED = {
    "CORR_LEX_01": "CORRECT", "CORR_LEX_02": "CORRECT", "CORR_LEX_03": "CORRECT",
    "CORR_SEM_01": "CORRECT", "CORR_REL_01": "CORRECT", "CORR_REL_03": "CORRECT",
    "CORR_DUP_01": "REMOVE_DUPLICATE", "CORR_MISS_01": "FLAG_OR_ABSTAIN",
    "CORR_MISS_02": "FLAG_OR_ABSTAIN", "CORR_NUM_01": "FLAG_OR_ABSTAIN",
    "CORR_NUM_02": "FLAG_OR_ABSTAIN", "CORR_TIME_01": "FLAG_OR_ABSTAIN",
    "CORR_TIME_02": "FLAG_OR_ABSTAIN", "CORR_UNIT_01": "FLAG_OR_ABSTAIN",
    "CORR_UNIT_02": "FLAG_OR_ABSTAIN", "CORR_DUP_02": "STRESS_TEST_ONLY",
}
UNIT_PAIRS = {
    "mg/dL": ("g/dL", 0.001), "g/dL": ("mg/dL", 1000.0),
    "mg/L": ("g/L", 0.001), "g/L": ("mg/L", 1000.0),
    "ug/mL": ("mg/mL", 0.001), "mg/mL": ("ug/mL", 1000.0),
    "ng/mL": ("ug/mL", 0.001), "ug/L": ("mg/L", 0.001),
    "mmol/L": ("umol/L", 1000.0), "umol/L": ("mmol/L", 0.001),
}


def text(value: object) -> str:
    return "" if pd.isna(value) else str(value)


def write_tables(root: Path, tables: dict[str, pd.DataFrame]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for domain, stem in TABLE_FILES.items():
        tables[domain].to_csv(root / f"{stem}.csv", index=False, encoding="utf-8-sig")
    # Examination is deliberately schema-only, per the frozen adapter contract.
    pd.DataFrame(columns=["examination_id", "patient_id", "visit_id", "examination_name", "modality", "order_time", "exam_time", "status"]).to_csv(
        root / "examination.csv", index=False, encoding="utf-8-sig"
    )


def alternative_patient(values: list[int], current: int, event_id: str) -> int:
    choices = [value for value in values if value != current]
    if not choices:
        raise RuntimeError("No partition-local alternative patient is available")
    return min(choices, key=lambda value: sha256(f"{event_id}:{value}".encode()).hexdigest())


def materialize(tables: dict[str, pd.DataFrame], variant: str, plan: pd.DataFrame) -> list[dict[str, object]]:
    domain = VARIANT_DOMAIN[variant]
    row_id = ROW_ID[domain]
    target = tables[domain]
    indexed = {text(value): index for index, value in target[row_id].items()}
    events: list[dict[str, object]] = []
    diagnosis_pool = tables["Diagnosis"][["diagnosis_code", "diagnosis_name"]].dropna().drop_duplicates()
    debug_patients = sorted(int(v) for v in tables["Patient"]["patient_id"].dropna().unique())

    for ordinal, selected in enumerate(plan.itertuples(index=False), start=1):
        original_id = text(getattr(selected, row_id))
        if original_id not in indexed:
            raise KeyError(f"Planned {domain} row not found: {original_id}")
        index = indexed[original_id]
        event_id = f"{variant}_{ordinal:07d}"
        before: dict[str, object] = {}
        after: dict[str, object] = {}
        secondary_id = ""

        if variant == "CORR_MISS_01":
            before["result_value"] = target.at[index, "result_value"]
            target.at[index, "result_value"] = pd.NA
            after["result_value"] = pd.NA
        elif variant == "CORR_MISS_02":
            for field in ("dose_value", "dose_unit"):
                before[field] = target.at[index, field]
                target.at[index, field] = pd.NA
                after[field] = pd.NA
        elif variant == "CORR_LEX_01":
            before["drug_name"] = target.at[index, "drug_name"]
            target.at[index, "drug_name"] = "  " + text(before["drug_name"]).swapcase() + "  "
            after["drug_name"] = target.at[index, "drug_name"]
        elif variant == "CORR_LEX_02":
            value = text(target.at[index, "diagnosis_name"])
            position = int(sha256(event_id.encode()).hexdigest(), 16) % (len(value) - 1)
            before["diagnosis_name"] = value
            target.at[index, "diagnosis_name"] = value[:position] + value[position + 1] + value[position] + value[position + 2:]
            after["diagnosis_name"] = target.at[index, "diagnosis_name"]
        elif variant == "CORR_LEX_03":
            value = text(target.at[index, "diagnosis_code"])
            before["diagnosis_code"] = value
            target.at[index, "diagnosis_code"] = value.replace(".", "") if "." in value else value[:3] + "." + value[3:]
            after["diagnosis_code"] = target.at[index, "diagnosis_code"]
        elif variant == "CORR_SEM_01":
            code = text(target.at[index, "diagnosis_code"])
            candidates = diagnosis_pool.loc[diagnosis_pool["diagnosis_code"].astype(str).ne(code), "diagnosis_name"].astype(str).tolist()
            replacement = min(candidates, key=lambda value: sha256(f"{event_id}:{value}".encode()).hexdigest())
            before["diagnosis_name"] = target.at[index, "diagnosis_name"]
            target.at[index, "diagnosis_name"] = replacement
            after["diagnosis_name"] = replacement
        elif variant == "CORR_UNIT_01":
            before["unit"] = target.at[index, "unit"]
            target.at[index, "unit"] = "__INVALID_UNIT_V12__"
            after["unit"] = target.at[index, "unit"]
        elif variant == "CORR_NUM_01":
            before["result_value"] = target.at[index, "result_value"]
            factor = 10.0 if int(sha256(event_id.encode()).hexdigest(), 16) % 2 else 0.1
            target.at[index, "result_value"] = str(float(before["result_value"]) * factor)
            after["result_value"] = target.at[index, "result_value"]
        elif variant == "CORR_NUM_02":
            before["dose_value"] = target.at[index, "dose_value"]
            factor = 1000.0 if int(sha256(event_id.encode()).hexdigest(), 16) % 2 else 100.0
            target.at[index, "dose_value"] = str(float(before["dose_value"]) * factor)
            after["dose_value"] = target.at[index, "dose_value"]
        elif variant == "CORR_TIME_01":
            before = {field: target.at[index, field] for field in ("start_time", "stop_time")}
            target.at[index, "start_time"], target.at[index, "stop_time"] = before["stop_time"], before["start_time"]
            after = {field: target.at[index, field] for field in before}
        elif variant == "CORR_TIME_02":
            before["lab_time"] = target.at[index, "lab_time"]
            visit_key = str(int(float(target.at[index, "visit_id"])))
            visit = tables["Visit"].loc[
                pd.to_numeric(tables["Visit"]["visit_id"], errors="coerce").astype("Int64").astype("string").eq(visit_key)
            ]
            discharge = pd.to_datetime(visit.iloc[0]["discharge_time"], errors="raise")
            target.at[index, "lab_time"] = (discharge + timedelta(hours=24)).isoformat(sep=" ")
            after["lab_time"] = target.at[index, "lab_time"]
        elif variant in {"CORR_REL_01", "CORR_REL_03"}:
            before["patient_id"] = target.at[index, "patient_id"]
            target.at[index, "patient_id"] = alternative_patient(debug_patients, int(before["patient_id"]), event_id)
            after["patient_id"] = target.at[index, "patient_id"]
        elif variant in {"CORR_DUP_01", "CORR_DUP_02"}:
            copied = target.loc[index].copy()
            secondary_id = f"INJ_{variant}_{ordinal:07d}"
            before["__ROW__"] = "source row retained"
            copied[row_id] = secondary_id
            if variant == "CORR_DUP_02":
                before["result_value"] = copied["result_value"]
                copied["result_value"] = str(float(copied["result_value"]) * 1.01)
                after["result_value"] = copied["result_value"]
            target.loc[len(target)] = copied
            after["__ROW__"] = "injected duplicate row"
        elif variant == "CORR_UNIT_02":
            source_unit = text(target.at[index, "unit"])
            paired_unit, _factor = UNIT_PAIRS[source_unit]
            before = {"result_value": target.at[index, "result_value"], "unit": source_unit}
            # Deliberately retain the numeric value while replacing the unit with
            # its frozen scalable pair; this is a reproducible unit-scale mismatch.
            target.at[index, "unit"] = paired_unit
            after = {"result_value": target.at[index, "result_value"], "unit": paired_unit}
        else:
            raise ValueError(f"Unsupported or not-applicable variant: {variant}")
        events.append({"event_id": event_id, "variant_id": variant, "table_name": domain, "record_id": original_id, "secondary_record_id": secondary_id, "expected_behavior": EXPECTED[variant], "before_json": json.dumps(before, ensure_ascii=False, default=text), "after_json": json.dumps(after, ensure_ascii=False, default=text)})
    return events


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--variant", required=True, choices=sorted(EXPECTED))
    parser.add_argument("--rate", type=int, required=True, choices=[5, 10, 20, 30, 40])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--partition", choices=["DEBUG", "HELDOUT"], default="DEBUG")
    parser.add_argument("--execute", action="store_true", help="Required to write materialized data.")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("Refusing to write: rerun with --execute after engineering review.")
    plan_path = args.plan_dir / f"{args.variant}_{args.partition.lower()}_rate{args.rate:02d}_plan.csv"
    plan = pd.read_csv(plan_path, dtype=str)
    mapped, protocol = args.base / "mapped", args.base / "protocol"
    partition = pd.read_csv(protocol / "mimic_demo_patient_partition_v1_1.csv")
    target_ids = set(partition.loc[partition["partition"].eq(args.partition), "patient_id"].astype(int))
    tables = {domain: pd.read_csv(mapped / f"mimic_{stem}_clean_reference.csv", low_memory=False) for domain, stem in TABLE_FILES.items()}
    tables["Medication"].insert(0, "medication_event_id", [f"MIMICMED_{i:08d}" for i in range(1, len(tables["Medication"]) + 1)])
    tables = {domain: frame.loc[frame["patient_id"].isin(target_ids)].copy() for domain, frame in tables.items()}
    clean = {domain: frame.copy() for domain, frame in tables.items()}
    events = materialize(tables, args.variant, plan)
    if args.output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite condition directory: {args.output_dir}")
    write_tables(args.output_dir / "clean_reference", clean)
    write_tables(args.output_dir / "operational_input", tables)
    gt = args.output_dir / "ground_truth"
    gt.mkdir(parents=True)
    pd.DataFrame(events).to_csv(gt / "injected_event_truth.csv", index=False, encoding="utf-8-sig")
    (args.output_dir / "materialization_manifest.json").write_text(json.dumps({"partition": args.partition, "variant_id": args.variant, "rate_pct": args.rate, "event_count": len(events), "execution": "materialized"}, indent=2), encoding="utf-8")
    print(f"Materialized {len(events)} events in {args.output_dir}")


if __name__ == "__main__":
    main()
