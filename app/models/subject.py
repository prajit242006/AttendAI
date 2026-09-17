"""Subject model - one row per course taught."""

from datetime import datetime

from app import db


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(80), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    students = db.relationship(
        "Student", secondary="student_subjects", back_populates="subjects"
    )
    sessions = db.relationship(
        "AttendanceSession", back_populates="subject", cascade="all, delete-orphan"
    )
    records = db.relationship(
        "AttendanceRecord", back_populates="subject", cascade="all, delete-orphan"
    )

    @property
    def label(self):
        return "{} - {}".format(self.code, self.name)

    def __repr__(self):
        return "<Subject {}>".format(self.code)
