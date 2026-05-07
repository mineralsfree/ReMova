import json

from peratrasher.pipeline import run


def test_pipeline_runs_ftfy_end_to_end(tmp_path):
    input_path = tmp_path / "in.jsonl"
    output_path = tmp_path / "out.jsonl"
    stats_dir = tmp_path / "stats"
    config_path = tmp_path / "cfg.yaml"

    rows = [
        {"text": "schÃ¶n", "original_code": "deu_Latn"},
        {"text": "Hello", "original_code": "eng_Latn"},
    ]
    input_path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )

    config_path.write_text(
        f"input: {input_path}\n"
        f"output: {output_path}\n"
        f"stats_dir: {stats_dir}\n"
        "stages:\n"
        "  - name: ftfy\n",
        encoding="utf-8",
    )

    run(str(config_path))

    out_rows = [
        json.loads(l)
        for l in output_path.read_text(encoding="utf-8").splitlines()
        if l
    ]
    assert len(out_rows) == 2
    assert out_rows[0]["text"] == "schön"
    assert out_rows[1]["text"] == "Hello"
    for r in out_rows:
        assert "removal_reasons" in r
        assert "metrics" in r

    stats = json.loads((stats_dir / "ftfy.json").read_text())
    assert stats["rows_total"] == 2
    assert stats["rows_changed"] == 1
