"""Tests for ERROR_TYPES and ERROR_PATTERNS structure in calc_error_detector (no UNO)."""
import unittest
from core.calc_error_detector import ERROR_TYPES, ERROR_PATTERNS


class TestErrorDetectorData(unittest.TestCase):
    def test_error_types_has_required_fields(self):
        for code, info in ERROR_TYPES.items():
            self.assertIn("code", info, "ERROR_TYPES[%s] missing 'code'" % code)
            self.assertIn("name", info, "ERROR_TYPES[%s] missing 'name'" % code)
            self.assertIn("description", info, "ERROR_TYPES[%s] missing 'description'" % code)
            self.assertIsInstance(info["code"], str)
            self.assertIsInstance(info["name"], str)
            self.assertIsInstance(info["description"], str)

    def test_error_patterns_non_empty_list_of_strings(self):
        self.assertIsInstance(ERROR_PATTERNS, list)
        self.assertGreater(len(ERROR_PATTERNS), 0)
        for p in ERROR_PATTERNS:
            self.assertIsInstance(p, str)
            self.assertGreater(len(p), 0)


if __name__ == "__main__":
    unittest.main()
