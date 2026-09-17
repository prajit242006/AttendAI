"""Tests for the validation helpers and the presence maths."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.helpers import (  # noqa: E402
    ValidationError,
    parse_time,
    percent,
    validate_email,
    validate_int,
    validate_register_number,
    validate_subject_code,
)


class HelperTests(unittest.TestCase):
    def test_register_number_is_uppercased(self):
        self.assertEqual(validate_register_number(" 23cs001 "), "23CS001")

    def test_bad_register_number_rejected(self):
        with self.assertRaises(ValidationError):
            validate_register_number("x!")

    def test_email_validation(self):
        self.assertEqual(validate_email("A@B.com"), "a@b.com")
        self.assertIsNone(validate_email(""))
        with self.assertRaises(ValidationError):
            validate_email("not-an-email")

    def test_subject_code(self):
        self.assertEqual(validate_subject_code("cs8391"), "CS8391")

    def test_int_bounds(self):
        self.assertEqual(validate_int("3", "Year", 1, 5), 3)
        with self.assertRaises(ValidationError):
            validate_int("9", "Year", 1, 5)

    def test_time_parsing(self):
        self.assertEqual(parse_time("09:00").hour, 9)
        with self.assertRaises(ValidationError):
            parse_time("nine")

    def test_percent_never_divides_by_zero(self):
        self.assertEqual(percent(0, 0), 0.0)
        self.assertEqual(percent(8, 10), 80.0)


if __name__ == "__main__":
    unittest.main()
