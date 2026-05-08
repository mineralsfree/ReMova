"""
Belarusian typography cleanup, ported from be.wikipedia Wikificator.
Source: https://be.wikipedia.org/wiki/MediaWiki:Gadget-wikificator.js

For plaintext (e.g. parallel corpora). Wiki-specific transformations
(templates, links, headings, tables, refs) are intentionally excluded.

Order matters. Apply via clean(text).

Notes for MT corpus use:
- Apostrophe normalization (' / ʼ -> ’) and invisible-char removal are
  high-value: they reduce OOV and tokenization noise.
- NBSP insertion rules are typographic; if your tokenizer treats NBSP as
  ordinary whitespace this is a no-op, otherwise consider skipping
  (apply_nbsp=False).
- Dash/minus conversions push ASCII hyphens to Unicode em-dash / minus.
  Disable via apply_dashes=False if you want ASCII-only output.
"""

import re

NBSP = "\u00a0"

# ---- Always-on: invisibles, apostrophes, entities, whitespace -----------

CORE = [
    # Soft hyphen + LTR/RTL direction marks
    (re.compile(r"[\u00AD\u200E\u200F]+"), ""),
    # Apostrophe: ' (U+0027) and ʼ (U+02BC) between letters -> ’ (U+2019)
    (re.compile(r"([\wа-яА-ЯёЁўЎіІ])['\u02BC]([\wа-яА-ЯёЁўЎіІ])"), "\\1\u2019\\2"),
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

DASHES = [
    (re.compile(r"–"), "-"),  # en-dash -> hyphen (intermediate)
    (re.compile(r"(\s)-{1,3} "), r"\1— "),  # " -- " -> " — "
    (re.compile(r"(\d)--(\d)"), r"\1—\2"),  # "1--2" -> "1—2"
    (re.compile(r"(\s)-(\d)"), r"\1−\2"),  # " -5" -> " −5" (proper minus)
    (re.compile(r"(sup>|sub>|\s)-(\d)"), r"\1−\2"),
]

# ---- NBSP insertion rules -----------------------------------------------

NBSP_RULES = [
    # Year ranges & "гг."
    (
        re.compile(r"([(\s])([12]?\d{3})[\u00A0 ]?(?:-{1,3}|—) ?([12]?\d{3})(?![\w-])"),
        r"\1\2—\3",
    ),
    (re.compile(r"([12]?\d{3}) ?(гг?\.)"), r"\1" + NBSP + r"\2"),
    # Century ranges & "стст."
    (
        re.compile(r"([(\s])([IVX]{1,5})[\u00A0 ]?(?:-{1,3}|—) ?([IVX]{1,5})(?![\w-])"),
        r"\1\2—\3",
    ),
    (re.compile(r"([IVX]{1,5}) ?(стст?\.)"), r"\1" + NBSP + r"\2"),
    # Number + unit (млн, млрд, трлн, мм/см/дм/км, мг/кг, м, г)
    (
        re.compile(
            r'(\d)[\u00A0 ]?(млн|млрд|трлн|(?:м|с|д|к)?м|[км]г)\.?(?=[,;.]| "?[а-яёўі-])'
        ),
        r"\1" + NBSP + r"\2",
    ),
    (re.compile(r"(\d)[\u00A0 ](тыс)([^\.А-Яа-яЁёЎўІі])"), r"\1" + NBSP + r"\2.\3"),
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
    # Temperature: "20 °C" -> "20\u00A0°C"
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
    (re.compile(r"(\s\d+)\.(\d+[\u00A0 ]*[%‰°])"), r"\1,\2"),
]

# ---- Whitespace collapse (run last) -------------------------------------

COLLAPSE = [
    (re.compile(r"[ \t\u00A0]{2,}"), " "),
]

# ---- Quote pairing (multi-pass) -----------------------------------------
# Strategy: unify all quote glyphs to ASCII " then re-pair into «…» / „…“.

_QUOTE_UNIFY = re.compile(r"[«»\u201C\u201D„]")
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
    # Switch inner pair to „ … “  (Belarusian/Russian nesting convention)
    while _QUOTE_NEST_RE.search(text):
        text = _QUOTE_NEST.sub("«\\1„\\2\u201c", text)
    return text


def clean(
    text: str,
    *,
    apply_dashes: bool = True,
    apply_nbsp: bool = True,
    apply_quotes: bool = True,
) -> str:
    """Apply Belarusian typography fixes. See module docstring for caveats."""
    for pat, rep in CORE:
        text = pat.sub(rep, text)
    if apply_dashes:
        for pat, rep in DASHES:
            text = pat.sub(rep, text)
    if apply_nbsp:
        for pat, rep in NBSP_RULES:
            text = pat.sub(rep, text)
    if apply_quotes:
        text = normalize_quotes(text)
    for pat, rep in COLLAPSE:
        text = pat.sub(rep, text)
    return text


if __name__ == "__main__":
    import sys

    sys.stdout.write(clean(sys.stdin.read()))
