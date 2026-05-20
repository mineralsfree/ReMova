"""Strip Wikipedia inline citation / cleanup tags.

Covers what's actually rendered into OPUS-Wikimedia text:

  * numeric citations: [5], [12]
  * single-letter footnotes: [a], [b]
  * note markers: [note 1], [n 1]
  * the well-known phrase tags from Wikipedia's
    Category:Inline cleanup templates (`[citation needed]`,
    `[clarification needed]`, `[who?]`, etc.)

Deliberate non-matches:

  * `[sic]` — sometimes intentional in quoted material; left as-is.
  * 4+ digit `[2024]` — likely a year, not a citation.
  * Generic `[anything else]` — editor insertions in quotes
    ("He [the president] said…") and IPA pronunciations are
    legitimate content.
"""

import re

from peratrasher.base import Stage

# Phrase set drawn from Wikipedia's Category:Inline cleanup templates and
# Category:Inline citation cleanup templates. Case-insensitive at match time.
_INLINE_TAGS = {
    # verification / sourcing
    "citation needed", "better source needed", "verification needed",
    "failed verification", "not in citation given", "unreliable source?",
    "self-published source?", "self-published inline", "predatory source?",
    "third-party source needed", "non-primary source needed",
    "primary source inline", "user-generated source?",
    # clarification family
    "clarification needed", "clarify", "explain", "elaborate",
    "further explanation needed", "definition needed", "example needed",
    "vague", "ambiguous",
    # interrogatives
    "who?", "whom?", "what?", "when?", "where?", "why?", "how?", "which?",
    # dispute / NPOV
    "dubious – discuss", "dubious", "discuss", "disputed – discuss",
    "according to whom?", "by whom?", "neutrality disputed",
    "POV statement", "editorializing", "weasel words", "peacock prose",
    "original research?", "synthesis?", "opinion", "tone", "loaded language",
    # incompleteness
    "page needed", "year needed", "volume needed", "season needed",
    "episode needed", "time needed", "date missing", "title missing",
    "chapter needed", "quote needed", "context needed",
    # misc
    "contradictory", "non sequitur", "relevant?", "off-topic?",
    "anachronism", "incomprehensible",
}

_phrase = "|".join(re.escape(t) for t in _INLINE_TAGS)
# Leading ` ?` consumes a single preceding space if present, so "годзе [1] X"
# collapses to "годзе X" with one space instead of two. When there is no
# preceding space ("claim.[5] X" → "claim. X"), nothing is consumed and the
# original spacing is preserved.
_INLINE_RE = re.compile(
    rf" ?(?:"
    rf"\[\s*(?:{_phrase})\s*\]"        # phrase tags
    rf"|\[\s*\d{{1,3}}\s*\]"           # [5], [12]
    rf"|\[\s*[a-z]\s*\]"               # [a], [b]
    rf"|\[\s*note\s+\d+\s*\]"          # [note 1]
    rf"|\[\s*n\s+\d+\s*\]"             # [n 1]
    rf")",
    re.IGNORECASE,
)


class CitationsStage(Stage):
    name = "citations"

    def __init__(
        self, input_field: str = "text", output_field: str | None = None
    ) -> None:
        self.input_field = input_field
        self.output_field = output_field if output_field is not None else input_field
        if input_field != "text":
            self.name = f"citations_{input_field}"
        self._rows_total = 0
        self._rows_changed = 0

    def process(self, row: dict) -> None:
        self._rows_total += 1
        original = row[self.input_field]
        cleaned = _INLINE_RE.sub("", original)
        if cleaned != original:
            self._rows_changed += 1
            row[self.output_field] = cleaned

    def stats(self) -> dict:
        return {
            "rows_total": self._rows_total,
            "rows_changed": self._rows_changed,
        }
