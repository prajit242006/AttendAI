"""
AttendAI - configuration
------------------------
All tunable settings live here. Values are read from the .env file
(see .env.example) so that no password is ever committed to the project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Absolute path of the project root (the folder that contains run.py).
BASE_DIR = Path(__file__).resolve().parent

# Load the .env file sitting next to this file.
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration shared by every environment."""

    # ------------------------------------------------------------------
    # Flask / security
    # ------------------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "attendai-dev-secret-change-me")
    WTF_CSRF_TIME_LIMIT = None          # CSRF token valid for the whole session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # ------------------------------------------------------------------
    # Database (MySQL by default, see README for the exact commands)
    # ------------------------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:root@localhost/attendai_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # ------------------------------------------------------------------
    # Folders used by the computer-vision part
    # ------------------------------------------------------------------
    BASE_DIR = BASE_DIR
    FACE_DATA_DIR = Path(os.getenv("FACE_DATA_DIR", BASE_DIR / "face_data"))
    MODELS_DIR = Path(os.getenv("MODELS_DIR", BASE_DIR / "models_data"))
    LBPH_MODEL_PATH = MODELS_DIR / "lbph_model.yml"
    LABELS_PATH = MODELS_DIR / "labels.json"

    # ------------------------------------------------------------------
    # Face recognition tuning
    # ------------------------------------------------------------------
    # LBPH returns a DISTANCE: smaller = better match.
    # A prediction is accepted only when distance <= RECOGNITION_THRESHOLD.
    RECOGNITION_THRESHOLD = float(os.getenv("RECOGNITION_THRESHOLD", 70))
    FACE_SAMPLE_SIZE = 200              # every stored face is 200x200 grayscale
    MIN_FACE_SAMPLES = int(os.getenv("MIN_FACE_SAMPLES", 5))
    FACE_SAMPLES_TARGET = int(os.getenv("FACE_SAMPLES_TARGET", 15))

    # ------------------------------------------------------------------
    # Attendance rules (defaults for the "Start attendance" form)
    # ------------------------------------------------------------------
    DEFAULT_LATE_THRESHOLD_MIN = int(os.getenv("DEFAULT_LATE_THRESHOLD_MIN", 10))
    DEFAULT_PRESENCE_THRESHOLD = float(os.getenv("DEFAULT_PRESENCE_THRESHOLD", 75))
    DEFAULT_CHECK_INTERVAL_SEC = int(os.getenv("DEFAULT_CHECK_INTERVAL_SEC", 10))
    MIN_ATTENDANCE_PERCENT = float(os.getenv("MIN_ATTENDANCE_PERCENT", 75))

    # ------------------------------------------------------------------
    # Liveness (basic, demonstration level - see README)
    # ------------------------------------------------------------------
    LIVENESS_ENABLED = os.getenv("LIVENESS_ENABLED", "true").lower() == "true"
    # How far (as a fraction of the face width) the head must move sideways.
    LIVENESS_MOVE_RATIO = float(os.getenv("LIVENESS_MOVE_RATIO", 0.18))
    # How much bigger the face box must become for the "move closer" challenge.
    LIVENESS_SCALE_RATIO = float(os.getenv("LIVENESS_SCALE_RATIO", 1.15))
    LIVENESS_TIMEOUT_SEC = int(os.getenv("LIVENESS_TIMEOUT_SEC", 25))

    # ------------------------------------------------------------------
    # Default teacher account created on first run
    # ------------------------------------------------------------------
    DEFAULT_TEACHER_USERNAME = os.getenv("DEFAULT_TEACHER_USERNAME", "admin")
    DEFAULT_TEACHER_PASSWORD = os.getenv("DEFAULT_TEACHER_PASSWORD", "Admin@123")
    DEFAULT_TEACHER_NAME = os.getenv("DEFAULT_TEACHER_NAME", "Administrator")
    DEFAULT_TEACHER_EMAIL = os.getenv("DEFAULT_TEACHER_EMAIL", "admin@attendai.local")

    # Max upload size for the base64 webcam frames (8 MB is plenty).
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name=None):
    """Return the configuration class for the given environment name."""
    name = (name or os.getenv("FLASK_ENV") or "development").lower()
    return CONFIG_BY_NAME.get(name, DevelopmentConfig)
