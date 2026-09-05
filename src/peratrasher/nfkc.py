"""Unicode NFKC normalization. Collapses compatibility lookalikes:
fullwidth/halfwidth Latin and digits, ligatures, Roman-numeral codepoints,
superscript digits, etc. See plan.txt FIXING block.

After NFKC we also drop standalone combining marks (U+0300-U+036F & friends),
i.e. the optional stress accents seen in dictionary / Wikipedia-pronunciation /
stress-marked Bible & literary text ("яе́", "што́", "імя́"). NFKC keeps these —
Cyrillic vowel + acute has no precomposed codepoint, so it never composes away,
and LanguageTool then flags the accented word as an unknown misspelling.

Stripping is done on the *composed* (NFKC) string, NOT via NFD: real Belarusian
letters ё/й/ў are precomposed codepoints there (combining()==0) and survive,
while the leftover stress marks (combining()!=0) are removed. Decomposing first
would shred ё→е, й→и, ў→у.
"""

import unicodedata

from peratrasher.base import Stage


def _strip_combining(text: str) -> str:
    """Remove combining-mark codepoints from an already-composed string.
    Keeps base/precomposed letters; drops standalone accents like U+0301."""
    if not any(unicodedata.combining(c) for c in text):
        return text
    return "".join(c for c in text if not unicodedata.combining(c))


class NFKCStage(Stage):
    name = "nfkc"

    def __init__(
        self, input_field: str = "text", output_field: str | None = None
    ) -> None:
        self.input_field = input_field
        self.output_field = output_field if output_field is not None else input_field
        if input_field != "text":
            self.name = f"nfkc_{input_field}"
        self._rows_total = 0
        self._rows_changed = 0

    def process(self, row: dict) -> None:
        self._rows_total += 1
        original = row[self.input_field]
        normalized = _strip_combining(unicodedata.normalize("NFKC", original))
        if normalized != original:
            self._rows_changed += 1
            row[self.output_field] = normalized

    def stats(self) -> dict:
        return {
            "rows_total": self._rows_total,
            "rows_changed": self._rows_changed,
        }
