"""Standalone near-duplicate dedup over the pipeline's JSONL output.

Wraps `text-dedup`'s MinHash-LSH pipeline. Reads the pipeline output JSONL,
runs MinHash-LSH on a chosen text field, and writes a new JSONL where every
input row appears with two extra metrics:

  metrics["dedup_cluster_id"]: int   # shared by near-duplicates
  metrics["dedup_keeper"]:     bool  # one True per cluster (smallest index)

Signal-only: no rows are dropped. Downstream filter decides what to remove.

We call text-dedup's pipeline functions directly (`load_and_preprocess`,
`fingerprint`, `cluster`, `assign`) and skip its `save_dataset` step,
because the latter calls `Dataset.save_to_disk` which spawns a multiprocess
Manager that fails under our environment.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from peratrasher.jsonio import iter_jsonl, write_row

# Stop HF datasets from probing the hub on every load.
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")


def run_dedup(config_path: str | Path) -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    input_path = Path(cfg["input"])
    output_path = Path(cfg["output"])
    stats_dir = Path(cfg["stats_dir"])
    prefix = cfg["stats_prefix"]
    text_field = cfg["text_field"]

    mh = cfg.get("minhash", {})
    threshold = float(mh.get("threshold", 0.8))
    ngram_size = int(mh.get("ngram_size", 5))
    num_perm = int(mh.get("num_perm", 128))
    min_length = int(mh.get("min_length", 5))
    num_proc = int(mh.get("num_proc", 1))

    stats_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()

    rows: list[dict] = []
    texts: list[str] = []
    for row in iter_jsonl(input_path):
        rows.append(row)
        texts.append(row[text_field])

    with tempfile.TemporaryDirectory(prefix="peratrasher-dedup-") as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        in_parquet = tmpdir / "in.parquet"
        out_dir = tmpdir / "out"
        out_dir.mkdir()
        toml_path = tmpdir / "config.toml"

        pq.write_table(pa.table({"text": texts}), in_parquet)

        toml_path.write_text(
            f"""
[input]
input_type = "local_files"
file_type = "parquet"
read_arguments.path = "parquet"
read_arguments.data_files = ["{in_parquet}"]
read_arguments.split = "train"

[algorithm]
algorithm_name = "minhash"
text_column = "text"
num_perm = {num_perm}
ngram_size = {ngram_size}
threshold = {threshold}
min_length = {min_length}
num_proc = {num_proc}

[output]
output_dir = "{out_dir}"
skip_filtering = true
keep_index_column = true
keep_cluster_column = true

[debug]
logging_level = 30
"""
        )

        from text_dedup.config import MinHashAlgorithmConfig
        from text_dedup.config.base import load_config_from_toml
        from text_dedup.minhash import assign, cluster, fingerprint, load_and_preprocess

        td_cfg = load_config_from_toml(toml_path)
        algo = cast(MinHashAlgorithmConfig, td_cfg.algorithm)

        ds, _, _ = load_and_preprocess(td_cfg)
        if len(ds) > 0:
            embedded = fingerprint(td_cfg, ds)
            assignment = cluster(td_cfg, embedded)
            ds_full = assign(td_cfg, ds, assignment)
            indices = list(ds_full[algo.internal_index_column])
            clusters_col = list(ds_full[algo.cluster_column])
            cluster_of: dict[int, int] = dict(zip(indices, clusters_col))
        else:
            cluster_of = {}

    def cluster_id_for(i: int) -> int:
        # Filtered-out rows (below min_length) get a per-row negative singleton id.
        cid = cluster_of.get(i)
        return int(cid) if cid is not None else -(i + 1)

    members: dict[int, list[int]] = defaultdict(list)
    for i in range(len(rows)):
        members[cluster_id_for(i)].append(i)
    keepers: set[int] = {min(m) for m in members.values()}

    with open(output_path, "w", encoding="utf-8") as fout:
        for i, row in enumerate(rows):
            row.setdefault("metrics", {})["dedup_cluster_id"] = cluster_id_for(i)
            row["metrics"]["dedup_keeper"] = i in keepers
            write_row(fout, row)

    elapsed = time.perf_counter() - start
    n_clusters = len(members)
    n_clusters_with_dups = sum(1 for m in members.values() if len(m) > 1)
    stats = {
        "rows_total": len(rows),
        "clusters_total": n_clusters,
        "clusters_with_duplicates": n_clusters_with_dups,
        "rows_kept": len(keepers),
        "rows_dropped": len(rows) - len(keepers),
        "text_field": text_field,
        "minhash": {
            "threshold": threshold,
            "ngram_size": ngram_size,
            "num_perm": num_perm,
            "min_length": min_length,
        },
        "processing_time_s": round(elapsed, 3),
    }
    stats_path = stats_dir / f"{prefix}_dedup.json"
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"  dedup: {len(rows)} rows -> {len(keepers)} kept "
        f"({n_clusters_with_dups} clusters with near-dups) in {elapsed:.1f}s",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Near-duplicate dedup over the pipeline's JSONL output."
    )
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    args = parser.parse_args()
    run_dedup(args.config)


if __name__ == "__main__":
    main()
