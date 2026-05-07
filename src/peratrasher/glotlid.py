import fasttext

from peratrasher.base import Stage


class GlotLIDStage(Stage):
    name = "glotlid"

    def __init__(self, model_path: str, score_threshold: float = 0.5) -> None:
        self.model = fasttext.load_model(model_path)
        self.score_threshold = score_threshold
        self._rows_total = 0
        self._rows_flagged = 0
        self._scores: list[float] = []

    def process(self, row: dict) -> None:
        self._rows_total += 1
        text = row["text"].replace("\n", " ")
        labels, scores = self.model.predict(text, k=1)
        label = labels[0].removeprefix("__label__")
        score = float(scores[0])

        metrics = row.setdefault("metrics", {})
        metrics["glotlid_label"] = label
        metrics["glotlid_score"] = score

        if label != row.get("original_code") or score < self.score_threshold:
            row.setdefault("removal_reasons", []).append("wrong_lang")
            self._rows_flagged += 1

        self._scores.append(score)

    def stats(self) -> dict:
        out: dict = {
            "rows_total": self._rows_total,
            "rows_flagged": self._rows_flagged,
        }
        if self._scores:
            sorted_scores = sorted(self._scores)
            n = len(sorted_scores)

            def q(p: float) -> float:
                return sorted_scores[min(int(n * p), n - 1)]

            out["score_quantiles"] = {
                "p10": q(0.10),
                "p50": q(0.50),
                "p90": q(0.90),
                "p99": q(0.99),
            }
        return out
