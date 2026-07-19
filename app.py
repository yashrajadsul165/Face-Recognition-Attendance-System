"""Webcam-based face recognition attendance system.

Register one clear reference image per person, then run the webcam mode to
recognise registered faces and save one attendance record per person per day.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
KNOWN_FACES_DIR = PROJECT_ROOT / "known_faces"
ATTENDANCE_DIR = PROJECT_ROOT / "attendance"
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def safe_name(name: str) -> str:
    """Return a display name containing only safe filename characters."""
    cleaned = re.sub(r"[^A-Za-z0-9 _-]", "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise ValueError("Name must contain at least one letter or number.")
    return cleaned


def validate_reference_image(image_path: Path) -> None:
    """Require a reference image containing exactly one detectable face."""
    try:
        import face_recognition
    except ImportError as exc:
        raise RuntimeError(
            "The face-recognition package is not installed. "
            "Run `pip install -r requirements.txt`."
        ) from exc

    image = face_recognition.load_image_file(str(image_path))
    encodings = face_recognition.face_encodings(image)
    if len(encodings) != 1:
        raise ValueError(
            "The reference image must contain exactly one clearly visible face."
        )


def register_face(name: str, image_path: Path, overwrite: bool = False) -> Path:
    """Validate and copy a person's reference image into known_faces/."""
    image_path = image_path.expanduser().resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    extension = image_path.suffix.lower()
    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError("Reference image must be a JPG, JPEG or PNG file.")

    display_name = safe_name(name)
    filename = display_name.replace(" ", "_") + extension
    destination = KNOWN_FACES_DIR / filename

    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"A reference image already exists for {display_name}. "
            "Use --overwrite to replace it."
        )

    validate_reference_image(image_path)
    KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(image_path, destination)
    return destination


def load_known_faces() -> tuple[list[object], list[str]]:
    """Load face encodings and names from known_faces/."""
    try:
        import face_recognition
    except ImportError as exc:
        raise RuntimeError(
            "The face-recognition package is not installed. "
            "Run `pip install -r requirements.txt`."
        ) from exc

    KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
    encodings: list[object] = []
    names: list[str] = []

    for image_path in sorted(KNOWN_FACES_DIR.iterdir()):
        if image_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            continue

        image = face_recognition.load_image_file(str(image_path))
        image_encodings = face_recognition.face_encodings(image)
        if len(image_encodings) != 1:
            print(f"Skipping {image_path.name}: expected exactly one face.")
            continue

        encodings.append(image_encodings[0])
        names.append(image_path.stem.replace("_", " "))

    return encodings, names


def load_marked_names(
    attendance_dir: Path = ATTENDANCE_DIR,
    now: datetime | None = None,
) -> set[str]:
    """Return names already recorded on the selected day."""
    timestamp = now or datetime.now()
    csv_path = attendance_dir / f"attendance_{timestamp:%Y-%m-%d}.csv"
    if not csv_path.exists():
        return set()

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        return {
            row["name"]
            for row in csv.DictReader(csv_file)
            if row.get("name")
        }


def mark_attendance(
    name: str,
    face_distance: float | None = None,
    attendance_dir: Path = ATTENDANCE_DIR,
    now: datetime | None = None,
) -> bool:
    """Write one attendance record per person per day.

    Returns True when a new row is written and False when the person has
    already been marked present for the day.
    """
    timestamp = now or datetime.now()
    attendance_dir.mkdir(parents=True, exist_ok=True)
    csv_path = attendance_dir / f"attendance_{timestamp:%Y-%m-%d}.csv"

    existing_names = load_marked_names(attendance_dir, timestamp)

    if name in existing_names:
        return False

    is_new_file = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file, fieldnames=["name", "date", "time", "face_distance"]
        )
        if is_new_file:
            writer.writeheader()
        writer.writerow(
            {
                "name": name,
                "date": f"{timestamp:%Y-%m-%d}",
                "time": f"{timestamp:%H:%M:%S}",
                "face_distance": (
                    f"{face_distance:.4f}" if face_distance is not None else ""
                ),
            }
        )
    return True


def run_camera(
    camera_index: int = 0,
    tolerance: float = 0.5,
    detection_model: str = "hog",
) -> None:
    """Recognise faces from a webcam and record attendance."""
    try:
        import cv2
        import face_recognition
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "Project dependencies are missing. Run `pip install -r requirements.txt`."
        ) from exc

    known_encodings, known_names = load_known_faces()
    if not known_encodings:
        raise RuntimeError(
            "No valid reference faces found. Register a person before running the camera."
        )

    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        raise RuntimeError(f"Could not open camera {camera_index}.")

    marked_names = load_marked_names()
    print("Attendance camera started. Press q in the camera window to exit.")
    try:
        while True:
            success, frame = camera.read()
            if not success:
                print("Could not read a camera frame.")
                break

            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(
                rgb_frame, model=detection_model
            )
            face_encodings = face_recognition.face_encodings(rgb_frame, locations)

            for (top, right, bottom, left), face_encoding in zip(
                locations, face_encodings
            ):
                distances = face_recognition.face_distance(
                    known_encodings, face_encoding
                )
                best_match_index = int(np.argmin(distances))
                best_distance = float(distances[best_match_index])
                name = "Unknown"

                if best_distance <= tolerance:
                    name = known_names[best_match_index]
                    if name not in marked_names:
                        if mark_attendance(name, best_distance):
                            print(f"Attendance marked for {name}.")
                        marked_names.add(name)

                top, right, bottom, left = (
                    top * 4,
                    right * 4,
                    bottom * 4,
                    left * 4,
                )
                colour = (0, 170, 0) if name != "Unknown" else (0, 0, 220)
                cv2.rectangle(frame, (left, top), (right, bottom), colour, 2)
                cv2.rectangle(
                    frame, (left, bottom - 30), (right, bottom), colour, cv2.FILLED
                )
                cv2.putText(
                    frame,
                    name,
                    (left + 6, bottom - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    1,
                )

            cv2.imshow("Face Recognition Attendance", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Register faces and record attendance using a webcam."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser(
        "register", help="Register one reference image for a person."
    )
    register_parser.add_argument("--name", required=True, help="Person's full name.")
    register_parser.add_argument(
        "--image", type=Path, required=True, help="Path to a JPG or PNG image."
    )
    register_parser.add_argument(
        "--overwrite", action="store_true", help="Replace an existing reference image."
    )

    run_parser = subparsers.add_parser(
        "run", help="Start recognition and attendance recording."
    )
    run_parser.add_argument("--camera", type=int, default=0, help="Webcam index.")
    run_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.5,
        help="Maximum face distance accepted as a match (default: 0.5).",
    )
    run_parser.add_argument(
        "--model",
        choices=["hog", "cnn"],
        default="hog",
        help="Face detection model. HOG is faster on normal computers.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "register":
            destination = register_face(args.name, args.image, args.overwrite)
            print(f"Reference face registered: {destination}")
        else:
            if not 0.0 < args.tolerance < 1.0:
                raise ValueError("Tolerance must be between 0 and 1.")
            run_camera(args.camera, args.tolerance, args.model)
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
