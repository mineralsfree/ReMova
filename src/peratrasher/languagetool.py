"""LanguageTool stage backed by one or more persistent LocalChecker subprocesses.

Spawns N JVMs per stage instance and dispatches rows across them with a thread
pool, so the rule engine actually uses N cores. Each JVM talks the
``--stdin-loop`` line protocol (one JSON-encoded string per request line, one
``/v2/check`` JSON object per response line). Avoids HTTP entirely.
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import shutil
import subprocess
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

from peratrasher.base import Stage


class _CheckerClient(Protocol):
    def check(self, text: str) -> dict[str, Any]: ...
    def close(self) -> None: ...


_LT_SETUP_HINT = (
    "The languagetool stage needs a LanguageTool build exposing "
    "org.languagetool.server.LocalChecker, which is not in a stock "
    "LanguageTool distribution — see 'Build LanguageTool with LocalChecker' "
    "in README.MD."
)


def _preflight(argv: list[str]) -> None:
    """Reject a `command` that cannot work before paying for a JVM start.

    Without this, a missing launcher surfaces as a bare Popen FileNotFoundError
    and a stale `@argfile` path costs the full `startup_timeout` before failing
    with a wall of JVM stderr.
    """
    if shutil.which(argv[0]) is None:
        raise FileNotFoundError(f"{argv[0]!r} not found on PATH. {_LT_SETUP_HINT}")
    for arg in argv:
        # `java @file` — the classpath argfile produced when building LT.
        if arg.startswith("@") and not os.path.exists(arg[1:]):
            raise FileNotFoundError(
                f"java argfile {arg[1:]!r} does not exist. {_LT_SETUP_HINT}"
            )


class LocalCheckerClient:
    """Manages a long-running LocalChecker JVM process and exchanges one
    request/response per call. Not thread-safe — one client per worker thread.
    """

    def __init__(
        self,
        command: list[str],
        language: str = "be-BY",
        startup_timeout: float = 30.0,
        no_suggestions: bool = True,
    ) -> None:
        argv = list(command) + ["--stdin-loop", "--language", language]
        if no_suggestions:
            argv.append("--no-suggestions")
        self._argv = argv
        _preflight(argv)
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,  # line-buffered text mode
        )
        self._closed = False
        self._stderr_lines: list[str] = []
        self._stderr_lock = threading.Lock()
        self._ready_event = threading.Event()
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, name="localchecker-stderr", daemon=True
        )
        self._stderr_thread.start()
        self._await_ready(startup_timeout)
        atexit.register(self.close)

    def _drain_stderr(self) -> None:
        # Capture stderr indefinitely so the JVM never blocks on a full pipe.
        # Lines before READY are also buffered here.
        assert self._proc.stderr is not None
        for line in self._proc.stderr:
            with self._stderr_lock:
                self._stderr_lines.append(line.rstrip("\n"))
                if line.strip() == "READY":
                    self._ready_event.set()

    def _await_ready(self, timeout: float) -> None:
        if not self._ready_event.wait(timeout):
            self._kill()
            raise RuntimeError(
                f"LocalChecker did not signal READY within {timeout}s. "
                f"argv={self._argv!r} stderr={self._stderr_tail()!r}"
            )

    def _stderr_tail(self, n: int = 20) -> str:
        with self._stderr_lock:
            return "\n".join(self._stderr_lines[-n:])

    def check(self, text: str) -> dict[str, Any]:
        """Send one piece of text, return the parsed JSON response."""
        if self._closed:
            raise RuntimeError("LocalCheckerClient is closed")
        proc = self._proc
        if proc.poll() is not None:
            raise RuntimeError(
                f"LocalChecker subprocess exited with code {proc.returncode}. "
                f"stderr={self._stderr_tail()!r}"
            )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps(text, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError(
                "LocalChecker closed stdout unexpectedly. "
                f"stderr={self._stderr_tail()!r}"
            )
        return json.loads(line)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        proc = self._proc
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._kill()

    def _kill(self) -> None:
        try:
            self._proc.kill()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=2)
        except Exception:
            pass


def _looks_like_proper_noun(word: str, text: str, offset: int) -> bool:
    """Heuristic: is `word` a likely proper noun / loan word, *not* a real
    misspelling? Two cases:

    1. Pure ASCII-Latin token (taxonomy names, brands, English embeds).
    2. Capitalized non-sentence-initial token (Cyrillic uppercase first letter
       NOT preceded by `.!?` — most likely a name / place not in LT's dict).
    """
    if not word:
        return False
    if word.isascii() and word.isalpha():
        return True
    if word[0].isupper():
        i = offset - 1
        while i >= 0 and text[i].isspace():
            i -= 1
        if i < 0:
            return False  # word is at start of input
        return text[i] not in ".!?"
    return False


class LanguageToolStage(Stage):
    name = "languagetool"

    def __init__(
        self,
        command: list[str] | None = None,
        language: str = "be-BY",
        disabled_rules: list[str] | None = None,
        startup_timeout: float = 30.0,
        no_suggestions: bool = True,
        workers: int = 1,
        client: _CheckerClient | None = None,
        input_field: str = "text",
        metric_prefix: str = "langtool",
        exclude_proper_nouns: bool = False,
        track_word_freq: bool = True,
        word_freq_top: int = 500,
        word_freq_issue_types: tuple[str, ...] = ("misspelling",),
    ) -> None:
        if workers < 1:
            raise ValueError(f"workers must be >= 1, got {workers}")
        self.input_field = input_field
        self.metric_prefix = metric_prefix
        self.exclude_proper_nouns = exclude_proper_nouns
        if input_field != "text":
            self.name = f"languagetool_{input_field}"
        self._owns_clients = False
        if client is not None:
            # Test / single-client injection path: no parallelism, no JVMs spawned.
            self._clients: list[_CheckerClient] = [client]
        else:
            if command is None:
                raise ValueError(
                    "LanguageToolStage needs either `command` (subprocess argv "
                    "prefix for LocalChecker, e.g. ['java', '-cp', CP, "
                    "'org.languagetool.server.LocalChecker']) or an explicit "
                    "`client`."
                )
            self._owns_clients = True
            self._clients = [
                LocalCheckerClient(
                    command=command,
                    language=language,
                    startup_timeout=startup_timeout,
                    no_suggestions=no_suggestions,
                )
                for _ in range(workers)
            ]
        # Queue acts as a semaphore over the (non-thread-safe) clients.
        # Worker threads check one out, run the request, return it.
        self._client_q: queue.Queue[_CheckerClient] = queue.Queue()
        for c in self._clients:
            self._client_q.put(c)
        self._workers = len(self._clients)
        self._pool: ThreadPoolExecutor | None = (
            ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="lt")
            if self._workers > 1
            else None
        )
        self.language = language
        self.disabled_rules = set(disabled_rules or [])
        self.track_word_freq = track_word_freq
        self.word_freq_top = word_freq_top
        self.word_freq_issue_types = set(word_freq_issue_types)
        self._stats_lock = threading.Lock()
        self._rows_total = 0
        self._rows_with_matches = 0
        self._issue_type_totals: Counter[str] = Counter()
        self._match_counts: list[int] = []
        self._excluded_proper_nouns_total = 0
        # Per-word + per-rule frequency over surviving matches (after the
        # proper-noun heuristic). Same signal `tools/lt_word_freq.py` produces,
        # piggybacked onto the main pass so a 10M-row corpus is scanned once.
        self._word_freq: Counter[str] = Counter()
        self._rule_freq: Counter[str] = Counter()

    # --- single-row entrypoint (kept for tests / callers that still use it) ---
    def process(self, row: dict) -> None:
        client = self._client_q.get()
        try:
            self._process_with(client, row)
        finally:
            self._client_q.put(client)

    # --- batch entrypoint (used by pipeline.run for parallelism) ---
    def process_batch(self, rows: list[dict]) -> None:
        if not rows:
            return
        if self._pool is None or len(rows) == 1:
            for row in rows:
                self.process(row)
            return
        # ThreadPoolExecutor.map blocks until all complete and re-raises
        # exceptions. Order doesn't matter — we mutate rows in place.
        list(self._pool.map(self._dispatch_one, rows))

    def _dispatch_one(self, row: dict) -> None:
        client = self._client_q.get()
        try:
            self._process_with(client, row)
        finally:
            self._client_q.put(client)

    def _process_with(self, client: _CheckerClient, row: dict) -> None:
        text = row[self.input_field]
        payload = client.check(text)
        if "error" in payload and "matches" not in payload:
            raise RuntimeError(f"LocalChecker error: {payload['error']}")
        matches = payload.get("matches", [])

        if self.disabled_rules:
            matches = [
                m
                for m in matches
                if (m.get("rule", {}).get("id") or "") not in self.disabled_rules
            ]

        types: Counter[str] = Counter()
        excluded = 0
        words_local: list[str] = []
        rules_local: list[str] = []
        for m in matches:
            rule = m.get("rule", {}) or {}
            issue_type = rule.get("issueType") or "uncategorized"
            rule_id = rule.get("id") or "<no-id>"
            offset = int(m.get("offset", 0))
            length = int(m.get("length", 0))
            word = text[offset : offset + length]
            # Only misspellings are exclusion-eligible: LT's other issue types
            # (grammar, whitespace, etc.) don't fire on proper nouns.
            if (
                self.exclude_proper_nouns
                and issue_type == "misspelling"
                and _looks_like_proper_noun(word, text, offset)
            ):
                excluded += 1
                continue
            types[issue_type] += 1
            if self.track_word_freq and issue_type in self.word_freq_issue_types:
                words_local.append(word.lower())
                rules_local.append(rule_id)

        count = sum(types.values())
        num_words = int(row.get("num_words") or 0)
        if num_words <= 0:
            num_words = len(row[self.input_field].split())
        num_words = max(num_words, 1)
        density = count / num_words

        row.setdefault("metrics", {})[self.metric_prefix] = {
            "types": dict(types),
            "count": count,
            "density": density,
            "excluded_proper_nouns": excluded,
        }

        with self._stats_lock:
            self._rows_total += 1
            self._match_counts.append(count)
            self._excluded_proper_nouns_total += excluded
            if count > 0:
                self._rows_with_matches += 1
                self._issue_type_totals.update(types)
            if words_local:
                self._word_freq.update(words_local)
                self._rule_freq.update(rules_local)

    def stats(self) -> dict:
        with self._stats_lock:
            out: dict[str, Any] = {
                "rows_total": self._rows_total,
                "rows_with_matches": self._rows_with_matches,
                "issue_type_totals": dict(self._issue_type_totals),
                "excluded_proper_nouns_total": self._excluded_proper_nouns_total,
            }
            counts = list(self._match_counts)
            if self.track_word_freq:
                out["distinct_flagged_words"] = len(self._word_freq)
                out["total_flagged_word_occurrences"] = sum(self._word_freq.values())
                out["top_flagged_words"] = dict(
                    self._word_freq.most_common(self.word_freq_top)
                )
                out["top_rule_ids"] = dict(
                    self._rule_freq.most_common(self.word_freq_top)
                )
        if counts:
            sorted_counts = sorted(counts)
            n = len(sorted_counts)

            def q(p: float) -> int:
                return sorted_counts[min(int(n * p), n - 1)]

            out["match_count_quantiles"] = {
                "p10": q(0.10),
                "p50": q(0.50),
                "p90": q(0.90),
                "p99": q(0.99),
            }
        return out

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None
        if self._owns_clients:
            for c in self._clients:
                try:
                    c.close()
                except Exception:
                    pass
        else:
            # client was injected; let the caller close it.
            pass
