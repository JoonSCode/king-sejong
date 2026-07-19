#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import codex_process_contract as process
import codex_ticket_runner as runner


class CodexSubprocessAdapterTests(unittest.TestCase):
    def test_executes_structured_argv_without_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a harmless helper process expressed only as argv and stdin.
            root = Path(tmp)
            request = process.CodexProcessRequest(
                ticket_id="ticket-helper",
                model="test-model",
                argv=(sys.executable, "-c", "import sys; print(sys.stdin.read())"),
                stdin_text="structured-input",
                cwd=root,
                timeout_seconds=5,
                output_limit_bytes=1024,
            )

            # When: the concrete process adapter runs the helper.
            result = runner.SubprocessCodexProcess().run(request, root / "cancel")

            # Then: the helper receives stdin and exits without shell interpretation.
            self.assertEqual(result.status, runner.ProcessStatus.COMPLETED)
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.stdout.strip(), request.stdin_text)

    def test_observes_cancellation_after_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Given: a harmless long-running helper and a later Core cancellation marker.
            root = Path(tmp)
            cancellation_path = root / "cancel"
            request = process.CodexProcessRequest(
                ticket_id="ticket-cancel-helper",
                model="test-model",
                argv=(sys.executable, "-c", "import time; time.sleep(5)"),
                stdin_text="",
                cwd=root,
                timeout_seconds=5,
                output_limit_bytes=1024,
            )
            timer = threading.Timer(0.1, lambda: cancellation_path.write_text("cancelled\n"))

            # When: cancellation arrives after the child process started.
            started = time.monotonic()
            timer.start()
            try:
                result = runner.SubprocessCodexProcess(poll_interval_seconds=0.02).run(request, cancellation_path)
            finally:
                timer.cancel()
                timer.join()

            # Then: the adapter terminates promptly and reports cancellation, not timeout.
            self.assertEqual(result.status, runner.ProcessStatus.CANCELLED)
            self.assertLess(time.monotonic() - started, 2)


if __name__ == "__main__":
    unittest.main()
