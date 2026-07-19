import io
import unittest

from dashboard.analytics import (
    AttendanceDataError,
    count_by_date,
    count_by_person,
    parse_attendance_csv,
    summarise_attendance,
)


VALID_CSV = """name,date,time,face_distance
Demo A,2026-07-18,09:00:00,0.3100
Demo B,2026-07-18,09:05:00,0.4200
Demo A,2026-07-19,09:01:00,0.3300
"""


class AttendanceAnalyticsTests(unittest.TestCase):
    def test_parses_and_summarises_valid_csv(self) -> None:
        records = parse_attendance_csv(io.StringIO(VALID_CSV))
        summary = summarise_attendance(records)

        self.assertEqual(summary["records"], 3)
        self.assertEqual(summary["people"], 2)
        self.assertEqual(summary["days"], 2)
        self.assertAlmostEqual(summary["average_distance"], 0.353333, places=5)
        self.assertEqual(count_by_person(records)[0], ("Demo A", 2))
        self.assertEqual(
            count_by_date(records), [("2026-07-18", 2), ("2026-07-19", 1)]
        )

    def test_rejects_missing_columns(self) -> None:
        with self.assertRaisesRegex(AttendanceDataError, "face_distance"):
            parse_attendance_csv(io.StringIO("name,date,time\nA,2026-07-18,09:00:00\n"))

    def test_rejects_invalid_dates(self) -> None:
        invalid = "name,date,time,face_distance\nA,18-07-2026,09:00:00,0.4\n"
        with self.assertRaisesRegex(AttendanceDataError, "invalid date or time"):
            parse_attendance_csv(io.StringIO(invalid))


if __name__ == "__main__":
    unittest.main()
