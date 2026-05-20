import json

import pytest

from peratrasher.moses_prep import run


def _write(path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_jsonl(path):
    return [
        json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l
    ]


def test_basic_round_trip(tmp_path):
    src = tmp_path / "in.bel"
    tgt = tmp_path / "in.eng"
    out = tmp_path / "out.jsonl"
    _write(src, ["Я іду ў школу.", "Ён чытае кнігу."])
    _write(tgt, ["I go to school.", "He reads a book."])

    counts = run(src, tgt, out, src_lang="bel_Cyrl", tgt_lang="eng_Latn")

    assert counts == {"read": 2, "malformed": 0, "too_short": 0, "written": 2}
    rows = _read_jsonl(out)
    assert rows[0] == {
        "src": "Я іду ў школу.",
        "tgt": "I go to school.",
        "src_lang": "bel_Cyrl",
        "tgt_lang": "eng_Latn",
    }


def test_drop_short_src(tmp_path):
    src = tmp_path / "in.bel"
    tgt = tmp_path / "in.eng"
    out = tmp_path / "out.jsonl"
    _write(src, ["Прывітанне!", "Гэта добры дзень."])  # 1 then 3 words
    _write(tgt, ["Hello everyone here today.", "Today is good."])
    counts = run(src, tgt, out, min_words=3)
    assert counts["too_short"] == 1
    assert counts["written"] == 1
    rows = _read_jsonl(out)
    assert rows[0]["src"] == "Гэта добры дзень."


def test_drop_short_tgt(tmp_path):
    src = tmp_path / "in.bel"
    tgt = tmp_path / "in.eng"
    out = tmp_path / "out.jsonl"
    _write(src, ["Гэта вельмі цікава сёння.", "Я ў школе зараз."])
    _write(tgt, ["Hi.", "I am at school now."])
    counts = run(src, tgt, out, min_words=3)
    assert counts["too_short"] == 1
    assert counts["written"] == 1


def test_drop_empty_line(tmp_path):
    src = tmp_path / "in.bel"
    tgt = tmp_path / "in.eng"
    out = tmp_path / "out.jsonl"
    _write(src, ["", "Гэта добры дзень."])  # first line empty
    _write(tgt, ["Today is good.", "Today is good."])
    counts = run(src, tgt, out)
    assert counts["malformed"] == 1
    assert counts["written"] == 1


def test_uneven_line_counts_raises(tmp_path):
    src = tmp_path / "in.bel"
    tgt = tmp_path / "in.eng"
    out = tmp_path / "out.jsonl"
    _write(src, ["a a a", "b b b", "c c c"])
    _write(tgt, ["x x x", "y y y"])
    with pytest.raises(ValueError, match="line count mismatch"):
        run(src, tgt, out)


def test_uneven_line_counts_raises_other_way(tmp_path):
    src = tmp_path / "in.bel"
    tgt = tmp_path / "in.eng"
    out = tmp_path / "out.jsonl"
    _write(src, ["a a a"])
    _write(tgt, ["x x x", "y y y"])
    with pytest.raises(ValueError, match="line count mismatch"):
        run(src, tgt, out)


def test_lang_fields_omitted_when_not_provided(tmp_path):
    src = tmp_path / "in.bel"
    tgt = tmp_path / "in.eng"
    out = tmp_path / "out.jsonl"
    _write(src, ["Гэта добры дзень."])
    _write(tgt, ["Today is good."])
    run(src, tgt, out)
    row = _read_jsonl(out)[0]
    assert "src_lang" not in row
    assert "tgt_lang" not in row


def test_min_words_one_keeps_single_token(tmp_path):
    src = tmp_path / "in.bel"
    tgt = tmp_path / "in.eng"
    out = tmp_path / "out.jsonl"
    _write(src, ["Так."])
    _write(tgt, ["Yes."])
    counts = run(src, tgt, out, min_words=1)
    assert counts["written"] == 1


def test_handles_bom(tmp_path):
    src = tmp_path / "in.bel"
    tgt = tmp_path / "in.eng"
    out = tmp_path / "out.jsonl"
    # Write src with UTF-8 BOM.
    src.write_bytes(b"\xef\xbb\xbf" + "Гэта добры дзень.\n".encode("utf-8"))
    _write(tgt, ["Today is good."])
    run(src, tgt, out)
    row = _read_jsonl(out)[0]
    assert row["src"] == "Гэта добры дзень."  # BOM stripped
