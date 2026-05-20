"""Parallel-pair cleaning CLI.

Runs the same Stage pipeline as the monolingual pipeline but on bitext rows
(`src` + `tgt` fields). Every monolingual stage with an `input_field` kwarg
(wikificator, ftfy, nfkc, glotlid) can be used directly — just write it
twice in the YAML, once per side. Two extra parallel-only stages are
provided:

  * length_ratio  — drops pairs whose length ratio is out of bounds.
  * bi_glotlid    — one GlotLID model, two predictions per row (saves the
                    second model load over running glotlid twice).
"""

import argparse
from collections import Counter
from typing import Any

import fasttext
import yaml

from peratrasher.base import Stage
from peratrasher.pipeline import STAGES, _run_pipeline


class LengthRatioStage(Stage):
    name = "length_ratio"

    def __init__(
        self,
        src_field: str = "src",
        tgt_field: str = "tgt",
        min_ratio: float = 0.5,
        max_ratio: float = 2.0,
        unit: str = "words",
        length_slack: int | None = None,
    ) -> None:
        if unit not in ("chars", "words"):
            raise ValueError(f"unit must be 'chars' or 'words', got {unit!r}")
        if length_slack is not None and length_slack < 0:
            raise ValueError(f"length_slack must be >= 0, got {length_slack}")
        self.src_field = src_field
        self.tgt_field = tgt_field
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio
        self.unit = unit
        # When set, a pair is flagged only if BOTH the ratio bound and the
        # absolute length difference are violated. Short pairs (diff <= slack)
        # are protected from being flagged on ratio alone.
        self.length_slack = length_slack
        self._rows_total = 0
        self._rows_flagged = 0
        self._ratios: list[float] = []
        self._diffs: list[int] = []

    def _measure(self, text: str) -> int:
        return len(text.split()) if self.unit == "words" else len(text)

    def process(self, row: dict) -> None:
        self._rows_total += 1
        src_len = max(self._measure(row[self.src_field]), 1)
        tgt_len = max(self._measure(row[self.tgt_field]), 1)
        ratio = tgt_len / src_len
        abs_diff = abs(tgt_len - src_len)
        metrics = row.setdefault("metrics", {})
        metrics["len_ratio"] = ratio
        metrics["len_diff"] = abs_diff
        self._ratios.append(ratio)
        self._diffs.append(abs_diff)
        reasons = row.setdefault("removal_reasons", [])
        ratio_violated = not (self.min_ratio <= ratio <= self.max_ratio)
        diff_violated = self.length_slack is None or abs_diff > self.length_slack
        if ratio_violated and diff_violated:
            reasons.append("len_ratio_out_of_bounds")
            self._rows_flagged += 1

    def stats(self) -> dict:
        out: dict[str, Any] = {
            "rows_total": self._rows_total,
            "rows_flagged": self._rows_flagged,
            "unit": self.unit,
            "bounds": [self.min_ratio, self.max_ratio],
            "length_slack": self.length_slack,
        }
        if self._ratios:
            n = len(self._ratios)
            sorted_r = sorted(self._ratios)
            sorted_d = sorted(self._diffs)

            def q(xs: list, p: float):
                return xs[min(int(n * p), n - 1)]

            out["len_ratio_quantiles"] = {
                "p10": q(sorted_r, 0.10),
                "p50": q(sorted_r, 0.50),
                "p90": q(sorted_r, 0.90),
                "p99": q(sorted_r, 0.99),
            }
            out["len_diff_quantiles"] = {
                "p10": q(sorted_d, 0.10),
                "p50": q(sorted_d, 0.50),
                "p90": q(sorted_d, 0.90),
                "p99": q(sorted_d, 0.99),
            }
        return out


class BiGlotLIDStage(Stage):
    """Single GlotLID model, two predictions per row. Saves the second
    model load compared with running `glotlid` twice."""

    name = "bi_glotlid"

    def __init__(
        self,
        model_path: str,
        src_field: str = "src",
        tgt_field: str = "tgt",
        src_lang_field: str = "src_lang",
        tgt_lang_field: str = "tgt_lang",
        score_threshold: float = 0.7,
        min_words: int = 0,
    ) -> None:
        self.model = fasttext.load_model(model_path)
        self.src_field = src_field
        self.tgt_field = tgt_field
        self.src_lang_field = src_lang_field
        self.tgt_lang_field = tgt_lang_field
        self.score_threshold = score_threshold
        # GlotLID is unreliable on very short text (≤4 tokens it mostly guesses
        # at the script level, e.g. flagging short Belarusian as Russian/
        # Ukrainian or short English as Esperanto/Swiss-German). When
        # `min_words > 0` and EITHER side has fewer tokens than that, we skip
        # the flag step entirely (still record predictions for diagnostics).
        self.min_words = min_words
        self._rows_total = 0
        self._src_flagged = 0
        self._tgt_flagged = 0
        self._both_flagged = 0
        self._skipped_short = 0
        self._src_label_totals: Counter[str] = Counter()
        self._tgt_label_totals: Counter[str] = Counter()

    def _predict(self, text: str) -> tuple[str, float]:
        labels, scores = self.model.predict(text.replace("\n", " "), k=1)
        return labels[0].removeprefix("__label__"), float(scores[0])

    def process(self, row: dict) -> None:
        self._rows_total += 1
        src_text = row[self.src_field]
        tgt_text = row[self.tgt_field]
        src_label, src_score = self._predict(src_text)
        tgt_label, tgt_score = self._predict(tgt_text)

        metrics = row.setdefault("metrics", {})
        metrics["src_glotlid_label"] = src_label
        metrics["src_glotlid_score"] = src_score
        metrics["tgt_glotlid_label"] = tgt_label
        metrics["tgt_glotlid_score"] = tgt_score

        self._src_label_totals[src_label] += 1
        self._tgt_label_totals[tgt_label] += 1

        # Skip flag evaluation for too-short pairs — GlotLID is unreliable
        # below ~5 tokens. Predictions are kept on the row for diagnostics;
        # we just don't treat a short-text mismatch as a hard objection.
        if self.min_words > 0 and (
            len(src_text.split()) < self.min_words
            or len(tgt_text.split()) < self.min_words
        ):
            self._skipped_short += 1
            # Make sure `removal_reasons` exists on the row so downstream
            # filters can still inspect it.
            row.setdefault("removal_reasons", [])
            return

        src_wrong = (
            src_label != row.get(self.src_lang_field)
            or src_score < self.score_threshold
        )
        tgt_wrong = (
            tgt_label != row.get(self.tgt_lang_field)
            or tgt_score < self.score_threshold
        )

        reasons = row.setdefault("removal_reasons", [])
        if src_wrong:
            reasons.append("src_wrong_lang")
            self._src_flagged += 1
        if tgt_wrong:
            reasons.append("tgt_wrong_lang")
            self._tgt_flagged += 1
        if src_wrong and tgt_wrong:
            self._both_flagged += 1

    def stats(self) -> dict:
        return {
            "rows_total": self._rows_total,
            "src_flagged": self._src_flagged,
            "tgt_flagged": self._tgt_flagged,
            "both_flagged": self._both_flagged,
            "skipped_short": self._skipped_short,
            "min_words": self.min_words,
            "src_label_totals": dict(self._src_label_totals),
            "tgt_label_totals": dict(self._tgt_label_totals),
        }


# Parallel STAGES inherits all monolingual stages, so wikificator/ftfy/nfkc/
# glotlid can be reused on `src`/`tgt` by setting their `input_field` kwarg.
PARALLEL_STAGES: dict[str, type[Stage]] = {
    **STAGES,
    "length_ratio": LengthRatioStage,
    "bi_glotlid": BiGlotLIDStage,
}


def run(config_path: str) -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)
    _run_pipeline(cfg, PARALLEL_STAGES)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parallel-pair (bitext) cleaner. Monolingual stages reusable via input_field."
    )
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
