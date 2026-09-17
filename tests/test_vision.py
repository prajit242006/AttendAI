"""
Tests for the computer-vision layer.

These run WITHOUT a database and WITHOUT a camera:

    python -m unittest discover -s tests -v
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.vision.face_detector import FaceDetector, decode_base64_image, to_gray  # noqa: E402
from app.vision.face_trainer import (  # noqa: E402
    build_dataset,
    count_samples,
    save_face_samples,
    train_model,
)
from app.vision.face_recognizer import FaceRecognitionService  # noqa: E402
from app.vision.liveness import (  # noqa: E402
    CHALLENGE_LEFT,
    PASSED,
    PENDING,
    LivenessManager,
)


def synthetic_face(seed):
    """A repeatable 200x200 grayscale pattern standing in for one person."""
    rng = np.random.RandomState(seed)
    base = np.full((200, 200), min(110 + seed * 25, 200), dtype=np.uint8)
    noise = rng.randint(0, 35, (200, 200), dtype=np.uint8)
    return cv2.GaussianBlur(cv2.add(base, noise), (5, 5), 0)


class DetectorTests(unittest.TestCase):
    def test_cascade_loads(self):
        detector = FaceDetector()
        self.assertFalse(detector.cascade.empty())

    def test_blank_frame_has_no_face(self):
        detector = FaceDetector()
        blank = np.zeros((480, 640), dtype=np.uint8)
        box, status = detector.detect_single(blank)
        self.assertEqual(status, "NO_FACE")
        self.assertIsNone(box)

    def test_base64_round_trip(self):
        image = np.zeros((60, 80, 3), dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", image)
        self.assertTrue(ok)
        import base64

        data_url = "data:image/jpeg;base64," + base64.b64encode(buffer).decode()
        decoded = decode_base64_image(data_url)
        self.assertEqual(decoded.shape[:2], (60, 80))
        self.assertEqual(to_gray(decoded).ndim, 2)


class TrainerRecognizerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.face_dir = self.tmp / "face_data"
        self.models_dir = self.tmp / "models_data"
        self.face_dir.mkdir()
        self.models_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_train_and_predict(self):
        for index, register in enumerate(["23CS001", "23CS002"], start=1):
            faces = [synthetic_face(index) for _ in range(8)]
            save_face_samples(self.face_dir, register, faces)
            self.assertEqual(count_samples(self.face_dir, register), 8)

        samples, labels, label_map = build_dataset(self.face_dir)
        self.assertEqual(len(samples), 16)
        self.assertEqual(len(label_map), 2)

        model_path = self.models_dir / "lbph_model.yml"
        labels_path = self.models_dir / "labels.json"
        payload = train_model(self.face_dir, model_path, labels_path)

        self.assertEqual(payload["students"], 2)
        self.assertTrue(os.path.exists(model_path))

        service = FaceRecognitionService(model_path, labels_path, threshold=200)
        result = service.predict_face(synthetic_face(1))
        self.assertTrue(result["recognized"])
        self.assertEqual(result["register_number"], "23CS001")

    def test_threshold_rejects_stranger(self):
        save_face_samples(self.face_dir, "23CS001", [synthetic_face(1) for _ in range(6)])
        model_path = self.models_dir / "lbph_model.yml"
        labels_path = self.models_dir / "labels.json"
        train_model(self.face_dir, model_path, labels_path)

        service = FaceRecognitionService(model_path, labels_path, threshold=0.0001)
        result = service.predict_face(synthetic_face(9))
        self.assertFalse(result["recognized"])
        self.assertIsNone(result["register_number"])


class LivenessTests(unittest.TestCase):
    def test_movement_passes_the_challenge(self):
        manager = LivenessManager()
        box = (200, 150, 100, 100)

        state, _ = manager.check(1, "23CS001", box, 640)
        self.assertEqual(state, PENDING)

        challenge = manager.get(1, "23CS001")
        challenge.challenge = CHALLENGE_LEFT          # make the test deterministic

        state, _ = manager.check(1, "23CS001", (200, 150, 100, 100), 640)
        self.assertEqual(state, PENDING)              # no movement yet

        state, _ = manager.check(1, "23CS001", (260, 150, 100, 100), 640)
        self.assertEqual(state, PASSED)               # moved far enough

    def test_challenge_is_cleared_after_success(self):
        manager = LivenessManager()
        manager.check(2, "23CS002", (100, 100, 80, 80), 640)
        manager.get(2, "23CS002").challenge = CHALLENGE_LEFT
        manager.check(2, "23CS002", (200, 100, 80, 80), 640)
        self.assertIsNone(manager.get(2, "23CS002"))


if __name__ == "__main__":
    unittest.main()
