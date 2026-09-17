"""
Attendance business logic.

Everything that decides *what happens* to an attendance record lives
here so the route files stay short and readable:

  * mark_attendance()        - first successful recognition (PRESENT / LATE)
  * update_presence()        - the student was seen again (no duplicate row)
  * run_presence_tick()      - the continuous-presence counter
  * finalize_session()       - end the session, create ABSENT rows
"""

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.attendance import (
    STATUS_ABSENT,
    STATUS_LATE,
    STATUS_PRESENT,
    STATUS_REVIEW,
    SESSION_ENDED,
    AttendanceRecord,
    AttendanceSession,
)
from app.models.student import Student


# ----------------------------------------------------------------------
# Lookup helpers
# ----------------------------------------------------------------------
def get_record(session, student):
    """The single record this student may have in this session (or None)."""
    return AttendanceRecord.query.filter_by(
        attendance_session_id=session.id, student_id=student.id
    ).first()


def decide_status(session, detection_time):
    """PRESENT before the late cut-off, LATE after it."""
    return STATUS_LATE if detection_time > session.late_after else STATUS_PRESENT


# ----------------------------------------------------------------------
# Marking
# ----------------------------------------------------------------------
def mark_attendance(session, student, confidence=None, liveness_verified=True,
                    detection_time=None):
    """
    Create the student's attendance record for this session.

    Returns (record, created) - created is False when a record already
    existed, in which case the presence data is updated instead of a
    second row being inserted (duplicate prevention).
    """
    detection_time = detection_time or datetime.now()

    existing = get_record(session, student)
    if existing is not None:
        update_presence(session, existing, confidence=confidence,
                        detection_time=detection_time)
        return existing, False

    record = AttendanceRecord(
        student_id=student.id,
        subject_id=session.subject_id,
        attendance_session_id=session.id,
        session_date=session.session_date,
        first_detection_time=detection_time,
        last_detection_time=detection_time,
        status=decide_status(session, detection_time),
        liveness_verified=bool(liveness_verified),
        presence_count=1,
        total_checks=max(1, session.total_checks or 1),
        recognition_confidence=confidence,
        last_presence_tick=session.last_check_at or detection_time,
    )
    record.recompute_presence()

    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError:
        # Two frames arrived at almost the same moment - the UNIQUE
        # constraint (student_id, attendance_session_id) stopped the
        # duplicate, so fall back to updating the existing row.
        db.session.rollback()
        existing = get_record(session, student)
        if existing is None:
            raise
        update_presence(session, existing, confidence=confidence,
                        detection_time=detection_time)
        return existing, False

    return record, True


def update_presence(session, record, confidence=None, detection_time=None):
    """The student was recognised again: refresh timings and presence."""
    detection_time = detection_time or datetime.now()
    record.last_detection_time = detection_time
    if confidence is not None:
        record.recognition_confidence = confidence

    # Count this sighting only once per continuous-presence tick, so a
    # fast camera loop cannot inflate the presence percentage.
    tick = session.last_check_at
    if tick is None or record.last_presence_tick != tick:
        record.presence_count += 1
        record.last_presence_tick = tick or detection_time

    if record.total_checks < record.presence_count:
        record.total_checks = record.presence_count
    record.recompute_presence()
    db.session.commit()
    return record


# ----------------------------------------------------------------------
# Continuous presence verification
# ----------------------------------------------------------------------
def run_presence_tick(session, force=False):
    """
    One "check" of the continuous presence verification.

    Called from the recognition API. It only fires when at least
    check_interval_seconds have passed since the previous tick, so the
    expensive counting does not run on every single frame.

    Returns True when a tick actually happened.
    """
    now = datetime.now()
    interval = max(1, session.check_interval_seconds or 10)

    if not force and session.last_check_at is not None:
        if (now - session.last_check_at).total_seconds() < interval:
            return False

    session.last_check_at = now
    session.total_checks = (session.total_checks or 0) + 1

    for record in session.records.all():
        record.total_checks = session.total_checks
        record.recompute_presence()

    db.session.commit()
    return True


# ----------------------------------------------------------------------
# Ending a session
# ----------------------------------------------------------------------
def finalize_session(session):
    """
    End the session:
      1. stop it,
      2. recompute every presence percentage,
      3. downgrade students below the presence threshold to REVIEW_REQUIRED,
      4. create ABSENT records for enrolled students who were never seen.
    """
    if session.total_checks == 0:
        session.total_checks = 1

    seen_student_ids = set()
    summary = {"present": 0, "late": 0, "review": 0, "absent": 0}

    for record in session.records.all():
        seen_student_ids.add(record.student_id)
        record.total_checks = max(record.total_checks, session.total_checks)
        record.recompute_presence()

        if record.manually_modified:
            pass  # a teacher correction always wins
        elif record.presence_percentage < session.presence_threshold:
            record.status = STATUS_REVIEW

        if record.status == STATUS_PRESENT:
            summary["present"] += 1
        elif record.status == STATUS_LATE:
            summary["late"] += 1
        elif record.status == STATUS_REVIEW:
            summary["review"] += 1
        else:
            summary["absent"] += 1

    # Everyone enrolled in the subject who was never recognised is absent.
    enrolled = session.subject.students
    for student in enrolled:
        if student.id in seen_student_ids:
            continue
        db.session.add(
            AttendanceRecord(
                student_id=student.id,
                subject_id=session.subject_id,
                attendance_session_id=session.id,
                session_date=session.session_date,
                status=STATUS_ABSENT,
                liveness_verified=False,
                presence_count=0,
                total_checks=session.total_checks,
                presence_percentage=0.0,
                remarks="Auto-marked absent when the session ended.",
            )
        )
        summary["absent"] += 1

    session.status = SESSION_ENDED
    session.ended_at = datetime.now()
    db.session.commit()

    summary["total"] = sum(
        summary[key] for key in ("present", "late", "review", "absent")
    )
    return summary


def active_session_for_teacher(teacher_id):
    """The teacher's currently running session, if any."""
    return (
        AttendanceSession.query.filter_by(teacher_id=teacher_id, status="ACTIVE")
        .order_by(AttendanceSession.started_at.desc())
        .first()
    )


def session_live_rows(session):
    """Rows for the live attendance table."""
    records = (
        session.records.join(Student)
        .order_by(AttendanceRecord.first_detection_time.asc())
        .all()
    )
    return [record.to_dict() for record in records]


def correct_record(record, new_status, remarks=None):
    """Teacher manually corrects an attendance row."""
    record.status = new_status
    record.manually_modified = True
    if remarks:
        record.remarks = remarks[:255]
    if new_status == STATUS_ABSENT:
        record.liveness_verified = False
    db.session.commit()
    return record
