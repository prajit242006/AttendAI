"""
LBPH face recognition.

LBPH returns a DISTANCE, not a similarity: the smaller the number the
better the match. A prediction is accepted only when the distance is
below the configurable recognition threshold.

Confidence shown in the UI is a friendlier percentage:
    confidence = max(0, 100 - distance)

Supports:
1. Single-face recognition for existing AttendAI features.
2. Multi-face recognition for 2-5 students in the same webcam frame.
"""

import json
import threading
from pathlib import Path

import cv2

from app.vision.face_detector import get_detector, to_gray
from app.vision.face_trainer import _new_recognizer


class RecognitionError(Exception):
    pass


class FaceRecognitionService:
    """
    Loads models_data/lbph_model.yml once and reloads it automatically
    whenever the file on disk changes (i.e. after re-training).
    """

    def __init__(self, model_path, labels_path, threshold=70.0):
        self.model_path = Path(model_path)
        self.labels_path = Path(labels_path)
        self.threshold = float(threshold)

        self._recognizer = None
        self._labels = {}
        self._mtime = None
        self._lock = threading.Lock()

    # --------------------------------------------------------------
    @property
    def is_ready(self):
        return self.model_path.exists() and self.labels_path.exists()

    def load(self, force=False):
        """(Re)load the trained model if it exists or has changed."""

        if not self.is_ready:
            self._recognizer = None
            self._labels = {}
            return False

        mtime = self.model_path.stat().st_mtime

        with self._lock:
            if (
                force
                or self._recognizer is None
                or mtime != self._mtime
            ):
                recognizer = _new_recognizer()
                recognizer.read(str(self.model_path))

                with open(
                    self.labels_path,
                    "r",
                    encoding="utf-8"
                ) as handle:
                    payload = json.load(handle)

                self._recognizer = recognizer
                self._labels = payload.get("labels", {})
                self._mtime = mtime

        return True

    # --------------------------------------------------------------
    def predict_face(self, gray_face, threshold=None):
        """
        Predict one already cropped grayscale face.

        Returns:
        {
            recognized,
            register_number,
            distance,
            confidence,
            threshold
        }
        """

        if not self.load():
            raise RecognitionError(
                "Face model is not trained yet. "
                "Use 'Train face model' first."
            )

        threshold = float(
            threshold
            if threshold is not None
            else self.threshold
        )

        label, distance = self._recognizer.predict(gray_face)

        register_number = self._labels.get(str(label))

        distance = float(distance)

        confidence = max(
            0.0,
            round(100.0 - distance, 2)
        )

        recognized = (
            bool(register_number)
            and distance <= threshold
        )

        return {
            "recognized": recognized,
            "register_number": (
                register_number
                if recognized
                else None
            ),
            "distance": round(distance, 2),
            "confidence": confidence,
            "threshold": threshold,
        }

    # --------------------------------------------------------------
    # EXISTING SINGLE-FACE RECOGNITION
    # --------------------------------------------------------------

    def recognize_frame(self, bgr_image, threshold=None):
        """
        Existing AttendAI single-face pipeline.

        This is kept so the current single-student
        functionality continues to work.

        Status:
        NO_FACE
        MULTIPLE_FACES
        UNKNOWN
        RECOGNIZED
        """

        detector = get_detector()
        gray = to_gray(bgr_image)

        box, detect_status = detector.detect_single(gray)

        height, width = gray.shape[:2]

        result = {
            "status": detect_status,
            "box": box,
            "frame_width": width,
            "frame_height": height,
            "recognized": False,
            "register_number": None,
            "confidence": None,
            "distance": None,
        }

        if detect_status == "NO_FACE":
            return result

        if detect_status == "MULTIPLE_FACES":
            return result

        face = detector.crop_face(gray, box)

        prediction = self.predict_face(
            face,
            threshold=threshold
        )

        result.update(prediction)

        result["status"] = (
            "RECOGNIZED"
            if prediction["recognized"]
            else "UNKNOWN"
        )

        return result

    # --------------------------------------------------------------
    # NEW MULTI-FACE RECOGNITION
    # --------------------------------------------------------------

    def recognize_faces(self, bgr_image, threshold=None):
        """
        Detect and recognise ALL faces in one webcam frame.

        Designed for small classroom/demo scenarios
        containing approximately 2-5 students.

        Example return:

        {
            "status": "FACES_DETECTED",
            "face_count": 3,
            "faces": [
                {
                    "status": "RECOGNIZED",
                    "register_number": "...",
                    ...
                }
            ]
        }
        """

        detector = get_detector()

        gray = to_gray(bgr_image)

        height, width = gray.shape[:2]

        # Detect every face.
        boxes = detector.detect(gray)

        result = {
            "status": "NO_FACE",
            "frame_width": width,
            "frame_height": height,
            "face_count": 0,
            "recognized_count": 0,
            "faces": [],
        }

        # No faces
        if boxes is None or len(boxes) == 0:
            return result

        result["status"] = "FACES_DETECTED"
        result["face_count"] = len(boxes)

        # Avoid returning the same student twice if
        # overlapping boxes are produced.
        recognized_register_numbers = set()

        for box in boxes:

            # Convert numpy integers to normal Python integers.
            box = tuple(int(value) for value in box)

            try:

                # Crop and normalise face.
                face = detector.crop_face(
                    gray,
                    box
                )

                # LBPH prediction.
                prediction = self.predict_face(
                    face,
                    threshold=threshold
                )

                register_number = prediction[
                    "register_number"
                ]

                recognized = prediction[
                    "recognized"
                ]

                # If the same person was detected twice
                # in one frame, don't count twice.
                duplicate = False

                if recognized and register_number:

                    if (
                        register_number
                        in recognized_register_numbers
                    ):
                        duplicate = True
                        recognized = False

                    else:
                        recognized_register_numbers.add(
                            register_number
                        )

                if duplicate:

                    face_status = "DUPLICATE"

                elif recognized:

                    face_status = "RECOGNIZED"
                    result["recognized_count"] += 1

                else:

                    face_status = "UNKNOWN"

                face_result = {
                    "box": box,
                    "status": face_status,
                    "recognized": recognized,
                    "register_number": (
                        register_number
                        if recognized
                        else None
                    ),
                    "confidence": prediction[
                        "confidence"
                    ],
                    "distance": prediction[
                        "distance"
                    ],
                    "threshold": prediction[
                        "threshold"
                    ],
                }

                result["faces"].append(
                    face_result
                )

            except Exception as exc:

                # One bad face must not stop the remaining
                # students from being processed.
                result["faces"].append(
                    {
                        "box": box,
                        "status": "ERROR",
                        "recognized": False,
                        "register_number": None,
                        "confidence": None,
                        "distance": None,
                        "threshold": float(
                            threshold
                            if threshold is not None
                            else self.threshold
                        ),
                        "error": str(exc),
                    }
                )

        return result


# --------------------------------------------------------------
# SHARED SERVICE
# --------------------------------------------------------------

_service = None


def get_recognizer(app_config):
    """Return the shared recognition service for the running app."""

    global _service

    if _service is None:

        _service = FaceRecognitionService(
            app_config["LBPH_MODEL_PATH"],
            app_config["LABELS_PATH"],
            app_config["RECOGNITION_THRESHOLD"],
        )

    return _service


def reset_recognizer():
    """Force a reload after the model was retrained."""

    global _service

    if _service is not None:
        _service._recognizer = None
        _service._mtime = None