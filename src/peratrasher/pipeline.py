import json
from pathlib import Path
from typing import Any

import yaml

from peratrasher.base import Stage
from peratrasher.ftfy_stage import FtfyStage
from peratrasher.glotlid import GlotLIDStage
from peratrasher.jsonio import iter_jsonl, write_row

STAGES: dict[str, type[Stage]] = {
    "ftfy": FtfyStage,
    "glotlid": GlotLIDStage,
}


def build_stages(stage_configs: list[dict]) -> list[Stage]:
    stages: list[Stage] = []
    for entry in stage_configs:
        name = entry["name"]
        if name not in STAGES:
            raise ValueError(f"Unknown stage: {name!r}. Available: {sorted(STAGES)}")
        kwargs = {k: v for k, v in entry.items() if k != "name"}
        stages.append(STAGES[name](**kwargs))
    return stages


def run(config_path: str | Path) -> None:
    with open(config_path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    input_path = Path(cfg["input"])
    output_path = Path(cfg["output"])
    stats_dir = Path(cfg["stats_dir"])
    stats_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stages = build_stages(cfg["stages"])

    with open(output_path, "w", encoding="utf-8") as fout:
        for row in iter_jsonl(input_path):
            row.setdefault("removal_reasons", [])
            row.setdefault("metrics", {})
            for stage in stages:
                stage.process(row)
            write_row(fout, row)

    for stage in stages:
        stats_path = stats_dir / f"{stage.name}.json"
        stats_path.write_text(
            json.dumps(stage.stats(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
