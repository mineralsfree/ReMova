"""Unicode NFKC normalization. Collapses compatibility lookalikes:
fullwidth/halfwidth Latin and digits, ligatures, Roman-numeral codepoints,
superscript digits, etc. See plan.txt FIXING block.
"""

import unicodedata

from peratrasher.base import Stage


class NFKCStage(Stage):
    name = "nfkc"

    def __init__(self, output_field: str = "text") -> None:
        self.output_field = output_field
        self._rows_total = 0
        self._rows_changed = 0

    def process(self, row: dict) -> None:
        self._rows_total += 1
        original = row["text"]
        normalized = unicodedata.normalize("NFKC", original)
        if normalized != original:
            self._rows_changed += 1
            row[self.output_field] = normalized

    def stats(self) -> dict:
        return {
            "rows_total": self._rows_total,
            "rows_changed": self._rows_changed,
        }
