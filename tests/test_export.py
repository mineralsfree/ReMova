import json

import pytest

from peratrasher.export import _extract, _project, run


# ---- dotted-path resolver ------------------------------------------------


def test_extract_flat():
    assert _extract({"src": "hi"}, "src") == "hi"


def test_extract_dotted():
    assert _extract({"metrics": {"a": {"b": 0.5}}}, "metrics.a.b") == 0.5


def test_extract_missing_returns_none():
    assert _extract({}, "missing") is None
    assert _extract({"a": "x"}, "a.b") is None  # non-dict traversal


def test_project_subset():
    row = {"src": "hi", "tgt": "salut", "metrics": {"score": 0.9}, "extra": 42}
    assert _project(row, ["src", "tgt", "metrics.score"]) == {
        "src": "hi",
        "tgt": "salut",
        "metrics.score": 0.9,
    }


# ---- run() — jsonl format ------------------------------------------------


def _write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [
        json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l
    ]


def test_run_jsonl_flat_columns(tmp_path):
    inp = tmp_path / "in.jsonl"
    out = tmp_path / "out.jsonl"
    stats_dir = tmp_path / "stats"
    cfg = tmp_path / "cfg.yaml"

    _write_jsonl(
        inp,
        [
            {"src": "hi", "tgt": "прывітанне", "metrics": {"score": 0.9}, "extra": "drop me"},
            {"src": "bye", "tgt": "пакуль", "metrics": {"score": 0.8}, "extra": "also drop"},
        ],
    )
    cfg.write_text(
        f"input: {inp}\n"
        f"output: {out}\n"
        f"stats_dir: {stats_dir}\n"
        "stats_prefix: t\n"
        "format: jsonl\n"
        "columns: [src, tgt]\n",
        encoding="utf-8",
    )

    run(str(cfg))

    rows = _read_jsonl(out)
    assert len(rows) == 2
    assert rows[0] == {"src": "hi", "tgt": "прывітанне"}
    assert rows[1] == {"src": "bye", "tgt": "пакуль"}

    stats = json.loads((stats_dir / "t_export.json").read_text())
    assert stats["rows_written"] == 2
    assert stats["columns"] == ["src", "tgt"]
    assert stats["format"] == "jsonl"
    assert stats["compression"] is None


def test_run_jsonl_dotted_columns(tmp_path):
    inp = tmp_path / "in.jsonl"
    out = tmp_path / "out.jsonl"
    stats_dir = tmp_path / "stats"
    cfg = tmp_path / "cfg.yaml"

    _write_jsonl(
        inp,
        [{"src": "hi", "metrics": {"a": {"b": 1.23}}}],
    )
    cfg.write_text(
        f"input: {inp}\n"
        f"output: {out}\n"
        f"stats_dir: {stats_dir}\n"
        "stats_prefix: t\n"
        "format: jsonl\n"
        "columns: [src, metrics.a.b]\n",
        encoding="utf-8",
    )
    run(str(cfg))
    assert _read_jsonl(out)[0] == {"src": "hi", "metrics.a.b": 1.23}


# ---- run() — parquet format ----------------------------------------------


def test_run_parquet_round_trip(tmp_path):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")

    inp = tmp_path / "in.jsonl"
    out = tmp_path / "out.parquet"
    stats_dir = tmp_path / "stats"
    cfg = tmp_path / "cfg.yaml"

    rows = [
        {"src": "hello world", "tgt": "прывітанне свет", "src_id": 1, "tgt_id": 11},
        {"src": "good day", "tgt": "добры дзень", "src_id": 2, "tgt_id": 12},
    ]
    _write_jsonl(inp, rows)
    cfg.write_text(
        f"input: {inp}\n"
        f"output: {out}\n"
        f"stats_dir: {stats_dir}\n"
        "stats_prefix: t\n"
        "format: parquet\n"
        "compression: zstd\n"
        "columns: [src, tgt, src_id, tgt_id]\n",
        encoding="utf-8",
    )

    run(str(cfg))

    table = pq.read_table(out)
    assert table.num_rows == 2
    assert set(table.column_names) == {"src", "tgt", "src_id", "tgt_id"}
    df = table.to_pandas()
    assert list(df["src"]) == ["hello world", "good day"]
    assert list(df["tgt"]) == ["прывітанне свет", "добры дзень"]
    assert list(df["src_id"]) == [1, 2]

    stats = json.loads((stats_dir / "t_export.json").read_text())
    assert stats["format"] == "parquet"
    assert stats["compression"] == "zstd"
    assert stats["rows_written"] == 2


def test_run_parquet_drops_metadata_columns(tmp_path):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")

    inp = tmp_path / "in.jsonl"
    out = tmp_path / "out.parquet"
    cfg = tmp_path / "cfg.yaml"
    stats_dir = tmp_path / "stats"

    _write_jsonl(
        inp,
        [
            {
                "src": "hi",
                "tgt": "пакуль",
                "metrics": {"score": 0.9, "dedup_keeper": True},
                "removal_reasons": [],
            }
        ],
    )
    cfg.write_text(
        f"input: {inp}\n"
        f"output: {out}\n"
        f"stats_dir: {stats_dir}\n"
        "stats_prefix: t\n"
        "format: parquet\n"
        "columns: [src, tgt]\n",
        encoding="utf-8",
    )
    run(str(cfg))
    table = pq.read_table(out)
    assert set(table.column_names) == {"src", "tgt"}
    # metrics / removal_reasons not in output.


# ---- error paths ---------------------------------------------------------


def test_bad_format_raises(tmp_path):
    inp = tmp_path / "in.jsonl"
    _write_jsonl(inp, [])
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        f"input: {inp}\n"
        f"output: {tmp_path}/out.x\n"
        f"stats_dir: {tmp_path}/stats\n"
        "stats_prefix: t\n"
        "format: arrow\n"   # unsupported
        "columns: [src]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="format must be"):
        run(str(cfg))


def test_empty_columns_raises(tmp_path):
    inp = tmp_path / "in.jsonl"
    _write_jsonl(inp, [])
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        f"input: {inp}\n"
        f"output: {tmp_path}/out.jsonl\n"
        f"stats_dir: {tmp_path}/stats\n"
        "stats_prefix: t\n"
        "format: jsonl\n"
        "columns: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="columns must be"):
        run(str(cfg))
