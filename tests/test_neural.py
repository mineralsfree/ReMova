"""Tests for the neural QE stages.

Each stage takes test-injection hooks (`_encoder_obj`, `_blaser_obj`, …) so
the suite runs green without the `neural` extra installed — same
test-by-injection pattern used in `test_languagetool.py` (FakeClient) and
`test_glotlid.py` (monkeypatched fasttext.load_model).
"""

from __future__ import annotations

import pytest

# BLASER tests construct fake torch tensors. Skip the file entirely if torch
# isn't installed (i.e. when the `neural` optional extra hasn't been pulled).
pytest.importorskip("torch")

from peratrasher.neural import (  # noqa: E402  (after importorskip)
    BlaserStage,
    NEURAL_STAGES,
    SonarCosineStage,
)


# ---- Dispatcher registry -------------------------------------------------


def test_neural_stages_dict_complete():
    assert set(NEURAL_STAGES.keys()) == {"blaser", "sonar_cosine"}


# ---- BlaserStage ---------------------------------------------------------


class FakeSonarEncoder:
    """Stand-in for sonar.inference_pipelines.text.TextToEmbeddingModelPipeline.

    `embeddings` is a dict from text to a 1-D torch tensor; predict() stacks
    them into a [batch, dim] tensor in input order. `calls` records what each
    invocation saw — useful for asserting field / lang-code wiring.
    """

    def __init__(self, embeddings: dict) -> None:
        self.embeddings = embeddings
        self.calls: list[dict] = []

    def predict(self, texts, source_lang, batch_size):  # type: ignore[no-untyped-def]
        import torch

        self.calls.append(
            {
                "texts": list(texts),
                "source_lang": source_lang,
                "batch_size": batch_size,
            }
        )
        return torch.stack([self.embeddings[t] for t in texts])


class FakeBlaserModel:
    """Stand-in for the loaded BLASER regressor. Returns queued scores as a
    [N, 1] tensor when called with (src=..., mt=...)."""

    def __init__(self, queued: list[list[float]]) -> None:
        self._queued = list(queued)
        self.calls: list[dict] = []

    def __call__(self, src, mt):  # type: ignore[no-untyped-def]
        import torch

        if not self._queued:
            raise RuntimeError(
                f"FakeBlaserModel out of queued scores; got {src.shape[0]} more rows"
            )
        scores = self._queued.pop(0)
        if len(scores) != src.shape[0]:
            raise RuntimeError(
                f"FakeBlaserModel: queued {len(scores)} scores, got {src.shape[0]} rows"
            )
        self.calls.append({"src_shape": tuple(src.shape), "mt_shape": tuple(mt.shape)})
        return torch.tensor(scores).reshape(-1, 1)

    def eval(self):
        return self


def _make_blaser_stage(
    embeddings: dict,
    queued_scores: list[list[float]],
    **kwargs,
) -> BlaserStage:
    return BlaserStage(
        _encoder_obj=FakeSonarEncoder(embeddings),
        _blaser_obj=FakeBlaserModel(queued_scores),
        **kwargs,
    )


def test_blaser_writes_metric_per_row():
    import torch

    embs = {
        "Прывітанне.": torch.tensor([1.0, 0.0, 0.0]),
        "Hello.": torch.tensor([0.9, 0.1, 0.0]),
        "Дзякуй.": torch.tensor([0.0, 1.0, 0.0]),
        "Thanks.": torch.tensor([0.0, 0.9, 0.1]),
    }
    stage = _make_blaser_stage(embs, [[4.2, 4.8]])
    rows = [
        {"src": "Прывітанне.", "tgt": "Hello."},
        {"src": "Дзякуй.", "tgt": "Thanks."},
    ]
    stage.process_batch(rows)
    assert rows[0]["metrics"]["blaser_score"] == pytest.approx(4.2)
    assert rows[1]["metrics"]["blaser_score"] == pytest.approx(4.8)


def test_blaser_uses_configured_fields_and_lang_codes():
    import torch

    embs = {
        "Гэта прыклад.": torch.tensor([1.0, 0.0]),
        "This is an example.": torch.tensor([0.9, 0.1]),
    }
    stage = _make_blaser_stage(
        embs,
        [[4.0]],
        src_field="src_text",
        tgt_field="tgt_text",
        src_lang="bel_Cyrl",
        tgt_lang="eng_Latn",
    )
    row = {"src_text": "Гэта прыклад.", "tgt_text": "This is an example."}
    stage.process_batch([row])
    # Encoder saw the right fields and lang codes:
    src_call, tgt_call = stage.encoder.calls
    assert src_call["texts"] == ["Гэта прыклад."]
    assert src_call["source_lang"] == "bel_Cyrl"
    assert tgt_call["texts"] == ["This is an example."]
    assert tgt_call["source_lang"] == "eng_Latn"


def test_blaser_metric_key_override_suffixes_name():
    import torch

    embs = {"a": torch.tensor([1.0]), "b": torch.tensor([1.0])}
    stage = _make_blaser_stage(embs, [[3.5]], metric_key="blaser_qe")
    assert stage.name == "blaser_blaser_qe"
    row = {"src": "a", "tgt": "b"}
    stage.process_batch([row])
    assert "blaser_qe" in row["metrics"]
    assert "blaser_score" not in row["metrics"]


def test_blaser_default_metric_key_keeps_default_name():
    stage = _make_blaser_stage({}, [])
    assert stage.name == "blaser"


def test_blaser_empty_batch_is_noop():
    stage = _make_blaser_stage({}, [])
    stage.process_batch([])
    assert stage.encoder.calls == []
    assert stage.blaser.calls == []
    assert stage.stats()["rows_total"] == 0


def test_blaser_passes_batch_size_to_encoder():
    import torch

    embs = {"a": torch.tensor([1.0]), "b": torch.tensor([1.0])}
    stage = _make_blaser_stage(embs, [[4.0]], batch_size=8)
    stage.process_batch([{"src": "a", "tgt": "b"}])
    assert stage.encoder.calls[0]["batch_size"] == 8


def test_blaser_stats_quantiles_and_mean():
    import torch

    texts = ["s0", "s1", "s2", "s3", "s4"]
    targets = ["t0", "t1", "t2", "t3", "t4"]
    embs = {t: torch.tensor([1.0]) for t in texts + targets}
    stage = _make_blaser_stage(embs, [[1.0, 2.0, 3.0, 4.0, 5.0]])
    rows = [{"src": s, "tgt": t} for s, t in zip(texts, targets)]
    stage.process_batch(rows)
    s = stage.stats()
    assert s["rows_total"] == 5
    assert s["mean"] == pytest.approx(3.0)
    assert s["score_quantiles"]["p50"] == pytest.approx(3.0)
    assert s["encoder"] == "text_sonar_basic_encoder"
    assert s["blaser_model"] == "blaser_2_0_qe"
    assert s["metric_key"] == "blaser_score"


def test_blaser_close_clears_handles():
    stage = _make_blaser_stage({}, [])
    stage.close()
    assert stage.encoder is None
    assert stage.blaser is None


def test_blaser_process_single_row_via_batch():
    import torch

    embs = {"a": torch.tensor([1.0]), "b": torch.tensor([1.0])}
    stage = _make_blaser_stage(embs, [[3.7]])
    row = {"src": "a", "tgt": "b"}
    stage.process(row)
    assert row["metrics"]["blaser_score"] == pytest.approx(3.7)


def test_sonar_cosine_stub_raises():
    with pytest.raises(NotImplementedError, match="SonarCosineStage"):
        SonarCosineStage()
