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
