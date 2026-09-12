#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from benchmark_instruction_surface import single_line_frontmatter_description


class SingleLineFrontmatterDescriptionTests(unittest.TestCase):
    def write_skill(self, description_line: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "SKILL.md"
        path.write_text(f"---\nname: example\n{description_line}\n---\n", encoding="utf-8")
        return path

    def test_reads_plain_single_line_description(self) -> None:
        path = self.write_skill("description: Route Sejong/세종 work.")

        self.assertEqual(single_line_frontmatter_description(path), "Route Sejong/세종 work.")

    def test_rejects_ambiguous_or_multiline_values(self) -> None:
        for description_line in ('description: "quoted"', "description: >", "description: "):
            with self.subTest(description_line=description_line):
                path = self.write_skill(description_line)
                with self.assertRaises(ValueError):
                    single_line_frontmatter_description(path)


if __name__ == "__main__":
    unittest.main()
