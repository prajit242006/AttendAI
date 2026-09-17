"""User + Teacher models.

Every person who can log in has a row in `users`. The role column decides
whether they are a TEACHER or a STUDENT. Passwords are never stored in
plain text - only a Werkzeug hash is kept.
"""

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

ROLE_TEACHER = "TEACHER"
ROLE_STUDENT = "STUDENT"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False, default=ROLE_STUDENT, index=True)
    is_active_flag = db.Column("is_active", db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    teacher = db.relationship(
        "Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    student = db.relationship(
        "Student", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    # -- password helpers -------------------------------------------------
    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    # -- role helpers -----------------------------------------------------
    @property
    def is_teacher(self):
        return self.role == ROLE_TEACHER

    @property
    def is_student(self):
        return self.role == ROLE_STUDENT

    @property
    def is_active(self):
        """Flask-Login uses this to block disabled accounts."""
        return bool(self.is_active_flag)

    @property
    def display_name(self):
        if self.teacher:
            return self.teacher.name
        if self.student:
            return self.student.name
        return self.username

    def __repr__(self):
        return "<User {} ({})>".format(self.username, self.role)


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    department = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="teacher")
    sessions = db.relationship("AttendanceSession", back_populates="teacher")

    def __repr__(self):
        return "<Teacher {}>".format(self.name)
