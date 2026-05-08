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


def test_stats_aggregates_across_rows():
    stage = WikificatorStage()
    for text in ["&copy;", "&reg;", "plain"]:
        stage.process({"text": text})
    s = stage.stats()
    assert s["rows_total"] == 3
    assert s["rows_changed"] == 2
    assert sum(s["rule_fire_counts"].values()) >= 2
