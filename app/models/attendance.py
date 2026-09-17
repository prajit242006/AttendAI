"""Attendance models.

AttendanceSession = one class hour started by a teacher.
AttendanceRecord  = one student's result inside that session.

The UNIQUE(student_id, attendance_session_id) constraint on
attendance_records is what makes duplicate attendance impossible.
"""

from datetime import datetime

from app import db

STATUS_PRESENT = "PRESENT"
STATUS_ABSENT = "ABSENT"
STATUS_LATE = "LATE"
STATUS_REVIEW = "REVIEW_REQUIRED"

SESSION_ACTIVE = "ACTIVE"
SESSION_ENDED = "ENDED"

ALL_STATUSES = [STATUS_PRESENT, STATUS_LATE, STATUS_ABSENT, STATUS_REVIEW]


class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)

    session_date = db.Column(db.Date, nullable=False, index=True)
    class_start_time = db.Column(db.Time, nullable=False)

    # rules chosen by the teacher when the session was started
    late_threshold_minutes = db.Column(db.Integer, default=10, nullable=False)
    presence_threshold = db.Column(db.Float, default=75.0, nullable=False)
    recognition_threshold = db.Column(db.Float, default=70.0, nullable=False)
    check_interval_seconds = db.Column(db.Integer, default=10, nullable=False)

    status = db.Column(db.String(16), default=SESSION_ACTIVE, nullable=False, index=True)
    started_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    # timestamp of the last continuous-presence tick
    last_check_at = db.Column(db.DateTime, nullable=True)
    total_checks = db.Column(db.Integer, default=0, nullable=False)

    subject = db.relationship("Subject", back_populates="sessions")
    teacher = db.relationship("Teacher", back_populates="sessions")
    records = db.relationship(
        "AttendanceRecord", back_populates="session",
        cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def is_active(self):
        return self.status == SESSION_ACTIVE

    @property
    def late_after(self):
        """datetime after which an arrival counts as LATE."""
        from datetime import timedelta

        start = datetime.combine(self.session_date, self.class_start_time)
        return start + timedelta(minutes=self.late_threshold_minutes)

    def __repr__(self):
        return "<AttendanceSession {} subject={} {}>".format(
            self.id, self.subject_id, self.status
        )


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "attendance_session_id", name="uq_student_session"
        ),
        db.Index("ix_record_date_status", "session_date", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attendance_session_id = db.Column(
        db.Integer, db.ForeignKey("attendance_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    session_date = db.Column(db.Date, nullable=False, index=True)
    first_detection_time = db.Column(db.DateTime, nullable=True)
    last_detection_time = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20), default=STATUS_ABSENT, nullable=False, index=True)
    liveness_verified = db.Column(db.Boolean, default=False, nullable=False)

    presence_count = db.Column(db.Integer, default=0, nullable=False)
    total_checks = db.Column(db.Integer, default=0, nullable=False)
    presence_percentage = db.Column(db.Float, default=0.0, nullable=False)
    # last continuous-presence tick this student was counted in
    last_presence_tick = db.Column(db.DateTime, nullable=True)

    recognition_confidence = db.Column(db.Float, nullable=True)
    manually_modified = db.Column(db.Boolean, default=False, nullable=False)
    remarks = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    student = db.relationship("Student", back_populates="records")
    subject = db.relationship("Subject", back_populates="records")
    session = db.relationship("AttendanceSession", back_populates="records")

    # ------------------------------------------------------------------
    def recompute_presence(self):
        """presence_percentage = presence_count / total_checks * 100."""
        if self.total_checks > 0:
            self.presence_percentage = round(
                (self.presence_count / float(self.total_checks)) * 100.0, 2
            )
        else:
            self.presence_percentage = 0.0
        return self.presence_percentage

    @property
    def counts_as_present(self):
        return self.status in (STATUS_PRESENT, STATUS_LATE)

    def to_dict(self):
        return {
            "id": self.id,
            "register_number": self.student.register_number if self.student else "",
            "name": self.student.name if self.student else "",
            "first_detection": (
                self.first_detection_time.strftime("%I:%M %p") if self.first_detection_time else "-"
            ),
            "last_detection": (
                self.last_detection_time.strftime("%I:%M %p") if self.last_detection_time else "-"
            ),
            "liveness": "VERIFIED" if self.liveness_verified else "-",
            "presence": self.presence_percentage,
            "presence_count": self.presence_count,
            "total_checks": self.total_checks,
            "status": self.status,
            "manually_modified": self.manually_modified,
        }

    def __repr__(self):
        return "<AttendanceRecord student={} session={} {}>".format(
            self.student_id, self.attendance_session_id, self.status
        )
