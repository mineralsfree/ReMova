"""Neural QE metrics — scores survived JSONL with one or more model-based
quality estimators. Today: BLASER 2.0 (`sonar-space`). Planned:
SONAR-cosine.

Mirrors the dedup/filter/export pattern: standalone CLI
(`peratrasher-neural`), one YAML config, JSONL in, JSONL out. Signal-only —
each stage writes `metrics.<metric_key>` on every row and never drops.

Stages are reused from `peratrasher.pipeline._run_pipeline`, so batching,
progress, per-stage stats, and `processing_time_s` come for free. Heavy
model deps are imported lazily inside `__init__`; importing this module
without `sonar-space` installed is fine — a stage only fails when
actually constructed.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import yaml

from peratrasher.base import Stage
from peratrasher.configio import load_config
from peratrasher.pipeline import _run_pipeline

class BlaserStage(Stage):
    """BLASER 2.0 reference-free QE (Meta) over SONAR embeddings.

    Encodes src and tgt with SONAR's text encoder, then runs the small MLP
    regressor trained on XSTS human judgments. Output is roughly [1, 5]
    on the original XSTS scale.

    Same Stage shape as the rest of the pipeline — read src/tgt, write
    `metrics.<metric_key>`, signal-only. Lang codes are SONAR / FLORES-200
    style (`bel_Cyrl`, `eng_Latn`).
    """

    name = "blaser"

    def __init__(
        self,
        src_field: str = "src",
        tgt_field: str = "tgt",
        src_lang: str = "bel_Cyrl",
        tgt_lang: str = "eng_Latn",
        encoder: str = "text_sonar_basic_encoder",
        blaser_model: str = "blaser_2_0_qe",
        metric_key: str = "blaser_score",
        batch_size: int = 32,
        device: str = "cuda",
        progress_bar: bool = False,
        _encoder_obj: Any = None,
        _blaser_obj: Any = None,
    ) -> None:
        self.src_field = src_field
        self.tgt_field = tgt_field
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.encoder_name = encoder
        self.blaser_model_name = blaser_model
        self.metric_key = metric_key
        self.batch_size = batch_size
        self.device = device
        self.progress_bar = progress_bar
        if metric_key != "blaser_score":
            self.name = f"blaser_{metric_key}"

        if _encoder_obj is not None or _blaser_obj is not None:
            # Test-injection path. Either or both may be supplied.
            self.encoder = _encoder_obj
            self.blaser = _blaser_obj
        else:
            # Lazy imports — only when the stage is actually constructed.
            import torch
            from sonar.inference_pipelines.text import (
                TextToEmbeddingModelPipeline,
            )
            from sonar.models.blaser.loader import load_blaser_model

            dev = torch.device(device)
            self.encoder = TextToEmbeddingModelPipeline(
                encoder=encoder, tokenizer=encoder, device=dev,
            )
            # load_blaser_model loads onto CPU regardless; move it so its
            # weights match the encoder's output tensors (avoid the
            # "weight on cpu but expected on mps/cuda" RuntimeError).
            self.blaser = load_blaser_model(blaser_model).eval().to(dev)

        self._rows_total = 0
        self._scores: list[float] = []

    def process(self, row: dict) -> None:
        self.process_batch([row])

    def process_batch(self, rows: list[dict]) -> None:
        if not rows:
            return
        src_texts = [r[self.src_field] for r in rows]
        tgt_texts = [r[self.tgt_field] for r in rows]

        src_emb = self.encoder.predict(
            src_texts, source_lang=self.src_lang, batch_size=self.batch_size,
        )
        tgt_emb = self.encoder.predict(
            tgt_texts, source_lang=self.tgt_lang, batch_size=self.batch_size,
        )

        import torch

        with torch.inference_mode():
            # BLASER QE: pass (src, mt); regressor returns [N, 1].
            scores_tensor = self.blaser(src=src_emb, mt=tgt_emb)
            scores = scores_tensor.squeeze(dim=-1).tolist()

        for row, score in zip(rows, scores):
            row.setdefault("metrics", {})[self.metric_key] = float(score)
            self._scores.append(float(score))
        self._rows_total += len(rows)
        if self.progress_bar:
            running_mean = sum(self._scores) / len(self._scores)
            print(
                f"  blaser: {self._rows_total} rows scored "
                f"(running mean={running_mean:.3f})",
                file=sys.stderr,
                flush=True,
            )

    def stats(self) -> dict:
        out: dict[str, Any] = {
            "rows_total": self._rows_total,
            "encoder": self.encoder_name,
            "blaser_model": self.blaser_model_name,
            "metric_key": self.metric_key,
        }
        if self._scores:
            sorted_s = sorted(self._scores)
            n = len(sorted_s)

            def q(p: float) -> float:
                return sorted_s[min(int(n * p), n - 1)]

            out["score_quantiles"] = {
                "p10": q(0.10),
                "p50": q(0.50),
                "p90": q(0.90),
                "p99": q(0.99),
            }
            out["mean"] = sum(self._scores) / len(self._scores)
        return out

    def close(self) -> None:
        self.encoder = None
        self.blaser = None
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:
            pass


class SonarCosineStage(Stage):
    """Stub for SONAR-cosine geometric similarity between src and tgt.

    Cheaper than BLASER: just embed both sides with SONAR's text encoder
    and compute cosine. Useful for catching gross misalignment.
    """

    name = "sonar_cosine"

    def __init__(self, **kwargs: Any) -> None:
        raise NotImplementedError(
            "SonarCosineStage is a stub. Implement using sonar-space text "
            "encoder + dot-product / cosine."
        )


NEURAL_STAGES: dict[str, type[Stage]] = {
    "blaser": BlaserStage,
    "sonar_cosine": SonarCosineStage,
}


def run(config_path: str) -> None:
    cfg: dict[str, Any] = load_config(config_path)
    _run_pipeline(cfg, NEURAL_STAGES)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Neural QE metrics on JSONL (BLASER 2.0 today; SONAR-cosine "
            "planned). Designed to run on the rule-filter's survived output "
            "so GPU compute only touches kept rows."
        )
    )
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
