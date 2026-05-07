from peratrasher.ftfy_stage import FtfyStage


def test_clean_text_unchanged():
    stage = FtfyStage()
    row = {"text": "Hello, world."}
    stage.process(row)
    assert row["text"] == "Hello, world."
    stats = stage.stats()
    assert stats["rows_total"] == 1
    assert stats["rows_changed"] == 0


def test_mojibake_fixed_in_place():
    stage = FtfyStage()
    row = {"text": "schÃ¶n"}
    stage.process(row)
    assert row["text"] == "schön"
    stats = stage.stats()
    assert stats["rows_total"] == 1
    assert stats["rows_changed"] == 1
    assert stats["explanation_kinds"]


def test_alternate_output_field_keeps_original():
    stage = FtfyStage(output_field="text_ftfy")
    row = {"text": "schÃ¶n"}
    stage.process(row)
    assert row["text"] == "schÃ¶n"
    assert row["text_ftfy"] == "schön"
    assert stage.stats()["rows_changed"] == 1


def test_alternate_output_field_sparse_on_unchanged():
    stage = FtfyStage(output_field="text_ftfy")
    row = {"text": "Hello"}
    stage.process(row)
    assert "text_ftfy" not in row
    assert stage.stats()["rows_changed"] == 0
