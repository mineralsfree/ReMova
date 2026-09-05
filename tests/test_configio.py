"""Tests for peratrasher.configio.load_config()."""

from __future__ import annotations

import pytest

from peratrasher.configio import load_config


def test_no_vars_passes_through(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("input: data/foo.jsonl\nworkers: 8\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg == {"input": "data/foo.jsonl", "workers": 8}


def test_braced_var_substituted(tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET", "open_sub")
    p = tmp_path / "c.yaml"
    p.write_text("input: data/${DATASET}_clean.jsonl\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg == {"input": "data/open_sub_clean.jsonl"}


def test_unbraced_var_substituted(tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET", "x")
    p = tmp_path / "c.yaml"
    p.write_text("name: $DATASET\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg == {"name": "x"}


def test_missing_var_raises_with_hint(tmp_path, monkeypatch):
    monkeypatch.delenv("DATASET", raising=False)
    p = tmp_path / "c.yaml"
    p.write_text("input: data/${DATASET}.jsonl\n", encoding="utf-8")
    with pytest.raises(KeyError, match="DATASET"):
        load_config(p)


def test_multiple_vars_listed_in_error(tmp_path, monkeypatch):
    monkeypatch.delenv("A", raising=False)
    monkeypatch.delenv("B", raising=False)
    p = tmp_path / "c.yaml"
    p.write_text("x: $A\ny: ${B}\n", encoding="utf-8")
    with pytest.raises(KeyError) as ei:
        load_config(p)
    msg = str(ei.value)
    assert "$A" in msg and ("$B" in msg or "${B}" in msg)


def test_nested_values_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("FIELD", "be")
    p = tmp_path / "c.yaml"
    p.write_text(
        "stages:\n  - name: ftfy\n    input_field: ${FIELD}\n",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg == {"stages": [{"name": "ftfy", "input_field": "be"}]}
