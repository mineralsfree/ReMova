#!/usr/bin/env python3
"""End-to-end benchmark for the LanguageToolStage subprocess pipeline.

Streams real rows through a LocalChecker subprocess (with --with-timing) and
reports per-phase cost so we can tell whether time is going into:

  - JLanguageTool.check()         (Java rule engine)
  - JSON serialize                (Java)
  - IPC + flush + readline        (Python<->Java pipe)
  - json.loads on the response    (Python)
  - the stage's filter/aggregate  (Python)

Usage:
    python tools/bench_languagetool.py \
        --config configs/pipeline.yaml \
        --input data/file2.txt \
        --rows 500
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


def stage_config(yaml_path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(yaml_path.read_text())
    for entry in cfg.get("stages", []):
        if entry.get("name") == "languagetool":
            return entry
    sys.exit(f"No 'languagetool' stage found in {yaml_path}")


def spawn(command: list[str], language: str, timeout: float = 30.0) -> subprocess.Popen:
    argv = list(command) + ["--stdin-loop", "--language", language, "--with-timing"]
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1,
    )
    err: list[str] = []

    def drain():
        for line in proc.stderr:
            err.append(line.rstrip("\n"))

    threading.Thread(target=drain, daemon=True).start()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(l == "READY" for l in err):
            return proc
        if proc.poll() is not None:
            sys.exit(f"subprocess exited before READY: {err!r}")
        time.sleep(0.02)
    proc.kill()
    sys.exit(f"timeout waiting for READY; stderr={err!r}")


def fmt_us(ms: float) -> str:
    return f"{ms*1000:7.0f} µs"


def percentiles(xs: list[float], ps=(10, 50, 90, 99)) -> dict[int, float]:
    if not xs:
        return {p: 0.0 for p in ps}
    s = sorted(xs)
    n = len(s)
    return {p: s[min(int(n * p / 100), n - 1)] for p in ps}


def stats_block(label: str, xs: list[float]) -> str:
    if not xs:
        return f"  {label:<14} (no samples)"
    pcts = percentiles(xs)
    return (
        f"  {label:<14} "
        f"mean={statistics.mean(xs)*1000:7.2f}ms  "
        f"p50={pcts[50]*1000:7.2f}  p90={pcts[90]*1000:7.2f}  "
        f"p99={pcts[99]*1000:7.2f}  max={max(xs)*1000:7.2f}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="path to pipeline.yaml")
    ap.add_argument("--input", required=True, help="path to JSONL input")
    ap.add_argument("--rows", type=int, default=500)
    ap.add_argument("--warmup", type=int, default=20)
    args = ap.parse_args()

    cfg = stage_config(Path(args.config))
    command = cfg["command"]
    language = cfg.get("language", "be-BY")
    disabled_rules: set[str] = set(cfg.get("disabled_rules") or [])

    print(f"# config: language={language} disabled_rules={sorted(disabled_rules)}")
    print(f"# command: {command}")
    print(f"# input:   {args.input}  rows={args.rows} warmup={args.warmup}")

    # Stream rows from input
    rows: list[dict[str, Any]] = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
            if len(rows) >= args.rows + args.warmup:
                break
    if len(rows) < args.rows:
        print(f"WARNING: only {len(rows)} rows available, requested {args.rows}")
    print(f"# loaded {len(rows)} rows")

    proc = spawn(command, language)
    print("# subprocess READY, starting bench")

    char_lengths: list[int] = []
    response_bytes: list[int] = []
    match_counts: list[int] = []

    t_check: list[float] = []
    t_serialize: list[float] = []
    t_roundtrip: list[float] = []
    t_ipc: list[float] = []
    t_parse: list[float] = []
    t_filter: list[float] = []
    t_total: list[float] = []

    issue_types: Counter[str] = Counter()

    # Warmup
    for r in rows[: args.warmup]:
        proc.stdin.write(json.dumps(r["text"], ensure_ascii=False) + "\n")
        proc.stdin.flush()
        proc.stdout.readline()

    bench_rows = rows[args.warmup : args.warmup + args.rows]
    bench_start = time.perf_counter()

    for r in bench_rows:
        text = r["text"]
        char_lengths.append(len(text))
        payload = json.dumps(text, ensure_ascii=False) + "\n"

        t0 = time.perf_counter()
        proc.stdin.write(payload)
        proc.stdin.flush()
        line = proc.stdout.readline()
        t1 = time.perf_counter()
        response_bytes.append(len(line))

        t_parse_start = time.perf_counter()
        obj = json.loads(line)
        t_parse_end = time.perf_counter()

        meta = obj.get("_meta") or {}
        check_ms = float(meta.get("check_ms", 0.0)) / 1000.0  # ms -> s
        serialize_ms = float(meta.get("serialize_ms", 0.0)) / 1000.0

        t_filter_start = time.perf_counter()
        matches = obj.get("matches", [])
        if disabled_rules:
            matches = [
                m for m in matches
                if (m.get("rule", {}).get("id") or "") not in disabled_rules
            ]
        local_types: Counter[str] = Counter()
        for m in matches:
            local_types[m.get("rule", {}).get("issueType") or "uncategorized"] += 1
        # Match what the real stage does:
        density = len(matches) / max(int(r.get("num_words") or 0), 1)
        _ = {"types": dict(local_types), "count": len(matches), "density": density}
        t_filter_end = time.perf_counter()

        match_counts.append(len(matches))
        issue_types.update(local_types)

        roundtrip = t1 - t0  # python wall clock for write+flush+read
        t_roundtrip.append(roundtrip)
        t_check.append(check_ms)
        t_serialize.append(serialize_ms)
        # IPC = roundtrip - (java check + java serialize)
        # (negative occasionally if clocks drift; clamp at 0)
        t_ipc.append(max(0.0, roundtrip - check_ms - serialize_ms))
        t_parse.append(t_parse_end - t_parse_start)
        t_filter.append(t_filter_end - t_filter_start)
        t_total.append(roundtrip + (t_parse_end - t_parse_start) + (t_filter_end - t_filter_start))

    bench_elapsed = time.perf_counter() - bench_start
    proc.stdin.close()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    # --- report ---
    print()
    print(f"=== bench summary: {len(t_total)} rows in {bench_elapsed:.2f}s "
          f"({bench_elapsed / len(t_total) * 1000:.2f} ms/row wall) ===")
    print()
    cl = sorted(char_lengths)
    n = len(cl)
    print(f"input chars:    mean={statistics.mean(char_lengths):.0f}  "
          f"p50={cl[n//2]}  p90={cl[n*9//10]}  p99={cl[n*99//100]}  max={max(cl)}")
    print(f"response bytes: mean={statistics.mean(response_bytes):.0f}  "
          f"p90={sorted(response_bytes)[n*9//10]}")
    print(f"matches/row:    mean={statistics.mean(match_counts):.2f}  "
          f"max={max(match_counts)}")
    print()
    print("per-row phase timings:")
    print(stats_block("Java check",   t_check))
    print(stats_block("Java serial.", t_serialize))
    print(stats_block("IPC (pipe)",   t_ipc))
    print(stats_block("Py json.loads",t_parse))
    print(stats_block("Py filter",    t_filter))
    print(stats_block("Py roundtrip", t_roundtrip))
    print(stats_block("TOTAL/row",    t_total))
    print()

    # Where the time goes (sum across all rows)
    total_sum = sum(t_total)
    parts = [
        ("Java check",   sum(t_check)),
        ("Java serial.", sum(t_serialize)),
        ("IPC (pipe)",   sum(t_ipc)),
        ("Py json.loads",sum(t_parse)),
        ("Py filter",    sum(t_filter)),
    ]
    print(f"share of total wall ({total_sum:.2f}s):")
    for name, s in parts:
        share = s / total_sum * 100 if total_sum > 0 else 0
        print(f"  {name:<14} {s*1000:8.0f} ms  ({share:5.1f}%)")

    # Bucket by text length
    buckets = [(0, 200), (200, 500), (500, 1000), (1000, 2000), (2000, 10**9)]
    print()
    print("per-row total by text length:")
    for lo, hi in buckets:
        b = [t for t, c in zip(t_total, char_lengths) if lo <= c < hi]
        if not b:
            continue
        label = f"{lo}-{hi}" if hi < 10**9 else f"{lo}+"
        print(f"  {label:>10} chars  n={len(b):4d}  "
              f"mean={statistics.mean(b)*1000:7.2f}ms  "
              f"max={max(b)*1000:7.2f}ms")
    print()
    top_types = issue_types.most_common(8)
    print("top issue types:", top_types)


if __name__ == "__main__":
    main()
