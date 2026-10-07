"""Path-only adapter and runtime monitor for the frozen V3 scalability panel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import threading
import time

import psutil


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-source", required=True, type=Path)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scale", required=True)
    parser.add_argument("--replicate", required=True, type=int)
    parser.add_argument("--seed", default=42, type=int)
    parser.add_argument("--rate", default=20, type=int)
    args = parser.parse_args()
    frozen_source = args.frozen_source.resolve()
    if not frozen_source.is_file():
        raise FileNotFoundError(frozen_source)

    if not args.input_dir.is_dir():
        raise FileNotFoundError(args.input_dir)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing output: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=False)

    source_text = frozen_source.read_text(encoding="utf-8")
    original_hash = digest(frozen_source)
    input_line = 'INPUT = COND / "operational_input"'
    output_block = '''OUT = (
    ROOT
    / "phase4_results"
    / "final_test"
    / f"seed_{SEED}"
    / f"corruption_{RATE:02d}"
    / "FULL_FRAMEWORK_V3"
)'''
    if source_text.count(input_line) != 1 or source_text.count(output_block) != 1:
        raise RuntimeError("Frozen-source path anchors did not match exactly; no execution performed.")
    adapted = source_text.replace(input_line, f"INPUT = Path({str(args.input_dir)!r})")
    adapted = adapted.replace(output_block, f"OUT = Path({str(args.output_dir)!r})")

    process = psutil.Process()
    peak_rss = 0
    stop = threading.Event()

    def monitor() -> None:
        nonlocal peak_rss
        while not stop.is_set():
            try:
                rss = process.memory_info().rss
                for child in process.children(recursive=True):
                    rss += child.memory_info().rss
                peak_rss = max(peak_rss, rss)
            except (psutil.Error, OSError):
                pass
            time.sleep(0.2)

    started = time.perf_counter()
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    error = None
    try:
        import sys
        old_argv = sys.argv
        sys.argv = [str(frozen_source), "--seed", str(args.seed), "--rate", str(args.rate)]
        namespace = {"__name__": "__main__", "__file__": str(frozen_source)}
        exec(compile(adapted, str(frozen_source), "exec"), namespace)
    except BaseException as exc:  # retain error in the manifest then re-raise
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        elapsed = time.perf_counter() - started
        stop.set()
        watcher.join(timeout=2)
        import sys
        if "old_argv" in locals():
            sys.argv = old_argv
        expected = [
            args.output_dir / "cleaned" / f"{table}.csv"
            for table in ("patient", "visit", "diagnosis", "laboratory", "medication", "examination")
        ] + [args.output_dir / "action_log.csv", args.output_dir / "module_summary.csv"]
        manifest = {
            "scale": args.scale,
            "replicate": args.replicate,
            "source_condition": f"seed_{args.seed}/corruption_{args.rate:02d}",
            "frozen_source": str(frozen_source),
            "frozen_source_sha256": original_hash,
            "path_only_adapter": True,
            "input_dir": str(args.input_dir),
            "output_dir": str(args.output_dir),
            "elapsed_seconds": elapsed,
            "peak_rss_bytes": peak_rss,
            "error": error,
            "expected_outputs_present": {str(p.relative_to(args.output_dir)): p.exists() for p in expected},
        }
        if (args.output_dir / "action_log.csv").exists():
            manifest["action_log_bytes"] = (args.output_dir / "action_log.csv").stat().st_size
        if (args.output_dir / "module_summary.csv").exists():
            manifest["module_summary_bytes"] = (args.output_dir / "module_summary.csv").stat().st_size
        (args.output_dir / "scalability_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
