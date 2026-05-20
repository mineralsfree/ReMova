import pytest

from peratrasher.citations import CitationsStage


@pytest.mark.parametrize(
    "text_in, expected",
    [
        # numeric citations
        ("Some claim.[5] Another.[123] End.", "Some claim. Another. End."),
        # phrase tags (case-insensitive)
        ("Some claim.[citation needed] More.", "Some claim. More."),
        ("Case insensitive[Citation Needed]", "Case insensitive"),
        ("Question[who?] body.", "Question body."),
        # footnote letters and note markers
        ("Letter footnote[a] here.", "Letter footnote here."),
        ("Note marker[note 1] here.", "Note marker here."),
        ("Note marker[n 2] here.", "Note marker here."),
        # tag floating between two words: preceding space eaten, trailing kept → one space remains
        ("Абрана сябрам ў 1975 годзе [1] Стыпендыя.", "Абрана сябрам ў 1975 годзе Стыпендыя."),
        # tag glued to a period: no preceding space → trailing space preserved
        ("claim.[5] More text.", "claim. More text."),
        # tag glued tight on both sides: nothing inserted
        ("word[1]glued", "wordglued"),
    ],
)
def test_strips_inline_tags(text_in, expected):
    stage = CitationsStage()
    row = {"text": text_in}
    stage.process(row)
    assert row["text"] == expected


@pytest.mark.parametrize(
    "text",
    [
        # [sic] is intentional in quoted material
        'He said "they was [sic] going".',
        # years in brackets — 4+ digits not matched
        "In [2024] this happened.",
        # editor insertions in quotes — multi-word, not in INLINE_TAGS
        "He [the president] said something.",
        # IPA pronunciations
        "The word is pronounced [ˈbiːˌtuːl].",
    ],
)
def test_preserves_legitimate_brackets(text):
    stage = CitationsStage()
    row = {"text": text}
    stage.process(row)
    assert row["text"] == text
    assert stage.stats()["rows_changed"] == 0


def test_runs_on_alternate_field():
    stage = CitationsStage(input_field="tgt")
    row = {"src": "untouched [5]", "tgt": "cleaned[12]"}
    stage.process(row)
    assert row["src"] == "untouched [5]"  # different field
    assert row["tgt"] == "cleaned"
    assert stage.name == "citations_tgt"
