"""
Analytics.

Every number and every chart in AttendAI is calculated here straight
from the database - nothing on the dashboard is hard-coded.
"""

from datetime import date, timedelta

from sqlalchemy import func

from app import db
from app.models.attendance import (
    STATUS_ABSENT,
    STATUS_LATE,
    STATUS_PRESENT,
    STATUS_REVIEW,
    AttendanceRecord,
    AttendanceSession,
)
from app.models.student import Student
from app.models.subject import Subject
from app.utils.helpers import percent

PRESENT_STATUSES = (STATUS_PRESENT, STATUS_LATE)


# ----------------------------------------------------------------------
# Counting helpers
# ----------------------------------------------------------------------
def _count_on(day, status):
    return (
        db.session.query(func.count(func.distinct(AttendanceRecord.student_id)))
        .filter(AttendanceRecord.session_date == day,
                AttendanceRecord.status == status)
        .scalar()
        or 0
    )


def today_counts(day=None):
    day = day or date.today()
    return {
        "date": day,
        "present": _count_on(day, STATUS_PRESENT),
        "late": _count_on(day, STATUS_LATE),
        "absent": _count_on(day, STATUS_ABSENT),
        "review": _count_on(day, STATUS_REVIEW),
    }


def overall_attendance_percentage():
    """(present + late) / all records, across the whole database."""
    total = db.session.query(func.count(AttendanceRecord.id)).scalar() or 0
    if not total:
        return 0.0
    present = (
        db.session.query(func.count(AttendanceRecord.id))
        .filter(AttendanceRecord.status.in_(PRESENT_STATUSES))
        .scalar()
        or 0
    )
    return percent(present, total)


def student_subject_percentages(student_id):
    """Subject-wise attendance for one student."""
    rows = (
        db.session.query(
            Subject.id,
            Subject.code,
            Subject.name,
            func.count(AttendanceRecord.id).label("total"),
            func.sum(
                db.case((AttendanceRecord.status.in_(PRESENT_STATUSES), 1), else_=0)
            ).label("attended"),
        )
        .join(AttendanceRecord, AttendanceRecord.subject_id == Subject.id)
        .filter(AttendanceRecord.student_id == student_id)
        .group_by(Subject.id, Subject.code, Subject.name)
        .order_by(Subject.code)
        .all()
    )

    result = []
    for subject_id, code, name, total, attended in rows:
        attended = int(attended or 0)
        total = int(total or 0)
        result.append(
            {
                "subject_id": subject_id,
                "code": code,
                "name": name,
                "total": total,
                "attended": attended,
                "percentage": percent(attended, total),
            }
        )
    return result


def student_status_counts(student_id):
    rows = (
        db.session.query(AttendanceRecord.status, func.count(AttendanceRecord.id))
        .filter(AttendanceRecord.student_id == student_id)
        .group_by(AttendanceRecord.status)
        .all()
    )
    counts = {STATUS_PRESENT: 0, STATUS_LATE: 0, STATUS_ABSENT: 0, STATUS_REVIEW: 0}
    for status, value in rows:
        counts[status] = int(value)
    counts["total"] = sum(counts.values())
    attended = counts[STATUS_PRESENT] + counts[STATUS_LATE]
    counts["percentage"] = percent(attended, counts["total"])
    return counts


def student_overall_percentage(student_id):
    return student_status_counts(student_id)["percentage"]


# ----------------------------------------------------------------------
# Low attendance
# ----------------------------------------------------------------------
def low_attendance_students(minimum=75.0, limit=None):
    """
    Students whose OVERALL attendance is below the required minimum.
    Only students who actually have records are considered.
    """
    rows = (
        db.session.query(
            Student,
            func.count(AttendanceRecord.id).label("total"),
            func.sum(
                db.case((AttendanceRecord.status.in_(PRESENT_STATUSES), 1), else_=0)
            ).label("attended"),
        )
        .join(AttendanceRecord, AttendanceRecord.student_id == Student.id)
        .group_by(Student.id)
        .all()
    )

    result = []
    for student, total, attended in rows:
        pct = percent(int(attended or 0), int(total or 0))
        if pct < minimum:
            result.append(
                {
                    "student": student,
                    "total": int(total or 0),
                    "attended": int(attended or 0),
                    "percentage": pct,
                }
            )
    result.sort(key=lambda item: item["percentage"])
    return result[:limit] if limit else result


def low_attendance_by_subject(minimum=75.0):
    """Subject-wise shortage rows (student + subject + percentage)."""
    rows = (
        db.session.query(
            Student,
            Subject,
            func.count(AttendanceRecord.id).label("total"),
            func.sum(
                db.case((AttendanceRecord.status.in_(PRESENT_STATUSES), 1), else_=0)
            ).label("attended"),
        )
        .join(AttendanceRecord, AttendanceRecord.student_id == Student.id)
        .join(Subject, Subject.id == AttendanceRecord.subject_id)
        .group_by(Student.id, Subject.id)
        .all()
    )

    result = []
    for student, subject, total, attended in rows:
        pct = percent(int(attended or 0), int(total or 0))
        if pct < minimum:
            result.append(
                {
                    "student": student,
                    "subject": subject,
                    "total": int(total or 0),
                    "attended": int(attended or 0),
                    "percentage": pct,
                }
            )
    result.sort(key=lambda item: item["percentage"])
    return result


def top_attendance_students(limit=5):
    rows = (
        db.session.query(
            Student,
            func.count(AttendanceRecord.id).label("total"),
            func.sum(
                db.case((AttendanceRecord.status.in_(PRESENT_STATUSES), 1), else_=0)
            ).label("attended"),
        )
        .join(AttendanceRecord, AttendanceRecord.student_id == Student.id)
        .group_by(Student.id)
        .all()
    )
    result = [
        {
            "student": student,
            "percentage": percent(int(attended or 0), int(total or 0)),
            "total": int(total or 0),
        }
        for student, total, attended in rows
    ]
    result.sort(key=lambda item: item["percentage"], reverse=True)
    return result[:limit]


# ----------------------------------------------------------------------
# Chart data
# ----------------------------------------------------------------------
def daily_trend(days=7):
    """Present / late / absent counts for the last N days (Chart.js)."""
    today = date.today()
    labels, present, late, absent = [], [], [], []

    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        labels.append(day.strftime("%d %b"))
        present.append(_count_on(day, STATUS_PRESENT))
        late.append(_count_on(day, STATUS_LATE))
        absent.append(_count_on(day, STATUS_ABSENT))

    return {"labels": labels, "present": present, "late": late, "absent": absent}


def subject_wise_attendance():
    """Attendance percentage per subject (Chart.js)."""
    rows = (
        db.session.query(
            Subject.code,
            Subject.name,
            func.count(AttendanceRecord.id).label("total"),
            func.sum(
                db.case((AttendanceRecord.status.in_(PRESENT_STATUSES), 1), else_=0)
            ).label("attended"),
        )
        .outerjoin(AttendanceRecord, AttendanceRecord.subject_id == Subject.id)
        .group_by(Subject.id, Subject.code, Subject.name)
        .order_by(Subject.code)
        .all()
    )

    labels, values, details = [], [], []
    for code, name, total, attended in rows:
        pct = percent(int(attended or 0), int(total or 0))
        labels.append(code)
        values.append(pct)
        details.append(
            {
                "code": code,
                "name": name,
                "total": int(total or 0),
                "attended": int(attended or 0),
                "percentage": pct,
            }
        )
    return {"labels": labels, "values": values, "details": details}


def status_distribution():
    rows = (
        db.session.query(AttendanceRecord.status, func.count(AttendanceRecord.id))
        .group_by(AttendanceRecord.status)
        .all()
    )
    mapping = {STATUS_PRESENT: 0, STATUS_LATE: 0, STATUS_ABSENT: 0, STATUS_REVIEW: 0}
    for status, value in rows:
        mapping[status] = int(value)
    return {"labels": list(mapping.keys()), "values": list(mapping.values())}


# ----------------------------------------------------------------------
# Dashboard bundle
# ----------------------------------------------------------------------
def teacher_dashboard_data(minimum=75.0):
    counts = today_counts()
    recent_sessions = (
        AttendanceSession.query.order_by(AttendanceSession.started_at.desc())
        .limit(5)
        .all()
    )
    low = low_attendance_students(minimum)

    return {
        "total_students": db.session.query(func.count(Student.id)).scalar() or 0,
        "total_subjects": db.session.query(func.count(Subject.id)).scalar() or 0,
        "faces_registered": (
            db.session.query(func.count(Student.id))
            .filter(Student.face_registered.is_(True))
            .scalar()
            or 0
        ),
        "present_today": counts["present"],
        "absent_today": counts["absent"],
        "late_today": counts["late"],
        "review_today": counts["review"],
        "below_minimum": len(low),
        "low_students": low[:5],
        "overall_percentage": overall_attendance_percentage(),
        "recent_sessions": recent_sessions,
        "trend": daily_trend(7),
        "subject_wise": subject_wise_attendance(),
        "status_distribution": status_distribution(),
    }
