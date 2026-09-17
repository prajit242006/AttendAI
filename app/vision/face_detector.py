"""
Face detection with OpenCV Haar cascades.

The cascade XML files ship INSIDE the opencv-contrib-python package
(cv2.data.haarcascades), so nothing has to be downloaded and no model
file is missing from the project.
"""

import base64
import binascii
import os

import cv2
import numpy as np

# Size every cropped face is resized to before training / predicting.
FACE_SIZE = 200


class FaceDetectionError(Exception):
    """Raised when a frame cannot be decoded or the cascade is missing."""


def _cascade_path(filename):
    path = os.path.join(cv2.data.haarcascades, filename)
    if not os.path.exists(path):
        raise FaceDetectionError(
            "OpenCV cascade file not found: {}. Install opencv-contrib-python.".format(path)
        )
    return path


class FaceDetector:
    """Thin wrapper around the frontal-face Haar cascade."""

    def __init__(self, scale_factor=1.1, min_neighbors=4, min_size=(60, 60)):
        self.cascade = cv2.CascadeClassifier(
            _cascade_path("haarcascade_frontalface_default.xml")
        )
        if self.cascade.empty():
            raise FaceDetectionError("Failed to load the frontal face cascade.")
        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_size = min_size

    # ------------------------------------------------------------------
    def detect(self, gray_image):
        """Return a list of (x, y, w, h) boxes, biggest face first."""
        faces = self.cascade.detectMultiScale(
            gray_image,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_size,
        )
        boxes = [tuple(int(v) for v in box) for box in faces]
        boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
        return boxes

    def detect_single(self, gray_image):
        """
        Detect exactly one usable face.

        Returns (box, status) where status is one of:
        NO_FACE / MULTIPLE_FACES / OK
        """
        boxes = self.detect(gray_image)
        if not boxes:
            return None, "NO_FACE"
        if len(boxes) > 1:
            return boxes[0], "MULTIPLE_FACES"
        return boxes[0], "OK"

    @staticmethod
    def crop_face(gray_image, box, size=FACE_SIZE):
        """Crop the box out of the grayscale frame and normalise it."""
        x, y, w, h = box
        face = gray_image[y:y + h, x:x + w]
        if face.size == 0:
            raise FaceDetectionError("Empty face crop.")
        face = cv2.resize(face, (size, size), interpolation=cv2.INTER_AREA)
        # Histogram equalisation makes LBPH much less sensitive to lighting.
        return cv2.equalizeHist(face)


# ----------------------------------------------------------------------
# Helpers for turning browser webcam frames into OpenCV images
# ----------------------------------------------------------------------
def decode_base64_image(data_url):
    """
    Convert a 'data:image/jpeg;base64,...' string coming from the browser
    into a BGR numpy image.
    """
    if not data_url:
        raise FaceDetectionError("No image data received.")
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    try:
        raw = base64.b64decode(data_url)
    except (binascii.Error, ValueError):
        raise FaceDetectionError("The captured frame could not be decoded.")

    buffer = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise FaceDetectionError("The captured frame is not a valid image.")
    return image


def to_gray(image):
    """BGR -> grayscale (LBPH always works on grayscale)."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


# One shared detector instance - creating the cascade is relatively costly.
_detector = None


def get_detector():
    global _detector
    if _detector is None:
        _detector = FaceDetector()
    return _detector
