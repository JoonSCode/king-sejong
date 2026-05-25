from __future__ import annotations

import unittest
from unittest.mock import patch

from sejong_paths import path_contains_or_equals, path_key, paths_equal


class SejongPathTests(unittest.TestCase):
    def test_darwin_path_keys_fold_home_case(self) -> None:
        with patch("sys.platform", "darwin"):
            self.assertEqual(
                path_key("/Users/Junsu/Develop/king-sejong"),
                path_key("/Users/junsu/Develop/king-sejong"),
            )

    def test_darwin_path_containment_folds_case(self) -> None:
        with patch("sys.platform", "darwin"):
            self.assertTrue(
                path_contains_or_equals(
                    "/Users/Junsu/Develop/king-sejong/docs/sejong",
                    "/Users/junsu/Develop/king-sejong",
                )
            )

    def test_non_darwin_path_keys_preserve_case(self) -> None:
        with patch("sys.platform", "linux"):
            self.assertNotEqual(
                path_key("/Users/Junsu/Develop/king-sejong"),
                path_key("/Users/junsu/Develop/king-sejong"),
            )

    def test_paths_equal_falls_back_to_platform_key(self) -> None:
        with patch("sys.platform", "darwin"):
            self.assertTrue(
                paths_equal(
                    "/Users/Junsu/Develop/king-sejong",
                    "/Users/junsu/Develop/king-sejong",
                )
            )


if __name__ == "__main__":
    unittest.main()
