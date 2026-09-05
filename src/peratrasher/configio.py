"""YAML config loader with `$VAR` / `${VAR}` substitution from os.environ.

Lets a single set of `configs/*.yaml` describe the pipeline shape while the
dataset-specific bits (paths, field names, lang codes, stats prefix) live in
a per-dataset `.env` file the user sources before running. Same syntax as
the shell — `os.path.expandvars` does the substitution.

Unresolved placeholders are surfaced as a `KeyError` with a hint, rather
than silently producing nonsense paths.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

# Catches both `$VAR` and `${VAR}` forms — same as os.path.expandvars accepts.
_VAR_RE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")


def load_config(path: str | Path) -> dict[str, Any]:
    """Read YAML at `path`, expand env vars in the raw text, return parsed dict."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    expanded = os.path.expandvars(text)
    leftover = sorted(set(_VAR_RE.findall(expanded)))
    if leftover:
        raise KeyError(
            f"Unresolved env var(s) in {path}: {leftover}. "
            "Did you `source datasets/<name>.env` before running?"
        )
    return yaml.safe_load(expanded)
