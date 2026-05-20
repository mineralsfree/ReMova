"""Tatoeba TSV → JSONL prep tool.

Reads a 4-column tab-separated Tatoeba export (src_id, src, tgt_id, tgt),
drops pairs where either side has fewer than `--min-words` whitespace
tokens, and writes the survivors as JSONL ready for `peratrasher-parallel`.
"""

import argparse
import sys
from pathlib import Path

from peratrasher.jsonio import write_row


def run(
    input_path: str | Path,
    output_path: str | Path,
    *,
    min_words: int = 3,
    src_lang: str | None = None,
    tgt_lang: str | None = None,
) -> dict[str, int]:
    """Convert + filter the TSV. Returns counts {read, malformed, too_short, written}."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    read = malformed = too_short = written = 0

    with (
        open(input_path, encoding="utf-8-sig") as fin,
        open(output_path, "w", encoding="utf-8") as fout,
    ):
        for line in fin:
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            read += 1
            parts = line.split("\t")
            if len(parts) != 4:
                malformed += 1
                continue
            src_id_str, src, tgt_id_str, tgt = parts
            if len(src.split()) < min_words or len(tgt.split()) < min_words:
                too_short += 1
                continue

            row: dict = {
                "src_id": int(src_id_str),
                "src": src,
                "tgt_id": int(tgt_id_str),
                "tgt": tgt,
            }
            if src_lang is not None:
                row["src_lang"] = src_lang
            if tgt_lang is not None:
                row["tgt_lang"] = tgt_lang
            write_row(fout, row)
            written += 1

    return {
        "read": read,
        "malformed": malformed,
        "too_short": too_short,
        "written": written,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a Tatoeba 4-column TSV (src_id, src, tgt_id, tgt) to JSONL, "
            "dropping pairs where either side has fewer than --min-words tokens."
        )
    )
    parser.add_argument("--input", required=True, help="Path to TSV input.")
    parser.add_argument("--output", required=True, help="Path to JSONL output.")
    parser.add_argument(
        "--min-words",
        type=int,
        default=3,
        help="Minimum whitespace-token count required on BOTH sides (default: 3).",
    )
    parser.add_argument(
        "--src-lang",
        default=None,
        help="If set, written into each row as 'src_lang' (e.g. 'bel_Cyrl').",
    )
    parser.add_argument(
        "--tgt-lang",
        default=None,
        help="If set, written into each row as 'tgt_lang' (e.g. 'eng_Latn').",
    )
    args = parser.parse_args()

    counts = run(
        args.input,
        args.output,
        min_words=args.min_words,
        src_lang=args.src_lang,
        tgt_lang=args.tgt_lang,
    )
    for k in ("read", "malformed", "too_short", "written"):
        print(f"  {k}: {counts[k]}", file=sys.stderr)


if __name__ == "__main__":
    main()
