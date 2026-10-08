from pathlib import Path
import argparse
import json
import math
import os
from collections import defaultdict

import numpy as np
import pandas as pd


# ============================================================
# HIS SYNTHETIC BENCHMARK V1.3
# PHASE 4A-5 - FINAL UNIVERSAL EVALUATOR
# Serial-action attribution correction: excludes a validated second-stage
# CORRECT action when the same injected cell was already matched to a prior
# action group and the final state is valid.  V3 cleaning logic is unchanged.
# ============================================================

TABLE_INFO = {
    "Patient": {"file": "patient.csv", "pk": "patient_id"},
    "Visit": {"file": "visit.csv", "pk": "visit_id"},
    "Diagnosis": {"file": "diagnosis.csv", "pk": "diagnosis_id"},
    "Laboratory": {"file": "laboratory.csv", "pk": "lab_id"},
    "Medication": {"file": "medication.csv", "pk": "medication_event_id"},
    "Examination": {"file": "examination.csv", "pk": "examination_id"},
}

VALID_ACTIONS = {
    "CORRECT",
    "STANDARDIZE",
    "FLAG",
    "REMOVE_DUPLICATE",
    "ABSTAIN",
}

REQUIRED_ACTION_LOG_COLUMNS = [
    "method_name",
    "action_group_id",
    "table_name",
    "record_id",
    "secondary_record_id",
    "field_name",
    "action_type",
    "before_value",
    "after_value",
    "confidence",
    "reason_code",
]


# ============================================================
# HELPERS
# ============================================================

def normalize_value(value):
    if value is None:
        return "<NA>"

    try:
        if pd.isna(value):
            return "<NA>"
    except Exception:
        pass

    text = str(value).strip()

    if text in {
        "",
        "<NA>",
        "nan",
        "NaN",
        "None",
        "NULL",
        "null",
    }:
        return "<NA>"

    return text


def values_equal(a, b):
    a = normalize_value(a)
    b = normalize_value(b)

    if a == b:
        return True

    if a == "<NA>" or b == "<NA>":
        return False

    try:
        fa = float(a)
        fb = float(b)

        if np.isfinite(fa) and np.isfinite(fb):
            return math.isclose(
                fa,
                fb,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )

    except Exception:
        pass

    return False


def safe_div(num, den):
    if den == 0:
        return np.nan

    return num / den


def safe_div_zero(num, den):
    """
    Zero-division convention for event-classification metrics.
    If there are no predicted positives, Precision is reported as 0.0.
    This keeps NO_CLEANING and other zero-prediction baselines comparable.
    """
    if den == 0:
        return 0.0

    return num / den


def harmonic_mean_zero(p, r):
    """
    F1 convention: if Precision + Recall == 0, report 0.0.
    """
    if pd.isna(p) or pd.isna(r):
        return 0.0

    if p + r == 0:
        return 0.0

    return 2 * p * r / (p + r)


def ensure_action_log_schema(df):
    missing = [
        c
        for c in REQUIRED_ACTION_LOG_COLUMNS
        if c not in df.columns
    ]

    if missing:
        raise RuntimeError(
            "action_log.csv missing required columns: "
            + ", ".join(missing)
        )

    if len(df) == 0:
        return

    invalid_actions = sorted(
        set(df["action_type"].astype(str))
        -
        VALID_ACTIONS
    )

    if invalid_actions:
        raise RuntimeError(
            "Invalid action_type values: "
            + ", ".join(invalid_actions)
        )

    if (
        df["action_group_id"]
        .astype(str)
        .eq("")
        .any()
    ):
        raise RuntimeError(
            "action_group_id cannot be blank."
        )


def action_compatible(
    predicted_action,
    expected_action,
):
    predicted_action = str(predicted_action)
    expected_action = str(expected_action)

    if expected_action == "FLAG_ONLY":
        return predicted_action in {
            "FLAG",
            "ABSTAIN",
        }

    if expected_action == "REMOVE_DUPLICATE":
        return (
            predicted_action
            ==
            "REMOVE_DUPLICATE"
        )

    if expected_action == "ABSTAIN":
        return predicted_action in {
            "ABSTAIN",
            "FLAG",
        }

    if expected_action in {
        "CORRECT",
        "STANDARDIZE",
    }:
        # Event detection is intentionally broader than repair:
        # flag/abstain can detect a problem but will not receive
        # recovery/edit credit.
        return predicted_action in {
            "CORRECT",
            "STANDARDIZE",
            "FLAG",
            "ABSTAIN",
        }

    return False


def build_action_indices(action_log):
    """
    Efficient indices for event matching.
    """
    groups = {
        str(gid): group.copy()
        for gid, group
        in action_log.groupby(
            "action_group_id",
            sort=False,
        )
    }

    cell_index = defaultdict(list)
    row_index = defaultdict(list)

    for row in action_log.itertuples(index=False):

        gid = str(row.action_group_id)
        table = str(row.table_name)
        rid = str(row.record_id)
        srid = str(row.secondary_record_id)
        field = str(row.field_name)

        if field == "__ROW__" or str(row.action_type) == "REMOVE_DUPLICATE":

            if rid:
                row_index[
                    (table, rid)
                ].append(gid)

            if srid:
                row_index[
                    (table, srid)
                ].append(gid)

        else:

            cell_index[
                (
                    table,
                    rid,
                    field,
                )
            ].append(gid)

    return groups, cell_index, row_index


def match_events(
    event_gt,
    groups,
    cell_index,
    row_index,
):
    event_to_group = {}
    used_groups = set()

    for row in event_gt.itertuples(index=False):

        eid = str(row.corruption_event_id)
        table = str(row.table_name)
        rid = str(row.record_id)
        srid = str(row.secondary_record_id)
        field = str(row.field_name)
        second_field = str(row.secondary_field_name)
        expected_action = str(row.expected_action)

        candidate_groups = []

        if field == "__ROW__":

            for key_id in [rid, srid]:

                if not key_id:
                    continue

                candidate_groups.extend(
                    row_index.get(
                        (table, key_id),
                        [],
                    )
                )

        else:

            candidate_groups.extend(
                cell_index.get(
                    (table, rid, field),
                    [],
                )
            )

            if second_field:

                candidate_groups.extend(
                    cell_index.get(
                        (
                            table,
                            rid,
                            second_field,
                        ),
                        [],
                    )
                )

        # Preserve deterministic first-seen order while deduplicating.
        seen = set()
        ordered_candidates = []

        for gid in candidate_groups:

            if gid not in seen:

                seen.add(gid)
                ordered_candidates.append(gid)

        for gid in ordered_candidates:

            if gid in used_groups:
                continue

            group = groups[gid]

            compatible = (
                group["action_type"]
                .astype(str)
                .map(
                    lambda x:
                    action_compatible(
                        x,
                        expected_action,
                    )
                )
                .any()
            )

            if not compatible:
                continue

            event_to_group[eid] = gid
            used_groups.add(gid)

            break

    return event_to_group, used_groups


def collect_needed_states(
    state_gt,
    negative_sample,
    event_gt,
):
    """
    Build a compact per-table request:
    - needed scalar record/field states
    - needed duplicate record existence checks
    """
    needed_fields = defaultdict(
        lambda: defaultdict(set)
    )

    needed_ids = defaultdict(set)

    for row in state_gt.itertuples(index=False):

        table = str(row.table_name)
        rid = str(row.record_id)
        field = str(row.field_name)

        if field == "__ROW__":
            needed_ids[table].add(rid)
            continue

        needed_fields[table][rid].add(field)
        needed_ids[table].add(rid)

    for row in negative_sample.itertuples(index=False):

        table = str(row.table_name)
        rid = str(row.record_id)
        field = str(row.field_name)

        needed_fields[table][rid].add(field)
        needed_ids[table].add(rid)

    dup_events = event_gt[
        event_gt["expected_action"].eq(
            "REMOVE_DUPLICATE"
        )
    ]

    for row in dup_events.itertuples(index=False):

        table = str(row.table_name)
        rid = str(row.record_id)
        srid = str(row.secondary_record_id)

        if rid:
            needed_ids[table].add(rid)

        if srid:
            needed_ids[table].add(srid)

    return needed_fields, needed_ids


def load_cleaned_context(
    cleaned_dir,
    needed_fields,
    needed_ids,
):
    """
    Read each cleaned table once.
    Stores only requested rows/fields and existence status.
    """
    values = defaultdict(dict)
    existing_ids = defaultdict(set)

    for table in set(
        list(needed_fields.keys())
        +
        list(needed_ids.keys())
    ):

        info = TABLE_INFO[table]
        path = cleaned_dir / info["file"]

        if not path.exists():
            raise FileNotFoundError(path)

        pk = info["pk"]
        requested_ids = set(
            needed_ids.get(
                table,
                set(),
            )
        )

        field_union = set()

        for fields in (
            needed_fields.get(
                table,
                {}
            ).values()
        ):
            field_union.update(fields)

        header = pd.read_csv(
            path,
            nrows=0,
        ).columns.tolist()

        missing_fields = [
            f
            for f in field_union
            if f not in header
        ]

        # A missing field is allowed at evaluation time:
        # the evaluator will count those sampled/GT states as incorrect.
        read_fields = [
            f
            for f in field_union
            if f in header
        ]

        usecols = [pk] + read_fields

        for chunk in pd.read_csv(
            path,
            usecols=usecols,
            dtype=str,
            keep_default_na=False,
            chunksize=200_000,
        ):

            mask = (
                chunk[pk]
                .astype(str)
                .isin(
                    requested_ids
                )
            )

            if not mask.any():
                continue

            subset = chunk.loc[mask]

            for record in (
                subset.to_dict(
                    orient="records"
                )
            ):

                rid = str(record[pk])
                existing_ids[table].add(rid)
                values[table][rid] = record

        # No error is thrown for missing requested rows:
        # absence is an evaluable outcome.

    return values, existing_ids


def accepted_final_value(
    final_value,
    source_target,
    canonical_target,
):
    return (
        values_equal(
            final_value,
            source_target,
        )
        or
        values_equal(
            final_value,
            canonical_target,
        )
    )


def infer_benchmark_root(gt_dir):
    """
    Expected GT paths:
      .../phase3_development/seed_x/corruption_xx/ground_truth
      .../phase3_final_test/seed_x/corruption_xx/ground_truth
    """
    p = Path(gt_dir).resolve()

    for parent in [p] + list(p.parents):
        if parent.name == "HIS_Synthetic_Dataset_V1_3_REALITY_CALIBRATED":
            return parent

    raise RuntimeError(
        "Could not infer benchmark root from gt_dir."
    )


def load_reference_cells_for_standardizations(
    benchmark_root,
    standardize_rows,
):
    """
    Load only the source_valid / canonical cells touched by unmatched
    STANDARDIZE actions. This is evaluator-only reference access and is
    never exposed to the cleaning method.
    """
    if len(standardize_rows) == 0:
        return {}

    requests = defaultdict(
        lambda: defaultdict(set)
    )

    for row in standardize_rows.itertuples(index=False):
        table = str(row.table_name)
        rid = str(row.record_id)
        field = str(row.field_name)

        if table not in TABLE_INFO:
            continue

        if field == "__ROW__":
            continue

        requests[table][rid].add(field)

    result = {}

    for table, id_map in requests.items():
        info = TABLE_INFO[table]
        pk = info["pk"]

        source_path = (
            benchmark_root
            / "source_valid"
            / info["file"]
        )

        canonical_path = (
            benchmark_root
            / "canonical_reference"
            / info["file"]
        )

        requested_ids = set(id_map.keys())

        fields = set()
        for fs in id_map.values():
            fields.update(fs)

        source_header = pd.read_csv(
            source_path,
            nrows=0,
        ).columns.tolist()

        canonical_header = pd.read_csv(
            canonical_path,
            nrows=0,
        ).columns.tolist()

        usable_fields = [
            f
            for f in fields
            if (
                f in source_header
                and
                f in canonical_header
            )
        ]

        usecols = [pk] + usable_fields

        source_map = {}
        canonical_map = {}

        for chunk in pd.read_csv(
            source_path,
            usecols=usecols,
            dtype=str,
            keep_default_na=False,
            chunksize=200_000,
        ):
            mask = (
                chunk[pk]
                .astype(str)
                .isin(requested_ids)
            )

            if not mask.any():
                continue

            for rec in (
                chunk.loc[mask]
                .to_dict(orient="records")
            ):
                source_map[str(rec[pk])] = rec

        for chunk in pd.read_csv(
            canonical_path,
            usecols=usecols,
            dtype=str,
            keep_default_na=False,
            chunksize=200_000,
        ):
            mask = (
                chunk[pk]
                .astype(str)
                .isin(requested_ids)
            )

            if not mask.any():
                continue

            for rec in (
                chunk.loc[mask]
                .to_dict(orient="records")
            ):
                canonical_map[str(rec[pk])] = rec

        for rid, fields_for_rid in id_map.items():
            srec = source_map.get(rid)
            crec = canonical_map.get(rid)

            if srec is None or crec is None:
                continue

            for field in fields_for_rid:
                if (
                    field not in srec
                    or
                    field not in crec
                ):
                    continue

                result[
                    (table, rid, field)
                ] = {
                    "source_valid_value":
                        srec[field],
                    "canonical_target_value":
                        crec[field],
                }

    return result


# ============================================================
# MAIN EVALUATION
# ============================================================

def evaluate(
    gt_dir,
    cleaned_dir,
    action_log_path,
    negative_sample_path,
    output_dir,
    method_name,
):

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    event_gt = pd.read_csv(
        gt_dir / "event_gt.csv",
        dtype=str,
        keep_default_na=False,
    )

    state_gt = pd.read_csv(
        gt_dir / "state_gt.csv",
        dtype=str,
        keep_default_na=False,
    )

    action_log = pd.read_csv(
        action_log_path,
        dtype=str,
        keep_default_na=False,
    )

    negative_sample = pd.read_csv(
        negative_sample_path,
        dtype=str,
        keep_default_na=False,
    )

    ensure_action_log_schema(
        action_log
    )

    if len(action_log) > 0:

        unique_methods = (
            action_log["method_name"]
            .astype(str)
            .unique()
        )

        if len(unique_methods) != 1:

            raise RuntimeError(
                "action_log.csv must contain exactly "
                "one method_name when non-empty."
            )

        if str(unique_methods[0]) != method_name:

            raise RuntimeError(
                f"method_name mismatch: "
                f"CLI={method_name}, "
                f"action_log={unique_methods[0]}"
            )

    # --------------------------------------------------------
    # Event-level matching
    # --------------------------------------------------------

    (
        groups,
        cell_index,
        row_index,
    ) = build_action_indices(
        action_log
    )

    (
        event_to_group,
        used_groups,
    ) = match_events(
        event_gt,
        groups,
        cell_index,
        row_index,
    )

    tp = len(event_to_group)
    fn = len(event_gt) - tp

    # --------------------------------------------------------
    # Load only needed cleaned states
    # --------------------------------------------------------

    (
        needed_fields,
        needed_ids,
    ) = collect_needed_states(
        state_gt,
        negative_sample,
        event_gt,
    )

    # Unmatched legitimate STANDARDIZE actions may target untouched
    # source-valid cells that are absent from State GT and the frozen
    # negative-state sample. Add every STANDARDIZE target to the compact
    # cleaned-state request so the evaluator can validate its final value.
    for row in action_log[
        action_log["action_type"].eq("STANDARDIZE")
    ].itertuples(index=False):

        table = str(row.table_name)
        rid = str(row.record_id)
        field = str(row.field_name)

        if (
            table in TABLE_INFO
            and
            field != "__ROW__"
        ):
            needed_fields[table][rid].add(field)
            needed_ids[table].add(rid)

    (
        cleaned_values,
        existing_ids,
    ) = load_cleaned_context(
        cleaned_dir,
        needed_fields,
        needed_ids,
    )

    # --------------------------------------------------------
    # Legitimate unmatched STANDARDIZE actions
    # --------------------------------------------------------
    #
    # Per frozen Phase 4A-1 definition, an unmatched prediction is FP
    # only when it is not a justified canonical standardization.
    #
    unmatched_group_ids_initial = (
        set(groups.keys())
        -
        used_groups
    )

    unmatched_standardize_rows = (
        action_log[
            action_log[
                "action_group_id"
            ]
            .astype(str)
            .isin(
                unmatched_group_ids_initial
            )
            &
            action_log[
                "action_type"
            ].eq(
                "STANDARDIZE"
            )
        ]
        .copy()
    )

    benchmark_root = infer_benchmark_root(
        gt_dir
    )

    reference_cells = (
        load_reference_cells_for_standardizations(
            benchmark_root,
            unmatched_standardize_rows,
        )
    )

    corrupted_state_keys = set(
        zip(
            state_gt["table_name"].astype(str),
            state_gt["record_id"].astype(str),
            state_gt["field_name"].astype(str),
        )
    )

    legitimate_standardize_groups = set()

    for gid, group in (
        unmatched_standardize_rows.groupby(
            "action_group_id",
            sort=False,
        )
    ):
        gid = str(gid)
        group_ok = True
        saw_standardize = False

        for row in group.itertuples(index=False):
            if str(row.action_type) != "STANDARDIZE":
                group_ok = False
                break

            saw_standardize = True

            table = str(row.table_name)
            rid = str(row.record_id)
            field = str(row.field_name)

            key = (table, rid, field)

            if key in corrupted_state_keys:
                group_ok = False
                break

            ref = reference_cells.get(key)

            if ref is None:
                group_ok = False
                break

            source_value = ref["source_valid_value"]
            canonical_value = ref["canonical_target_value"]

            if values_equal(
                source_value,
                canonical_value,
            ):
                group_ok = False
                break

            if not values_equal(
                row.before_value,
                source_value,
            ):
                group_ok = False
                break

            cleaned_record = (
                cleaned_values
                .get(table, {})
                .get(rid)
            )

            if (
                cleaned_record is None
                or
                field not in cleaned_record
            ):
                group_ok = False
                break

            if not values_equal(
                cleaned_record[field],
                canonical_value,
            ):
                group_ok = False
                break

        if saw_standardize and group_ok:
            legitimate_standardize_groups.add(gid)

    # A single injected state can legitimately require two sequential actions
    # (for example M1 lexical normalization followed by M2 code-supported
    # semantic canonicalization).  The original evaluator matched the first
    # group to the event, then counted the second group as a false-positive
    # edit despite the final cell being correct.  Exclude only a narrow,
    # auditable class: a non-row group containing CORRECT actions only, where
    # every touched cell belongs to an already matched group and its final
    # value satisfies that State-GT cell.
    state_map_for_serial = {
        (str(row.table_name), str(row.record_id), str(row.field_name)): row
        for row in state_gt.itertuples(index=False)
    }
    matched_cell_keys = set()
    for matched_gid in used_groups:
        for row in groups[str(matched_gid)].itertuples(index=False):
            if str(row.field_name) != "__ROW__":
                matched_cell_keys.add(
                    (str(row.table_name), str(row.record_id), str(row.field_name))
                )

    serial_followup_groups = set()
    for gid, group in groups.items():
        if gid in used_groups:
            continue
        group_ok = True
        saw_action = False
        for row in group.itertuples(index=False):
            if str(row.action_type) != "CORRECT" or str(row.field_name) == "__ROW__":
                group_ok = False
                break
            saw_action = True
            key = (str(row.table_name), str(row.record_id), str(row.field_name))
            state_row = state_map_for_serial.get(key)
            record = cleaned_values.get(key[0], {}).get(key[1])
            if (
                key not in matched_cell_keys
                or state_row is None
                or record is None
                or key[2] not in record
                or not accepted_final_value(
                    record[key[2]],
                    state_row.source_valid_value,
                    state_row.canonical_target_value,
                )
            ):
                group_ok = False
                break
        if saw_action and group_ok:
            serial_followup_groups.add(gid)

    fp_group_ids = (
        unmatched_group_ids_initial
        -
        legitimate_standardize_groups
        -
        serial_followup_groups
    )

    fp = len(fp_group_ids)

    precision = safe_div_zero(
        tp,
        tp + fp,
    )

    recall = safe_div_zero(
        tp,
        tp + fn,
    )

    f1 = harmonic_mean_zero(
        precision,
        recall,
    )

    # --------------------------------------------------------
    # Scalar recovery metrics
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # RecoveryAcc and PostCleanCellAcc are evaluated only on
    # auto-repairable scalar states (CORRECT/STANDARDIZE).
    # FLAG_ONLY / ABSTAIN states are assessed via FlagSafety.
    # Row duplicates are assessed via DupRecall.
    # --------------------------------------------------------

    repairable_states = state_gt[
        state_gt["field_name"].ne("__ROW__")
        &
        state_gt["expected_action"].isin(
            {
                "CORRECT",
                "STANDARDIZE",
            }
        )
    ].copy()

    recovered_cells = 0

    for row in repairable_states.itertuples(index=False):

        table = str(row.table_name)
        rid = str(row.record_id)
        field = str(row.field_name)

        record = (
            cleaned_values
            .get(
                table,
                {}
            )
            .get(
                rid
            )
        )

        if record is None:
            continue

        if field not in record:
            continue

        final_value = record[field]

        if accepted_final_value(
            final_value,
            row.source_valid_value,
            row.canonical_target_value,
        ):
            recovered_cells += 1

    recovery_accuracy = safe_div(
        recovered_cells,
        len(repairable_states),
    )

    # --------------------------------------------------------
    # Duplicate recall
    # --------------------------------------------------------

    duplicate_events = event_gt[
        event_gt["expected_action"].eq(
            "REMOVE_DUPLICATE"
        )
    ]

    correctly_removed_duplicates = 0

    for row in duplicate_events.itertuples(index=False):

        table = str(row.table_name)
        original_id = str(row.record_id)
        duplicate_id = str(row.secondary_record_id)

        original_exists = (
            original_id
            in
            existing_ids.get(
                table,
                set(),
            )
        )

        duplicate_exists = (
            duplicate_id
            in
            existing_ids.get(
                table,
                set(),
            )
        )

        if (
            original_exists
            and
            not duplicate_exists
        ):
            correctly_removed_duplicates += 1

    duplicate_recall = safe_div(
        correctly_removed_duplicates,
        len(duplicate_events),
    )

    # --------------------------------------------------------
    # FLAG_ONLY safety
    # --------------------------------------------------------

    matched_group_lookup = {
        eid: groups[gid]
        for eid, gid
        in event_to_group.items()
    }

    flag_only_events = event_gt[
        event_gt["expected_action"].eq(
            "FLAG_ONLY"
        )
    ]

    safely_handled_flag_only = 0

    for row in flag_only_events.itertuples(index=False):

        eid = str(row.corruption_event_id)

        group = matched_group_lookup.get(
            eid
        )

        if group is None:
            continue

        unsafe_edit = (
            group["action_type"]
            .isin(
                {
                    "CORRECT",
                    "STANDARDIZE",
                    "REMOVE_DUPLICATE",
                }
            )
            .any()
        )

        safe_signal = (
            group["action_type"]
            .isin(
                {
                    "FLAG",
                    "ABSTAIN",
                }
            )
            .any()
        )

        if (
            safe_signal
            and
            not unsafe_edit
        ):
            safely_handled_flag_only += 1

    flag_safety = safe_div(
        safely_handled_flag_only,
        len(flag_only_events),
    )

    # --------------------------------------------------------
    # Edit precision / FCR
    # --------------------------------------------------------

    edit_rows = action_log[
        action_log["action_type"].isin(
            {
                "CORRECT",
                "STANDARDIZE",
                "REMOVE_DUPLICATE",
            }
        )
    ].copy()

    matched_group_ids = set(
        event_to_group.values()
    )

    correct_edits = 0
    incorrect_edits = 0

    # Build state lookup.
    state_map = {}

    for row in state_gt.itertuples(index=False):

        state_map[
            (
                str(row.table_name),
                str(row.record_id),
                str(row.field_name),
            )
        ] = row

    for row in edit_rows.itertuples(index=False):

        gid = str(row.action_group_id)

        if gid not in matched_group_ids:
            if gid in serial_followup_groups:
                continue
            if (
                str(row.action_type) == "STANDARDIZE"
                and
                gid in legitimate_standardize_groups
            ):
                correct_edits += 1
            else:
                incorrect_edits += 1

            continue

        table = str(row.table_name)
        rid = str(row.record_id)
        srid = str(row.secondary_record_id)
        field = str(row.field_name)
        action_type = str(row.action_type)

        if action_type == "REMOVE_DUPLICATE":

            target_id = (
                srid
                if srid
                else rid
            )

            removed = (
                target_id
                not in
                existing_ids.get(
                    table,
                    set(),
                )
            )

            if removed:
                correct_edits += 1
            else:
                incorrect_edits += 1

            continue

        state_row = state_map.get(
            (
                table,
                rid,
                field,
            )
        )

        if state_row is None:
            incorrect_edits += 1
            continue

        record = (
            cleaned_values
            .get(
                table,
                {}
            )
            .get(
                rid
            )
        )

        if (
            record is None
            or
            field not in record
        ):
            incorrect_edits += 1
            continue

        final_value = record[field]

        if accepted_final_value(
            final_value,
            state_row.source_valid_value,
            state_row.canonical_target_value,
        ):
            correct_edits += 1
        else:
            incorrect_edits += 1

    all_executed_edits = (
        correct_edits
        +
        incorrect_edits
    )

    edit_precision = safe_div(
        correct_edits,
        all_executed_edits,
    )

    false_correction_rate = safe_div(
        incorrect_edits,
        all_executed_edits,
    )

    # --------------------------------------------------------
    # Abstention rate
    # --------------------------------------------------------

    predicted_action_groups = len(groups)

    abstain_groups = (
        action_log[
            action_log["action_type"].eq(
                "ABSTAIN"
            )
        ]["action_group_id"]
        .astype(str)
        .nunique()
    )

    abstention_rate = safe_div(
        abstain_groups,
        predicted_action_groups,
    )

    # --------------------------------------------------------
    # NER / collateral damage
    # --------------------------------------------------------

    newly_invalid = 0
    negative_evaluated = len(
        negative_sample
    )

    negative_trace_rows = []

    for row in negative_sample.itertuples(index=False):

        table = str(row.table_name)
        rid = str(row.record_id)
        field = str(row.field_name)

        record = (
            cleaned_values
            .get(
                table,
                {}
            )
            .get(
                rid
            )
        )

        if record is None:
            is_valid_after = False
            final_value = "__ROW_MISSING__"

        elif field not in record:
            is_valid_after = False
            final_value = "__FIELD_MISSING__"

        else:
            final_value = record[field]

            is_valid_after = (
                accepted_final_value(
                    final_value,
                    row.source_valid_value,
                    row.canonical_target_value,
                )
            )

        is_new_error = (
            not is_valid_after
        )

        if is_new_error:
            newly_invalid += 1

        negative_trace_rows.append({
            "sample_id":
                str(row.sample_id),

            "table_name":
                table,

            "record_id":
                rid,

            "field_name":
                field,

            "source_valid_value":
                str(
                    row.source_valid_value
                ),

            "canonical_target_value":
                str(
                    row.canonical_target_value
                ),

            "final_value":
                normalize_value(
                    final_value
                ),

            "is_new_error":
                bool(
                    is_new_error
                ),
        })

    new_error_rate = safe_div(
        newly_invalid,
        negative_evaluated,
    )

    # --------------------------------------------------------
    # Post-clean cell accuracy
    # --------------------------------------------------------
    #
    # Evaluated scalar-state universe:
    #   A) repairable corrupted scalar states (CORRECT/STANDARDIZE)
    #   B) frozen initially-valid negative-state sample
    #
    # FLAG_ONLY states are intentionally excluded because safe handling may
    # preserve the source anomaly while flagging it. Duplicate rows are also
    # excluded because they are evaluated through DupRecall.
    #
    # This makes PostCleanCellAcc distinct from RecoveryAcc:
    # RecoveryAcc asks "how many repairable corrupted cells were recovered?"
    # PostCleanCellAcc asks "how accurate is the final evaluated scalar-state
    # universe after cleaning, including collateral damage?"
    #
    post_clean_correct_cells = (
        recovered_cells
        +
        (
            negative_evaluated
            -
            newly_invalid
        )
    )

    post_clean_evaluated_cells = (
        len(repairable_states)
        +
        negative_evaluated
    )

    post_clean_cell_accuracy = safe_div(
        post_clean_correct_cells,
        post_clean_evaluated_cells,
    )

    # --------------------------------------------------------
    # Event trace / unmatched groups
    # --------------------------------------------------------
    # Optional storage control for batch re-evaluation.  This does not change
    # matching or any metric; it only suppresses large diagnostic CSV writes.
    write_traces = os.environ.get("HIS_EVALUATOR_SKIP_TRACES", "0") != "1"

    if write_traces:
        event_trace_rows = []

        for row in event_gt.itertuples(index=False):

            eid = str(row.corruption_event_id)
            gid = event_to_group.get(
                eid,
                "",
            )

            event_trace_rows.append({
                "corruption_event_id": eid,
                "variant_id": str(row.variant_id),
                "expected_action": str(row.expected_action),
                "matched": bool(gid),
                "matched_action_group_id": gid,
            })

        event_trace = pd.DataFrame(event_trace_rows)
        unmatched_df = pd.DataFrame({"action_group_id": sorted(fp_group_ids)})
        negative_trace = pd.DataFrame(negative_trace_rows)

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    metrics = pd.DataFrame([
        {
            "method_name": method_name,
            "metric": "TP",
            "value": tp,
        },
        {
            "method_name": method_name,
            "metric": "FP",
            "value": fp,
        },
        {
            "method_name": method_name,
            "metric": "LegitimateUnmatchedStandardizeGroups",
            "value": len(legitimate_standardize_groups),
        },
        {
            "method_name": method_name,
            "metric": "SerialFollowUpGroupsExcluded",
            "value": len(serial_followup_groups),
        },
        {
            "method_name": method_name,
            "metric": "FN",
            "value": fn,
        },
        {
            "method_name": method_name,
            "metric": "Precision",
            "value": precision,
        },
        {
            "method_name": method_name,
            "metric": "Recall",
            "value": recall,
        },
        {
            "method_name": method_name,
            "metric": "F1",
            "value": f1,
        },
        {
            "method_name": method_name,
            "metric": "CorrectEdits",
            "value": correct_edits,
        },
        {
            "method_name": method_name,
            "metric": "IncorrectEdits",
            "value": incorrect_edits,
        },
        {
            "method_name": method_name,
            "metric": "EditPrecision",
            "value": edit_precision,
        },
        {
            "method_name": method_name,
            "metric": "FCR",
            "value": false_correction_rate,
        },
        {
            "method_name": method_name,
            "metric": "NewlyInvalidNegativeStates",
            "value": newly_invalid,
        },
        {
            "method_name": method_name,
            "metric": "NegativeStatesEvaluated",
            "value": negative_evaluated,
        },
        {
            "method_name": method_name,
            "metric": "NER",
            "value": new_error_rate,
        },
        {
            "method_name": method_name,
            "metric": "PostCleanCorrectCells",
            "value": post_clean_correct_cells,
        },
        {
            "method_name": method_name,
            "metric": "PostCleanEvaluatedCells",
            "value": post_clean_evaluated_cells,
        },
        {
            "method_name": method_name,
            "metric": "PostCleanCellAcc",
            "value": post_clean_cell_accuracy,
        },
        {
            "method_name": method_name,
            "metric": "AbstentionRate",
            "value": abstention_rate,
        },
        {
            "method_name": method_name,
            "metric": "FlagSafety",
            "value": flag_safety,
        },
        {
            "method_name": method_name,
            "metric": "DupRecall",
            "value": duplicate_recall,
        },
        {
            "method_name": method_name,
            "metric": "RecoveryAcc",
            "value": recovery_accuracy,
        },
    ])

    metrics.to_csv(
        output_dir
        / "evaluation_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if write_traces:
        event_trace.to_csv(
            output_dir / "event_matching_trace.csv",
            index=False,
            encoding="utf-8-sig",
        )
        unmatched_df.to_csv(
            output_dir / "unmatched_action_groups.csv",
            index=False,
            encoding="utf-8-sig",
        )
        negative_trace.to_csv(
            output_dir / "negative_state_evaluation_trace.csv",
            index=False,
            encoding="utf-8-sig",
        )

    summary = {
        "method_name":
            method_name,

        "gt_events":
            int(
                len(event_gt)
            ),

        "predicted_action_groups":
            int(
                predicted_action_groups
            ),

        "matched_gt_events":
            int(
                tp
            ),

        "unmatched_gt_events":
            int(
                fn
            ),

        "unmatched_action_groups":
            int(
                fp
            ),

        "legitimate_unmatched_standardize_groups":
            int(
                len(
                    legitimate_standardize_groups
                )
            ),

        "repairable_scalar_states":
            int(
                len(
                    repairable_states
                )
            ),

        "recovered_scalar_states":
            int(
                recovered_cells
            ),

        "negative_states_evaluated":
            int(
                negative_evaluated
            ),

        "newly_invalid_negative_states":
            int(
                newly_invalid
            ),

        "protocol_note":
            (
                "RecoveryAcc evaluates only CORRECT/STANDARDIZE corrupted "
                "scalar states. PostCleanCellAcc combines those repairable "
                "states with the frozen initially-valid negative-state sample. "
                "FLAG_ONLY is evaluated by FlagSafety; duplicates by DupRecall."
            ),
    }

    with open(
        output_dir
        / "evaluation_summary.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("=" * 125)
    print("PHASE 4A-5 FINAL UNIVERSAL EVALUATOR")
    print("=" * 125)

    print(
        metrics.to_string(
            index=False
        )
    )

    print("\nEvaluation outputs:")
    print(output_dir)

    print("=" * 125)


# ============================================================
# CLI
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Final universal evaluator for "
            "HIS Synthetic Benchmark V1.3"
        )
    )

    parser.add_argument(
        "--gt-dir",
        required=True,
    )

    parser.add_argument(
        "--cleaned-dir",
        required=True,
    )

    parser.add_argument(
        "--action-log",
        required=True,
    )

    parser.add_argument(
        "--negative-sample",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    parser.add_argument(
        "--method-name",
        required=True,
    )

    args = parser.parse_args()

    evaluate(
        gt_dir=Path(
            args.gt_dir
        ),

        cleaned_dir=Path(
            args.cleaned_dir
        ),

        action_log_path=Path(
            args.action_log
        ),

        negative_sample_path=Path(
            args.negative_sample
        ),

        output_dir=Path(
            args.output_dir
        ),

        method_name=str(
            args.method_name
        ),
    )


if __name__ == "__main__":
    main()
