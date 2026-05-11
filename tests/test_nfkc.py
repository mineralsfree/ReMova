from peratrasher.nfkc import NFKCStage


def test_clean_ascii_unchanged():
    stage = NFKCStage()
    row = {"text": "Hello, world."}
    stage.process(row)
    assert row["text"] == "Hello, world."
    assert stage.stats()["rows_changed"] == 0


def test_fullwidth_latin_collapsed():
    stage = NFKCStage()
    row = {"text": "ｐｒｉｖｅｔ"}  # U+FF50.. fullwidth
    stage.process(row)
    assert row["text"] == "privet"
    assert stage.stats()["rows_changed"] == 1


def test_ligature_decomposed():
    stage = NFKCStage()
    row = {"text": "ﬁve"}  # U+FB01 fi ligature
    stage.process(row)
    assert row["text"] == "five"


def test_roman_numeral_compat_decomposed():
    # NFKC (not NFC) decomposes Roman-numeral compat codepoints.
    stage = NFKCStage()
    row = {"text": "Ⅻ"}  # U+216B
    stage.process(row)
    assert row["text"] == "XII"


def test_alternate_output_field_keeps_original():
    stage = NFKCStage(output_field="text_nfkc")
    row = {"text": "ｉ"}
    stage.process(row)
    assert row["text"] == "ｉ"
    assert row["text_nfkc"] == "i"
    assert stage.stats()["rows_changed"] == 1


def test_alternate_output_field_sparse_on_unchanged():
    stage = NFKCStage(output_field="text_nfkc")
    row = {"text": "plain"}
    stage.process(row)
    assert "text_nfkc" not in row
    assert stage.stats()["rows_changed"] == 0


def test_stats_aggregate_across_rows():
    stage = NFKCStage()
    for t in ["plain", "ｉ", "ﬁ", "ascii"]:
        stage.process({"text": t})
    s = stage.stats()
    assert s["rows_total"] == 4
    assert s["rows_changed"] == 2
