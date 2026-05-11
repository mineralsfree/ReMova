import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from peratrasher.base import Stage
from peratrasher.ftfy_stage import FtfyStage
from peratrasher.glotlid import GlotLIDStage
from peratrasher.jsonio import iter_jsonl, write_row
from peratrasher.languagetool import LanguageToolStage
from peratrasher.nfkc import NFKCStage
from peratrasher.wikificator import WikificatorStage

STAGES: dict[str, type[Stage]] = {
    "wikificator": WikificatorStage,
    "ftfy": FtfyStage,
    "nfkc": NFKCStage,
    "glotlid": GlotLIDStage,
    "languagetool": LanguageToolStage,
}

DEFAULT_BATCH_SIZE = 128


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
    prefix = cfg["stats_prefix"]
    batch_size = int(cfg.get("batch_size", DEFAULT_BATCH_SIZE))
    stats_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stages = build_stages(cfg["stages"])
    times: dict[str, float] = {stage.name: 0.0 for stage in stages}

    def flush(batch: list[dict], fout) -> None:
        for stage in stages:
            t0 = time.perf_counter()
            stage.process_batch(batch)
            times[stage.name] += time.perf_counter() - t0
        for row in batch:
            write_row(fout, row)
        batch.clear()

    n_rows = 0
    start = time.perf_counter()
    with open(output_path, "w", encoding="utf-8") as fout:
        batch: list[dict] = []
        for row in iter_jsonl(input_path):
            row.setdefault("removal_reasons", [])
            row.setdefault("metrics", {})
            batch.append(row)
            if len(batch) >= batch_size:
                flushed = len(batch)
                flush(batch, fout)
                n_rows += flushed
                if (n_rows // 1000) > ((n_rows - flushed) // 1000):
                    rate = n_rows / (time.perf_counter() - start)
                    print(f"  {n_rows} rows ({rate:.0f}/s)", file=sys.stderr, flush=True)
        if batch:
            flushed = len(batch)
            flush(batch, fout)
            n_rows += flushed

    elapsed = time.perf_counter() - start
    print(f"  done: {n_rows} rows in {elapsed:.1f}s", file=sys.stderr)

    for stage in stages:
        stats_path = stats_dir / f"{prefix}_{stage.name}.json"
        s = stage.stats()
        s["processing_time_s"] = round(times[stage.name], 3)
        stats_path.write_text(
            json.dumps(s, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
