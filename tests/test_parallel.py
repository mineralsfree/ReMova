import json

import pytest

from peratrasher import parallel
from peratrasher.parallel import BiGlotLIDStage, LengthRatioStage, run


# ---- LengthRatioStage ----------------------------------------------------


def test_length_ratio_in_bounds():
    stage = LengthRatioStage(min_ratio=0.5, max_ratio=2.0)
    row = {"src": "hello world", "tgt": "прывітанне свет"}
    stage.process(row)
    assert "len_ratio_out_of_bounds" not in row["removal_reasons"]
    assert 0.5 <= row["metrics"]["len_ratio"] <= 2.0


def test_length_ratio_too_long_target_flagged():
    stage = LengthRatioStage(min_ratio=0.5, max_ratio=2.0)
    row = {"src": "hi", "tgt": "a very long target translation indeed"}
    stage.process(row)
    assert "len_ratio_out_of_bounds" in row["removal_reasons"]


def test_length_ratio_too_short_target_flagged():
    stage = LengthRatioStage(min_ratio=0.5, max_ratio=2.0)
    row = {"src": "a very long source sentence indeed", "tgt": "hi"}
    stage.process(row)
    assert "len_ratio_out_of_bounds" in row["removal_reasons"]


def test_length_ratio_unit_words():
    stage = LengthRatioStage(min_ratio=0.5, max_ratio=2.0, unit="words")
    row = {"src": "one two three", "tgt": "адзін два тры"}
    stage.process(row)
    assert row["metrics"]["len_ratio"] == pytest.approx(1.0)


def test_length_ratio_bad_unit_raises():
    with pytest.raises(ValueError):
        LengthRatioStage(unit="bytes")


def test_length_ratio_stats_quantiles():
    stage = LengthRatioStage(unit="chars")
    pairs = [
        ("a", "abcd"),       # ratio 4.0  (flagged)
        ("abc", "abc"),      # ratio 1.0
        ("abcd", "ab"),      # ratio 0.5
        ("abcde", "ab"),     # ratio 0.4  (flagged)
    ]
    for s, t in pairs:
        stage.process({"src": s, "tgt": t})
    s = stage.stats()
    assert s["rows_total"] == 4
    assert s["rows_flagged"] == 2
    assert "p50" in s["len_ratio_quantiles"]


def test_length_slack_protects_short_pair():
    # ratio out of bounds but abs_diff <= slack -> no flag.
    stage = LengthRatioStage(min_ratio=0.5, max_ratio=2.0, length_slack=4)
    row = {"src": "Прывітанне!", "tgt": "Hi there everyone"}  # 1 vs 3 words
    stage.process(row)
    assert "len_ratio_out_of_bounds" not in row["removal_reasons"]
    assert row["metrics"]["len_diff"] == 2


def test_length_slack_still_flags_long_pair():
    # ratio out of bounds AND abs_diff > slack -> flag.
    stage = LengthRatioStage(min_ratio=0.5, max_ratio=2.0, length_slack=4)
    row = {"src": "one two three four five", "tgt": " ".join(["x"] * 15)}
    stage.process(row)
    assert "len_ratio_out_of_bounds" in row["removal_reasons"]


def test_length_slack_none_preserves_old_behavior():
    # No slack: ratio alone determines flagging (short pair still flagged).
    stage = LengthRatioStage(min_ratio=0.5, max_ratio=2.0)
    row = {"src": "hi", "tgt": "hello there my friend now"}  # 1 vs 5
    stage.process(row)
    assert "len_ratio_out_of_bounds" in row["removal_reasons"]


def test_length_slack_negative_raises():
    with pytest.raises(ValueError):
        LengthRatioStage(length_slack=-1)


def test_length_diff_recorded_in_stats():
    stage = LengthRatioStage(length_slack=2)
    stage.process({"src": "a b c", "tgt": "a b c d"})  # diff=1
    stage.process({"src": "a b c d e f g h", "tgt": "x"})  # diff=7
    s = stage.stats()
    assert "len_diff_quantiles" in s
    assert s["length_slack"] == 2


def test_length_ratio_custom_field_names():
    stage = LengthRatioStage(src_field="source", tgt_field="target")
    row = {"source": "hello", "target": "прывітанне"}
    stage.process(row)
    assert "len_ratio" in row["metrics"]


# ---- BiGlotLIDStage ------------------------------------------------------


class FakeModel:
    """One canned (label, score) tuple per text exactly matched."""

    def __init__(self, replies: dict[str, tuple[str, float]]) -> None:
        self.replies = replies

    def predict(self, text: str, k: int = 1):
        label, score = self.replies[text]
        return [f"__label__{label}"], [score]


@pytest.fixture
def patch_load(monkeypatch):
    def patcher(replies: dict[str, tuple[str, float]]) -> None:
        monkeypatch.setattr(
            parallel.fasttext, "load_model", lambda path: FakeModel(replies)
        )

    return patcher


def test_bi_glotlid_match_no_flag(patch_load):
    patch_load(
        {
            "hello world": ("eng_Latn", 0.99),
            "прывітанне свет": ("bel_Cyrl", 0.99),
        }
    )
    stage = BiGlotLIDStage(model_path="ignored", score_threshold=0.7)
    row = {
        "src": "hello world",
        "tgt": "прывітанне свет",
        "src_lang": "eng_Latn",
        "tgt_lang": "bel_Cyrl",
    }
    stage.process(row)
    assert row["removal_reasons"] == []
    assert row["metrics"]["src_glotlid_label"] == "eng_Latn"
    assert row["metrics"]["tgt_glotlid_label"] == "bel_Cyrl"


def test_bi_glotlid_src_wrong_lang_flagged(patch_load):
    patch_load(
        {
            "це російський": ("rus_Cyrl", 0.99),
            "прывітанне свет": ("bel_Cyrl", 0.99),
        }
    )
    stage = BiGlotLIDStage(model_path="ignored", score_threshold=0.7)
    row = {
        "src": "це російський",
        "tgt": "прывітанне свет",
        "src_lang": "eng_Latn",
        "tgt_lang": "bel_Cyrl",
    }
    stage.process(row)
    assert "src_wrong_lang" in row["removal_reasons"]
    assert "tgt_wrong_lang" not in row["removal_reasons"]


def test_bi_glotlid_tgt_wrong_lang_flagged(patch_load):
    patch_load(
        {
            "hello world": ("eng_Latn", 0.99),
            "это русский": ("rus_Cyrl", 0.99),
        }
    )
    stage = BiGlotLIDStage(model_path="ignored", score_threshold=0.7)
    row = {
        "src": "hello world",
        "tgt": "это русский",
        "src_lang": "eng_Latn",
        "tgt_lang": "bel_Cyrl",
    }
    stage.process(row)
    assert "src_wrong_lang" not in row["removal_reasons"]
    assert "tgt_wrong_lang" in row["removal_reasons"]


def test_bi_glotlid_both_wrong_lang_counted(patch_load):
    patch_load(
        {
            "це російський": ("rus_Cyrl", 0.99),
            "это русский": ("rus_Cyrl", 0.99),
        }
    )
    stage = BiGlotLIDStage(model_path="ignored", score_threshold=0.7)
    row = {
        "src": "це російський",
        "tgt": "это русский",
        "src_lang": "eng_Latn",
        "tgt_lang": "bel_Cyrl",
    }
    stage.process(row)
    assert "src_wrong_lang" in row["removal_reasons"]
    assert "tgt_wrong_lang" in row["removal_reasons"]
    assert stage.stats()["both_flagged"] == 1


def test_bi_glotlid_low_score_flagged(patch_load):
    patch_load(
        {
            "ambiguous": ("eng_Latn", 0.4),
            "прывітанне свет": ("bel_Cyrl", 0.99),
        }
    )
    stage = BiGlotLIDStage(model_path="ignored", score_threshold=0.7)
    row = {
        "src": "ambiguous",
        "tgt": "прывітанне свет",
        "src_lang": "eng_Latn",
        "tgt_lang": "bel_Cyrl",
    }
    stage.process(row)
    assert "src_wrong_lang" in row["removal_reasons"]


def test_bi_glotlid_min_words_skips_short_mismatch(patch_load):
    # Short Belarusian utterance that GlotLID would mislabel as Russian.
    # With min_words=5, this short pair should NOT be flagged.
    patch_load(
        {
            "Пра нас": ("rus_Cyrl", 0.527),
            "About us": ("gsw_Latn", 0.918),
        }
    )
    stage = BiGlotLIDStage(
        model_path="ignored",
        score_threshold=0.7,
        min_words=5,
    )
    row = {
        "src": "Пра нас",            # 2 words
        "tgt": "About us",           # 2 words
        "src_lang": "bel_Cyrl",
        "tgt_lang": "eng_Latn",
    }
    stage.process(row)
    assert row["removal_reasons"] == []   # skipped, not flagged
    # Predictions are still on the row for diagnostics:
    assert row["metrics"]["src_glotlid_label"] == "rus_Cyrl"
    assert stage.stats()["skipped_short"] == 1


def test_bi_glotlid_min_words_still_flags_long_mismatch(patch_load):
    # A long row with a genuine wrong-language tgt — should still flag
    # even when min_words is set.
    patch_load(
        {
            "Гэта прыклад доўгага сказа на беларускай мове сапраўды.": ("bel_Cyrl", 0.99),
            "Ceci est un exemple de phrase longue en français vraiment.": ("fra_Latn", 0.99),
        }
    )
    stage = BiGlotLIDStage(
        model_path="ignored",
        score_threshold=0.7,
        min_words=5,
    )
    row = {
        "src": "Гэта прыклад доўгага сказа на беларускай мове сапраўды.",
        "tgt": "Ceci est un exemple de phrase longue en français vraiment.",
        "src_lang": "bel_Cyrl",
        "tgt_lang": "eng_Latn",
    }
    stage.process(row)
    assert "tgt_wrong_lang" in row["removal_reasons"]
    assert stage.stats()["skipped_short"] == 0


def test_bi_glotlid_min_words_zero_preserves_old_behavior(patch_load):
    # Default min_words=0 → no skip logic → short mismatch IS flagged.
    patch_load(
        {
            "Пра нас": ("rus_Cyrl", 0.99),
            "About us": ("eng_Latn", 0.99),
        }
    )
    stage = BiGlotLIDStage(model_path="ignored", score_threshold=0.7)
    row = {
        "src": "Пра нас",
        "tgt": "About us",
        "src_lang": "bel_Cyrl",
        "tgt_lang": "eng_Latn",
    }
    stage.process(row)
    assert "src_wrong_lang" in row["removal_reasons"]
    assert stage.stats()["skipped_short"] == 0


def test_bi_glotlid_label_totals_aggregate(patch_load):
    patch_load(
        {
            "a": ("eng_Latn", 0.99),
            "b": ("bel_Cyrl", 0.99),
            "c": ("eng_Latn", 0.99),
            "d": ("bel_Cyrl", 0.99),
        }
    )
    stage = BiGlotLIDStage(model_path="ignored", score_threshold=0.7)
    for s, t in (("a", "b"), ("c", "d")):
        stage.process(
            {"src": s, "tgt": t, "src_lang": "eng_Latn", "tgt_lang": "bel_Cyrl"}
        )
    st = stage.stats()
    assert st["src_label_totals"] == {"eng_Latn": 2}
    assert st["tgt_label_totals"] == {"bel_Cyrl": 2}


# ---- Runner end-to-end ---------------------------------------------------


def test_monolingual_stage_reusable_on_src_and_tgt(tmp_path):
    """Same WikificatorStage class registered twice in the parallel pipeline,
    once on `src` and once on `tgt` — stats files must not collide and each
    side's text must be cleaned independently."""
    input_path = tmp_path / "in.jsonl"
    output_path = tmp_path / "out.jsonl"
    stats_dir = tmp_path / "stats"
    config_path = tmp_path / "cfg.yaml"

    rows = [
        # `src` has the mojibake-style apostrophe; `tgt` is already clean.
        {"src": "д'я", "tgt": "д’я"},
    ]
    input_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    config_path.write_text(
        f"input: {input_path}\n"
        f"output: {output_path}\n"
        f"stats_dir: {stats_dir}\n"
        "stats_prefix: test\n"
        "stages:\n"
        "  - name: wikificator\n"
        "    input_field: src\n"
        "  - name: wikificator\n"
        "    input_field: tgt\n",
        encoding="utf-8",
    )

    run(str(config_path))

    out = [
        json.loads(l)
        for l in output_path.read_text(encoding="utf-8").splitlines()
        if l
    ]
    assert out[0]["src"] == "д’я"  # apostrophe normalized
    assert out[0]["tgt"] == "д’я"  # was already clean

    # Per-side stats files exist and don't collide.
    src_stats = json.loads((stats_dir / "test_wikificator_src.json").read_text())
    tgt_stats = json.loads((stats_dir / "test_wikificator_tgt.json").read_text())
    assert src_stats["rows_changed"] == 1
    assert tgt_stats["rows_changed"] == 0


def test_parallel_runner_end_to_end(tmp_path):
    input_path = tmp_path / "in.jsonl"
    output_path = tmp_path / "out.jsonl"
    stats_dir = tmp_path / "stats"
    config_path = tmp_path / "cfg.yaml"

    rows = [
        {"src": "hello", "tgt": "прывітанне"},
        {"src": "hi", "tgt": "a very long target indeed exceeding the ratio"},
    ]
    input_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )

    config_path.write_text(
        f"input: {input_path}\n"
        f"output: {output_path}\n"
        f"stats_dir: {stats_dir}\n"
        "stats_prefix: test\n"
        "stages:\n"
        "  - name: length_ratio\n"
        "    min_ratio: 0.5\n"
        "    max_ratio: 2.0\n",
        encoding="utf-8",
    )

    run(str(config_path))

    out_rows = [
        json.loads(l)
        for l in output_path.read_text(encoding="utf-8").splitlines()
        if l
    ]
    assert len(out_rows) == 2
    assert "len_ratio" in out_rows[0]["metrics"]
    assert "len_ratio_out_of_bounds" in out_rows[1]["removal_reasons"]

    stats = json.loads((stats_dir / "test_length_ratio.json").read_text())
    assert stats["rows_total"] == 2
    assert stats["rows_flagged"] == 1
    assert "processing_time_s" in stats
