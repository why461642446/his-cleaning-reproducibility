"""Path configuration wrapper for the byte-preserved frozen V3 source.

This wrapper changes only the historical source's BASE assignment in a temporary
copy.  It verifies the source hash before execution and never writes back to the
provenance copy under frozen_v3/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


EXPECTED_SHA256 = "2d9ddd764056c2c54ed10c1f66f3715e6ccdabff49512c764f4e161d6d0f7c50"
HISTORICAL_BASE = 'BASE = Path(r"D:\\发四区")'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    required = {"benchmark_parent", "seed", "rate"}
    missing = required - set(cfg)
    if missing:
        raise ValueError(f"Missing config keys: {sorted(missing)}")

    package = Path(__file__).resolve().parents[1]
    source = package / "frozen_v3" / "run_phase4c4_full_framework_v3_final_rates_v1_3.py"
    if sha256(source) != EXPECTED_SHA256:
        raise RuntimeError("Frozen source hash differs from the recorded accepted artifact.")

    base = Path(cfg["benchmark_parent"]).resolve()
    root = base / "HIS_Synthetic_Dataset_V1_3_REALITY_CALIBRATED"
    if not root.is_dir():
        raise FileNotFoundError(f"Expected benchmark root not found: {root}")

    text = source.read_text(encoding="utf-8")
    if text.count(HISTORICAL_BASE) != 1:
        raise RuntimeError("Expected BASE assignment anchor was not found exactly once.")
    replacement = f"BASE = Path(r{str(base)!r})"
    configured = text.replace(HISTORICAL_BASE, replacement)

    with tempfile.TemporaryDirectory(prefix="frozen_v3_config_") as tmp:
        temporary_source = Path(tmp) / source.name
        temporary_source.write_text(configured, encoding="utf-8")
        command = [sys.executable, str(temporary_source), "--seed", str(cfg["seed"]), "--rate", str(cfg["rate"])]
        completed = subprocess.run(command)
        if completed.returncode:
            raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
