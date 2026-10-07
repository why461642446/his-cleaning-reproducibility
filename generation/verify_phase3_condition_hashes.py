"""Verify a generated Phase 3 condition against a retained accepted hash manifest."""
from __future__ import annotations
import argparse, csv, hashlib
from pathlib import Path

def digest(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def main():
    a=argparse.ArgumentParser(); a.add_argument('--benchmark-root',required=True,type=Path); a.add_argument('--expected-manifest',required=True,type=Path); x=a.parse_args()
    rows=list(csv.DictReader(x.expected_manifest.open(encoding='utf-8-sig'))); failures=[]
    for row in rows:
        relative=Path(row['file']); actual=x.benchmark_root/relative
        if not actual.is_file() or digest(actual)!=row['sha256']: failures.append(row['file'])
    print(f'checked={len(rows)} matched={len(rows)-len(failures)} failed={len(failures)}')
    if failures: raise SystemExit('Hash verification failed: '+', '.join(failures))
if __name__=='__main__': main()
