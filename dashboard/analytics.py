"""Validation and summary helpers for attendance CSV files."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from typing import TextIO

REQUIRED_COLUMNS = ("name", "date", "time", "face_distance")


class AttendanceDataError(ValueError):
    """Raised when an attendance CSV cannot be safely interpreted."""


@dataclass(frozen=True)
class AttendanceRecord:
    """One validated attendance row."""

    name: str
    date: date
    time: time
    timestamp: datetime
    face_distance: float | None

    def as_dict(self) -> dict[str, object]:
        """Return a display-friendly dictionary."""
        data = asdict(self)
        data["date"] = self.date.isoformat()
        data["time"] = self.time.strftime("%H:%M:%S")
        return data


def parse_attendance_csv(csv_file: TextIO) -> list[AttendanceRecord]:
    """Parse and validate an attendance CSV file."""
    reader = csv.DictReader(csv_file)
    if reader.fieldnames is None:
        raise AttendanceDataError("The CSV file does not contain a header row.")

    columns = {column.strip().lower(): column for column in reader.fieldnames}
    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        raise AttendanceDataError(
            "Missing required column(s): " + ", ".join(missing)
        )

    records: list[AttendanceRecord] = []
    for row_number, row in enumerate(reader, start=2):
        name = (row.get(columns["name"]) or "").strip()
        if not name:
            continue

        date_text = (row.get(columns["date"]) or "").strip()
        time_text = (row.get(columns["time"]) or "").strip()
        try:
            timestamp = datetime.strptime(
                f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S"
            )
        except ValueError as exc:
            raise AttendanceDataError(
                f"Row {row_number} has an invalid date or time."
            ) from exc

        distance_text = (row.get(columns["face_distance"]) or "").strip()
        try:
            face_distance = float(distance_text) if distance_text else None
        except ValueError as exc:
            raise AttendanceDataError(
                f"Row {row_number} has an invalid face distance."
            ) from exc
        if face_distance is not None and face_distance < 0:
            raise AttendanceDataError(
                f"Row {row_number} has a negative face distance."
            )

        records.append(
            AttendanceRecord(
                name=name,
                date=timestamp.date(),
                time=timestamp.time(),
                timestamp=timestamp,
                face_distance=face_distance,
            )
        )

    if not records:
        raise AttendanceDataError("The CSV file does not contain attendance records.")
    return sorted(records, key=lambda record: record.timestamp)


def summarise_attendance(records: list[AttendanceRecord]) -> dict[str, object]:
    """Calculate the headline metrics used by the dashboard."""
    if not records:
        raise AttendanceDataError("Cannot summarise an empty attendance list.")

    distances = [
        record.face_distance
        for record in records
        if record.face_distance is not None
    ]
    return {
        "records": len(records),
        "people": len({record.name for record in records}),
        "days": len({record.date for record in records}),
        "average_distance": (
            sum(distances) / len(distances) if distances else None
        ),
    }


def count_by_person(records: list[AttendanceRecord]) -> list[tuple[str, int]]:
    """Return attendance totals per person, highest first."""
    return sorted(
        Counter(record.name for record in records).items(),
        key=lambda item: (-item[1], item[0].lower()),
    )


def count_by_date(records: list[AttendanceRecord]) -> list[tuple[str, int]]:
    """Return chronological attendance totals per date."""
    counts = Counter(record.date.isoformat() for record in records)
    return sorted(counts.items())
