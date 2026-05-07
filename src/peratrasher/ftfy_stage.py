from collections import Counter

from ftfy import fix_and_explain

from peratrasher.base import Stage


class FtfyStage(Stage):
    name = "ftfy"

    def __init__(self, output_field: str = "text") -> None:
        self.output_field = output_field
        self._rows_total = 0
        self._rows_changed = 0
        self._explanations: Counter[str] = Counter()

    def process(self, row: dict) -> None:
        self._rows_total += 1
        original = row["text"]
        result = fix_and_explain(original)
        if result.text != original:
            self._rows_changed += 1
            row[self.output_field] = result.text
            for step in result.explanation or []:
                self._explanations[step[0]] += 1

    def stats(self) -> dict:
        return {
            "rows_total": self._rows_total,
            "rows_changed": self._rows_changed,
            "explanation_kinds": dict(self._explanations),
        }
