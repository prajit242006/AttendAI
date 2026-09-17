"""FaceProfile - bookkeeping for the face samples stored on disk.

The images themselves live in face_data/<register_number>/ ; this table
only remembers how many samples exist, which numeric LBPH label the
student owns and when the samples were last updated.
"""

from datetime import datetime

from app import db


class FaceProfile(db.Model):
    __tablename__ = "face_profiles"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    label = db.Column(db.Integer, nullable=True, index=True)   # numeric LBPH label
    sample_count = db.Column(db.Integer, default=0, nullable=False)
    samples_dir = db.Column(db.String(255), nullable=False)
    trained = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    student = db.relationship("Student", back_populates="face_profile")

    def __repr__(self):
        return "<FaceProfile student={} samples={}>".format(self.student_id, self.sample_count)
