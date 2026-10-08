from pathlib import Path
import argparse
from collections import defaultdict
from difflib import SequenceMatcher
import shutil

import numpy as np
import pandas as pd


# =============================================================================
# HIS Synthetic Benchmark V1.3
# Phase 4C-3 - Full Cleaning Framework V2
# DEV seed = 20260922
# corruption = 5%
# =============================================================================

BASE = Path(r"D:\发四区")

ROOT = (
    BASE
    / "HIS_Synthetic_Dataset_V1_3_REALITY_CALIBRATED"
)

parser = argparse.ArgumentParser(description="Run frozen FULL_FRAMEWORK_V3 for a DEV corruption rate.")
parser.add_argument("--seed", type=int, required=True, choices=[42, 142, 242, 342, 442])
parser.add_argument("--rate", type=int, required=True, choices=[5, 10, 20, 30, 40])
args = parser.parse_args()
SEED = args.seed
RATE = args.rate

COND = (
    ROOT
    / "phase3_final_test"
    / f"seed_{SEED}"
    / f"corruption_{RATE:02d}"
)

INPUT = COND / "operational_input"

CANONICAL = (
    ROOT
    / "canonical_reference"
)

OUT = (
    ROOT
    / "phase4_results"
    / "final_test"
    / f"seed_{SEED}"
    / f"corruption_{RATE:02d}"
    / "FULL_FRAMEWORK_V3"
)

CLEANED = OUT / "cleaned"

ACTION_LOG = (
    OUT
    / "action_log.csv"
)

MODULE_SUMMARY = (
    OUT
    / "module_summary.csv"
)

CLEANED.mkdir(
    parents=True,
    exist_ok=True,
)

METHOD = "FULL_FRAMEWORK_V3"


# =============================================================================
# Parameters frozen on DEV
# =============================================================================

FUZZY_SIM_THRESHOLD = 0.95
FUZZY_FREQ_RATIO = 5.0
FUZZY_MAX_LEN_DIFF = 5

ROBUST_Z_THRESHOLD = 6.0
MIN_STAT_GROUP_SIZE = 30

MISSING_GROUP_MIN_N = 30
MISSING_PRESENT_RATE = 0.98

# Conservative medication semantic context detector
MED_CONTEXT_MIN_GROUP = 100
MED_CONTEXT_DOMINANCE = 0.80


# =============================================================================
# Action log
# =============================================================================

ACTION_COLUMNS = [
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
    "module_id",
]

actions = []

module_counts = defaultdict(int)

action_counter = 0


# =============================================================================
# Helpers
# =============================================================================

def norm(v):

    if v is None:
        return ""

    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass

    s = str(v).strip()

    if s in {
        "",
        "nan",
        "NaN",
        "None",
        "NULL",
        "null",
        "<NA>",
    }:
        return ""

    return s


def lower(v):

    return norm(v).lower()


def is_missing(v):

    return norm(v) == ""


def same(a, b):

    return norm(a) == norm(b)


def similarity(a, b):

    return SequenceMatcher(
        None,
        lower(a),
        lower(b),
    ).ratio()


def next_action_id():

    global action_counter

    action_counter += 1

    return (
        f"FW2_"
        f"{action_counter:09d}"
    )


def add_action(
    table_name,
    record_id,
    field_name,
    action_type,
    before_value,
    after_value,
    confidence,
    reason_code,
    module_id,
    secondary_record_id="",
):

    actions.append({

        "method_name":
            METHOD,

        "action_group_id":
            next_action_id(),

        "table_name":
            table_name,

        "record_id":
            str(record_id),

        "secondary_record_id":
            str(
                secondary_record_id
            ),

        "field_name":
            field_name,

        "action_type":
            action_type,

        "before_value":
            norm(
                before_value
            ),

        "after_value":
            norm(
                after_value
            ),

        "confidence":
            (
                ""
                if confidence is None
                else
                f"{float(confidence):.6f}"
            ),

        "reason_code":
            reason_code,

        "module_id":
            module_id,
    })

    module_counts[
        module_id
    ] += 1


def load_csv(path):

    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )


def save_csv(df, path):

    df.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )


def find_col(
    df,
    candidates,
    required=False,
):

    for col in candidates:

        if col in df.columns:

            return col

    if required:

        raise KeyError(
            "Required column not found: "
            f"{candidates}\n"
            f"Available columns:\n"
            f"{list(df.columns)}"
        )

    return None


def unique_map(
    df,
    key_col,
    value_col,
):

    if (
        key_col is None
        or
        value_col is None
    ):
        return {}

    x = df[
        [
            key_col,
            value_col,
        ]
    ].copy()

    x[
        key_col
    ] = x[
        key_col
    ].map(norm)

    x[
        value_col
    ] = x[
        value_col
    ].map(norm)

    x = x[
        x[key_col].ne("")
        &
        x[value_col].ne("")
    ].drop_duplicates()

    result = {}

    for key, group in x.groupby(
        key_col
    ):

        values = sorted(
            set(
                group[
                    value_col
                ]
            )
        )

        if len(values) == 1:

            result[
                key
            ] = values[0]

    return result


def casefold_dictionary(
    values,
):

    tmp = defaultdict(set)

    for value in values:

        value = norm(value)

        if value:

            tmp[
                value.lower()
            ].add(
                value
            )

    result = {}

    for key, values in tmp.items():

        if len(values) == 1:

            result[
                key
            ] = next(
                iter(values)
            )

    return result


# =============================================================================
# Load operational data
# =============================================================================

print("=" * 140)
print(
    "HIS SYNTHETIC BENCHMARK V1.3"
)
print(
    "PHASE 4C-4 - FULL CLEANING FRAMEWORK V3"
)
print(
    f"FINAL_TEST seed={SEED} | corruption={RATE}%"
)
print("=" * 140)


print(
    "\n[1/12] Loading operational input..."
)

patient = load_csv(
    INPUT
    / "patient.csv"
)

visit = load_csv(
    INPUT
    / "visit.csv"
)

diagnosis = load_csv(
    INPUT
    / "diagnosis.csv"
)

laboratory = load_csv(
    INPUT
    / "laboratory.csv"
)

medication = load_csv(
    INPUT
    / "medication.csv"
)

examination = load_csv(
    INPUT
    / "examination.csv"
)


print(
    f"Patient={len(patient):,} "
    f"Visit={len(visit):,} "
    f"Diagnosis={len(diagnosis):,} "
    f"Laboratory={len(laboratory):,} "
    f"Medication={len(medication):,} "
    f"Examination={len(examination):,}"
)


# =============================================================================
# Column discovery
# =============================================================================

visit_pk = find_col(
    visit,
    [
        "visit_id",
    ],
    True,
)

visit_patient = find_col(
    visit,
    [
        "patient_id",
    ],
    True,
)

visit_start = find_col(
    visit,
    [
        "admission_time",
        "admit_time",
        "visit_start_time",
        "start_time",
    ],
)

visit_end = find_col(
    visit,
    [
        "discharge_time",
        "visit_end_time",
        "end_time",
    ],
)


dx_pk = find_col(
    diagnosis,
    [
        "diagnosis_id",
    ],
    True,
)

dx_code = find_col(
    diagnosis,
    [
        "diagnosis_code",
        "icd_code",
        "code",
    ],
)

dx_name = find_col(
    diagnosis,
    [
        "diagnosis_name",
        "diagnosis_description",
        "name",
    ],
)


lab_pk = find_col(
    laboratory,
    [
        "lab_id",
        "laboratory_id",
    ],
    True,
)

lab_patient = find_col(
    laboratory,
    [
        "patient_id",
    ],
)

lab_visit = find_col(
    laboratory,
    [
        "visit_id",
    ],
)

lab_name = find_col(
    laboratory,
    [
        "lab_name",
        "test_name",
        "item_name",
        "lab_test_name",
        "test_item",
    ],
)

lab_value = find_col(
    laboratory,
    [
        "result_value",
        "lab_value",
        "value",
    ],
)

lab_unit = find_col(
    laboratory,
    [
        "unit",
        "result_unit",
        "value_unit",
    ],
)

lab_time = find_col(
    laboratory,
    [
        "lab_time",
        "result_time",
        "charttime",
        "event_time",
    ],
)


med_pk = find_col(
    medication,
    [
        "medication_event_id",
        "medication_id",
    ],
    True,
)

med_patient = find_col(
    medication,
    [
        "patient_id",
    ],
)

med_visit = find_col(
    medication,
    [
        "visit_id",
    ],
)

med_drug = find_col(
    medication,
    [
        "drug_name",
        "medication_name",
        "drug",
    ],
)

med_dose = find_col(
    medication,
    [
        "dose_value",
        "dose",
        "amount",
    ],
)

med_unit = find_col(
    medication,
    [
        "dose_unit",
        "unit",
        "amount_unit",
    ],
)

med_route = find_col(
    medication,
    [
        "route",
        "route_name",
    ],
)

med_start = find_col(
    medication,
    [
        "start_time",
        "med_start_time",
        "order_start_time",
    ],
)

med_stop = find_col(
    medication,
    [
        "stop_time",
        "med_stop_time",
        "order_stop_time",
    ],
)


exam_pk = find_col(
    examination,
    [
        "examination_id",
        "exam_id",
    ],
    True,
)

exam_patient = find_col(
    examination,
    [
        "patient_id",
    ],
)

exam_visit = find_col(
    examination,
    [
        "visit_id",
    ],
)

exam_name = find_col(
    examination,
    [
        "examination_name",
        "exam_name",
        "procedure_name",
    ],
)

exam_modality = find_col(
    examination,
    [
        "modality",
        "exam_modality",
    ],
)

exam_status = find_col(
    examination,
    [
        "result_status",
        "status",
        "exam_status",
    ],
)

exam_order = find_col(
    examination,
    [
        "order_time",
        "ordered_time",
    ],
)

exam_time = find_col(
    examination,
    [
        "exam_time",
        "performed_time",
        "result_time",
    ],
)


# =============================================================================
# Canonical concept-level dictionaries
# =============================================================================

print(
    "\n[2/12] Building concept-level dictionaries..."
)

c_dx = load_csv(
    CANONICAL
    / "diagnosis.csv"
)

c_lab = load_csv(
    CANONICAL
    / "laboratory.csv"
)

c_med = load_csv(
    CANONICAL
    / "medication.csv"
)

c_exam = load_csv(
    CANONICAL
    / "examination.csv"
)


c_dx_code = find_col(
    c_dx,
    [
        "diagnosis_code",
        "icd_code",
        "code",
    ],
)

c_dx_name = find_col(
    c_dx,
    [
        "diagnosis_name",
        "diagnosis_description",
        "name",
    ],
)

c_lab_name = find_col(
    c_lab,
    [
        "lab_name",
        "test_name",
        "item_name",
        "lab_test_name",
        "test_item",
    ],
)

c_lab_unit = find_col(
    c_lab,
    [
        "unit",
        "result_unit",
        "value_unit",
    ],
)

c_med_drug = find_col(
    c_med,
    [
        "drug_name",
        "medication_name",
        "drug",
    ],
)

c_med_unit = find_col(
    c_med,
    [
        "dose_unit",
        "unit",
        "amount_unit",
    ],
)

c_med_route = find_col(
    c_med,
    [
        "route",
        "route_name",
    ],
)

c_exam_name = find_col(
    c_exam,
    [
        "examination_name",
        "exam_name",
        "procedure_name",
    ],
)

c_exam_modality = find_col(
    c_exam,
    [
        "modality",
        "exam_modality",
    ],
)

c_exam_status = find_col(
    c_exam,
    [
        "result_status",
        "status",
        "exam_status",
    ],
)


dx_code_name = unique_map(
    c_dx,
    c_dx_code,
    c_dx_name,
)

dx_name_code = unique_map(
    c_dx,
    c_dx_name,
    c_dx_code,
)

lab_name_unit = unique_map(
    c_lab,
    c_lab_name,
    c_lab_unit,
)

med_drug_unit = unique_map(
    c_med,
    c_med_drug,
    c_med_unit,
)

med_drug_route = unique_map(
    c_med,
    c_med_drug,
    c_med_route,
)

exam_name_modality = unique_map(
    c_exam,
    c_exam_name,
    c_exam_modality,
)


canonical_dx_names = (
    []
    if c_dx_name is None
    else
    c_dx[
        c_dx_name
    ].tolist()
)

canonical_med_names = (
    []
    if c_med_drug is None
    else
    c_med[
        c_med_drug
    ].tolist()
)

canonical_exam_names = (
    []
    if c_exam_name is None
    else
    c_exam[
        c_exam_name
    ].tolist()
)

canonical_exam_status = (
    []
    if c_exam_status is None
    else
    c_exam[
        c_exam_status
    ].tolist()
)


dx_casefold = casefold_dictionary(
    canonical_dx_names
)

med_casefold = casefold_dictionary(
    canonical_med_names
)

exam_casefold = casefold_dictionary(
    canonical_exam_names
)

exam_status_casefold = (
    casefold_dictionary(
        canonical_exam_status
    )
)


print(
    f"Diagnosis dictionary: "
    f"{len(dx_code_name)}"
)

print(
    f"Laboratory unit dictionary: "
    f"{len(lab_name_unit)}"
)

print(
    f"Medication unit dictionary: "
    f"{len(med_drug_unit)}"
)

print(
    f"Medication route dictionary: "
    f"{len(med_drug_route)}"
)

print(
    f"Examination modality dictionary: "
    f"{len(exam_name_modality)}"
)


# =============================================================================
# Medication semantic context pre-screen
# =============================================================================

print(
    "\n[2B/12] "
    "Pre-screening medication semantic context..."
)


def normalized_drug(v):

    s = norm(v)

    if not s:
        return ""

    target = med_casefold.get(
        s.lower()
    )

    if target is not None:
        return target

    return s


def dominant_map(
    df,
    key_series,
    value_col,
):

    if value_col is None:
        return {}

    x = pd.DataFrame({

        "key":
            key_series,

        "value":
            df[
                value_col
            ].map(norm),
    })

    x = x[
        x["key"].ne("")
        &
        x["value"].ne("")
    ]

    if len(x) == 0:
        return {}

    group_n = (
        x.groupby(
            "key"
        )
        .size()
    )

    counts = (
        x.groupby(
            [
                "key",
                "value",
            ]
        )
        .size()
        .rename(
            "count"
        )
        .reset_index()
    )

    counts = counts.sort_values(
        [
            "key",
            "count",
            "value",
        ],
        ascending=[
            True,
            False,
            True,
        ],
    )

    top = (
        counts.groupby(
            "key",
            as_index=False,
        )
        .first()
    )

    result = {}

    for _, row in top.iterrows():

        key = row["key"]

        n = int(
            group_n.loc[
                key
            ]
        )

        count = int(
            row["count"]
        )

        result[
            key
        ] = {

            "value":
                row["value"],

            "n":
                n,

            "support":
                (
                    count / n
                    if n > 0
                    else 0
                ),
        }

    return result


med_semantic_suspicious = set()


if (
    med_drug is not None
    and
    med_unit is not None
    and
    med_route is not None
):

    drug_keys = (
        medication[
            med_drug
        ]
        .map(
            normalized_drug
        )
    )

    unit_mode = dominant_map(
        medication,
        drug_keys,
        med_unit,
    )

    route_mode = dominant_map(
        medication,
        drug_keys,
        med_route,
    )

    for i in medication.index:

        rid = norm(
            medication.at[
                i,
                med_pk,
            ]
        )

        key = drug_keys.loc[
            i
        ]

        if not key:
            continue

        observed_unit = norm(
            medication.at[
                i,
                med_unit,
            ]
        )

        observed_route = norm(
            medication.at[
                i,
                med_route,
            ]
        )

        if (
            not observed_unit
            or
            not observed_route
        ):
            continue

        u = unit_mode.get(
            key
        )

        r = route_mode.get(
            key
        )

        if (
            u is None
            or
            r is None
        ):
            continue

        if (
            u["n"]
            <
            MED_CONTEXT_MIN_GROUP
            or
            r["n"]
            <
            MED_CONTEXT_MIN_GROUP
        ):
            continue

        if (
            u["support"]
            <
            MED_CONTEXT_DOMINANCE
            or
            r["support"]
            <
            MED_CONTEXT_DOMINANCE
        ):
            continue

        unit_conflict = (
            observed_unit
            !=
            u["value"]
        )

        route_conflict = (
            observed_route
            !=
            r["value"]
        )

        if (
            unit_conflict
            and
            route_conflict
        ):

            med_semantic_suspicious.add(
                rid
            )


print(
    "Medication semantic-context suspicious rows: "
    f"{len(med_semantic_suspicious):,}"
)


# =============================================================================
# M1 Lexical normalization
# =============================================================================

print(
    "\n[3/12] "
    "M1 - Lexical normalization..."
)


def casefold_standardize(
    df,
    table,
    pk,
    field,
    dictionary,
    reason,
    skip_ids=None,
):

    if (
        field is None
        or
        not dictionary
    ):
        return 0

    if skip_ids is None:
        skip_ids = set()

    count = 0

    for i in df.index:

        rid = norm(
            df.at[
                i,
                pk,
            ]
        )

        if rid in skip_ids:
            continue

        before = norm(
            df.at[
                i,
                field,
            ]
        )

        if not before:
            continue

        target = dictionary.get(
            before.lower()
        )

        if (
            target is None
            or
            same(
                before,
                target,
            )
        ):
            continue

        add_action(
            table,
            rid,
            field,
            "STANDARDIZE",
            before,
            target,
            1.0,
            reason,
            "M1",
        )

        df.at[
            i,
            field,
        ] = target

        count += 1

    return count


def fuzzy_mapping(
    series,
):

    values = (
        series
        .astype(str)
        .str.strip()
    )

    freq = values.value_counts()

    unique_values = [
        x
        for x in freq.index
        if norm(x)
    ]

    result = {}

    for source in unique_values:

        sf = int(
            freq[
                source
            ]
        )

        best_target = None
        best_score = -1

        for target in unique_values:

            if source == target:
                continue

            if (
                abs(
                    len(source)
                    -
                    len(target)
                )
                >
                FUZZY_MAX_LEN_DIFF
            ):
                continue

            tf = int(
                freq[
                    target
                ]
            )

            ratio = (
                tf / sf
            )

            if (
                ratio
                <
                FUZZY_FREQ_RATIO
            ):
                continue

            score = similarity(
                source,
                target,
            )

            if (
                score
                <
                FUZZY_SIM_THRESHOLD
            ):
                continue

            if score > best_score:

                best_score = score
                best_target = target

        if best_target is not None:

            result[
                source
            ] = (
                best_target,
                best_score,
            )

    return result


def apply_fuzzy(
    df,
    table,
    pk,
    field,
    mapping,
    skip_ids=None,
):

    if field is None:
        return 0

    if skip_ids is None:
        skip_ids = set()

    count = 0

    for source, (
        target,
        score,
    ) in mapping.items():

        mask = (
            df[field]
            .astype(str)
            .str.strip()
            .eq(source)
        )

        idx = []

        for i in df.index[
            mask
        ]:

            rid = norm(
                df.at[
                    i,
                    pk,
                ]
            )

            if rid not in skip_ids:

                idx.append(
                    i
                )

        for i in idx:

            add_action(
                table,
                df.at[
                    i,
                    pk,
                ],
                field,
                "CORRECT",
                source,
                target,
                score,
                "LEXICAL_FREQUENCY_DOMINANT_FUZZY",
                "M1",
            )

        if idx:

            df.loc[
                idx,
                field,
            ] = target

            count += len(
                idx
            )

    return count


m1_dx_case = (
    casefold_standardize(
        diagnosis,
        "Diagnosis",
        dx_pk,
        dx_name,
        dx_casefold,
        "LEXICAL_CASEFOLD_TO_CANONICAL",
    )
)

m1_med_case = (
    casefold_standardize(
        medication,
        "Medication",
        med_pk,
        med_drug,
        med_casefold,
        "LEXICAL_CASEFOLD_TO_CANONICAL",
        med_semantic_suspicious,
    )
)

m1_exam_case = (
    casefold_standardize(
        examination,
        "Examination",
        exam_pk,
        exam_name,
        exam_casefold,
        "LEXICAL_CASEFOLD_TO_CANONICAL",
    )
)

m1_status_case = (
    casefold_standardize(
        examination,
        "Examination",
        exam_pk,
        exam_status,
        exam_status_casefold,
        "LEXICAL_STATUS_CASEFOLD_TO_CANONICAL",
    )
)


dx_fuzzy = (
    {}
    if dx_name is None
    else
    fuzzy_mapping(
        diagnosis[
            dx_name
        ]
    )
)

med_fuzzy = (
    {}
    if med_drug is None
    else
    fuzzy_mapping(
        medication[
            med_drug
        ]
    )
)

exam_fuzzy = (
    {}
    if exam_name is None
    else
    fuzzy_mapping(
        examination[
            exam_name
        ]
    )
)


m1_dx_fuzzy = (
    apply_fuzzy(
        diagnosis,
        "Diagnosis",
        dx_pk,
        dx_name,
        dx_fuzzy,
    )
)

m1_med_fuzzy = (
    apply_fuzzy(
        medication,
        "Medication",
        med_pk,
        med_drug,
        med_fuzzy,
        med_semantic_suspicious,
    )
)

m1_exam_fuzzy = (
    apply_fuzzy(
        examination,
        "Examination",
        exam_pk,
        exam_name,
        exam_fuzzy,
    )
)


print(
    "M1 actions: "
    f"dx_case={m1_dx_case:,}, "
    f"dx_fuzzy={m1_dx_fuzzy:,}, "
    f"med_case={m1_med_case:,}, "
    f"med_fuzzy={m1_med_fuzzy:,}, "
    f"exam_case={m1_exam_case:,}, "
    f"exam_fuzzy={m1_exam_fuzzy:,}, "
    f"status_case={m1_status_case:,}"
)


# =============================================================================
# M2 Semantic standardization
# =============================================================================

print(
    "\n[4/12] "
    "M2 - Semantic standardization..."
)

m2_count = 0


# Diagnosis code -> name

if (
    dx_code is not None
    and
    dx_name is not None
):

    for i in diagnosis.index:

        code = norm(
            diagnosis.at[
                i,
                dx_code,
            ]
        )

        before = norm(
            diagnosis.at[
                i,
                dx_name,
            ]
        )

        target = dx_code_name.get(
            code
        )

        if (
            target is None
            or
            same(
                before,
                target,
            )
        ):
            continue

        add_action(
            "Diagnosis",
            diagnosis.at[
                i,
                dx_pk,
            ],
            dx_name,
            "CORRECT",
            before,
            target,
            1.0,
            "SEMANTIC_CODE_TO_CANONICAL_NAME",
            "M2",
        )

        diagnosis.at[
            i,
            dx_name,
        ] = target

        m2_count += 1


# Diagnosis name -> code

if (
    dx_code is not None
    and
    dx_name is not None
):

    for i in diagnosis.index:

        name = norm(
            diagnosis.at[
                i,
                dx_name,
            ]
        )

        before = norm(
            diagnosis.at[
                i,
                dx_code,
            ]
        )

        target = dx_name_code.get(
            name
        )

        if (
            target is None
            or
            same(
                before,
                target,
            )
        ):
            continue

        add_action(
            "Diagnosis",
            diagnosis.at[
                i,
                dx_pk,
            ],
            dx_code,
            "CORRECT",
            before,
            target,
            1.0,
            "SEMANTIC_NAME_TO_CANONICAL_CODE",
            "M2",
        )

        diagnosis.at[
            i,
            dx_code,
        ] = target

        m2_count += 1


# Medication semantic conflict -> ABSTAIN

if med_drug is not None:

    for i in medication.index:

        rid = norm(
            medication.at[
                i,
                med_pk,
            ]
        )

        if (
            rid
            not in
            med_semantic_suspicious
        ):
            continue

        add_action(
            "Medication",
            rid,
            med_drug,
            "ABSTAIN",
            medication.at[
                i,
                med_drug,
            ],
            "",
            1.0,
            "SEMANTIC_MED_CONTEXT_CONFLICT_ABSTAIN",
            "M2",
        )

        m2_count += 1


# Examination name -> modality

if (
    exam_name is not None
    and
    exam_modality is not None
):

    for i in examination.index:

        name = norm(
            examination.at[
                i,
                exam_name,
            ]
        )

        before = norm(
            examination.at[
                i,
                exam_modality,
            ]
        )

        target = (
            exam_name_modality.get(
                name
            )
        )

        if (
            target is None
            or
            same(
                before,
                target,
            )
        ):
            continue

        add_action(
            "Examination",
            examination.at[
                i,
                exam_pk,
            ],
            exam_modality,
            "STANDARDIZE",
            before,
            target,
            1.0,
            "SEMANTIC_EXAM_NAME_TO_MODALITY",
            "M2",
        )

        examination.at[
            i,
            exam_modality,
        ] = target

        m2_count += 1


print(
    f"M2 actions: "
    f"{m2_count:,}"
)


# =============================================================================
# M3 Missingness handling
# =============================================================================

print(
    "\n[5/12] "
    "M3 - Missingness handling..."
)


def flag_missing(
    df,
    table,
    pk,
    field,
    group_field,
    reason,
):

    if (
        field is None
        or
        group_field is None
    ):
        return 0

    temp = df[
        [
            group_field,
            field,
        ]
    ].copy()

    temp[
        "present"
    ] = (
        ~temp[
            field
        ].map(
            is_missing
        )
    ).astype(int)

    stat = (
        temp.groupby(
            group_field
        )[
            "present"
        ]
        .agg(
            [
                "count",
                "mean",
            ]
        )
    )

    stat_map = {}

    for key, row in stat.iterrows():

        stat_map[
            norm(key)
        ] = (
            int(
                row["count"]
            ),
            float(
                row["mean"]
            ),
        )

    count = 0

    for i in df.index:

        if not is_missing(
            df.at[
                i,
                field,
            ]
        ):
            continue

        key = norm(
            df.at[
                i,
                group_field,
            ]
        )

        info = stat_map.get(
            key
        )

        if info is None:
            continue

        n, rate = info

        if (
            n
            >=
            MISSING_GROUP_MIN_N
            and
            rate
            >=
            MISSING_PRESENT_RATE
        ):

            add_action(
                table,
                df.at[
                    i,
                    pk,
                ],
                field,
                "ABSTAIN",
                df.at[
                    i,
                    field,
                ],
                "",
                rate,
                reason,
                "M3",
            )

            count += 1

    return count


# Important V2 fix:
# CORR_MISS_01 actually targets Laboratory.result_value

m3_lab_result = flag_missing(
    laboratory,
    "Laboratory",
    lab_pk,
    lab_value,
    lab_name,
    "MISSING_EXPECTED_LAB_RESULT_ABSTAIN",
)

m3_lab_unit = flag_missing(
    laboratory,
    "Laboratory",
    lab_pk,
    lab_unit,
    lab_name,
    "MISSING_EXPECTED_LAB_UNIT_ABSTAIN",
)

m3_med_dose = flag_missing(
    medication,
    "Medication",
    med_pk,
    med_dose,
    med_drug,
    "MISSING_EXPECTED_MED_DOSE_ABSTAIN",
)

m3_med_unit = flag_missing(
    medication,
    "Medication",
    med_pk,
    med_unit,
    med_drug,
    "MISSING_EXPECTED_MED_UNIT_ABSTAIN",
)


print(
    "M3 actions: "
    f"lab_result={m3_lab_result:,}, "
    f"lab_unit={m3_lab_unit:,}, "
    f"med_dose={m3_med_dose:,}, "
    f"med_unit={m3_med_unit:,}"
)


# =============================================================================
# M4 Numeric + unit consistency
# =============================================================================

print(
    "\n[6/12] "
    "M4 - Numeric and unit consistency..."
)

m4_count = 0


# -----------------------------------------------------------------------------
# Lab unit standardization
# -----------------------------------------------------------------------------

if (
    lab_name is not None
    and
    lab_unit is not None
):

    for i in laboratory.index:

        name = norm(
            laboratory.at[
                i,
                lab_name,
            ]
        )

        before = norm(
            laboratory.at[
                i,
                lab_unit,
            ]
        )

        target = (
            lab_name_unit.get(
                name
            )
        )

        if (
            target is None
            or
            same(
                before,
                target,
            )
            or
            is_missing(
                before
            )
        ):
            continue

        add_action(
            "Laboratory",
            laboratory.at[
                i,
                lab_pk,
            ],
            lab_unit,
            "STANDARDIZE",
            before,
            target,
            1.0,
            "UNIT_CANONICAL_BY_LAB_CONCEPT",
            "M4",
        )

        laboratory.at[
            i,
            lab_unit,
        ] = target

        m4_count += 1


# -----------------------------------------------------------------------------
# Medication unit/route policy - V3 SAFETY REVISION
# -----------------------------------------------------------------------------
#
# Medication dose_unit and route are preserved.
#
# Rationale:
# A single medication concept can legitimately occur with multiple
# dose representations, administration routes, formulations, or order
# contexts. A concept-level canonical value is therefore insufficient
# evidence for automatic record-level replacement.
#
# V3 does NOT perform:
#
#     observed dose_unit -> canonical dose_unit
#     observed route     -> canonical route
#
# on the basis of drug_name alone.
#
# Drug-name semantic conflicts remain handled by M2 ABSTAIN.
#
# This removes unsafe cross-field error propagation while preserving
# the original operational values.
# -----------------------------------------------------------------------------

m4_med_unit_standardized = 0
m4_med_route_standardized = 0



# -----------------------------------------------------------------------------
# Robust numeric anomaly detection
# V3: FLAG ONLY.
# Do NOT guess scale-repair values from statistical distribution.
# -----------------------------------------------------------------------------

def robust_numeric_flag(
    df,
    table,
    pk,
    value_col,
    group_cols,
    reason,
):

    if (
        value_col is None
        or
        any(
            c is None
            for c in group_cols
        )
    ):
        return 0

    x = df[
        group_cols
        +
        [
            value_col,
        ]
    ].copy()

    for c in group_cols:

        x[
            c
        ] = x[
            c
        ].map(
            lower
        )

    x[
        "num"
    ] = pd.to_numeric(
        x[
            value_col
        ],
        errors="coerce",
    )

    valid = x[
        x[
            "num"
        ].notna()
    ].copy()

    if len(valid) == 0:
        return 0

    base = (
        valid.groupby(
            group_cols,
            dropna=False,
        )[
            "num"
        ]
        .agg(
            n="count",
            median="median",
        )
        .reset_index()
    )

    valid = valid.merge(
        base,
        on=group_cols,
        how="left",
    )

    valid[
        "absdev"
    ] = (
        valid[
            "num"
        ]
        -
        valid[
            "median"
        ]
    ).abs()

    mad = (
        valid.groupby(
            group_cols,
            dropna=False,
        )[
            "absdev"
        ]
        .median()
        .rename(
            "mad"
        )
        .reset_index()
    )

    valid = valid.merge(
        mad,
        on=group_cols,
        how="left",
    )

    stats = {}

    for _, row in (
        valid[
            group_cols
            +
            [
                "n",
                "median",
                "mad",
            ]
        ]
        .drop_duplicates(
            subset=group_cols
        )
        .iterrows()
    ):

        key = tuple(
            lower(
                row[c]
            )
            for c in group_cols
        )

        stats[
            key
        ] = (
            int(
                row["n"]
            ),
            float(
                row["median"]
            ),
            (
                float(
                    row["mad"]
                )
                if pd.notna(
                    row["mad"]
                )
                else np.nan
            ),
        )

    count = 0

    for i in df.index:

        try:

            value = float(
                df.at[
                    i,
                    value_col,
                ]
            )

        except Exception:

            continue

        key = tuple(
            lower(
                df.at[
                    i,
                    c,
                ]
            )
            for c in group_cols
        )

        info = stats.get(
            key
        )

        if info is None:
            continue

        n, median, mad_value = info

        if (
            n
            <
            MIN_STAT_GROUP_SIZE
            or
            not np.isfinite(
                mad_value
            )
            or
            mad_value
            <= 0
        ):
            continue

        z = (
            0.6745
            *
            abs(
                value
                -
                median
            )
            /
            mad_value
        )

        if (
            not np.isfinite(
                z
            )
            or
            z
            <=
            ROBUST_Z_THRESHOLD
        ):
            continue

        add_action(
            table,
            df.at[
                i,
                pk,
            ],
            value_col,
            "FLAG",
            df.at[
                i,
                value_col,
            ],
            "",
            min(
                1.0,
                z
                /
                (
                    z
                    +
                    ROBUST_Z_THRESHOLD
                ),
            ),
            reason,
            "M4",
        )

        count += 1

    return count


m4_lab_numeric = robust_numeric_flag(
    laboratory,
    "Laboratory",
    lab_pk,
    lab_value,
    [
        lab_name,
        lab_unit,
    ],
    "LAB_ROBUST_OUTLIER_FLAG",
)

m4_med_numeric = robust_numeric_flag(
    medication,
    "Medication",
    med_pk,
    med_dose,
    [
        med_drug,
        med_unit,
    ],
    "MED_DOSE_ROBUST_OUTLIER_FLAG",
)


m4_count += (
    m4_lab_numeric
    +
    m4_med_numeric
)


print(
    "M4 actions: "
    f"{m4_count:,} "
    f"(lab_numeric="
    f"{m4_lab_numeric:,}, "
    f"med_numeric="
    f"{m4_med_numeric:,})"
)


# =============================================================================
# M5 Relational consistency
# =============================================================================

print(
    "\n[7/12] "
    "M5 - Relational consistency..."
)

visit_patient_map = {

    norm(
        row[
            visit_pk
        ]
    ):
    norm(
        row[
            visit_patient
        ]
    )

    for _, row
    in visit.iterrows()
}


def repair_relation(
    df,
    table,
    pk,
    visit_col,
    patient_col,
):

    if (
        visit_col is None
        or
        patient_col is None
    ):
        return 0

    count = 0

    for i in df.index:

        vid = norm(
            df.at[
                i,
                visit_col,
            ]
        )

        before = norm(
            df.at[
                i,
                patient_col,
            ]
        )

        target = (
            visit_patient_map.get(
                vid
            )
        )

        if (
            target is None
            or
            same(
                before,
                target,
            )
        ):
            continue

        add_action(
            table,
            df.at[
                i,
                pk,
            ],
            patient_col,
            "CORRECT",
            before,
            target,
            1.0,
            "REL_VISIT_TO_PATIENT_CONSISTENCY",
            "M5",
        )

        df.at[
            i,
            patient_col,
        ] = target

        count += 1

    return count


m5_lab = repair_relation(
    laboratory,
    "Laboratory",
    lab_pk,
    lab_visit,
    lab_patient,
)

m5_med = repair_relation(
    medication,
    "Medication",
    med_pk,
    med_visit,
    med_patient,
)

m5_exam = repair_relation(
    examination,
    "Examination",
    exam_pk,
    exam_visit,
    exam_patient,
)


print(
    "M5 actions: "
    f"lab={m5_lab:,}, "
    f"med={m5_med:,}, "
    f"exam={m5_exam:,}"
)


# =============================================================================
# M6 Temporal validation
# =============================================================================

print(
    "\n[8/12] "
    "M6 - Temporal validation..."
)

m6_count = 0


# Visit interval map

visit_interval = {}

if (
    visit_start is not None
    and
    visit_end is not None
):

    admit = pd.to_datetime(
        visit[
            visit_start
        ],
        errors="coerce",
    )

    discharge = pd.to_datetime(
        visit[
            visit_end
        ],
        errors="coerce",
    )

    for i in visit.index:

        visit_interval[
            norm(
                visit.at[
                    i,
                    visit_pk,
                ]
            )
        ] = (
            admit.loc[
                i
            ],
            discharge.loc[
                i
            ],
        )


# Laboratory outside encounter

if (
    lab_visit is not None
    and
    lab_time is not None
):

    lab_dt = pd.to_datetime(
        laboratory[
            lab_time
        ],
        errors="coerce",
    )

    for i in laboratory.index:

        vid = norm(
            laboratory.at[
                i,
                lab_visit,
            ]
        )

        interval = (
            visit_interval.get(
                vid
            )
        )

        t = lab_dt.loc[
            i
        ]

        if (
            interval is None
            or
            pd.isna(t)
        ):
            continue

        start, end = interval

        if (
            pd.isna(start)
            or
            pd.isna(end)
        ):
            continue

        if (
            t < start
            or
            t > end
        ):

            add_action(
                "Laboratory",
                laboratory.at[
                    i,
                    lab_pk,
                ],
                lab_time,
                "FLAG",
                laboratory.at[
                    i,
                    lab_time,
                ],
                "",
                1.0,
                "TIME_LAB_OUTSIDE_ENCOUNTER",
                "M6",
            )

            m6_count += 1


# Medication stop < start

if (
    med_start is not None
    and
    med_stop is not None
):

    start = pd.to_datetime(
        medication[
            med_start
        ],
        errors="coerce",
    )

    stop = pd.to_datetime(
        medication[
            med_stop
        ],
        errors="coerce",
    )

    mask = (
        start.notna()
        &
        stop.notna()
        &
        stop.lt(
            start
        )
    )

    for i in medication.index[
        mask
    ]:

        add_action(
            "Medication",
            medication.at[
                i,
                med_pk,
            ],
            med_stop,
            "FLAG",
            medication.at[
                i,
                med_stop,
            ],
            "",
            1.0,
            "TIME_MED_STOP_BEFORE_START",
            "M6",
        )

        m6_count += 1


# Examination exam < order

if (
    exam_order is not None
    and
    exam_time is not None
):

    order_dt = pd.to_datetime(
        examination[
            exam_order
        ],
        errors="coerce",
    )

    exam_dt = pd.to_datetime(
        examination[
            exam_time
        ],
        errors="coerce",
    )

    mask = (
        order_dt.notna()
        &
        exam_dt.notna()
        &
        exam_dt.lt(
            order_dt
        )
    )

    for i in examination.index[
        mask
    ]:

        add_action(
            "Examination",
            examination.at[
                i,
                exam_pk,
            ],
            exam_time,
            "FLAG",
            examination.at[
                i,
                exam_time,
            ],
            "",
            1.0,
            "TIME_EXAM_BEFORE_ORDER",
            "M6",
        )

        m6_count += 1


print(
    f"M6 actions: "
    f"{m6_count:,}"
)


# =============================================================================
# M7 Duplicate detection
# =============================================================================

print(
    "\n[9/12] "
    "M7 - Duplicate detection..."
)


def remove_exact_duplicates(
    df,
    table,
    pk,
):

    excluded = {
        pk,
        "source_record_id",
        "duplicate_group_id",
    }

    business_cols = [

        c
        for c in df.columns

        if c not in excluded
    ]

    dup_mask = df.duplicated(
        subset=business_cols,
        keep="first",
    )

    dup_idx = set(
        df.index[
            dup_mask
        ]
    )

    count = 0

    for i in df.index:

        if i not in dup_idx:
            continue

        # IMPORTANT:
        # record_id = row that is actually removed.
        # secondary_record_id remains empty.
        #
        # This matches evaluator contract and the
        # already validated Simple Rule baseline.

        add_action(
            table,
            df.at[
                i,
                pk,
            ],
            "__ROW__",
            "REMOVE_DUPLICATE",
            "",
            "",
            1.0,
            "DUP_EXACT_BUSINESS_ROW",
            "M7",
            secondary_record_id="",
        )

        count += 1

    cleaned = df.loc[
        ~dup_mask
    ].copy()

    return (
        cleaned,
        count,
    )


laboratory, m7_lab = (
    remove_exact_duplicates(
        laboratory,
        "Laboratory",
        lab_pk,
    )
)


print(
    f"M7 actions: "
    f"{m7_lab:,}"
)


# =============================================================================
# Save cleaned data
# =============================================================================

print(
    "\n[10/12] "
    "Saving cleaned tables..."
)

save_csv(
    patient,
    CLEANED
    / "patient.csv",
)

save_csv(
    visit,
    CLEANED
    / "visit.csv",
)

save_csv(
    diagnosis,
    CLEANED
    / "diagnosis.csv",
)

save_csv(
    laboratory,
    CLEANED
    / "laboratory.csv",
)

save_csv(
    medication,
    CLEANED
    / "medication.csv",
)

save_csv(
    examination,
    CLEANED
    / "examination.csv",
)


# =============================================================================
# Save action log
# =============================================================================

print(
    "\n[11/12] "
    "Saving action log..."
)

action_df = pd.DataFrame(
    actions,
    columns=ACTION_COLUMNS,
)

save_csv(
    action_df,
    ACTION_LOG,
)


module_summary = pd.DataFrame([

    {
        "module_id": m,
        "action_rows":
            int(
                module_counts.get(
                    m,
                    0,
                )
            ),
    }

    for m in [
        "M1",
        "M2",
        "M3",
        "M4",
        "M5",
        "M6",
        "M7",
    ]
])

save_csv(
    module_summary,
    MODULE_SUMMARY,
)


# =============================================================================
# Final report
# =============================================================================

print(
    "\n[12/12] "
    "Final report..."
)

print(
    f"\nTotal action rows: "
    f"{len(action_df):,}"
)


print(
    "\nMODULE SUMMARY:"
)

print(
    module_summary.to_string(
        index=False
    )
)


if len(action_df) > 0:

    print(
        "\nACTION SUMMARY:"
    )

    summary = (
        action_df.groupby(
            [
                "module_id",
                "table_name",
                "action_type",
                "reason_code",
            ],
            dropna=False,
        )
        .size()
        .rename(
            "count"
        )
        .reset_index()
        .sort_values(
            [
                "module_id",
                "table_name",
                "reason_code",
            ]
        )
    )

    print(
        summary.to_string(
            index=False
        )
    )


print(
    "\nV2 SAFETY CHANGES:"
)

print(
    "  - M3 detects missing Laboratory result_value and ABSTAINs."
)

print(
    "  - Medication semantic-context conflicts ABSTAIN on drug_name."
)

print(
    "  - Suspicious medication rows are excluded from lexical propagation."
)

print(
    "  - Medication dose_unit and route are PRESERVED; "
    "no drug-name-only automatic standardization is performed."
)

print(
    "  - Numeric statistical anomalies are FLAG_ONLY."
)

print(
    "  - No distribution-only scale guessing is performed."
)

print(
    "  - M7 duplicate action target direction is corrected."
)


print(
    f"\nCleaned output : "
    f"{CLEANED}"
)

print(
    f"Action log     : "
    f"{ACTION_LOG}"
)

print(
    f"Module summary : "
    f"{MODULE_SUMMARY}"
)


print(
    "\nPHASE 4C-3 COMPLETE - "
    "FULL CLEANING FRAMEWORK V2 "
    f"FINAL_TEST seed={SEED} | corruption={RATE}% GENERATED"
)

print("=" * 140)

