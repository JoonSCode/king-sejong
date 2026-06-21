#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SEJONG_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
RUNNER = SEJONG_ROOT / "scripts" / "sejong_doctor.py"


class SejongDoctorTests(unittest.TestCase):
    def test_doctor_reports_managed_paths_without_writing(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--repo-root",
                str(REPO_ROOT),
                "--skip-python-deps",
                "--skip-active-context",
                "--json",
            ],
            text=True,
            capture_output=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["format"], "sejong.doctor-result/v0.1-draft")
        checks = {check["name"]: check for check in payload["checks"]}
        self.assertEqual(checks["source-managed-paths"]["status"], "ok")
        self.assertEqual(checks["plugin-adapter-json"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
