import pytest

from peratrasher import glotlid


class FakeModel:
    def __init__(self, label: str, score: float) -> None:
        self.label = label
        self.score = score

    def predict(self, text: str, k: int = 1):
        return [f"__label__{self.label}"], [self.score]


@pytest.fixture
def patch_load(monkeypatch):
    def patcher(label: str, score: float) -> None:
        monkeypatch.setattr(
            glotlid.fasttext, "load_model", lambda path: FakeModel(label, score)
        )

    return patcher


def test_match_no_flag(patch_load):
    patch_load("bel_Cyrl", 0.99)
    stage = glotlid.GlotLIDStage(model_path="ignored", score_threshold=0.5)
    row = {"text": "тэст", "original_code": "bel_Cyrl"}
    stage.process(row)
    assert row["metrics"]["glotlid_label"] == "bel_Cyrl"
    assert row["metrics"]["glotlid_score"] == pytest.approx(0.99)
    assert "wrong_lang" not in row.get("removal_reasons", [])


def test_wrong_label_is_flagged(patch_load):
    patch_load("rus_Cyrl", 0.99)
    stage = glotlid.GlotLIDStage(model_path="ignored", score_threshold=0.5)
    row = {"text": "тест", "original_code": "bel_Cyrl"}
    stage.process(row)
    assert "wrong_lang" in row["removal_reasons"]
    assert stage.stats()["rows_flagged"] == 1


def test_low_score_is_flagged(patch_load):
    patch_load("bel_Cyrl", 0.3)
    stage = glotlid.GlotLIDStage(model_path="ignored", score_threshold=0.5)
    row = {"text": "ambiguous", "original_code": "bel_Cyrl"}
    stage.process(row)
    assert "wrong_lang" in row["removal_reasons"]


def test_quantiles_in_stats(patch_load):
    patch_load("bel_Cyrl", 0.8)
    stage = glotlid.GlotLIDStage(model_path="ignored", score_threshold=0.5)
    for _ in range(5):
        row = {"text": "x", "original_code": "bel_Cyrl"}
        stage.process(row)
    s = stage.stats()
    assert s["rows_total"] == 5
    assert "score_quantiles" in s
    assert s["score_quantiles"]["p50"] == pytest.approx(0.8)
