#!/usr/bin/env python3
"""Compare LanguageToolStage wall-clock at different worker counts.

Reads N rows from real input and runs them through the stage end-to-end
(spawns N JVMs, dispatches via ThreadPoolExecutor). Prints rows/sec and
total wall time for each configuration.

Usage:
    python tools/bench_parallel.py --config configs/pipeline.yaml \
        --input data/file2.txt --rows 500 --workers 1 4 8
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import yaml

from peratrasher.languagetool import LanguageToolStage


def stage_config(yaml_path: Path) -> dict:
    cfg = yaml.safe_load(yaml_path.read_text())
    for entry in cfg.get("stages", []):
        if entry.get("name") == "languagetool":
            return entry
    raise SystemExit(f"No 'languagetool' stage in {yaml_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--rows", type=int, default=500)
    ap.add_argument("--workers", nargs="+", type=int, default=[1, 4, 8])
    args = ap.parse_args()

    cfg = stage_config(Path(args.config))
    command = cfg["command"]
    language = cfg.get("language", "be-BY")
    disabled_rules = cfg.get("disabled_rules") or []
    no_suggestions = cfg.get("no_suggestions", True)

    rows: list[dict] = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
            if len(rows) >= args.rows:
                break
    print(f"# loaded {len(rows)} rows from {args.input}")

    print(f"\n{'workers':>8}  {'startup':>10}  {'wall':>10}  {'rows/sec':>10}  {'ms/row':>10}")
    for n in args.workers:
        rows_copy = [dict(r) for r in rows]  # fresh dicts so each run starts clean
        t_start = time.perf_counter()
        stage = LanguageToolStage(
            command=command,
            language=language,
            disabled_rules=disabled_rules,
            no_suggestions=no_suggestions,
            workers=n,
        )
        t_ready = time.perf_counter()
        # Warm: run 16 rows once to let JIT settle
        stage.process_batch(rows_copy[:16])
        t_warm = time.perf_counter()
        stage.process_batch(rows_copy)
        t_done = time.perf_counter()
        stage.close()
        startup = t_ready - t_start
        wall = t_done - t_warm
        rate = len(rows_copy) / wall if wall > 0 else 0
        per = wall / len(rows_copy) * 1000
        print(f"{n:>8}  {startup:>9.2f}s  {wall:>9.2f}s  {rate:>10.1f}  {per:>9.2f}")


if __name__ == "__main__":
    main()
