"""
Belarusian typography cleanup, ported from be.wikipedia Wikificator.
Source: https://be.wikipedia.org/wiki/MediaWiki:Gadget-wikificator.js

For plaintext (e.g. parallel corpora). Wiki-specific transformations
(templates, links, headings, tables, refs) are intentionally excluded.

Order matters. Apply via apply_rules(text).
"""

import re
from collections import Counter

from peratrasher.base import Stage

NBSP = " "

# ---- Always-on: invisibles, apostrophes, entities, whitespace -----------

CORE: list[tuple[re.Pattern, str]] = [
    # Soft hyphen + LTR/RTL direction marks
    (re.compile(r"[­‎‏]+"), ""),
    # Apostrophe: ' (U+0027) and ʼ (U+02BC) between letters -> ’ (U+2019)
    (re.compile(r"([\wа-яА-ЯёЁўЎіІ])['ʼ]([\wа-яА-ЯёЁўЎіІ])"), "\\1’\\2"),
    # HTML entities -> Unicode
    (re.compile(r"&copy;", re.I), "©"),
    (re.compile(r"&reg;", re.I), "®"),
    (re.compile(r"&sect;", re.I), "§"),
    (re.compile(r"&euro;", re.I), "€"),
    (re.compile(r"&yen;", re.I), "¥"),
    (re.compile(r"&pound;", re.I), "£"),
    (re.compile(r"&deg;"), "°"),
    (re.compile(r"\(tm\)|&trade;", re.I), "™"),
    (re.compile(r"\.\.\.|&hellip;"), "…"),
    (re.compile(r"\+-(?!\+|-)|&plusmn;"), "±"),
    (re.compile(r"~="), "≈"),
    (re.compile(r"&((la|ra|bd|ld)quo|quot);"), '"'),
    # Superscripts
    (re.compile(r"<sup>2</sup>|&sup2;", re.I), "²"),
    (re.compile(r"<sup>3</sup>|&sup3;", re.I), "³"),
    (re.compile(r"\^2(\D)"), r"²\1"),
    (re.compile(r"\^3(\D)"), r"³\1"),
    # ASCII guillemets <<X>> -> "X"
    (re.compile(r"<<(\S.+?\S)>>"), r'"\1"'),
    # №№ -> №
    (re.compile(r"№№"), "№"),
    # Trailing whitespace at EOL
    (re.compile(r"[ \t]+(\r?\n)"), r"\1"),
]

# ---- Dash / hyphen / minus normalization --------------------------------

DASHES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"–"), "-"),  # en-dash -> hyphen (intermediate)
    (re.compile(r"(\s)-{1,3} "), r"\1— "),  # " -- " -> " — "
    (re.compile(r"(\d)--(\d)"), r"\1—\2"),  # "1--2" -> "1—2"
    (re.compile(r"(\s)-(\d)"), r"\1−\2"),  # " -5" -> " −5" (proper minus)
    (re.compile(r"(sup>|sub>|\s)-(\d)"), r"\1−\2"),
]

# ---- NBSP insertion rules -----------------------------------------------

NBSP_RULES: list[tuple[re.Pattern, str]] = [
    # Year ranges & "гг."
    (
        re.compile(r"([(\s])([12]?\d{3})[  ]?(?:-{1,3}|—) ?([12]?\d{3})(?![\w-])"),
        r"\1\2—\3",
    ),
    (re.compile(r"([12]?\d{3}) ?(гг?\.)"), r"\1" + NBSP + r"\2"),
    # Century ranges & "стст."
    (
        re.compile(r"([(\s])([IVX]{1,5})[  ]?(?:-{1,3}|—) ?([IVX]{1,5})(?![\w-])"),
        r"\1\2—\3",
    ),
    (re.compile(r"([IVX]{1,5}) ?(стст?\.)"), r"\1" + NBSP + r"\2"),
    # Number + unit (млн, млрд, трлн, мм/см/дм/км, мг/кг, м, г)
    (
        re.compile(
            r'(\d)[  ]?(млн|млрд|трлн|(?:м|с|д|к)?м|[км]г)\.?(?=[,;.]| "?[а-яёўі-])'
        ),
        r"\1" + NBSP + r"\2",
    ),
    (re.compile(r"(\d)[  ](тыс)([^\.А-Яа-яЁёЎўІі])"), r"\1" + NBSP + r"\2.\3"),
    # ISBN
    (re.compile(r"ISBN:\s?(?=[\d\-]{8,17})"), "ISBN "),
    # Initials: А.С.Пушкін -> А. С. Пушкін (with NBSPs)
    (
        re.compile(r"([А-ЯЁЎІ]\.) ?([А-ЯЁЎІ]\.) ?([А-ЯЁЎІ][а-яёўі])"),
        r"\1" + NBSP + r"\2" + NBSP + r"\3",
    ),
    (re.compile(r"([А-ЯЁЎІ]\.)([А-ЯЁЎІ]\.)"), r"\1 \2"),
    # Sentence boundary missing space: "слова.Слова" -> "слова. Слова"
    (re.compile(r"([а-яёўі]\.)([А-ЯA-ZЁЎІ])"), r"\1 \2"),
    # Comma / semicolon: "word ,word" / "word , word" -> "word, word"
    (re.compile(r'([)"а-яa-zёўі\]])\s*,([\[("а-яa-zёўі])'), r"\1, \2"),
    (re.compile(r'([)"а-яa-zёўі\]])\s([,;])\s([\[("а-яa-zёўі])'), r"\1\2 \3"),
    # Percent / permille
    (
        re.compile(r"([^%/\w]\d+?(?:[.,]\d+?)?) ?([%‰])(?!-[А-Яа-яЁёЎўІі])"),
        r"\1" + NBSP + r"\2",
    ),
    (re.compile(r"(\d) ([%‰])(?=-[А-Яа-яЁёЎўІі])"), r"\1\2"),  # "5%-й"
    # № and §
    (re.compile(r"([№§])\s*(\d)"), r"\1" + NBSP + r"\2"),
    # Bracket whitespace
    (re.compile(r"\( +"), "("),
    (re.compile(r" +\)"), ")"),
    # Temperature: "20 °C" -> "20 °C"
    (
        re.compile(
            r'([\s\d=≈≠≤≥<>—("\'|])([+±−-]?\d+?(?:[.,]\d+?)?)'
            r'(?:[ °^*]| [°^*])[CС](?=[\s"\').,;!?|])'
        ),
        r"\1\2" + NBSP + "°C",
    ),
    (
        re.compile(
            r'([\s\d=≈≠≤≥<>—("\'|])([+±−-]?\d+?(?:[.,]\d+?)?)'
            r'(?:[ °^*]| [°^*])F(?=[\s"\').,;|!?])'
        ),
        r"\1\2" + NBSP + "°F",
    ),
    # Decimal: dot -> comma before %/‰/°
    (re.compile(r"(\s\d+)\.(\d+[  ]*[%‰°])"), r"\1,\2"),
]

# ---- Whitespace collapse (run last) -------------------------------------

COLLAPSE: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[ \t ]{2,}"), " "),
]

# ---- Quote pairing (multi-pass) -----------------------------------------
# Strategy: unify all quote glyphs to ASCII " then re-pair into «…» / „…“.

_QUOTE_UNIFY = re.compile(r"[«»“”„]")
_QUOTE_PAIR = re.compile(
    r'([\xa0\s\x02!|#\'"/(;+\-])"([^"]*)([^\s"(|])"'
    r"([^a-zA-Zа-яА-ЯёіўЁІ0-9])"
)
_QUOTE_NEST_RE = re.compile(r"«[^»]*«")
_QUOTE_NEST = re.compile(r"«([^»]*)«([^»]*)»")


def normalize_quotes(text: str) -> str:
    text = _QUOTE_UNIFY.sub('"', text)
    for _ in range(2):
        text = _QUOTE_PAIR.sub(r"\1«\2\3»\4", text)
    while _QUOTE_NEST_RE.search(text):
        text = _QUOTE_NEST.sub("«\\1„\\2“", text)
    return text


def _apply_group(
    text: str,
    rules: list[tuple[re.Pattern, str]],
    group: str,
    fires: Counter,
) -> str:
    for i, (pat, rep) in enumerate(rules):
        new = pat.sub(rep, text)
        if new != text:
            fires[f"{group}[{i}]"] += 1
            text = new
    return text


def apply_rules(
    text: str,
    *,
    apply_dashes: bool = True,
    apply_nbsp: bool = True,
    apply_quotes: bool = True,
) -> tuple[str, dict[str, int]]:
    """Apply Belarusian typography fixes; return (cleaned, per-rule fire counts)."""
    fires: Counter[str] = Counter()
    text = _apply_group(text, CORE, "core", fires)
    if apply_dashes:
        text = _apply_group(text, DASHES, "dashes", fires)
    if apply_nbsp:
        text = _apply_group(text, NBSP_RULES, "nbsp", fires)
    if apply_quotes:
        new = normalize_quotes(text)
        if new != text:
            fires["quotes"] += 1
            text = new
    text = _apply_group(text, COLLAPSE, "collapse", fires)
    return text, dict(fires)


class WikificatorStage(Stage):
    name = "wikificator"

    def __init__(
        self,
        output_field: str = "text",
        apply_dashes: bool = True,
        apply_nbsp: bool = True,
        apply_quotes: bool = True,
    ) -> None:
        self.output_field = output_field
        self.apply_dashes = apply_dashes
        self.apply_nbsp = apply_nbsp
        self.apply_quotes = apply_quotes
        self._rows_total = 0
        self._rows_changed = 0
        self._rule_fire_counts: Counter[str] = Counter()

    def process(self, row: dict) -> None:
        self._rows_total += 1
        original = row["text"]
        cleaned, fires = apply_rules(
            original,
            apply_dashes=self.apply_dashes,
            apply_nbsp=self.apply_nbsp,
            apply_quotes=self.apply_quotes,
        )
        if cleaned != original:
            self._rows_changed += 1
            row[self.output_field] = cleaned
        for name, n in fires.items():
            self._rule_fire_counts[name] += n

    def stats(self) -> dict:
        return {
            "rows_total": self._rows_total,
            "rows_changed": self._rows_changed,
            "rule_fire_counts": dict(self._rule_fire_counts),
        }
