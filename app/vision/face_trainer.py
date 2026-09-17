"""
Training of the LBPH face recognition model.

Face samples live in   face_data/<register_number>/sample_XX.png
The trained model is written to models_data/lbph_model.yml together with
models_data/labels.json which maps the numeric LBPH label back to the
student's register number.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from app.vision.face_detector import (
    FACE_SIZE,
    FaceDetectionError,
    get_detector,
    to_gray,
)

MIN_CLASSES_FOR_TRAINING = 1


class TrainingError(Exception):
    """Raised when the model cannot be trained."""


def _new_recognizer():
    """cv2.face lives in opencv-contrib-python, not in plain opencv-python."""
    if not hasattr(cv2, "face"):
        raise TrainingError(
            "cv2.face is missing. Install opencv-contrib-python "
            "(pip uninstall opencv-python, then pip install opencv-contrib-python)."
        )
    return cv2.face.LBPHFaceRecognizer_create(
        radius=1, neighbors=8, grid_x=8, grid_y=8
    )


def save_face_samples(face_data_dir, register_number, gray_faces, reset=True):
    """
    Write the cropped grayscale faces of one student to disk.

    Returns (student_folder, number_of_samples_stored).
    """
    student_dir = Path(face_data_dir) / str(register_number)
    if reset and student_dir.exists():
        for old in student_dir.glob("*.png"):
            old.unlink()
    student_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    stored = 0
    for index, face in enumerate(gray_faces, start=1):
        filename = student_dir / "sample_{}_{:02d}.png".format(stamp, index)
        if cv2.imwrite(str(filename), face):
            stored += 1
    return student_dir, stored


def count_samples(face_data_dir, register_number):
    student_dir = Path(face_data_dir) / str(register_number)
    if not student_dir.exists():
        return 0
    return len(list(student_dir.glob("*.png")))


def delete_face_samples(face_data_dir, register_number):
    """Remove one student's folder (used when a student is deleted)."""
    student_dir = Path(face_data_dir) / str(register_number)
    if not student_dir.exists():
        return False
    for item in student_dir.glob("*"):
        item.unlink()
    student_dir.rmdir()
    return True


def extract_faces_from_images(images, detector=None):
    """
    Take BGR frames, detect a face in each one and return the cropped
    grayscale faces. Frames without exactly one face are skipped and the
    reason is reported back so the UI can explain what happened.
    """
    detector = detector or get_detector()
    faces, skipped = [], []
    for image in images:
        gray = to_gray(image)
        box, status = detector.detect_single(gray)
        if status == "NO_FACE":
            skipped.append("NO_FACE")
            continue
        if status == "MULTIPLE_FACES":
            skipped.append("MULTIPLE_FACES")
            continue
        try:
            faces.append(detector.crop_face(gray, box))
        except FaceDetectionError:
            skipped.append("BAD_CROP")
    return faces, skipped


def build_dataset(face_data_dir):
    """
    Read every face_data/<register_number>/*.png file.

    Returns (samples, labels, label_map) where label_map maps
    "0" -> "23CS001".
    """
    face_data_dir = Path(face_data_dir)
    samples, labels, label_map = [], [], {}

    if not face_data_dir.exists():
        return samples, labels, label_map

    folders = sorted(
        [p for p in face_data_dir.iterdir() if p.is_dir() and not p.name.startswith(".")],
        key=lambda p: p.name,
    )

    next_label = 0
    for folder in folders:
        images = sorted(folder.glob("*.png"))
        if not images:
            continue
        for image_path in images:
            gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                continue
            if gray.shape[:2] != (FACE_SIZE, FACE_SIZE):
                gray = cv2.resize(gray, (FACE_SIZE, FACE_SIZE))
            samples.append(gray)
            labels.append(next_label)
        label_map[str(next_label)] = folder.name
        next_label += 1

    return samples, labels, label_map


def train_model(face_data_dir, model_path, labels_path):
    """
    Train LBPH on everything in face_data/ and save the result.

    Returns a small summary dict for the UI.
    """
    samples, labels, label_map = build_dataset(face_data_dir)

    if not samples:
        raise TrainingError(
            "No face samples found. Register at least one student's face first."
        )
    if len(label_map) < MIN_CLASSES_FOR_TRAINING:
        raise TrainingError("Not enough students with face data to train.")

    recognizer = _new_recognizer()
    recognizer.train(samples, np.array(labels, dtype=np.int32))

    model_path = Path(model_path)
    labels_path = Path(labels_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    recognizer.write(str(model_path))

    payload = {
        "labels": label_map,
        "students": len(label_map),
        "samples": len(samples),
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(labels_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    return payload


def model_info(model_path, labels_path):
    """Describe the trained model for the dashboard / face pages."""
    model_path, labels_path = Path(model_path), Path(labels_path)
    if not model_path.exists() or not labels_path.exists():
        return {"trained": False, "students": 0, "samples": 0, "trained_at": None}
    try:
        with open(labels_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (ValueError, OSError):
        return {"trained": False, "students": 0, "samples": 0, "trained_at": None}
    payload["trained"] = True
    payload.setdefault("students", len(payload.get("labels", {})))
    payload.setdefault("samples", 0)
    payload.setdefault("trained_at", None)
    payload["size_kb"] = round(os.path.getsize(model_path) / 1024.0, 1)
    return payload
