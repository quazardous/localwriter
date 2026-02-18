"""Tests for pure helper logic in core.calc_tools (no UNO)."""
import unittest
from core.calc_tools import _parse_color


class TestParseColor(unittest.TestCase):
    def test_named_colors(self):
        self.assertEqual(_parse_color("red"), 0xFF0000)
        self.assertEqual(_parse_color("yellow"), 0xFFFF00)
        self.assertEqual(_parse_color("green"), 0x00FF00)
        self.assertEqual(_parse_color("blue"), 0x0000FF)
        self.assertEqual(_parse_color("white"), 0xFFFFFF)
        self.assertEqual(_parse_color("black"), 0x000000)
        self.assertEqual(_parse_color("orange"), 0xFF8C00)
        self.assertEqual(_parse_color("purple"), 0x800080)
        self.assertEqual(_parse_color("gray"), 0x808080)

    def test_case_insensitive(self):
        self.assertEqual(_parse_color("RED"), 0xFF0000)
        self.assertEqual(_parse_color("Yellow"), 0xFFFF00)

    def test_hex(self):
        self.assertEqual(_parse_color("#FF0000"), 0xFF0000)
        self.assertEqual(_parse_color("#ffffff"), 0xFFFFFF)
        self.assertEqual(_parse_color("#000"), 0x000000)

    def test_empty_or_invalid_returns_none(self):
        self.assertIsNone(_parse_color(""))
        self.assertIsNone(_parse_color(None))
        self.assertIsNone(_parse_color("notacolor"))
        self.assertIsNone(_parse_color("#gggggg"))
        self.assertIsNone(_parse_color("  "))


if __name__ == "__main__":
    unittest.main()
