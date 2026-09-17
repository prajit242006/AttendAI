"""Database models for AttendAI.

Importing this package makes every model class visible to SQLAlchemy,
which is what db.create_all() needs.
"""

from app.models.user import User, Teacher, ROLE_TEACHER, ROLE_STUDENT
from app.models.student import Student, student_subjects
from app.models.subject import Subject
from app.models.face_profile import FaceProfile
from app.models.attendance import (
    AttendanceSession,
    AttendanceRecord,
    STATUS_PRESENT,
    STATUS_ABSENT,
    STATUS_LATE,
    STATUS_REVIEW,
)

__all__ = [
    "User",
    "Teacher",
    "Student",
    "Subject",
    "FaceProfile",
    "AttendanceSession",
    "AttendanceRecord",
    "student_subjects",
    "ROLE_TEACHER",
    "ROLE_STUDENT",
    "STATUS_PRESENT",
    "STATUS_ABSENT",
    "STATUS_LATE",
    "STATUS_REVIEW",
]
