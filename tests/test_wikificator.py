from peratrasher.wikificator import WikificatorStage, apply_rules


def test_clean_text_unchanged():
    stage = WikificatorStage()
    row = {"text": "plain ascii"}
    stage.process(row)
    assert row["text"] == "plain ascii"
    assert stage.stats()["rows_changed"] == 0


def test_apostrophe_normalized():
    stage = WikificatorStage()
    row = {"text": "д'я"}
    stage.process(row)
    assert row["text"] == "д’я"
    assert stage.stats()["rows_changed"] == 1


def test_html_entity_decoded():
    stage = WikificatorStage()
    row = {"text": "&copy; 2024"}
    stage.process(row)
    assert row["text"].startswith("©")


def test_double_hyphen_to_em_dash():
    stage = WikificatorStage()
    row = {"text": "слова -- слова"}
    stage.process(row)
    assert "—" in row["text"]


def test_alternate_output_field_keeps_original():
    stage = WikificatorStage(output_field="text_wiki")
    row = {"text": "&copy;"}
    stage.process(row)
    assert row["text"] == "&copy;"
    assert row["text_wiki"] == "©"


def test_alternate_output_field_sparse_on_unchanged():
    stage = WikificatorStage(output_field="text_wiki")
    row = {"text": "plain"}
    stage.process(row)
    assert "text_wiki" not in row


def test_apply_dashes_disabled():
    stage = WikificatorStage(apply_dashes=False)
    row = {"text": "слова -- слова"}
    stage.process(row)
    assert "—" not in row["text"]


def test_apply_rules_returns_per_group_fires():
    cleaned, fires = apply_rules("&copy; слова -- слова")
    assert "©" in cleaned
    assert "—" in cleaned
    assert any(k.startswith("core") for k in fires)
    assert any(k.startswith("dashes") for k in fires)


def test_latin_homoglyph_in_cyrillic_word_fixed():
    stage = WikificatorStage()
    row = {"text": "Iмя"}  # Latin I, then Cyrillic мя
    stage.process(row)
    assert row["text"] == "Імя"  # Belarusian І + Cyrillic мя


def test_latin_lowercase_homoglyph_fixed():
    stage = WikificatorStage()
    row = {"text": "cлова"}  # Latin c + Cyrillic лова
    stage.process(row)
    assert row["text"] == "слова"  # all Cyrillic


def test_pure_latin_word_unchanged():
    stage = WikificatorStage()
    row = {"text": "Hello iOS world"}
    stage.process(row)
    assert row["text"] == "Hello iOS world"
    assert stage.stats()["rows_changed"] == 0


def test_standalone_latin_letter_fixed_in_cyrillic_context():
    stage = WikificatorStage()
    row = {"text": "ён I яна"}  # Latin "I" between Belarusian words
    stage.process(row)
    assert row["text"] == "ён І яна"  # Belarusian І


def test_standalone_letter_left_alone_in_pure_latin_text():
    stage = WikificatorStage()
    row = {"text": "you and I"}  # no Cyrillic in text → don't touch the I
    stage.process(row)
    assert row["text"] == "you and I"


def test_multichar_pure_latin_acronym_left_alone_in_cyrillic_text():
    # "PC" is all-homoglyph but multi-char → keep as Latin acronym.
    stage = WikificatorStage()
    row = {"text": "купіў PC учора"}
    stage.process(row)
    assert row["text"] == "купіў PC учора"


def test_pure_cyrillic_word_unchanged():
    stage = WikificatorStage()
    row = {"text": "беларуская мова"}
    stage.process(row)
    assert row["text"] == "беларуская мова"
    assert stage.stats()["rows_changed"] == 0


def test_multiple_homoglyphs_in_one_word():
    # Latin P, y, c, c followed by Cyrillic кая
    stage = WikificatorStage()
    row = {"text": "Pyccкая"}
    stage.process(row)
    assert row["text"] == "Русская"


def test_homoglyph_counted_separately_from_core():
    stage = WikificatorStage()
    row = {"text": "cлова"}
    stage.process(row)
    assert "homoglyph" in stage.stats()["rule_fire_counts"]


def test_typo_plan_with_suffix():
    # " пляны" -> " планы" (tarashkievica -> official orthography)
    stage = WikificatorStage()
    row = {"text": "Гэта пляны на жыццё"}
    stage.process(row)
    assert "планы" in row["text"]
    assert "пляны" not in row["text"]


def test_typo_plan_standalone():
    # " плян" (no suffix) -> " план"
    stage = WikificatorStage()
    row = {"text": "Цэлы плян"}
    stage.process(row)
    assert row["text"].endswith("план")


def test_typo_muzey():
    stage = WikificatorStage()
    row = {"text": "Гэта вялікі музэй"}
    stage.process(row)
    assert "музей" in row["text"]
    assert "музэй" not in row["text"]


def test_typo_apostrophe_word():
    # "аб'явіў" (с U+0027) -> "аб’явіў" (typo rule normalizes apostrophe in this word)
    stage = WikificatorStage()
    row = {"text": "Ён аб'явіў перамогу"}
    stage.process(row)
    assert "аб’явіў" in row["text"]


def test_typo_counted_under_typos_group():
    stage = WikificatorStage()
    row = {"text": "Гэта плян"}
    stage.process(row)
    fires = stage.stats()["rule_fire_counts"]
    assert any(k.startswith("typos") for k in fires)


def test_apply_typos_disabled_keeps_original():
    stage = WikificatorStage(apply_typos=False)
    row = {"text": "Гэта плян на жыццё"}
    stage.process(row)
    assert "плян" in row["text"]


def test_stats_aggregates_across_rows():
    stage = WikificatorStage()
    for text in ["&copy;", "&reg;", "plain"]:
        stage.process({"text": text})
    s = stage.stats()
    assert s["rows_total"] == 3
    assert s["rows_changed"] == 2
    assert sum(s["rule_fire_counts"].values()) >= 2
