"""Configure the retained Phase 3F-4 generator without editing its provenance copy."""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True,type=Path); a=p.parse_args()
    cfg=json.loads(a.config.read_text(encoding='utf-8'))
    parent=Path(cfg['benchmark_parent']).resolve(); root=parent/'HIS_Synthetic_Dataset_V1_3_REALITY_CALIBRATED'
    for name in ('source_valid','canonical_reference','rules'):
        if not (root/name).is_dir(): raise FileNotFoundError(f'Missing required generator input: {root/name}')
    package=Path(__file__).resolve().parents[1]; source=package/'generation'/'generate_phase3f4_heldout_final_test_all_conditions_v1_3.py'
    text=source.read_text(encoding='utf-8')
    if text.count('BASE = Path("D:/发四区")')!=1: raise RuntimeError('Generator BASE anchor was not found exactly once.')
    text=text.replace('BASE = Path("D:/发四区")',f'BASE = Path(r{str(parent)!r})')
    seeds=cfg.get('seeds',[42,142,242,342,442]); rates=cfg.get('rates',[5,10,20,30,40])
    text=text.replace('SEEDS = [42, 142, 242, 342, 442]',f'SEEDS = {seeds!r}').replace('RATES = [5, 10, 20, 30, 40]',f'RATES = {rates!r}')
    with tempfile.TemporaryDirectory(prefix='phase3_config_') as tmp:
        runner=Path(tmp)/source.name; runner.write_text(text,encoding='utf-8')
        raise SystemExit(subprocess.run([sys.executable,str(runner)]).returncode)
if __name__=='__main__': main()
