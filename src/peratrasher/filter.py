"""Final filter stage: drop rows that fail any of a YAML-configured rule list.

Reads the JSONL produced by the rest of the pipeline (with `metrics` and
`removal_reasons` populated by earlier stages), applies each rule in order,
and writes survivors and rejects to two files. Each rejected row carries a
`filtered_by: [rule_name, ...]` field listing every rule that rejected it.

Rules are AND'd: a row survives only if every rule's predicate returns True.

Rule types
----------
- no_removal_reasons        — row passes iff `removal_reasons` is empty.
- reject_if_reason          — row passes iff a specific reason is NOT in
                              `removal_reasons`. Params: reason.
- min_metric                — row passes iff `_get(row, key) >= value`.
                              Missing key → fails. Params: key, value.
- max_metric                — row passes iff `_get(row, key) <= value`.
                              Missing key → passes (no signal, no objection).
                              Params: key, value.
- require_true              — row passes iff `bool(_get(row, key))`.
                              Missing key → fails. Params: key.
- not_contains              — row passes iff `substring` is NOT in
                              `_get(row, key)`. Non-string / missing →
                              passes (no objection). Params: key, substring.

`key` is a dotted path into the row dict, e.g. `metrics.src_langtool.density`.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

import yaml

from peratrasher.configio import load_config
from peratrasher.jsonio import iter_jsonl, write_row


def _get(row: dict, key: str, default=None):
    """Resolve a dotted path. 'metrics.src_langtool.density' →
    row['metrics']['src_langtool']['density']. Returns `default` if any segment
    is missing or any non-final segment is not a dict."""
    cur: Any = row
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _no_removal_reasons(row: dict, params: dict) -> bool:
    return not row.get("removal_reasons")


def _reject_if_reason(row: dict, params: dict) -> bool:
    return params["reason"] not in row.get("removal_reasons", [])


def _min_metric(row: dict, params: dict) -> bool:
    value = _get(row, params["key"])
    if value is None:
        return False  # missing signal — fail closed
    return value >= params["value"]


def _max_metric(row: dict, params: dict) -> bool:
    value = _get(row, params["key"])
    if value is None:
        return True  # missing signal — no objection
    return value <= params["value"]


def _require_true(row: dict, params: dict) -> bool:
    return bool(_get(row, params["key"]))


def _not_contains(row: dict, params: dict) -> bool:
    value = _get(row, params["key"])
    if not isinstance(value, str):
        return True
    return params["substring"] not in value


RULE_LIBRARY: dict[str, Callable[[dict, dict], bool]] = {
    "no_removal_reasons": _no_removal_reasons,
    "reject_if_reason": _reject_if_reason,
    "min_metric": _min_metric,
    "max_metric": _max_metric,
    "require_true": _require_true,
    "not_contains": _not_contains,
}


def apply_filter(row: dict, rules: list[dict]) -> list[str]:
    """Return list of rule names that REJECTED this row (empty = survived)."""
    failed: list[str] = []
    for rule in rules:
        predicate = RULE_LIBRARY[rule["type"]]
        if not predicate(row, rule):
            failed.append(rule["name"])
    return failed


def _validate_rules(rules: list[dict]) -> None:
    seen: set[str] = set()
    for r in rules:
        if "name" not in r:
            raise ValueError(f"filter rule missing `name`: {r!r}")
        if r["name"] in seen:
            raise ValueError(f"duplicate filter name: {r['name']!r}")
        seen.add(r["name"])
        if r["type"] not in RULE_LIBRARY:
            raise ValueError(
                f"unknown filter type {r['type']!r}. "
                f"Available: {sorted(RULE_LIBRARY)}"
            )


def run(config_path: str | Path) -> None:
    cfg: dict[str, Any] = load_config(config_path)

    input_path = Path(cfg["input"])
    survived_path = Path(cfg["survived"])
    rejected_path = Path(cfg["rejected"])
    stats_dir = Path(cfg["stats_dir"])
    prefix = cfg["stats_prefix"]
    rules: list[dict] = cfg["filters"]
    _validate_rules(rules)

    stats_dir.mkdir(parents=True, exist_ok=True)
    survived_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)

    rule_names = [r["name"] for r in rules]
    per_rule_failures: dict[str, int] = {n: 0 for n in rule_names}
    funnel_dropped: dict[str, int] = {n: 0 for n in rule_names}

    n_rows = 0
    n_survived = 0
    start = time.perf_counter()
    with (
        open(survived_path, "w", encoding="utf-8") as fout_s,
        open(rejected_path, "w", encoding="utf-8") as fout_r,
    ):
        for row in iter_jsonl(input_path):
            n_rows += 1
            failed = apply_filter(row, rules)
            if not failed:
                write_row(fout_s, row)
                n_survived += 1
                continue
            for name in failed:
                per_rule_failures[name] += 1
            # Funnel attribution: blame the FIRST failing rule in declared order.
            first_fail = next(n for n in rule_names if n in failed)
            funnel_dropped[first_fail] += 1
            row_out = dict(row)
            row_out["filtered_by"] = failed
            write_row(fout_r, row_out)

    # Build sequential funnel: remaining after each rule, in declared order.
    funnel: list[dict] = []
    remaining = n_rows
    for name in rule_names:
        d = funnel_dropped[name]
        remaining -= d
        funnel.append({"rule": name, "dropped": d, "remaining_after": remaining})

    elapsed = time.perf_counter() - start
    stats = {
        "rows_total": n_rows,
        "rows_survived": n_survived,
        "rows_rejected": n_rows - n_survived,
        "survival_rate": (n_survived / n_rows) if n_rows else 0.0,
        "per_rule_failures": per_rule_failures,
        "funnel": funnel,
        "processing_time_s": round(elapsed, 3),
    }
    (stats_dir / f"{prefix}_filter.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    rate = (n_survived / n_rows) if n_rows else 0
    print(
        f"  filter: {n_rows} rows -> {n_survived} survived ({rate:.1%}) "
        f"in {elapsed:.1f}s",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a list of YAML rules to a JSONL; write survivors and rejects "
            "to two files. Rejected rows carry `filtered_by: [rule_name, ...]`."
        )
    )
    parser.add_argument("--config", required=True, help="Path to YAML config.")
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
