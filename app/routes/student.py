"""
Student pages.

A student can only ever see their own data: every query below is built
from current_user.student.id, never from a URL parameter, so changing
the address bar cannot reveal somebody else's attendance.
"""

from flask import Blueprint, current_app, render_template, request
from flask_login import current_user, login_required

from app.models.attendance import ALL_STATUSES, AttendanceRecord
from app.models.subject import Subject
from app.services import analytics_service
from app.utils.decorators import student_required
from app.utils.helpers import ValidationError, clean, parse_date

student_bp = Blueprint("student", __name__)


@student_bp.before_request
@login_required
@student_required
def restrict_to_students():
    return None


def _me():
    return current_user.student


@student_bp.route("/dashboard")
def dashboard():
    student = _me()
    minimum = current_app.config["MIN_ATTENDANCE_PERCENT"]
    subjects = analytics_service.student_subject_percentages(student.id)

    return render_template(
        "student/dashboard.html",
        student=student,
        counts=analytics_service.student_status_counts(student.id),
        subjects=subjects,
        shortage=[row for row in subjects if row["percentage"] < minimum],
        minimum=minimum,
        recent=(
            AttendanceRecord.query.filter_by(student_id=student.id)
            .order_by(AttendanceRecord.session_date.desc(), AttendanceRecord.id.desc())
            .limit(8)
            .all()
        ),
    )


@student_bp.route("/attendance")
def attendance():
    student = _me()
    query = AttendanceRecord.query.filter_by(student_id=student.id)

    filters = {
        "subject_id": request.args.get("subject_id", type=int),
        "status": clean(request.args.get("status")),
        "date": clean(request.args.get("date")),
    }

    if filters["subject_id"]:
        query = query.filter(AttendanceRecord.subject_id == filters["subject_id"])
    if filters["status"]:
        query = query.filter(AttendanceRecord.status == filters["status"])
    if filters["date"]:
        try:
            query = query.filter(AttendanceRecord.session_date == parse_date(filters["date"]))
        except ValidationError:
            filters["date"] = ""

    records = query.order_by(
        AttendanceRecord.session_date.desc(), AttendanceRecord.id.desc()
    ).all()

    return render_template(
        "student/attendance.html",
        student=student,
        records=records,
        filters=filters,
        subjects=student.subjects or Subject.query.order_by(Subject.code).all(),
        statuses=ALL_STATUSES,
        summary=analytics_service.student_subject_percentages(student.id),
        minimum=current_app.config["MIN_ATTENDANCE_PERCENT"],
    )


@student_bp.route("/profile")
def profile():
    student = _me()
    return render_template(
        "student/profile.html",
        student=student,
        counts=analytics_service.student_status_counts(student.id),
        minimum=current_app.config["MIN_ATTENDANCE_PERCENT"],
    )
