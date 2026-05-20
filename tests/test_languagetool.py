from typing import Any

import pytest

from peratrasher.languagetool import LanguageToolStage


class FakeClient:
    """Minimal stand-in for LocalCheckerClient — returns a queued payload per call."""

    def __init__(self, payloads: list[dict] | None = None) -> None:
        self._payloads = list(payloads or [])
        self.calls: list[str] = []
        self.closed = False

    def queue(self, payload: dict) -> None:
        self._payloads.append(payload)

    def check(self, text: str) -> dict[str, Any]:
        self.calls.append(text)
        if not self._payloads:
            raise RuntimeError(f"FakeClient: no payload queued for {text!r}")
        return self._payloads.pop(0)

    def close(self) -> None:
        self.closed = True


def make_stage(matches: list[dict] | None = None, **kwargs) -> LanguageToolStage:
    client = FakeClient([{"matches": matches or []}] * 16)
    return LanguageToolStage(client=client, **kwargs)


def test_clean_text_no_matches():
    stage = make_stage(matches=[])
    row = {"text": "Hello world", "num_words": 2}
    stage.process(row)
    lt = row["metrics"]["langtool"]
    assert lt["count"] == 0
    assert lt["types"] == {}
    assert lt["density"] == 0


def test_misspelling_recorded():
    stage = make_stage(matches=[{"rule": {"issueType": "misspelling"}}])
    row = {"text": "wrng", "num_words": 1}
    stage.process(row)
    lt = row["metrics"]["langtool"]
    assert lt["count"] == 1
    assert lt["types"] == {"misspelling": 1}
    assert lt["density"] == 1.0


def test_mixed_issue_types():
    stage = make_stage(
        matches=[
            {"rule": {"issueType": "misspelling"}},
            {"rule": {"issueType": "grammar"}},
        ]
    )
    row = {"text": "...", "num_words": 10}
    stage.process(row)
    lt = row["metrics"]["langtool"]
    assert lt["count"] == 2
    assert lt["types"] == {"misspelling": 1, "grammar": 1}
    assert lt["density"] == pytest.approx(0.2)


def test_density_falls_back_when_num_words_missing():
    stage = make_stage(matches=[{"rule": {"issueType": "misspelling"}}])
    row = {"text": "wrng"}
    stage.process(row)
    assert row["metrics"]["langtool"]["density"] == 1.0


def test_density_handles_zero_num_words():
    stage = make_stage(matches=[{"rule": {"issueType": "misspelling"}}])
    row = {"text": "x", "num_words": 0}
    stage.process(row)
    assert row["metrics"]["langtool"]["density"] == 1.0


def test_density_computed_from_input_field_when_num_words_missing():
    # No upstream num_words → derive denominator from text we just checked.
    # 4 words, 2 matches → density = 0.5.
    stage = make_stage(
        matches=[
            {"rule": {"issueType": "misspelling"}},
            {"rule": {"issueType": "grammar"}},
        ]
    )
    row = {"text": "this has four words"}
    stage.process(row)
    assert row["metrics"]["langtool"]["density"] == pytest.approx(0.5)


def test_density_prefers_upstream_num_words_when_present():
    # Upstream metadata wins; we don't recompute even if the text disagrees.
    stage = make_stage(matches=[{"rule": {"issueType": "misspelling"}}])
    row = {"text": "this has four words", "num_words": 10}
    stage.process(row)
    assert row["metrics"]["langtool"]["density"] == pytest.approx(0.1)


def test_density_uses_input_field_not_hardcoded_text():
    # Stage configured on `src`; word count should come from row["src"],
    # not from row["text"] (which is a misleading single-word string here).
    stage = make_stage(
        matches=[{"rule": {"issueType": "misspelling"}}],
        input_field="src",
        metric_prefix="src_langtool",
    )
    row = {"text": "ignored", "src": "five words total in this sentence"}
    stage.process(row)
    assert row["metrics"]["src_langtool"]["density"] == pytest.approx(1 / 6)


def test_missing_issue_type_falls_back_to_uncategorized():
    stage = make_stage(matches=[{"rule": {}}, {"rule": {"issueType": None}}])
    stage.process({"text": "x", "num_words": 1})
    types = stage.stats()["issue_type_totals"]
    assert types == {"uncategorized": 2}


def test_subprocess_failure_raises():
    class DeadClient:
        def check(self, text: str) -> dict[str, Any]:
            raise RuntimeError("subprocess died")
        def close(self) -> None:
            pass

    stage = LanguageToolStage(client=DeadClient())
    with pytest.raises(RuntimeError, match="subprocess died"):
        stage.process({"text": "anything", "num_words": 1})


def test_error_payload_raises():
    client = FakeClient([{"error": "BadInputException: ..."}])
    stage = LanguageToolStage(client=client)
    with pytest.raises(RuntimeError, match="LocalChecker error"):
        stage.process({"text": "anything", "num_words": 1})


def test_stats_aggregate_across_rows():
    stage = make_stage(matches=[{"rule": {"issueType": "misspelling"}}])
    for _ in range(5):
        stage.process({"text": "x", "num_words": 1})
    s = stage.stats()
    assert s["rows_total"] == 5
    assert s["rows_with_matches"] == 5
    assert s["issue_type_totals"] == {"misspelling": 5}
    assert "match_count_quantiles" in s
    assert s["match_count_quantiles"]["p50"] == 1


def test_stats_with_no_matches_keeps_quantiles():
    stage = make_stage(matches=[])
    for _ in range(3):
        stage.process({"text": "clean", "num_words": 1})
    s = stage.stats()
    assert s["rows_total"] == 3
    assert s["rows_with_matches"] == 0
    assert s["issue_type_totals"] == {}
    assert s["match_count_quantiles"]["p50"] == 0


def test_disabled_rules_filter_client_side():
    client = FakeClient([
        {"matches": [
            {"rule": {"id": "MORFOLOGIK_RULE_BE_BY", "issueType": "misspelling"}},
            {"rule": {"id": "WHITESPACE_RULE", "issueType": "whitespace"}},
            {"rule": {"id": "MORFOLOGIK_RULE_BE_BY", "issueType": "misspelling"}},
        ]}
    ])
    stage = LanguageToolStage(client=client, disabled_rules=["WHITESPACE_RULE"])
    row = {"text": "x", "num_words": 1}
    stage.process(row)
    lt = row["metrics"]["langtool"]
    assert lt["count"] == 2
    assert lt["types"] == {"misspelling": 2}


def test_construct_without_command_or_client_raises():
    with pytest.raises(ValueError, match="needs either"):
        LanguageToolStage()


# ---- exclude_proper_nouns ------------------------------------------------


def test_exclude_proper_nouns_skips_latin_token():
    """Pure ASCII-Latin embed in Cyrillic text is treated as a proper noun."""
    text = "Hister — род жукоў."
    client = FakeClient(
        [{"matches": [{"rule": {"issueType": "misspelling"}, "offset": 0, "length": 6}]}]
    )
    stage = LanguageToolStage(client=client, exclude_proper_nouns=True)
    stage.process({"text": text, "num_words": 4})
    # access the metrics from the stage's own books
    s = stage.stats()
    assert s["excluded_proper_nouns_total"] == 1
    assert s["issue_type_totals"] == {}


def test_exclude_proper_nouns_skips_capitalized_non_initial():
    """Capitalized non-initial Cyrillic word treated as proper noun."""
    text = "Жыў у Швецыі тры гады."
    offset = text.index("Швецыі")
    client = FakeClient(
        [{"matches": [
            {"rule": {"issueType": "misspelling"}, "offset": offset, "length": len("Швецыі")}
        ]}]
    )
    stage = LanguageToolStage(client=client, exclude_proper_nouns=True)
    row = {"text": text, "num_words": 5}
    stage.process(row)
    lt = row["metrics"]["langtool"]
    assert lt["count"] == 0
    assert lt["excluded_proper_nouns"] == 1


def test_exclude_proper_nouns_keeps_sentence_initial():
    """A capitalized word at the very start of a sentence is NOT a proper-noun
    signal — could be a real misspelling at the start of the sentence."""
    text = "Тарашкевіца форма."
    client = FakeClient(
        [{"matches": [
            {"rule": {"issueType": "misspelling"}, "offset": 0, "length": len("Тарашкевіца")}
        ]}]
    )
    stage = LanguageToolStage(client=client, exclude_proper_nouns=True)
    row = {"text": text, "num_words": 2}
    stage.process(row)
    lt = row["metrics"]["langtool"]
    assert lt["count"] == 1
    assert lt["types"] == {"misspelling": 1}
    assert lt["excluded_proper_nouns"] == 0


def test_exclude_proper_nouns_keeps_after_period():
    """Capitalized after `. ` is sentence-initial, still real misspelling."""
    text = "Канец сказа. Тарашкевіца ёсць."
    offset = text.index("Тарашкевіца")
    client = FakeClient(
        [{"matches": [
            {"rule": {"issueType": "misspelling"}, "offset": offset, "length": len("Тарашкевіца")}
        ]}]
    )
    stage = LanguageToolStage(client=client, exclude_proper_nouns=True)
    row = {"text": text, "num_words": 4}
    stage.process(row)
    lt = row["metrics"]["langtool"]
    assert lt["count"] == 1  # kept — at sentence start despite mid-document position
    assert lt["excluded_proper_nouns"] == 0


def test_exclude_proper_nouns_does_not_affect_non_misspelling_types():
    """Grammar / whitespace matches stay counted even when they look proper-noun-ish."""
    text = "Some Capitalized word."
    offset = text.index("Capitalized")
    client = FakeClient(
        [{"matches": [
            {"rule": {"issueType": "grammar"}, "offset": offset, "length": len("Capitalized")}
        ]}]
    )
    stage = LanguageToolStage(client=client, exclude_proper_nouns=True)
    row = {"text": text, "num_words": 3}
    stage.process(row)
    lt = row["metrics"]["langtool"]
    assert lt["count"] == 1
    assert lt["types"] == {"grammar": 1}
    assert lt["excluded_proper_nouns"] == 0


def test_exclude_proper_nouns_disabled_by_default():
    """Default behavior unchanged: proper-noun-looking misspellings still counted."""
    text = "Жыў у Швецыі."
    offset = text.index("Швецыі")
    client = FakeClient(
        [{"matches": [
            {"rule": {"issueType": "misspelling"}, "offset": offset, "length": len("Швецыі")}
        ]}]
    )
    stage = LanguageToolStage(client=client)  # exclude_proper_nouns defaults to False
    row = {"text": text, "num_words": 3}
    stage.process(row)
    lt = row["metrics"]["langtool"]
    assert lt["count"] == 1
    assert lt["types"] == {"misspelling": 1}
    assert lt["excluded_proper_nouns"] == 0
