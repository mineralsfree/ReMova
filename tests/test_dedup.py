import json

from peratrasher.dedup import run_dedup


def _write_config(
    config_path,
    *,
    input_path,
    output_path,
    stats_dir,
    text_field="text",
    threshold=0.5,
    ngram_size=2,
    num_perm=64,
    min_length=1,
) -> None:
    config_path.write_text(
        f"input: {input_path}\n"
        f"output: {output_path}\n"
        f"stats_dir: {stats_dir}\n"
        "stats_prefix: test\n"
        f"text_field: {text_field}\n"
        "minhash:\n"
        f"  threshold: {threshold}\n"
        f"  ngram_size: {ngram_size}\n"
        f"  num_perm: {num_perm}\n"
        f"  min_length: {min_length}\n"
        "  num_proc: 1\n",
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]


def test_near_duplicates_clustered_one_keeper_per_cluster(tmp_path):
    input_path = tmp_path / "in.jsonl"
    output_path = tmp_path / "out.jsonl"
    stats_dir = tmp_path / "stats"
    config_path = tmp_path / "cfg.yaml"

    rows = [
        {"id": 0, "text": "the quick brown fox jumps over the lazy dog"},
        {"id": 1, "text": "the quick brown fox jumps over the lazy dog"},
        {"id": 2, "text": "the quick brown fox jumps over the lazy dog!!"},
        {"id": 3, "text": "totally different sentence here in the corpus"},
        {"id": 4, "text": "totally different sentence here in the corpus."},
        {"id": 5, "text": "a completely unrelated and unique line of text"},
    ]
    input_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    _write_config(
        config_path,
        input_path=input_path,
        output_path=output_path,
        stats_dir=stats_dir,
    )

    run_dedup(str(config_path))

    out_rows = _read_jsonl(output_path)
    assert len(out_rows) == 6

    # Every row has the dedup metrics.
    for r in out_rows:
        assert "dedup_cluster_id" in r["metrics"]
        assert isinstance(r["metrics"]["dedup_keeper"], bool)

    # Indices in the same cluster share an id.
    cid = lambda i: out_rows[i]["metrics"]["dedup_cluster_id"]
    assert cid(0) == cid(1) == cid(2)
    assert cid(3) == cid(4)
    assert cid(5) not in (cid(0), cid(3))

    # Exactly one keeper per cluster.
    keepers = [r["metrics"]["dedup_keeper"] for r in out_rows]
    assert sum(keepers[0:3]) == 1
    assert sum(keepers[3:5]) == 1
    assert keepers[5] is True

    stats = json.loads((stats_dir / "test_dedup.json").read_text())
    assert stats["rows_total"] == 6
    assert stats["rows_kept"] == 3
    assert stats["rows_dropped"] == 3
    assert stats["clusters_with_duplicates"] == 2


def test_text_field_param_picks_alternate_column(tmp_path):
    input_path = tmp_path / "in.jsonl"
    output_path = tmp_path / "out.jsonl"
    stats_dir = tmp_path / "stats"
    config_path = tmp_path / "cfg.yaml"

    # text differs across rows, text_wiki is identical -> dedup on text_wiki should cluster all.
    rows = [
        {"text": f"unique sentence number {i}", "text_wiki": "common shared cleaned text"}
        for i in range(4)
    ]
    input_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    _write_config(
        config_path,
        input_path=input_path,
        output_path=output_path,
        stats_dir=stats_dir,
        text_field="text_wiki",
    )

    run_dedup(str(config_path))

    out_rows = _read_jsonl(output_path)
    cluster_ids = {r["metrics"]["dedup_cluster_id"] for r in out_rows}
    assert len(cluster_ids) == 1  # all four cluster together
    assert sum(r["metrics"]["dedup_keeper"] for r in out_rows) == 1


def test_unique_rows_each_their_own_cluster(tmp_path):
    input_path = tmp_path / "in.jsonl"
    output_path = tmp_path / "out.jsonl"
    stats_dir = tmp_path / "stats"
    config_path = tmp_path / "cfg.yaml"

    # Truly disjoint vocabularies so MinHash sigs don't collide at threshold 0.5.
    rows = [
        {"text": "alpha bravo charlie delta echo foxtrot golf hotel india juliet"},
        {"text": "kilo lima mike november oscar papa quebec romeo sierra tango"},
        {"text": "uniform victor whiskey xray yankee zulu one two three four"},
        {"text": "five six seven eight nine ten eleven twelve thirteen fourteen"},
    ]
    input_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    _write_config(
        config_path,
        input_path=input_path,
        output_path=output_path,
        stats_dir=stats_dir,
    )

    run_dedup(str(config_path))

    out_rows = _read_jsonl(output_path)
    assert all(r["metrics"]["dedup_keeper"] for r in out_rows)
    stats = json.loads((stats_dir / "test_dedup.json").read_text())
    assert stats["rows_kept"] == 4
    assert stats["rows_dropped"] == 0
    assert stats["clusters_with_duplicates"] == 0
