import unittest
from core.calc_address_utils import column_to_index, index_to_column, parse_address, parse_range_string, format_address

class TestCalcAddressUtils(unittest.TestCase):
    def test_column_to_index(self):
        self.assertEqual(column_to_index("A"), 0)
        self.assertEqual(column_to_index("Z"), 25)
        self.assertEqual(column_to_index("AA"), 26)
        self.assertEqual(column_to_index("AZ"), 51)
        self.assertEqual(column_to_index("BA"), 52)
        self.assertEqual(column_to_index("ZZ"), 701)

    def test_index_to_column(self):
        self.assertEqual(index_to_column(0), "A")
        self.assertEqual(index_to_column(25), "Z")
        self.assertEqual(index_to_column(26), "AA")
        self.assertEqual(index_to_column(51), "AZ")
        self.assertEqual(index_to_column(52), "BA")
        self.assertEqual(index_to_column(701), "ZZ")

    def test_parse_address(self):
        self.assertEqual(parse_address("A1"), (0, 0))
        self.assertEqual(parse_address("B10"), (1, 9))
        self.assertEqual(parse_address("AA100"), (26, 99))
        with self.assertRaises(ValueError):
            parse_address("Invalid")
        with self.assertRaises(ValueError):
            parse_address("123")
        with self.assertRaises(ValueError):
            parse_address("A")
        with self.assertRaises(ValueError):
            parse_address("")

    def test_parse_range_string(self):
        self.assertEqual(parse_range_string("A1:B2"), ((0, 0), (1, 1)))
        self.assertEqual(parse_range_string("C3"), ((2, 2), (2, 2)))
        self.assertEqual(parse_range_string("A1:C10"), ((0, 0), (2, 9)))
        with self.assertRaises(ValueError):
            parse_range_string("A1-B2")
        with self.assertRaises(ValueError):
            parse_range_string("")
        with self.assertRaises(ValueError):
            parse_range_string("A1:Z")  # incomplete end cell

    def test_format_address(self):
        self.assertEqual(format_address(0, 0), "A1")
        self.assertEqual(format_address(1, 9), "B10")
        self.assertEqual(format_address(26, 99), "AA100")

    def test_format_address_roundtrip(self):
        """format_address(parse_address) and parse_address(format_address) round-trip."""
        for addr in ("A1", "B10", "Z1", "AA100"):
            col, row = parse_address(addr)
            self.assertEqual(format_address(col, row), addr)
        col, row = parse_address("C3")
        self.assertEqual(format_address(col, row), "C3")

if __name__ == "__main__":
    unittest.main()
