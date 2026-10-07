from pathlib import Path
import gc
import hashlib
import numpy as np
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

BASE = Path("D:/发四区")
ROOT = BASE / "HIS_Synthetic_Dataset_V1_3_REALITY_CALIBRATED"

SOURCE = ROOT / "source_valid"
CANONICAL = ROOT / "canonical_reference"
RULES = ROOT / "rules"

STAGE = "FINAL_TEST"

# Phase 3F-4 final heldout batch.
# Five frozen test seeds x five frozen corruption rates = 25 conditions.
SEEDS = [42, 142, 242, 342, 442]
RATES = [5, 10, 20, 30, 40]

BUDGET_PATH = (
    RULES
    / "phase3_final_heldout_capacity_aware_budget_v1_3.csv"
)

TAXONOMY_PATH = (
    RULES
    / "corruption_taxonomy_v1_3.csv"
)

EXPOSURE_PATH = (
    RULES
    / "phase3_operational_exposure_policy_v1_3.csv"
)


TABLE_INFO = {
    "Patient": {
        "file": "patient.csv",
        "pk": "patient_id",
    },
    "Visit": {
        "file": "visit.csv",
        "pk": "visit_id",
    },
    "Diagnosis": {
        "file": "diagnosis.csv",
        "pk": "diagnosis_id",
    },
    "Laboratory": {
        "file": "laboratory.csv",
        "pk": "lab_id",
    },
    "Medication": {
        "file": "medication.csv",
        "pk": "medication_event_id",
    },
    "Examination": {
        "file": "examination.csv",
        "pk": "examination_id",
    },
}


HELDOUT_VARIANTS = {
    "CORR_MISS_02",
    "CORR_LEX_02",
    "CORR_UNIT_02",
    "CORR_TIME_02",
    "CORR_DUP_02",
    "CORR_REL_03",
}


# ============================================================
# HELPERS
# ============================================================

def scalar_to_text(value):
    if value is None:
        return "<NA>"

    try:
        if pd.isna(value):
            return "<NA>"
    except Exception:
        pass

    return str(value)


def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            block = f.read(1024 * 1024)

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def build_fast_lookup(source_tables):

    lookup = {}

    for table, info in TABLE_INFO.items():

        pk = info["pk"]

        keys = (
            source_tables[table][pk]
            .astype(str)
        )

        if keys.duplicated().any():
            raise RuntimeError(
                f"{table}: source-valid PK is not unique."
            )

        lookup[table] = pd.Series(
            np.arange(
                len(source_tables[table]),
                dtype=np.int32,
            ),
            index=keys,
        )

    return lookup


def get_row_position(
    row_pos_lookup,
    table,
    record_id,
):

    key = str(record_id)
    lookup = row_pos_lookup[table]

    if key not in lookup.index:
        return None

    return int(
        lookup.at[key]
    )


def source_value(
    source_tables,
    row_pos_lookup,
    table,
    record_id,
    field,
):

    pos = get_row_position(
        row_pos_lookup,
        table,
        record_id,
    )

    if pos is None:
        return "<NA>"

    df = source_tables[table]

    if field not in df.columns:
        return "<NA>"

    return scalar_to_text(
        df.at[pos, field]
    )


def canonical_value(
    canonical_tables,
    row_pos_lookup,
    table,
    record_id,
    field,
):

    pos = get_row_position(
        row_pos_lookup,
        table,
        record_id,
    )

    if pos is None:
        return "<NA>"

    df = canonical_tables[table]

    if field not in df.columns:
        return "<NA>"

    return scalar_to_text(
        df.at[pos, field]
    )


def resolve_first_column(
    df,
    candidates,
    label,
):

    for col in candidates:

        if col in df.columns:
            return col

    raise RuntimeError(
        f"Cannot resolve {label}. "
        f"Tried: {candidates}"
    )


def make_available_selector(
    source_tables,
    working,
    reserved,
    rng,
):

    def available_indices(
        table,
        n,
        eligible_mask=None,
    ):

        df = working[table]
        pk = TABLE_INFO[table]["pk"]

        baseline_n = len(
            source_tables[table]
        )

        baseline_indices = np.arange(
            baseline_n
        )

        if eligible_mask is None:

            candidates = baseline_indices

        else:

            if isinstance(
                eligible_mask,
                pd.Series,
            ):

                eligible_array = (
                    eligible_mask
                    .iloc[:baseline_n]
                    .to_numpy(dtype=bool)
                )

            else:

                eligible_array = np.asarray(
                    eligible_mask,
                    dtype=bool,
                )[:baseline_n]

            candidates = (
                baseline_indices[
                    eligible_array
                ]
            )

        if reserved[table]:

            candidate_ids = (
                df.loc[
                    candidates,
                    pk,
                ]
                .astype(str)
            )

            keep = (
                ~candidate_ids.isin(
                    reserved[table]
                )
            )

            candidates = (
                candidates[
                    keep.to_numpy()
                ]
            )

        if len(candidates) < n:

            raise RuntimeError(
                f"{table}: requested {n:,} "
                f"but only {len(candidates):,} "
                f"eligible unreserved baseline rows remain."
            )

        selected = rng.choice(
            candidates,
            size=n,
            replace=False,
        )

        selected_ids = (
            df.loc[
                selected,
                pk,
            ]
            .astype(str)
            .tolist()
        )

        reserved[table].update(
            selected_ids
        )

        return selected

    return available_indices


# ============================================================
# LOAD FROZEN INPUTS
# ============================================================

print("=" * 145)
print("HIS SYNTHETIC BENCHMARK V1.3")
print("PHASE 3F-4 - HELDOUT FINAL-TEST ALL-CONDITIONS GENERATOR")
print("=" * 145)


for p in [
    BUDGET_PATH,
    TAXONOMY_PATH,
    EXPOSURE_PATH,
]:

    if not p.exists():
        raise FileNotFoundError(p)


budget_plan = pd.read_csv(
    BUDGET_PATH,
    low_memory=False,
)

taxonomy = pd.read_csv(
    TAXONOMY_PATH,
    low_memory=False,
)

exposure = pd.read_csv(
    EXPOSURE_PATH,
    low_memory=False,
)


actual_heldout = set(
    taxonomy.loc[
        taxonomy["split"].eq("HELDOUT"),
        "variant_id",
    ].astype(str)
)


if actual_heldout != HELDOUT_VARIANTS:

    raise RuntimeError(
        "Frozen HELDOUT variant set changed.\n"
        f"Expected: {sorted(HELDOUT_VARIANTS)}\n"
        f"Actual:   {sorted(actual_heldout)}"
    )


source_tables = {}
canonical_tables = {}


print("\nLoading frozen baseline tables...")


for table, info in TABLE_INFO.items():

    source_tables[table] = pd.read_csv(
        SOURCE / info["file"],
        low_memory=False,
    )

    canonical_tables[table] = pd.read_csv(
        CANONICAL / info["file"],
        low_memory=False,
    )

    print(
        f"  {table:<12}: "
        f"{len(source_tables[table]):,}"
    )


row_pos_lookup = build_fast_lookup(
    source_tables
)


# ============================================================
# RESOLVE REQUIRED FIELDS
# ============================================================

dx_name_col = resolve_first_column(
    source_tables["Diagnosis"],
    [
        "diagnosis_name",
        "diagnosis_description",
        "diagnosis_text",
    ],
    "Diagnosis name field",
)


lab_value_col = resolve_first_column(
    source_tables["Laboratory"],
    [
        "result_value",
        "lab_value",
        "value",
    ],
    "Laboratory numeric value field",
)


lab_unit_col = resolve_first_column(
    source_tables["Laboratory"],
    [
        "unit",
        "result_unit",
        "value_unit",
    ],
    "Laboratory unit field",
)


lab_time_col = resolve_first_column(
    source_tables["Laboratory"],
    [
        "lab_time",
        "result_time",
        "specimen_time",
        "charttime",
    ],
    "Laboratory timestamp field",
)


visit_start_col = resolve_first_column(
    source_tables["Visit"],
    [
        "admission_time",
        "admit_time",
        "visit_start_time",
        "encounter_start_time",
        "start_time",
    ],
    "Visit start field",
)


visit_end_col = resolve_first_column(
    source_tables["Visit"],
    [
        "discharge_time",
        "visit_end_time",
        "encounter_end_time",
        "end_time",
    ],
    "Visit end field",
)


med_dose_col = resolve_first_column(
    source_tables["Medication"],
    [
        "dose_value",
        "dose",
        "amount",
    ],
    "Medication dose field",
)


med_unit_col = resolve_first_column(
    source_tables["Medication"],
    [
        "dose_unit",
        "unit",
    ],
    "Medication dose-unit field",
)


med_patient_col = resolve_first_column(
    source_tables["Medication"],
    [
        "patient_id",
    ],
    "Medication patient field",
)


med_visit_col = resolve_first_column(
    source_tables["Medication"],
    [
        "visit_id",
    ],
    "Medication visit field",
)


print("\nResolved fields:")
print(f"  Diagnosis text : {dx_name_col}")
print(f"  Lab value      : {lab_value_col}")
print(f"  Lab unit       : {lab_unit_col}")
print(f"  Lab time       : {lab_time_col}")
print(f"  Visit start    : {visit_start_col}")
print(f"  Visit end      : {visit_end_col}")
print(f"  Med dose       : {med_dose_col}")
print(f"  Med dose unit  : {med_unit_col}")


# ============================================================
# STATIC CROSS-TABLE MAPS
# ============================================================

visit_source = (
    source_tables["Visit"]
    .copy()
)


visit_source[
    visit_start_col
] = pd.to_datetime(
    visit_source[
        visit_start_col
    ],
    errors="coerce",
)


visit_source[
    visit_end_col
] = pd.to_datetime(
    visit_source[
        visit_end_col
    ],
    errors="coerce",
)


visit_start_map = (
    visit_source
    .set_index("visit_id")[
        visit_start_col
    ]
    .to_dict()
)


visit_end_map = (
    visit_source
    .set_index("visit_id")[
        visit_end_col
    ]
    .to_dict()
)


visit_patient_map = (
    visit_source
    .set_index("visit_id")[
        "patient_id"
    ]
    .astype(str)
    .to_dict()
)


patient_pool = (
    source_tables["Patient"][
        "patient_id"
    ]
    .astype(str)
    .to_numpy()
)


# ============================================================
# CORRUPTION HELPERS
# ============================================================

def make_typo(text, rng):

    text = str(text)

    candidate_positions = [
        i
        for i, ch in enumerate(text)
        if not ch.isspace()
    ]

    if not candidate_positions:
        return text + "x"

    pos = int(
        rng.choice(
            candidate_positions
        )
    )

    operations = [
        "delete",
        "duplicate",
        "substitute",
    ]

    op = str(
        rng.choice(
            operations
        )
    )

    if op == "delete":

        after = (
            text[:pos]
            +
            text[pos + 1:]
        )

    elif op == "duplicate":

        after = (
            text[:pos]
            +
            text[pos]
            +
            text[pos:]
        )

    else:

        replacement = "x"

        if text[pos].lower() == "x":
            replacement = "z"

        after = (
            text[:pos]
            +
            replacement
            +
            text[pos + 1:]
        )

    if after == text:
        after = text + "x"

    return after


def inject_unit_scale_mismatch(
    value,
    unit,
):

    numeric = float(value)
    unit_text = str(unit)

    normalized = (
        unit_text
        .strip()
        .lower()
    )

    # If a known scale-paired unit exists, change ONLY the
    # unit label and intentionally leave the numeric value
    # unchanged. This creates a true numeric-unit mismatch.
    unit_map = {
        "mg/dl": "g/L",
        "g/dl": "g/L",
        "mg/l": "g/L",
        "g/l": "mg/L",
        "mmol/l": "umol/L",
        "umol/l": "mmol/L",
        "meq/l": "Eq/L",
        "eq/l": "mEq/L",
        "mcg/dl": "mg/dL",
        "ug/dl": "mg/dL",
    }

    if normalized in unit_map:

        return (
            numeric,
            unit_map[normalized],
        )

    # Generic fallback: leave the unit untouched but corrupt
    # the numeric scale by 1000x. This remains a heldout
    # numeric-unit scale inconsistency rather than a lexical
    # invalid-unit corruption.
    return (
        numeric * 1000.0,
        unit_text,
    )


# ============================================================
# GENERATOR
# ============================================================

def generate_condition(
    seed,
    rate,
):

    rng = np.random.default_rng(
        seed * 1000
        +
        rate
    )


    out_root = (
        ROOT
        / "phase3_final_test"
        / f"seed_{seed}"
        / f"corruption_{rate:02d}"
    )


    op_dir = (
        out_root
        / "operational_input"
    )

    gt_dir = (
        out_root
        / "ground_truth"
    )

    meta_dir = (
        out_root
        / "metadata"
    )


    for d in [
        op_dir,
        gt_dir,
        meta_dir,
    ]:

        d.mkdir(
            parents=True,
            exist_ok=True,
        )


    working = {
        table: df.copy()
        for table, df
        in source_tables.items()
    }


    reserved = {
        table: set()
        for table
        in TABLE_INFO
    }


    available_indices = (
        make_available_selector(
            source_tables,
            working,
            reserved,
            rng,
        )
    )


    condition_budget = (
        budget_plan[
            budget_plan[
                "corruption_rate_pct"
            ].eq(rate)
        ]
        .copy()
    )


    if (
        set(
            condition_budget[
                "variant_id"
            ].astype(str)
        )
        !=
        HELDOUT_VARIANTS
    ):

        raise RuntimeError(
            f"Rate {rate}: "
            "budget does not contain exactly "
            "the six frozen HELDOUT variants."
        )


    variant_budgets = dict(
        zip(
            condition_budget[
                "variant_id"
            ].astype(str),
            condition_budget[
                "allocated_events"
            ].astype(int),
        )
    )


    target_events = int(
        condition_budget[
            "allocated_events"
        ].sum()
    )


    event_gt = []

    event_counter = 1
    duplicate_counter = 1


    def new_event_id():

        nonlocal event_counter

        eid = (
            f"FTEV"
            f"{seed}_"
            f"{rate:02d}_"
            f"{event_counter:09d}"
        )

        event_counter += 1

        return eid


    def add_event(
        variant_id,
        category,
        table,
        record_id,
        field_name,
        before,
        after,
        expected_action,
        secondary_record_id="",
        secondary_field_name="",
    ):

        eid = new_event_id()

        if field_name == "__ROW__":

            source_v = "__ROW__"
            canonical_v = "__ROW__"

        else:

            source_v = source_value(
                source_tables,
                row_pos_lookup,
                table,
                record_id,
                field_name,
            )

            canonical_v = canonical_value(
                canonical_tables,
                row_pos_lookup,
                table,
                record_id,
                field_name,
            )


        event_gt.append({

            "corruption_event_id":
                eid,

            "experiment_stage":
                STAGE,

            "corruption_rate_pct":
                rate,

            "seed":
                seed,

            "variant_id":
                variant_id,

            "category":
                category,

            "table_name":
                table,

            "record_id":
                str(record_id),

            "secondary_record_id":
                str(secondary_record_id),

            "field_name":
                field_name,

            "secondary_field_name":
                secondary_field_name,

            "pre_corruption_value":
                scalar_to_text(before),

            "post_corruption_value":
                scalar_to_text(after),

            "source_valid_value":
                source_v,

            "canonical_target_value":
                canonical_v,

            "expected_action":
                expected_action,

            "event_group_id":
                eid,
        })


    print(
        f"\n--- FINAL TEST "
        f"seed={seed}, rate={rate}% ---"
    )

    print(
        f"Target events: "
        f"{target_events:,}"
    )


    # ========================================================
    # CORR_MISS_02
    # correlated multi-field missingness
    # Medication: dose_value + dose_unit
    # ========================================================

    n = variant_budgets[
        "CORR_MISS_02"
    ]


    miss_eligible = (
        working["Medication"][
            med_dose_col
        ].notna()
        &
        working["Medication"][
            med_unit_col
        ].notna()
    )


    idx = available_indices(
        "Medication",
        n,
        miss_eligible,
    )


    for i in idx:

        rid = working[
            "Medication"
        ].at[
            i,
            "medication_event_id",
        ]


        dose_before = working[
            "Medication"
        ].at[
            i,
            med_dose_col,
        ]


        unit_before = working[
            "Medication"
        ].at[
            i,
            med_unit_col,
        ]


        working[
            "Medication"
        ].at[
            i,
            med_dose_col,
        ] = np.nan


        working[
            "Medication"
        ].at[
            i,
            med_unit_col,
        ] = np.nan


        add_event(
            "CORR_MISS_02",
            "MISSINGNESS",
            "Medication",
            rid,
            med_dose_col,
            dose_before,
            np.nan,
            "CORRECT",
            secondary_field_name=
                med_unit_col,
        )


    # ========================================================
    # CORR_LEX_02
    # single-character typo
    # ========================================================

    n = variant_budgets[
        "CORR_LEX_02"
    ]


    lex_eligible = (
        working["Diagnosis"][
            dx_name_col
        ]
        .notna()
    )


    idx = available_indices(
        "Diagnosis",
        n,
        lex_eligible,
    )


    for i in idx:

        rid = working[
            "Diagnosis"
        ].at[
            i,
            "diagnosis_id",
        ]


        before = str(
            working[
                "Diagnosis"
            ].at[
                i,
                dx_name_col,
            ]
        )


        after = make_typo(
            before,
            rng,
        )


        working[
            "Diagnosis"
        ].at[
            i,
            dx_name_col,
        ] = after


        add_event(
            "CORR_LEX_02",
            "LEXICAL",
            "Diagnosis",
            rid,
            dx_name_col,
            before,
            after,
            "CORRECT",
        )


    # ========================================================
    # CORR_UNIT_02
    # numeric-unit scale mismatch
    # ========================================================

    n = variant_budgets[
        "CORR_UNIT_02"
    ]


    lab_numeric = pd.to_numeric(
        working["Laboratory"][
            lab_value_col
        ],
        errors="coerce",
    )


    unit_eligible = (
        lab_numeric.notna()
        &
        working["Laboratory"][
            lab_unit_col
        ].notna()
    )


    idx = available_indices(
        "Laboratory",
        n,
        unit_eligible,
    )


    for i in idx:

        rid = working[
            "Laboratory"
        ].at[
            i,
            "lab_id",
        ]


        value_before = float(
            working[
                "Laboratory"
            ].at[
                i,
                lab_value_col,
            ]
        )


        unit_before = str(
            working[
                "Laboratory"
            ].at[
                i,
                lab_unit_col,
            ]
        )


        value_after, unit_after = (
            inject_unit_scale_mismatch(
                value_before,
                unit_before,
            )
        )


        working[
            "Laboratory"
        ].at[
            i,
            lab_value_col,
        ] = value_after


        working[
            "Laboratory"
        ].at[
            i,
            lab_unit_col,
        ] = unit_after


        primary_field = (
            lab_unit_col
            if unit_after != unit_before
            else lab_value_col
        )


        primary_before = (
            unit_before
            if primary_field == lab_unit_col
            else value_before
        )


        primary_after = (
            unit_after
            if primary_field == lab_unit_col
            else value_after
        )


        secondary_field = (
            lab_value_col
            if (
                unit_after != unit_before
                and
                value_after != value_before
            )
            else ""
        )


        add_event(
            "CORR_UNIT_02",
            "UNIT",
            "Laboratory",
            rid,
            primary_field,
            primary_before,
            primary_after,
            "CORRECT",
            secondary_field_name=
                secondary_field,
        )


    # ========================================================
    # CORR_TIME_02
    # Laboratory timestamp outside encounter
    # ========================================================

    n = variant_budgets[
        "CORR_TIME_02"
    ]


    lab_visit_ids = (
        working["Laboratory"][
            "visit_id"
        ]
        .astype(str)
    )


    start_values = (
        lab_visit_ids.map(
            visit_start_map
        )
    )


    end_values = (
        lab_visit_ids.map(
            visit_end_map
        )
    )


    time_eligible = (
        start_values.notna()
        &
        end_values.notna()
    )


    idx = available_indices(
        "Laboratory",
        n,
        time_eligible,
    )


    for i in idx:

        rid = working[
            "Laboratory"
        ].at[
            i,
            "lab_id",
        ]


        visit_id = str(
            working[
                "Laboratory"
            ].at[
                i,
                "visit_id",
            ]
        )


        before = working[
            "Laboratory"
        ].at[
            i,
            lab_time_col,
        ]


        start_t = pd.Timestamp(
            visit_start_map[
                visit_id
            ]
        )


        end_t = pd.Timestamp(
            visit_end_map[
                visit_id
            ]
        )


        hours = int(
            rng.integers(
                1,
                73,
            )
        )


        if rng.random() < 0.5:

            after_t = (
                start_t
                -
                pd.Timedelta(
                    hours=hours
                )
            )

        else:

            after_t = (
                end_t
                +
                pd.Timedelta(
                    hours=hours
                )
            )


        after = (
            after_t
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )


        working[
            "Laboratory"
        ].at[
            i,
            lab_time_col,
        ] = after


        add_event(
            "CORR_TIME_02",
            "TEMPORAL",
            "Laboratory",
            rid,
            lab_time_col,
            before,
            after,
            "FLAG_ONLY",
        )


    # ========================================================
    # CORR_DUP_02
    # near duplicate with one non-key value mutation
    # ========================================================

    n = variant_budgets[
        "CORR_DUP_02"
    ]


    dup_numeric = pd.to_numeric(
        working["Laboratory"][
            lab_value_col
        ],
        errors="coerce",
    )


    dup_eligible = (
        dup_numeric.notna()
    )


    idx = available_indices(
        "Laboratory",
        n,
        dup_eligible,
    )


    duplicate_rows = []


    for i in idx:

        original = (
            working[
                "Laboratory"
            ]
            .loc[i]
            .copy()
        )


        original_id = str(
            original[
                "lab_id"
            ]
        )


        duplicate_id = (
            f"{original_id}"
            f"_NDUP"
            f"{duplicate_counter:07d}"
        )


        duplicate_counter += 1


        duplicate = (
            original.copy()
        )


        duplicate[
            "lab_id"
        ] = duplicate_id


        original_numeric = float(
            original[
                lab_value_col
            ]
        )


        delta = (
            abs(
                original_numeric
            )
            *
            0.01
        )


        if delta == 0:
            delta = 0.001


        duplicate[
            lab_value_col
        ] = (
            original_numeric
            +
            delta
        )


        duplicate_rows.append(
            duplicate
        )


        add_event(
            "CORR_DUP_02",
            "DUPLICATE",
            "Laboratory",
            original_id,
            "__ROW__",
            "__ROW__",
            "__NEAR_DUPLICATE__",
            "REMOVE_DUPLICATE",
            secondary_record_id=
                duplicate_id,
        )


    if duplicate_rows:

        working[
            "Laboratory"
        ] = pd.concat(
            [
                working[
                    "Laboratory"
                ],
                pd.DataFrame(
                    duplicate_rows
                ),
            ],
            ignore_index=True,
        )


    # ========================================================
    # CORR_REL_03
    # Medication patient/visit dependency violation
    # ========================================================

    n = variant_budgets[
        "CORR_REL_03"
    ]


    med_visit_ids = (
        working["Medication"][
            med_visit_col
        ]
        .astype(str)
    )


    rel_eligible = (
        med_visit_ids.isin(
            visit_patient_map.keys()
        )
    )


    idx = available_indices(
        "Medication",
        n,
        rel_eligible,
    )


    for i in idx:

        rid = working[
            "Medication"
        ].at[
            i,
            "medication_event_id",
        ]


        visit_id = str(
            working[
                "Medication"
            ].at[
                i,
                med_visit_col,
            ]
        )


        true_patient = str(
            visit_patient_map[
                visit_id
            ]
        )


        before = str(
            working[
                "Medication"
            ].at[
                i,
                med_patient_col,
            ]
        )


        after = str(
            rng.choice(
                patient_pool
            )
        )


        while (
            after == true_patient
            or
            after == before
        ):

            after = str(
                rng.choice(
                    patient_pool
                )
            )


        working[
            "Medication"
        ].at[
            i,
            med_patient_col,
        ] = after


        add_event(
            "CORR_REL_03",
            "RELATIONAL",
            "Medication",
            rid,
            med_patient_col,
            before,
            after,
            "CORRECT",
        )


    # ========================================================
    # EVENT GT
    # ========================================================

    event_gt_df = pd.DataFrame(
        event_gt
    )


    if len(
        event_gt_df
    ) != target_events:

        raise RuntimeError(
            f"seed={seed}, rate={rate}: "
            f"Event GT rows "
            f"{len(event_gt_df):,} "
            f"!= budget "
            f"{target_events:,}"
        )


    # ========================================================
    # STATE GT
    # ========================================================

    state_rows = []


    for event in event_gt:

        table = event[
            "table_name"
        ]

        rid = event[
            "record_id"
        ]

        field = event[
            "field_name"
        ]

        eid = event[
            "corruption_event_id"
        ]


        if field == "__ROW__":

            state_rows.append({

                "experiment_stage":
                    STAGE,

                "corruption_rate_pct":
                    rate,

                "seed":
                    seed,

                "table_name":
                    table,

                "record_id":
                    event[
                        "secondary_record_id"
                    ],

                "field_name":
                    "__ROW__",

                "source_valid_value":
                    "__ABSENT__",

                "corrupted_value":
                    "__NEAR_DUPLICATE_ROW__",

                "canonical_target_value":
                    "__ABSENT__",

                "is_corrupted":
                    True,

                "requires_standardization":
                    False,

                "expected_action":
                    "REMOVE_DUPLICATE",

                "originating_event_id":
                    eid,
            })

            continue


        pos = get_row_position(
            row_pos_lookup,
            table,
            rid,
        )


        if pos is None:

            raise RuntimeError(
                f"Cannot resolve "
                f"{table}/{rid}"
            )


        source_v = source_value(
            source_tables,
            row_pos_lookup,
            table,
            rid,
            field,
        )


        canonical_v = canonical_value(
            canonical_tables,
            row_pos_lookup,
            table,
            rid,
            field,
        )


        corrupted_v = scalar_to_text(
            working[table].at[
                pos,
                field,
            ]
        )


        state_rows.append({

            "experiment_stage":
                STAGE,

            "corruption_rate_pct":
                rate,

            "seed":
                seed,

            "table_name":
                table,

            "record_id":
                rid,

            "field_name":
                field,

            "source_valid_value":
                source_v,

            "corrupted_value":
                corrupted_v,

            "canonical_target_value":
                canonical_v,

            "is_corrupted":
                True,

            "requires_standardization":
                source_v
                !=
                canonical_v,

            "expected_action":
                event[
                    "expected_action"
                ],

            "originating_event_id":
                eid,
        })


        second_field = event[
            "secondary_field_name"
        ]


        if second_field:

            source_v2 = source_value(
                source_tables,
                row_pos_lookup,
                table,
                rid,
                second_field,
            )


            canonical_v2 = canonical_value(
                canonical_tables,
                row_pos_lookup,
                table,
                rid,
                second_field,
            )


            corrupted_v2 = scalar_to_text(
                working[table].at[
                    pos,
                    second_field,
                ]
            )


            state_rows.append({

                "experiment_stage":
                    STAGE,

                "corruption_rate_pct":
                    rate,

                "seed":
                    seed,

                "table_name":
                    table,

                "record_id":
                    rid,

                "field_name":
                    second_field,

                "source_valid_value":
                    source_v2,

                "corrupted_value":
                    corrupted_v2,

                "canonical_target_value":
                    canonical_v2,

                "is_corrupted":
                    True,

                "requires_standardization":
                    source_v2
                    !=
                    canonical_v2,

                "expected_action":
                    event[
                        "expected_action"
                    ],

                "originating_event_id":
                    eid,
            })


    state_gt_df = pd.DataFrame(
        state_rows
    )


    # ========================================================
    # OPERATIONAL INPUT - REMOVE HIDDEN FIELDS
    # ========================================================

    operational_tables = {}


    for table, df in working.items():

        hidden = (
            exposure[
                exposure[
                    "table"
                ].eq(table)
                &
                exposure[
                    "final_phase3_operational_policy"
                ].eq(
                    "HIDDEN_FROM_CLEANING_PIPELINE"
                )
            ]["column"]
            .tolist()
        )


        hidden_existing = [
            c
            for c in hidden
            if c in df.columns
        ]


        operational_tables[
            table
        ] = df.drop(
            columns=hidden_existing
        )


    # ========================================================
    # BASIC VALIDATION
    # ========================================================

    validation_rows = []


    def check(
        name,
        passed,
        detail="",
    ):

        validation_rows.append({

            "check":
                name,

            "passed":
                bool(passed),

            "detail":
                detail,
        })


    check(
        "event_count_matches_budget",
        len(event_gt_df)
        ==
        target_events,
        (
            f"expected={target_events}, "
            f"actual={len(event_gt_df)}"
        ),
    )


    check(
        "exactly_6_heldout_variants_present",
        event_gt_df[
            "variant_id"
        ].nunique()
        ==
        6,
    )


    check(
        "only_heldout_variants_used",
        set(
            event_gt_df[
                "variant_id"
            ].astype(str)
        )
        ==
        HELDOUT_VARIANTS,
    )


    check(
        "event_ids_unique",
        event_gt_df[
            "corruption_event_id"
        ].is_unique,
    )


    check(
        "state_gt_created",
        len(
            state_gt_df
        )
        >=
        len(
            event_gt_df
        ),
    )


    exposure_ok = True


    for table, df in (
        operational_tables.items()
    ):

        hidden = (
            exposure[
                exposure[
                    "table"
                ].eq(table)
                &
                exposure[
                    "final_phase3_operational_policy"
                ].eq(
                    "HIDDEN_FROM_CLEANING_PIPELINE"
                )
            ]["column"]
            .tolist()
        )


        if any(
            c in df.columns
            for c in hidden
        ):

            exposure_ok = False
            break


    check(
        "gt_sensitive_fields_hidden",
        exposure_ok,
    )


    expected_lab_rows = (
        len(
            source_tables[
                "Laboratory"
            ]
        )
        +
        variant_budgets[
            "CORR_DUP_02"
        ]
    )


    check(
        "laboratory_near_duplicate_rows_accounted_for",
        len(
            operational_tables[
                "Laboratory"
            ]
        )
        ==
        expected_lab_rows,
    )


    validation_df = pd.DataFrame(
        validation_rows
    )


    if not validation_df[
        "passed"
    ].all():

        print(
            validation_df[
                ~validation_df[
                    "passed"
                ]
            ]
            .to_string(
                index=False
            )
        )

        raise RuntimeError(
            f"seed={seed}, rate={rate}: "
            "basic validation failed."
        )


    # ========================================================
    # SAVE
    # ========================================================

    for table, info in (
        TABLE_INFO.items()
    ):

        operational_tables[
            table
        ].to_csv(
            op_dir
            / info["file"],
            index=False,
            encoding="utf-8-sig",
        )


    event_gt_df.to_csv(
        gt_dir
        / "event_gt.csv",
        index=False,
        encoding="utf-8-sig",
    )


    state_gt_df.to_csv(
        gt_dir
        / "state_gt.csv",
        index=False,
        encoding="utf-8-sig",
    )


    variant_summary = (
        event_gt_df
        .groupby(
            [
                "variant_id",
                "category",
            ],
            as_index=False,
        )
        .size()
        .rename(
            columns={
                "size":
                    "events"
            }
        )
    )


    variant_summary[
        "percentage_of_all_events"
    ] = (
        variant_summary[
            "events"
        ]
        /
        len(
            event_gt_df
        )
        *
        100
    )


    variant_summary.to_csv(
        meta_dir
        / "variant_distribution.csv",
        index=False,
        encoding="utf-8-sig",
    )


    validation_df.to_csv(
        meta_dir
        / "validation.csv",
        index=False,
        encoding="utf-8-sig",
    )


    summary_df = pd.DataFrame([
        {
            "experiment_stage":
                STAGE,

            "seed":
                seed,

            "corruption_rate_pct":
                rate,

            "target_corruption_events":
                target_events,

            "actual_corruption_events":
                len(
                    event_gt_df
                ),

            "state_gt_rows":
                len(
                    state_gt_df
                ),

            "near_duplicate_rows_added":
                variant_budgets[
                    "CORR_DUP_02"
                ],
        }
    ])


    summary_df.to_csv(
        meta_dir
        / "corruption_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


    manifest_files = [
        gt_dir
        / "event_gt.csv",

        gt_dir
        / "state_gt.csv",

        meta_dir
        / "variant_distribution.csv",

        meta_dir
        / "validation.csv",

        meta_dir
        / "corruption_summary.csv",
    ]


    manifest_rows = []


    for path in (
        manifest_files
    ):

        manifest_rows.append({

            "file":
                str(
                    path.relative_to(
                        ROOT
                    )
                ),

            "sha256":
                sha256_file(
                    path
                ),
        })


    pd.DataFrame(
        manifest_rows
    ).to_csv(
        meta_dir
        / "sha256_manifest.csv",
        index=False,
        encoding="utf-8-sig",
    )


    print(
        f"Final-test condition complete | "
        f"seed={seed} | "
        f"rate={rate}% | "
        f"events={len(event_gt_df):,} | "
        f"state_gt={len(state_gt_df):,} | "
        f"near_duplicates="
        f"{variant_budgets['CORR_DUP_02']:,}"
    )


    del working
    del operational_tables
    del event_gt_df
    del state_gt_df

    gc.collect()


# ============================================================
# RUN PILOT
# ============================================================

for seed in SEEDS:

    for rate in RATES:

        generate_condition(
            seed,
            rate,
        )


print(
    "\n"
    +
    "=" * 145
)

print(
    "PHASE 3F-4 COMPLETE - "
    "ALL 25 HELDOUT FINAL-TEST CONDITIONS GENERATED"
)

print(
    "=" * 145
)
