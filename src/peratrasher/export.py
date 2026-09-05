"""Export filtered JSONL to a training-ready file (parquet or JSONL).

Projects every input row down to a chosen subset of columns and writes the
result as either a ZSTD-compressed Parquet file (default, smallest on disk,
fastest mmap reads for HF `datasets`) or a JSONL file (no new deps, accepted
by `datasets.load_dataset("json", data_files=...)`).

Column names can use dotted paths into nested fields, e.g.
`metrics.src_glotlid_score` flattens that signal into a top-level column.

Loading in HuggingFace:

    from datasets import load_dataset
    ds = load_dataset("parquet", data_files="data/tatoeba_train.parquet")

For MT training that expects the nested `translation` schema:

    ds = ds.map(lambda r: {"translation": {"bel": r["src"], "eng": r["tgt"]}})
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from peratrasher.configio import load_config
from peratrasher.jsonio import iter_jsonl, write_row


def _extract(row: dict, column: str) -> Any:
    """Resolve a (possibly dotted) column path into the row dict."""
    if "." not in column:
        return row.get(column)
    cur: Any = row
    for part in column.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _project(row: dict, columns: list[str]) -> dict:
    return {col: _extract(row, col) for col in columns}


def run(config_path: str | Path) -> None:
    cfg: dict[str, Any] = load_config(config_path)

    input_path = Path(cfg["input"])
    output_path = Path(cfg["output"])
    fmt = cfg.get("format", "parquet")
    columns: list[str] = cfg["columns"]
    stats_dir = Path(cfg["stats_dir"])
    prefix = cfg["stats_prefix"]
    compression = cfg.get("compression", "zstd")

    if fmt not in ("parquet", "jsonl"):
        raise ValueError(f"format must be 'parquet' or 'jsonl', got {fmt!r}")
    if not columns:
        raise ValueError("columns must be a non-empty list")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_dir.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    n_rows = 0

    if fmt == "jsonl":
        with open(output_path, "w", encoding="utf-8") as fout:
            for row in iter_jsonl(input_path):
                write_row(fout, _project(row, columns))
                n_rows += 1
    else:  # parquet
        import pyarrow as pa
        import pyarrow.parquet as pq

        data: dict[str, list[Any]] = {col: [] for col in columns}
        for row in iter_jsonl(input_path):
            for col in columns:
                data[col].append(_extract(row, col))
            n_rows += 1
        table = pa.table(data)
        pq.write_table(table, output_path, compression=compression)

    elapsed = time.perf_counter() - start
    file_size = output_path.stat().st_size

    stats = {
        "rows_written": n_rows,
        "columns": columns,
        "format": fmt,
        "compression": compression if fmt == "parquet" else None,
        "output_bytes": file_size,
        "input": str(input_path),
        "output": str(output_path),
        "processing_time_s": round(elapsed, 3),
    }
    (stats_dir / f"{prefix}_export.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    rate_mb = file_size / 1024 / 1024
    print(
        f"  export: {n_rows} rows -> {output_path} "
        f"({rate_mb:.2f} MB, {fmt}) in {elapsed:.1f}s",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Project a filtered JSONL down to chosen columns and write a "
            "training-ready parquet (HF-style) or JSONL."
        )
    )
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
