"""Moses (OPUS) → JSONL prep tool.

OPUS distributes parallel corpora as two line-aligned plaintext files, e.g.

    wikimedia.bel-eng.bel    # Belarusian, one sentence per line
    wikimedia.bel-eng.eng    # English, same line N is the translation

This tool reads both, drops pairs where either side is empty or has fewer than
`--min-words` whitespace tokens, and writes the survivors as JSONL ready for
`peratrasher-parallel`.

The output schema matches `peratrasher-tatoeba-prep`'s, minus the IDs:

    {"src": "...", "tgt": "...", "src_lang": "bel_Cyrl", "tgt_lang": "eng_Latn"}

Lang fields are optional CLI flags; when set, downstream `bi_glotlid` can
compare against them.
"""

import argparse
import sys
from itertools import zip_longest
from pathlib import Path

from peratrasher.jsonio import write_row


_SENTINEL = object()


def run(
    src_path: str | Path,
    tgt_path: str | Path,
    output_path: str | Path,
    *,
    min_words: int = 3,
    src_lang: str | None = None,
    tgt_lang: str | None = None,
) -> dict[str, int]:
    """Convert + filter the Moses pair. Returns {read, malformed, too_short, written}."""
    src_path = Path(src_path)
    tgt_path = Path(tgt_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    read = malformed = too_short = written = 0

    with (
        open(src_path, encoding="utf-8-sig") as fs,
        open(tgt_path, encoding="utf-8-sig") as ft,
        open(output_path, "w", encoding="utf-8") as fout,
    ):
        for src_line, tgt_line in zip_longest(fs, ft, fillvalue=_SENTINEL):
            if src_line is _SENTINEL or tgt_line is _SENTINEL:
                raise ValueError(
                    f"line count mismatch between {src_path} and {tgt_path}; "
                    f"both files must have the same number of lines"
                )
            read += 1
            src = src_line.rstrip("\n").rstrip("\r").strip()
            tgt = tgt_line.rstrip("\n").rstrip("\r").strip()
            if not src or not tgt:
                malformed += 1
                continue
            if len(src.split()) < min_words or len(tgt.split()) < min_words:
                too_short += 1
                continue
            row: dict = {"src": src, "tgt": tgt}
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
            "Convert an OPUS Moses-format parallel corpus (two line-aligned "
            "plaintext files) to JSONL, dropping pairs where either side is "
            "empty or has fewer than --min-words tokens."
        )
    )
    parser.add_argument("--src", required=True, help="Source-side plaintext file.")
    parser.add_argument("--tgt", required=True, help="Target-side plaintext file.")
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
        args.src,
        args.tgt,
        args.output,
        min_words=args.min_words,
        src_lang=args.src_lang,
        tgt_lang=args.tgt_lang,
    )
    for k in ("read", "malformed", "too_short", "written"):
        print(f"  {k}: {counts[k]}", file=sys.stderr)


if __name__ == "__main__":
    main()
