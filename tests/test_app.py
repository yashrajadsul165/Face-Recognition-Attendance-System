import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app import mark_attendance, safe_name


class SafeNameTests(unittest.TestCase):
    def test_normalises_spaces_and_removes_unsafe_characters(self) -> None:
        self.assertEqual(safe_name("  Yashraj   Adsul!  "), "Yashraj Adsul")

    def test_rejects_an_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            safe_name("!!!")


class AttendanceTests(unittest.TestCase):
    def test_records_each_person_only_once_per_day(self) -> None:
        timestamp = datetime(2026, 7, 16, 10, 30, 0)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)

            first_write = mark_attendance(
                "Demo User", 0.321, output_directory, timestamp
            )
            second_write = mark_attendance(
                "Demo User", 0.300, output_directory, timestamp
            )

            self.assertTrue(first_write)
            self.assertFalse(second_write)

            output_file = output_directory / "attendance_2026-07-16.csv"
            with output_file.open(encoding="utf-8") as csv_file:
                rows = list(csv.DictReader(csv_file))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "Demo User")
            self.assertEqual(rows[0]["face_distance"], "0.3210")


if __name__ == "__main__":
    unittest.main()
