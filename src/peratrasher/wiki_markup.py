"""Strip MediaWiki templates / wikilinks / formatting, keep reading text.

Wikipedia template families seen in be.wikipedia corpora:

  * `{{bt-bellat|Cyr|Lat}}`, `{{bt-latbel|Cyr|Lat}}` — BE Cyrillic↔Latin
    transliteration display. Reader sees Cyrillic by default; we keep the
    Cyrillic part. If arg 1 carries a `{{!}}`-escaped pipe (e.g.
    `Лебяда белая{{!}}лебядзе белай`), that's an embedded wiki-link
    `[[Лебяда белая|лебядзе белай]]` — the visible text is the part after
    `{{!}}`.
  * `{{нп3|target|display|lang|origname}}`, `{{нп}}`, `{{нп5}}`, `{{нпг}}`,
    `{{нп-арт}}` — interlanguage redlink. Reader sees `display` if non-empty,
    else `target`.
  * `{{lang-en|...}}`, `{{lang-de|...}}`, … — language tag, keep the
    wrapped text (last positional arg).
  * `{{cite ...}}`, `{{спасылка ...}}` — citation metadata; drop entirely.
  * Anything else — drop entirely. Safer than guessing.

After templates are handled, `mwparserfromhell.Wikicode.strip_code` removes
the rest: wiki links collapse to their display text, bold/italic markers
disappear, heading `==` signs go away.
"""

from __future__ import annotations

import re

import mwparserfromhell

from peratrasher.base import Stage

_DISPLAY_FIRST = {"bt-bellat", "bt-latbel"}
_DISPLAY_SECOND = {"нп3", "нп", "нп5", "нпг", "нп-арт"}
_DROP_PREFIXES = ("cite", "спасылка")
_WS_RE = re.compile(r"\s+")


def _positional(tpl) -> list[str]:
    return [str(p.value).strip() for p in tpl.params if not p.showkey]


def _bt_display(arg1: str, arg2: str) -> str:
    """bt-bellat / bt-latbel reading text."""
    if arg1:
        # Embedded wikilink via {{!}} escape: keep the display half.
        if "{{!}}" in arg1:
            return arg1.split("{{!}}", 1)[1].strip()
        return arg1
    return arg2


def clean(text: str) -> str:
    """Strip wiki markup; return the reading text."""
    code = mwparserfromhell.parse(text)
    for tpl in list(code.filter_templates(recursive=True)):
        try:
            name = str(tpl.name).strip().lower()
        except Exception:
            continue
        try:
            if name in _DISPLAY_FIRST:
                args = _positional(tpl)
                a1 = args[0] if len(args) >= 1 else ""
                a2 = args[1] if len(args) >= 2 else ""
                code.replace(tpl, _bt_display(a1, a2))
            elif name in _DISPLAY_SECOND:
                args = _positional(tpl)
                a1 = args[0] if len(args) >= 1 else ""
                a2 = args[1] if len(args) >= 2 else ""
                code.replace(tpl, a2 if a2 else a1)
            elif name.startswith("lang-") or name == "lang":
                args = _positional(tpl)
                code.replace(tpl, args[-1] if args else "")
            elif name == "!":
                code.replace(tpl, "|")
            elif any(name.startswith(p) for p in _DROP_PREFIXES):
                code.replace(tpl, "")
            else:
                code.replace(tpl, "")
        except ValueError:
            # Outer template already replaced; this inner one is gone with it.
            continue
    stripped = code.strip_code(normalize=True, collapse=True)
    return _WS_RE.sub(" ", stripped).strip()


class WikiMarkupStage(Stage):
    name = "wiki_markup"

    def __init__(
        self, input_field: str = "text", output_field: str | None = None
    ) -> None:
        self.input_field = input_field
        self.output_field = output_field if output_field is not None else input_field
        if input_field != "text":
            self.name = f"wiki_markup_{input_field}"
        self._rows_total = 0
        self._rows_changed = 0

    def process(self, row: dict) -> None:
        self._rows_total += 1
        original = row[self.input_field]
        # Fast-path: most rows have no wiki markup at all.
        if not any(m in original for m in ("{{", "[[", "''", "==", "<ref")):
            return
        cleaned = clean(original)
        if cleaned != original:
            self._rows_changed += 1
            row[self.output_field] = cleaned

    def stats(self) -> dict:
        return {
            "rows_total": self._rows_total,
            "rows_changed": self._rows_changed,
        }
