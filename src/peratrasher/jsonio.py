import json
from pathlib import Path
from typing import Iterator, TextIO


def iter_jsonl(path: str | Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_row(f: TextIO, row: dict) -> None:
    f.write(json.dumps(row, ensure_ascii=False))
    f.write("\n")
