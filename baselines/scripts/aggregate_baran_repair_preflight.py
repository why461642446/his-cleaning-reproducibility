"""Aggregate the frozen five-seed Baran repair comparator without altering runs."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


if "HIS_BASELINE_OUTPUT_ROOT" not in os.environ:
    raise RuntimeError("HIS_BASELINE_OUTPUT_ROOT must be set by the public baseline wrapper.")
BASE = Path(os.environ["HIS_BASELINE_OUTPUT_ROOT"])
SEEDS = [42, 142, 242, 342, 442]
RATE = 20


def main() -> None:
    rows = []
    for seed in SEEDS:
        folder = BASE / f"seed_{seed}_rate_{RATE:02d}" / "baran_repair_preflight_v1"
        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        manifest = pd.read_csv(folder / "baran_labelled_tuple_manifest.csv")
        summary["labelled_injected_errors"] = int(
            manifest["is_injected_diagnosis_name_error"].astype(bool).sum()
        )
        rows.append(summary)

    per_seed = pd.DataFrame(rows).sort_values("seed")
    numeric = per_seed.select_dtypes(include="number")
    aggregate = pd.DataFrame({
        "metric": numeric.columns,
        "mean": numeric.mean().values,
        "sample_sd": numeric.std(ddof=1).values,
        "minimum": numeric.min().values,
        "maximum": numeric.max().values,
    })
    out = BASE / "baran_repair_preflight_aggregate_v1"
    out.mkdir(parents=True, exist_ok=True)
    per_seed.to_csv(out / "baran_repair_per_seed.csv", index=False, encoding="utf-8-sig")
    aggregate.to_csv(out / "baran_repair_aggregate.csv", index=False, encoding="utf-8-sig")
    protocol = """# Baran repair comparator: frozen five-seed aggregate\n\nScope: five FINAL_TEST 20% diagnosis code-name samples (5,000 rows each), seeds 42/142/242/342/442. Baran received the two diagnosis fields and no V3 dictionary. Its standard fixed 20-tuple oracle-label simulation used the clean reference solely to reveal those twenty labels; labelled tuples were excluded from scoring.\n\nResult: none of the 100 sampled label tuples was an injected diagnosis-name error. Under this prespecified standard-label protocol, Baran therefore produced zero repairs in every seed. This is reported as a supervision-coverage limitation, not as a general claim about Baran or a knowledge-equivalent ranking against V3. Direct code lookup is reported separately to isolate the effect of the shared code-to-name dictionary.\n"""
    (out / "README.md").write_text(protocol, encoding="utf-8")
    print(per_seed[["seed", "labelled_injected_errors", "truth_error_rows", "predicted_repairs", "correct_repairs"]].to_string(index=False))
    print(f"Wrote aggregate to: {out}")


if __name__ == "__main__":
    main()
