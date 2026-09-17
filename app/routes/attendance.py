"""
Attendance session pages.

  /attendance/start        - the teacher chooses subject, time and rules
  /attendance/live/<id>    - the webcam page that marks attendance
  /attendance/end/<id>     - finish the session and create ABSENT rows
"""

from datetime import date, datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.models.attendance import AttendanceSession
from app.models.subject import Subject
from app.services.attendance_service import (
    active_session_for_teacher,
    finalize_session,
    session_live_rows,
)
from app.utils.decorators import teacher_required
from app.utils.helpers import (
    ValidationError,
    parse_date,
    parse_time,
    validate_float,
    validate_int,
)
from app.vision.face_recognizer import get_recognizer
from app.vision.face_trainer import model_info
from app.vision.liveness import liveness_manager

attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.before_request
@login_required
@teacher_required
def restrict_to_teachers():
    return None


def _teacher_id():
    return current_user.teacher.id


# ----------------------------------------------------------------------
@attendance_bp.route("/start", methods=["GET", "POST"])
def start():
    config = current_app.config
    running = active_session_for_teacher(_teacher_id())

    if request.method == "POST":
        try:
            session = _create_session(request.form)
            flash("Attendance session started for {}.".format(session.subject.label), "success")
            return redirect(url_for("attendance.live", session_id=session.id))
        except ValidationError as error:
            flash(str(error), "danger")

    return render_template(
        "teacher/start_attendance.html",
        subjects=Subject.query.order_by(Subject.code).all(),
        today=date.today().strftime("%Y-%m-%d"),
        now_time=datetime.now().strftime("%H:%M"),
        defaults={
            "late": config["DEFAULT_LATE_THRESHOLD_MIN"],
            "presence": config["DEFAULT_PRESENCE_THRESHOLD"],
            "interval": config["DEFAULT_CHECK_INTERVAL_SEC"],
            "recognition": config["RECOGNITION_THRESHOLD"],
        },
        running=running,
        model=model_info(config["LBPH_MODEL_PATH"], config["LABELS_PATH"]),
        form=request.form,
    )


def _create_session(form):
    subject_id = form.get("subject_id", type=int)
    subject = Subject.query.get(subject_id) if subject_id else None
    if subject is None:
        raise ValidationError("Choose the subject for this class.")
    if not subject.students:
        raise ValidationError(
            "No students are assigned to {}. Assign students to the subject first.".format(
                subject.code
            )
        )

    session = AttendanceSession(
        subject_id=subject.id,
        teacher_id=_teacher_id(),
        session_date=parse_date(form.get("session_date"), "Date", default=date.today()),
        class_start_time=parse_time(form.get("class_start_time"), "Class start time"),
        late_threshold_minutes=validate_int(
            form.get("late_threshold"), "Late threshold", 0, 240,
            default=current_app.config["DEFAULT_LATE_THRESHOLD_MIN"],
        ),
        presence_threshold=validate_float(
            form.get("presence_threshold"), "Presence threshold", 0, 100,
            default=current_app.config["DEFAULT_PRESENCE_THRESHOLD"],
        ),
        recognition_threshold=validate_float(
            form.get("recognition_threshold"), "Recognition threshold", 10, 200,
            default=current_app.config["RECOGNITION_THRESHOLD"],
        ),
        check_interval_seconds=validate_int(
            form.get("check_interval"), "Presence check interval", 2, 300,
            default=current_app.config["DEFAULT_CHECK_INTERVAL_SEC"],
        ),
    )
    db.session.add(session)
    db.session.commit()
    return session


# ----------------------------------------------------------------------
@attendance_bp.route("/live/<int:session_id>")
def live(session_id):
    session = AttendanceSession.query.get_or_404(session_id)
    recognizer = get_recognizer(current_app.config)

    if not recognizer.is_ready:
        flash(
            "The face model is not trained yet. Register faces and press "
            "'Train face model' before starting attendance.",
            "warning",
        )

    return render_template(
        "teacher/live_attendance.html",
        session=session,
        rows=session_live_rows(session),
        enrolled=len(session.subject.students),
        model_ready=recognizer.is_ready,
        liveness_enabled=current_app.config["LIVENESS_ENABLED"],
    )


@attendance_bp.route("/end/<int:session_id>", methods=["POST"])
def end(session_id):
    session = AttendanceSession.query.get_or_404(session_id)

    if not session.is_active:
        flash("That session has already ended.", "info")
        return redirect(url_for("teacher.attendance_history"))

    summary = finalize_session(session)
    liveness_manager.clear_session(session.id)

    flash(
        "Session ended. Present {present}, late {late}, needs review {review}, "
        "absent {absent}.".format(**summary),
        "success",
    )
    return redirect(
        url_for("teacher.attendance_history", date=session.session_date.strftime("%Y-%m-%d"))
    )
