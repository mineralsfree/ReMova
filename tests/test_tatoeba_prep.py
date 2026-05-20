import json

from peratrasher.tatoeba_prep import run


def _write_tsv(path, rows: list[list[str]]) -> None:
    path.write_text(
        "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8"
    )


def _read_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]


def test_basic_round_trip(tmp_path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.jsonl"
    _write_tsv(
        inp,
        [
            ["1", "Я іду ў школу.", "11", "I go to school."],
            ["2", "Ён чытае кнігу.", "12", "He reads a book."],
        ],
    )
    counts = run(inp, out)
    rows = _read_jsonl(out)
    assert counts == {"read": 2, "malformed": 0, "too_short": 0, "written": 2}
    assert rows[0] == {
        "src_id": 1,
        "src": "Я іду ў школу.",
        "tgt_id": 11,
        "tgt": "I go to school.",
    }


def test_drop_short_src(tmp_path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.jsonl"
    _write_tsv(
        inp,
        [
            ["1", "Прывітанне!", "11", "Hello everyone here today."],  # src=1 word
            ["2", "Гэта добры дзень.", "12", "Today is good."],
        ],
    )
    counts = run(inp, out, min_words=3)
    assert counts["too_short"] == 1
    assert counts["written"] == 1
    rows = _read_jsonl(out)
    assert rows[0]["src_id"] == 2


def test_drop_short_tgt(tmp_path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.jsonl"
    _write_tsv(
        inp,
        [
            ["1", "Гэта вельмі цікава сёння.", "11", "Hi."],  # tgt=1 word
            ["2", "Я ў школе зараз.", "12", "I am at school now."],
        ],
    )
    counts = run(inp, out, min_words=3)
    assert counts["too_short"] == 1
    assert counts["written"] == 1
    rows = _read_jsonl(out)
    assert rows[0]["src_id"] == 2


def test_drop_when_both_short(tmp_path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.jsonl"
    _write_tsv(inp, [["1", "Так.", "11", "Yes."]])
    counts = run(inp, out, min_words=3)
    assert counts == {"read": 1, "malformed": 0, "too_short": 1, "written": 0}


def test_malformed_lines_skipped(tmp_path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.jsonl"
    # Mix of: bad column count, blank line in middle, valid row.
    inp.write_text(
        "1\tonly two\tcols\n"        # 3 fields, malformed
        "\n"                          # blank, ignored
        "2\tГэта добры дзень.\t12\tToday is a good day.\n"
        "3\textra\tcols\there\there\there\n"  # 6 fields, malformed
        ,
        encoding="utf-8",
    )
    counts = run(inp, out)
    assert counts["malformed"] == 2
    assert counts["written"] == 1


def test_lang_fields_included_when_provided(tmp_path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.jsonl"
    _write_tsv(inp, [["1", "Гэта добры дзень.", "11", "Today is good."]])
    run(inp, out, src_lang="bel_Cyrl", tgt_lang="eng_Latn")
    row = _read_jsonl(out)[0]
    assert row["src_lang"] == "bel_Cyrl"
    assert row["tgt_lang"] == "eng_Latn"


def test_lang_fields_omitted_when_not_provided(tmp_path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.jsonl"
    _write_tsv(inp, [["1", "Гэта добры дзень.", "11", "Today is good."]])
    run(inp, out)
    row = _read_jsonl(out)[0]
    assert "src_lang" not in row
    assert "tgt_lang" not in row


def test_ids_parsed_as_int(tmp_path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.jsonl"
    _write_tsv(inp, [["337709", "Гэта добры дзень.", "67546", "Today is good."]])
    run(inp, out)
    row = _read_jsonl(out)[0]
    assert isinstance(row["src_id"], int) and row["src_id"] == 337709
    assert isinstance(row["tgt_id"], int) and row["tgt_id"] == 67546


def test_min_words_one_keeps_single_token(tmp_path):
    inp = tmp_path / "in.tsv"
    out = tmp_path / "out.jsonl"
    _write_tsv(inp, [["1", "Так.", "11", "Yes."]])
    counts = run(inp, out, min_words=1)
    assert counts["written"] == 1
