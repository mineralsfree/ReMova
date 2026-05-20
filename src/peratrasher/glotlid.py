import fasttext

from peratrasher.base import Stage


class GlotLIDStage(Stage):
    name = "glotlid"

    def __init__(
        self,
        model_path: str,
        input_field: str = "text",
        lang_field: str = "original_code",
        metric_prefix: str = "glotlid",
        removal_reason: str = "wrong_lang",
        score_threshold: float = 0.5,
    ) -> None:
        self.model = fasttext.load_model(model_path)
        self.input_field = input_field
        self.lang_field = lang_field
        self.metric_prefix = metric_prefix
        self.removal_reason = removal_reason
        self.score_threshold = score_threshold
        if input_field != "text":
            self.name = f"glotlid_{input_field}"
        self._rows_total = 0
        self._rows_flagged = 0
        self._scores: list[float] = []

    def process(self, row: dict) -> None:
        self._rows_total += 1
        text = row[self.input_field].replace("\n", " ")
        labels, scores = self.model.predict(text, k=1)
        label = labels[0].removeprefix("__label__")
        score = float(scores[0])

        metrics = row.setdefault("metrics", {})
        metrics[f"{self.metric_prefix}_label"] = label
        metrics[f"{self.metric_prefix}_score"] = score

        if label != row.get(self.lang_field) or score < self.score_threshold:
            row.setdefault("removal_reasons", []).append(self.removal_reason)
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
