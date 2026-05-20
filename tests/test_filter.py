import json

import pytest

from peratrasher.filter import (
    _get,
    _max_metric,
    _min_metric,
    _no_removal_reasons,
    _reject_if_reason,
    _require_true,
    apply_filter,
    run,
)


# ---- dotted-path resolver ------------------------------------------------


def test_get_resolves_nested_path():
    row = {"metrics": {"x": {"y": 0.5}}}
    assert _get(row, "metrics.x.y") == 0.5


def test_get_returns_default_on_missing():
    assert _get({"a": 1}, "b", default="nope") == "nope"
    assert _get({"a": {"b": 1}}, "a.c") is None


def test_get_does_not_traverse_non_dict():
    assert _get({"a": "string"}, "a.b") is None


# ---- individual rule predicates ------------------------------------------


def test_no_removal_reasons():
    assert _no_removal_reasons({"removal_reasons": []}, {})
    assert _no_removal_reasons({}, {})  # missing key treated as empty
    assert not _no_removal_reasons({"removal_reasons": ["wrong_lang"]}, {})


def test_reject_if_reason():
    assert _reject_if_reason({"removal_reasons": ["other"]}, {"reason": "wrong_lang"})
    assert not _reject_if_reason(
        {"removal_reasons": ["wrong_lang", "x"]}, {"reason": "wrong_lang"}
    )
    assert _reject_if_reason({}, {"reason": "wrong_lang"})  # no reasons → pass


def test_min_metric_passes_when_at_or_above_threshold():
    assert _min_metric({"metrics": {"s": 0.9}}, {"key": "metrics.s", "value": 0.5})
    assert _min_metric({"metrics": {"s": 0.5}}, {"key": "metrics.s", "value": 0.5})


def test_min_metric_fails_below_threshold():
    assert not _min_metric({"metrics": {"s": 0.3}}, {"key": "metrics.s", "value": 0.5})


def test_min_metric_fails_on_missing():
    assert not _min_metric({}, {"key": "metrics.s", "value": 0.5})


def test_max_metric_passes_at_or_below_threshold():
    assert _max_metric({"metrics": {"d": 0.05}}, {"key": "metrics.d", "value": 0.1})
    assert _max_metric({"metrics": {"d": 0.1}}, {"key": "metrics.d", "value": 0.1})


def test_max_metric_fails_above_threshold():
    assert not _max_metric({"metrics": {"d": 0.5}}, {"key": "metrics.d", "value": 0.1})


def test_max_metric_passes_on_missing():
    # No signal → no objection (lenient).
    assert _max_metric({}, {"key": "metrics.d", "value": 0.1})


def test_require_true():
    assert _require_true({"metrics": {"k": True}}, {"key": "metrics.k"})
    assert not _require_true({"metrics": {"k": False}}, {"key": "metrics.k"})
    assert not _require_true({}, {"key": "metrics.k"})  # missing → fail


# ---- apply_filter aggregation --------------------------------------------


def test_apply_filter_all_pass():
    row = {
        "metrics": {"s": 0.99, "keep": True},
        "removal_reasons": [],
    }
    rules = [
        {"name": "no_reasons", "type": "no_removal_reasons"},
        {"name": "confident", "type": "min_metric", "key": "metrics.s", "value": 0.5},
        {"name": "keeper", "type": "require_true", "key": "metrics.keep"},
    ]
    assert apply_filter(row, rules) == []


def test_apply_filter_collects_all_failures_in_order():
    row = {
        "metrics": {"s": 0.3, "keep": False},
        "removal_reasons": ["wrong_lang"],
    }
    rules = [
        {"name": "no_reasons", "type": "no_removal_reasons"},
        {"name": "confident", "type": "min_metric", "key": "metrics.s", "value": 0.5},
        {"name": "keeper", "type": "require_true", "key": "metrics.keep"},
    ]
    assert apply_filter(row, rules) == ["no_reasons", "confident", "keeper"]


# ---- run() end-to-end ----------------------------------------------------


def _write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [
        json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l
    ]


def test_run_end_to_end_two_file_output(tmp_path):
    input_path = tmp_path / "in.jsonl"
    survived_path = tmp_path / "survived.jsonl"
    rejected_path = tmp_path / "rejected.jsonl"
    stats_dir = tmp_path / "stats"
    config_path = tmp_path / "cfg.yaml"

    rows = [
        {"id": 0, "metrics": {"score": 0.99, "keep": True}, "removal_reasons": []},     # survives
        {"id": 1, "metrics": {"score": 0.3,  "keep": True}, "removal_reasons": []},     # confident fails
        {"id": 2, "metrics": {"score": 0.99, "keep": False}, "removal_reasons": []},    # keeper fails
        {"id": 3, "metrics": {"score": 0.99, "keep": True}, "removal_reasons": ["x"]},  # no_reasons fails
        {"id": 4, "metrics": {"score": 0.1,  "keep": False}, "removal_reasons": ["x"]}, # all three fail
    ]
    _write_jsonl(input_path, rows)
    config_path.write_text(
        f"input: {input_path}\n"
        f"survived: {survived_path}\n"
        f"rejected: {rejected_path}\n"
        f"stats_dir: {stats_dir}\n"
        "stats_prefix: test\n"
        "filters:\n"
        "  - {name: no_reasons,   type: no_removal_reasons}\n"
        "  - {name: confident,    type: min_metric, key: metrics.score, value: 0.5}\n"
        "  - {name: keeper,       type: require_true, key: metrics.keep}\n",
        encoding="utf-8",
    )

    run(str(config_path))

    survived = _read_jsonl(survived_path)
    rejected = _read_jsonl(rejected_path)

    assert len(survived) == 1 and survived[0]["id"] == 0
    assert "filtered_by" not in survived[0]

    assert len(rejected) == 4
    by_id = {r["id"]: r["filtered_by"] for r in rejected}
    assert by_id[1] == ["confident"]
    assert by_id[2] == ["keeper"]
    assert by_id[3] == ["no_reasons"]
    assert by_id[4] == ["no_reasons", "confident", "keeper"]


def test_run_stats_funnel_and_per_rule(tmp_path):
    input_path = tmp_path / "in.jsonl"
    config_path = tmp_path / "cfg.yaml"
    stats_dir = tmp_path / "stats"

    # 10 rows. 3 fail confident only. 2 fail keeper only. 1 fails both.
    # 4 survive.
    rows = [
        # 4 survivors
        *[{"metrics": {"s": 0.99, "k": True}, "removal_reasons": []} for _ in range(4)],
        # 3 confident-only failures (k=True so keeper passes)
        *[{"metrics": {"s": 0.1,  "k": True}, "removal_reasons": []} for _ in range(3)],
        # 2 keeper-only failures (s=0.99 so confident passes)
        *[{"metrics": {"s": 0.99, "k": False}, "removal_reasons": []} for _ in range(2)],
        # 1 both-fail
        {"metrics": {"s": 0.1, "k": False}, "removal_reasons": []},
    ]
    _write_jsonl(input_path, rows)
    config_path.write_text(
        f"input: {input_path}\n"
        f"survived: {tmp_path}/s.jsonl\n"
        f"rejected: {tmp_path}/r.jsonl\n"
        f"stats_dir: {stats_dir}\n"
        "stats_prefix: t\n"
        "filters:\n"
        "  - {name: confident, type: min_metric, key: metrics.s, value: 0.5}\n"
        "  - {name: keeper, type: require_true, key: metrics.k}\n",
        encoding="utf-8",
    )
    run(str(config_path))

    stats = json.loads((stats_dir / "t_filter.json").read_text())
    assert stats["rows_total"] == 10
    assert stats["rows_survived"] == 4
    assert stats["rows_rejected"] == 6
    # per-rule counts EVERY rule that failed (including overlap):
    assert stats["per_rule_failures"]["confident"] == 4  # 3 only + 1 both
    assert stats["per_rule_failures"]["keeper"] == 3     # 2 only + 1 both
    # Funnel attributes the both-fail row to the FIRST failing rule (confident)
    # so confident drops 4, keeper drops only 2.
    funnel = stats["funnel"]
    assert funnel[0] == {"rule": "confident", "dropped": 4, "remaining_after": 6}
    assert funnel[1] == {"rule": "keeper",    "dropped": 2, "remaining_after": 4}


def test_run_rejects_unknown_rule_type(tmp_path):
    input_path = tmp_path / "in.jsonl"
    _write_jsonl(input_path, [])
    config_path = tmp_path / "cfg.yaml"
    config_path.write_text(
        f"input: {input_path}\n"
        f"survived: {tmp_path}/s.jsonl\n"
        f"rejected: {tmp_path}/r.jsonl\n"
        f"stats_dir: {tmp_path}/stats\n"
        "stats_prefix: t\n"
        "filters:\n"
        "  - {name: foo, type: not_a_real_rule}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown filter type"):
        run(str(config_path))


def test_run_rejects_duplicate_rule_name(tmp_path):
    input_path = tmp_path / "in.jsonl"
    _write_jsonl(input_path, [])
    config_path = tmp_path / "cfg.yaml"
    config_path.write_text(
        f"input: {input_path}\n"
        f"survived: {tmp_path}/s.jsonl\n"
        f"rejected: {tmp_path}/r.jsonl\n"
        f"stats_dir: {tmp_path}/stats\n"
        "stats_prefix: t\n"
        "filters:\n"
        "  - {name: dup, type: no_removal_reasons}\n"
        "  - {name: dup, type: no_removal_reasons}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate filter name"):
        run(str(config_path))
