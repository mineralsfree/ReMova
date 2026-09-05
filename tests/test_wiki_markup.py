"""Tests for peratrasher.wiki_markup.

Cases drawn from data/wikimedia.jsonl — these are the actual template
shapes seen in the corpus, not synthetic examples.
"""

from __future__ import annotations

from peratrasher.wiki_markup import WikiMarkupStage, clean


# ---- нп3 — interlanguage redlink template --------------------------------

def test_np3_full_args_uses_display():
    out = clean("{{нп3|Дзяржаўная бібліятэка Бамберга|Бамбергская дзяржаўная бібліятэка|ru|Государственная библиотека Бамберга}}")
    assert out == "Бамбергская дзяржаўная бібліятэка"


def test_np3_empty_display_falls_back_to_target():
    out = clean("{{нп3|Каірскі кодэкс|||Codex Cairensis}}")
    assert out == "Каірскі кодэкс"


def test_np3_inline_in_sentence():
    out = clean("Ён жыў у {{нп3|Сыроватка крыві|сыроваткі|ru|Сыворотка крови}} часе.")
    assert out == "Ён жыў у сыроваткі часе."


# ---- bt-bellat — BE Cyrillic↔Latin transliteration -----------------------

def test_bt_bellat_empty_first_uses_latin():
    assert clean("{{bt-bellat||Aname}}") == "Aname"


def test_bt_bellat_embedded_pipe_yields_display():
    """{{!}} escape: Cyr-arg `Лебяда белая{{!}}лебядзе белай` is a wikilink
    where 'лебядзе белай' is the visible text."""
    out = clean("Корм — {{bt-bellat|Лебяда белая{{!}}лебядзе белай|Chenopodium album}}.")
    assert out == "Корм — лебядзе белай."


def test_bt_bellat_no_pipe_uses_first_arg():
    out = clean("{{bt-bellat|крушына ломкая|Frangula alnus}}")
    assert out == "крушына ломкая"


def test_bt_latbel_same_logic():
    assert clean("{{bt-latbel|Isopyrum ludlowii|}}") == "Isopyrum ludlowii"


# ---- lang-XX language tag ------------------------------------------------

def test_lang_en_keeps_wrapped_text():
    assert clean("{{lang-en|USS Winston S. Churchill DDG 81}}") == "USS Winston S. Churchill DDG 81"


def test_lang_de_inline():
    out = clean("Назва: {{lang-de|Bundesrepublik Deutschland}}.")
    assert out == "Назва: Bundesrepublik Deutschland."


# ---- citation templates dropped -----------------------------------------

def test_cite_dropped():
    assert clean("{{cite web|url=x|title=y}}") == ""


def test_cite_inline_leaves_only_surrounding():
    out = clean("Гэта факт{{cite web|url=x|title=y}}, праўда.")
    assert out == "Гэта факт, праўда."


# ---- unknown template dropped -------------------------------------------

def test_unknown_template_dropped():
    assert clean("Сёння {{невядомы|param}} дзень.") == "Сёння дзень."


# ---- generic wiki markup handled by strip_code --------------------------

def test_wikilink_with_display_kept():
    assert clean("Гэта [[wikilink|вікіспасылка]] у тэксце.") == "Гэта вікіспасылка у тэксце."


def test_wikilink_no_pipe():
    assert clean("[[Менск]] — сталіца.") == "Менск — сталіца."


def test_bold_and_italic_stripped():
    assert clean("'''Жыр''' гэта ''вельмі добра''.") == "Жыр гэта вельмі добра."


# ---- plain text passthrough ---------------------------------------------

def test_plain_text_unchanged():
    text = "Гэта звычайны тэкст без вікі-разметкі."
    assert clean(text) == text


# ---- Stage wrapper -------------------------------------------------------

def test_stage_skips_clean_rows():
    """Fast-path: rows with no markup are not parsed at all (process()
    early-returns before clean() is called)."""
    stage = WikiMarkupStage(input_field="src")
    row = {"src": "Звычайны тэкст без разметкі."}
    stage.process(row)
    assert row["src"] == "Звычайны тэкст без разметкі."
    assert stage.stats()["rows_changed"] == 0


def test_stage_rewrites_row_in_place():
    stage = WikiMarkupStage(input_field="src")
    row = {"src": "{{нп3|A|B|ru|C}}"}
    stage.process(row)
    assert row["src"] == "B"
    assert stage.stats()["rows_changed"] == 1


def test_stage_separate_output_field():
    stage = WikiMarkupStage(input_field="src", output_field="src_clean")
    row = {"src": "{{нп3|A|B|ru|C}}"}
    stage.process(row)
    assert row["src"] == "{{нп3|A|B|ru|C}}"
    assert row["src_clean"] == "B"


def test_stage_auto_suffixes_name_on_custom_field():
    stage = WikiMarkupStage(input_field="src")
    assert stage.name == "wiki_markup_src"


def test_stage_default_name_unchanged():
    stage = WikiMarkupStage()
    assert stage.name == "wiki_markup"
