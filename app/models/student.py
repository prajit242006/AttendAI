"""Student model and the student <-> subject association table."""

from datetime import datetime

from app import db

# A student can be enrolled in many subjects and a subject has many students.
student_subjects = db.Table(
    "student_subjects",
    db.Column("student_id", db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"),
              primary_key=True),
    db.Column("subject_id", db.Integer, db.ForeignKey("subjects.id", ondelete="CASCADE"),
              primary_key=True),
)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    register_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(80), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(10), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    face_registered = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="student")
    subjects = db.relationship(
        "Subject", secondary=student_subjects, back_populates="students"
    )
    face_profile = db.relationship(
        "FaceProfile", back_populates="student", uselist=False, cascade="all, delete-orphan"
    )
    records = db.relationship(
        "AttendanceRecord", back_populates="student", cascade="all, delete-orphan"
    )

    @property
    def username(self):
        return self.user.username if self.user else None

    def to_dict(self):
        return {
            "id": self.id,
            "register_number": self.register_number,
            "name": self.name,
            "department": self.department,
            "year": self.year,
            "section": self.section,
            "email": self.email,
            "face_registered": self.face_registered,
        }

    def __repr__(self):
        return "<Student {} {}>".format(self.register_number, self.name)
