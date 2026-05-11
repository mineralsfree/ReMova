"""LanguageTool stage backed by one or more persistent LocalChecker subprocesses.

Spawns N JVMs per stage instance and dispatches rows across them with a thread
pool, so the rule engine actually uses N cores. Each JVM talks the
``--stdin-loop`` line protocol (one JSON-encoded string per request line, one
``/v2/check`` JSON object per response line). Avoids HTTP entirely.
"""

from __future__ import annotations

import atexit
import json
import queue
import subprocess
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

from peratrasher.base import Stage


class _CheckerClient(Protocol):
    def check(self, text: str) -> dict[str, Any]: ...
    def close(self) -> None: ...


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
    ) -> None:
        if workers < 1:
            raise ValueError(f"workers must be >= 1, got {workers}")
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
        self._stats_lock = threading.Lock()
        self._rows_total = 0
        self._rows_with_matches = 0
        self._issue_type_totals: Counter[str] = Counter()
        self._match_counts: list[int] = []

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
        payload = client.check(row["text"])
        if "error" in payload and "matches" not in payload:
            raise RuntimeError(f"LocalChecker error: {payload['error']}")
        matches = payload.get("matches", [])

        if self.disabled_rules:
            matches = [
                m for m in matches
                if (m.get("rule", {}).get("id") or "") not in self.disabled_rules
            ]

        types: Counter[str] = Counter()
        for m in matches:
            issue_type = m.get("rule", {}).get("issueType") or "uncategorized"
            types[issue_type] += 1

        count = len(matches)
        num_words = max(int(row.get("num_words") or 0), 1)
        density = count / num_words

        row.setdefault("metrics", {})["langtool"] = {
            "types": dict(types),
            "count": count,
            "density": density,
        }

        with self._stats_lock:
            self._rows_total += 1
            self._match_counts.append(count)
            if count > 0:
                self._rows_with_matches += 1
                self._issue_type_totals.update(types)

    def stats(self) -> dict:
        with self._stats_lock:
            out: dict[str, Any] = {
                "rows_total": self._rows_total,
                "rows_with_matches": self._rows_with_matches,
                "issue_type_totals": dict(self._issue_type_totals),
            }
            counts = list(self._match_counts)
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
