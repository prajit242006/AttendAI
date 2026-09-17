"""
Teacher pages: dashboard, student management, subject management,
face registration, analytics, reports and the low-attendance list.
"""

from datetime import date

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.attendance import ALL_STATUSES, AttendanceRecord, AttendanceSession
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import ROLE_STUDENT, User
from app.services import analytics_service, report_service
from app.services.attendance_service import correct_record
from app.utils.decorators import teacher_required
from app.utils.helpers import (
    ValidationError,
    clean,
    parse_date,
    validate_email,
    validate_int,
    validate_name,
    validate_password,
    validate_register_number,
    validate_subject_code,
    validate_subject_name,
    validate_username,
)
from app.vision.face_trainer import (
    TrainingError,
    count_samples,
    delete_face_samples,
    model_info,
    train_model,
)
from app.vision.face_recognizer import reset_recognizer

teacher_bp = Blueprint("teacher", __name__)


@teacher_bp.before_request
@login_required
@teacher_required
def restrict_to_teachers():
    """Every route in this blueprint is teacher-only."""
    return None


# ======================================================================
# Dashboard
# ======================================================================
@teacher_bp.route("/dashboard")
def dashboard():
    data = analytics_service.teacher_dashboard_data(
        current_app.config["MIN_ATTENDANCE_PERCENT"]
    )
    data["model"] = model_info(
        current_app.config["LBPH_MODEL_PATH"], current_app.config["LABELS_PATH"]
    )
    return render_template("teacher/dashboard.html", data=data)


# ======================================================================
# Students
# ======================================================================
@teacher_bp.route("/students")
def students():
    query = Student.query
    search = clean(request.args.get("q"))
    department = clean(request.args.get("department"))

    if search:
        like = "%{}%".format(search)
        query = query.filter(
            or_(
                Student.name.ilike(like),
                Student.register_number.ilike(like),
                Student.email.ilike(like),
            )
        )
    if department:
        query = query.filter(Student.department == department)

    student_list = query.order_by(Student.register_number).all()
    departments = [row[0] for row in db.session.query(Student.department).distinct().all()]

    return render_template(
        "teacher/students.html",
        students=student_list,
        search=search,
        department=department,
        departments=sorted(d for d in departments if d),
    )


@teacher_bp.route("/students/new", methods=["GET", "POST"])
def student_new():
    if request.method == "POST":
        try:
            _create_student(request.form)
            flash("Student added.", "success")
            return redirect(url_for("teacher.students"))
        except ValidationError as error:
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("The student could not be saved. Check the database connection.", "danger")

    return render_template(
        "teacher/student_form.html", student=None, form=request.form, subjects=Subject.query.all()
    )


@teacher_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def student_edit(student_id):
    student = Student.query.get_or_404(student_id)

    if request.method == "POST":
        try:
            _update_student(student, request.form)
            flash("Student updated.", "success")
            return redirect(url_for("teacher.students"))
        except ValidationError as error:
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("The student could not be updated.", "danger")

    return render_template(
        "teacher/student_form.html",
        student=student,
        form=request.form,
        subjects=Subject.query.order_by(Subject.code).all(),
    )


@teacher_bp.route("/students/<int:student_id>/delete", methods=["POST"])
def student_delete(student_id):
    student = Student.query.get_or_404(student_id)
    register_number = student.register_number
    user = student.user
    try:
        delete_face_samples(current_app.config["FACE_DATA_DIR"], register_number)
        db.session.delete(student)
        if user:
            db.session.delete(user)
        db.session.commit()
        flash("Student {} removed.".format(register_number), "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("The student could not be removed.", "danger")
    return redirect(url_for("teacher.students"))


def _student_fields(form):
    """Validate the shared student fields and return them as a dict."""
    return {
        "name": validate_name(form.get("name"), "Student name"),
        "register_number": validate_register_number(form.get("register_number")),
        "department": validate_name(form.get("department"), "Department"),
        "year": validate_int(form.get("year"), "Year", 1, 5),
        "section": clean(form.get("section"))[:10] or None,
        "email": validate_email(form.get("email")),
    }


def _assign_subjects(student, form):
    ids = [int(value) for value in form.getlist("subjects") if str(value).isdigit()]
    student.subjects = Subject.query.filter(Subject.id.in_(ids)).all() if ids else []


def _create_student(form):
    fields = _student_fields(form)
    username = validate_username(form.get("username") or fields["register_number"])
    password = validate_password(form.get("password"))

    if Student.query.filter_by(register_number=fields["register_number"]).first():
        raise ValidationError(
            "Register number {} already exists.".format(fields["register_number"])
        )
    if User.query.filter_by(username=username).first():
        raise ValidationError("Username {} is already taken.".format(username))
    if fields["email"] and Student.query.filter_by(email=fields["email"]).first():
        raise ValidationError("That email is already used by another student.")

    user = User(username=username, role=ROLE_STUDENT)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    student = Student(user_id=user.id, **fields)
    db.session.add(student)
    db.session.flush()
    _assign_subjects(student, form)
    db.session.commit()
    return student


def _update_student(student, form):
    fields = _student_fields(form)

    clash = Student.query.filter(
        Student.register_number == fields["register_number"], Student.id != student.id
    ).first()
    if clash:
        raise ValidationError("Another student already uses that register number.")

    username = validate_username(form.get("username") or student.username)
    user_clash = User.query.filter(
        User.username == username, User.id != student.user_id
    ).first()
    if user_clash:
        raise ValidationError("Username {} is already taken.".format(username))

    for key, value in fields.items():
        setattr(student, key, value)

    student.user.username = username
    new_password = form.get("password")
    if clean(new_password):
        student.user.set_password(validate_password(new_password))

    _assign_subjects(student, form)
    db.session.commit()
    return student


# ======================================================================
# Subjects
# ======================================================================
@teacher_bp.route("/subjects")
def subjects():
    return render_template(
        "teacher/subjects.html", subjects=Subject.query.order_by(Subject.code).all()
    )


@teacher_bp.route("/subjects/new", methods=["GET", "POST"])
def subject_new():
    if request.method == "POST":
        try:
            fields = _subject_fields(request.form)
            if Subject.query.filter_by(code=fields["code"]).first():
                raise ValidationError("Subject code {} already exists.".format(fields["code"]))
            subject = Subject(**fields)
            db.session.add(subject)
            db.session.flush()
            _assign_students(subject, request.form)
            db.session.commit()
            flash("Subject added.", "success")
            return redirect(url_for("teacher.subjects"))
        except ValidationError as error:
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("The subject could not be saved.", "danger")

    return render_template(
        "teacher/subject_form.html",
        subject=None,
        form=request.form,
        students=Student.query.order_by(Student.register_number).all(),
    )


@teacher_bp.route("/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
def subject_edit(subject_id):
    subject = Subject.query.get_or_404(subject_id)

    if request.method == "POST":
        try:
            fields = _subject_fields(request.form)
            clash = Subject.query.filter(
                Subject.code == fields["code"], Subject.id != subject.id
            ).first()
            if clash:
                raise ValidationError("Another subject already uses that code.")
            for key, value in fields.items():
                setattr(subject, key, value)
            _assign_students(subject, request.form)
            db.session.commit()
            flash("Subject updated.", "success")
            return redirect(url_for("teacher.subjects"))
        except ValidationError as error:
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("The subject could not be updated.", "danger")

    return render_template(
        "teacher/subject_form.html",
        subject=subject,
        form=request.form,
        students=Student.query.order_by(Student.register_number).all(),
    )


@teacher_bp.route("/subjects/<int:subject_id>/delete", methods=["POST"])
def subject_delete(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    try:
        db.session.delete(subject)
        db.session.commit()
        flash("Subject {} removed.".format(subject.code), "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("The subject could not be removed.", "danger")
    return redirect(url_for("teacher.subjects"))


def _subject_fields(form):
    return {
        "code": validate_subject_code(form.get("code")),
        "name": validate_subject_name(form.get("name")),
        "department": validate_name(form.get("department"), "Department"),
        "year": validate_int(form.get("year"), "Year", 1, 5),
        "semester": validate_int(form.get("semester"), "Semester", 1, 10),
    }


def _assign_students(subject, form):
    ids = [int(value) for value in form.getlist("students") if str(value).isdigit()]
    subject.students = Student.query.filter(Student.id.in_(ids)).all() if ids else []


# ======================================================================
# Face registration + model training
# ======================================================================
@teacher_bp.route("/face-registration")
def face_registration():
    selected_id = request.args.get("student_id", type=int)
    students_list = Student.query.order_by(Student.register_number).all()
    selected = Student.query.get(selected_id) if selected_id else None

    sample_counts = {
        student.id: count_samples(
            current_app.config["FACE_DATA_DIR"], student.register_number
        )
        for student in students_list
    }

    return render_template(
        "teacher/face_registration.html",
        students=students_list,
        selected=selected,
        sample_counts=sample_counts,
        target_samples=current_app.config["FACE_SAMPLES_TARGET"],
        min_samples=current_app.config["MIN_FACE_SAMPLES"],
        model=model_info(
            current_app.config["LBPH_MODEL_PATH"], current_app.config["LABELS_PATH"]
        ),
    )


@teacher_bp.route("/train-model", methods=["POST"])
def train_face_model():
    """The TRAIN / UPDATE FACE MODEL button."""
    try:
        payload = train_model(
            current_app.config["FACE_DATA_DIR"],
            current_app.config["LBPH_MODEL_PATH"],
            current_app.config["LABELS_PATH"],
        )
        reset_recognizer()
        _sync_face_labels(payload.get("labels", {}))
        flash(
            "Face model trained on {} students and {} samples.".format(
                payload["students"], payload["samples"]
            ),
            "success",
        )
    except TrainingError as error:
        flash(str(error), "danger")
    return redirect(url_for("teacher.face_registration"))


def _sync_face_labels(label_map):
    """Copy the numeric LBPH labels back into the face_profiles table."""
    for label, register_number in label_map.items():
        student = Student.query.filter_by(register_number=register_number).first()
        if student is None or student.face_profile is None:
            continue
        student.face_profile.label = int(label)
        student.face_profile.trained = True
    db.session.commit()


# ======================================================================
# Attendance history
# ======================================================================
@teacher_bp.route("/attendance-history")
def attendance_history():
    query = AttendanceRecord.query.join(Student).join(Subject)

    filters = {
        "date": clean(request.args.get("date")),
        "student_id": request.args.get("student_id", type=int),
        "subject_id": request.args.get("subject_id", type=int),
        "department": clean(request.args.get("department")),
        "status": clean(request.args.get("status")),
    }

    if filters["date"]:
        try:
            query = query.filter(AttendanceRecord.session_date == parse_date(filters["date"]))
        except ValidationError as error:
            flash(str(error), "warning")
    if filters["student_id"]:
        query = query.filter(AttendanceRecord.student_id == filters["student_id"])
    if filters["subject_id"]:
        query = query.filter(AttendanceRecord.subject_id == filters["subject_id"])
    if filters["department"]:
        query = query.filter(Student.department == filters["department"])
    if filters["status"]:
        query = query.filter(AttendanceRecord.status == filters["status"])

    records = query.order_by(
        AttendanceRecord.session_date.desc(), Student.register_number
    ).limit(500).all()

    departments = [row[0] for row in db.session.query(Student.department).distinct().all()]

    return render_template(
        "teacher/attendance_history.html",
        records=records,
        filters=filters,
        students=Student.query.order_by(Student.register_number).all(),
        subjects=Subject.query.order_by(Subject.code).all(),
        departments=sorted(d for d in departments if d),
        statuses=ALL_STATUSES,
    )


@teacher_bp.route("/attendance/<int:record_id>/correct", methods=["POST"])
def attendance_correct(record_id):
    record = AttendanceRecord.query.get_or_404(record_id)
    new_status = clean(request.form.get("status")).upper()
    if new_status not in ALL_STATUSES:
        flash("Choose a valid attendance status.", "danger")
    else:
        correct_record(record, new_status, clean(request.form.get("remarks")))
        flash(
            "{} marked as {} (manual correction).".format(
                record.student.register_number, new_status
            ),
            "success",
        )
    return redirect(request.referrer or url_for("teacher.attendance_history"))


# ======================================================================
# Analytics / low attendance / reports
# ======================================================================
@teacher_bp.route("/analytics")
def analytics():
    minimum = current_app.config["MIN_ATTENDANCE_PERCENT"]
    counts = analytics_service.today_counts()
    return render_template(
        "teacher/analytics.html",
        overall=analytics_service.overall_attendance_percentage(),
        counts=counts,
        trend=analytics_service.daily_trend(7),
        subject_wise=analytics_service.subject_wise_attendance(),
        status_distribution=analytics_service.status_distribution(),
        low_students=analytics_service.low_attendance_students(minimum),
        top_students=analytics_service.top_attendance_students(5),
        minimum=minimum,
    )


@teacher_bp.route("/low-attendance")
def low_attendance():
    minimum = request.args.get(
        "minimum", type=float, default=current_app.config["MIN_ATTENDANCE_PERCENT"]
    )
    return render_template(
        "teacher/low_attendance.html",
        minimum=minimum,
        overall_rows=analytics_service.low_attendance_students(minimum),
        subject_rows=analytics_service.low_attendance_by_subject(minimum),
    )


@teacher_bp.route("/reports")
def reports():
    return render_template(
        "teacher/reports.html",
        subjects=Subject.query.order_by(Subject.code).all(),
        students=Student.query.order_by(Student.register_number).all(),
        today=date.today().strftime("%Y-%m-%d"),
        minimum=current_app.config["MIN_ATTENDANCE_PERCENT"],
    )


@teacher_bp.route("/reports/download/<report_type>")
def report_download(report_type):
    """CSV download for the four report types."""
    try:
        if report_type == "daily":
            report_date = parse_date(request.args.get("date"), default=date.today())
            filename, text = report_service.daily_report(report_date)
        elif report_type == "subject":
            subject_id = request.args.get("subject_id", type=int)
            filename, text = report_service.subject_report(subject_id)
        elif report_type == "student":
            student_id = request.args.get("student_id", type=int)
            filename, text = report_service.student_report(student_id)
        elif report_type == "shortage":
            minimum = request.args.get(
                "minimum", type=float, default=current_app.config["MIN_ATTENDANCE_PERCENT"]
            )
            filename, text = report_service.shortage_report(minimum)
        else:
            flash("Unknown report type.", "danger")
            return redirect(url_for("teacher.reports"))
    except ValidationError as error:
        flash(str(error), "danger")
        return redirect(url_for("teacher.reports"))

    if text is None:
        flash("Choose a valid subject or student before downloading.", "warning")
        return redirect(url_for("teacher.reports"))

    return Response(
        text,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename={}".format(filename)},
    )
