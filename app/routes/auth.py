"""Login / logout and the default-teacher bootstrap."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.models.student import Student
from app.models.user import ROLE_TEACHER, Teacher, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    """Send everybody to the right place."""
    if current_user.is_authenticated:
        return redirect(url_for("teacher.dashboard") if current_user.is_teacher
                        else url_for("student.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))

    if request.method == "POST":
        identifier = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not identifier or not password:
            flash("Enter your username and password.", "danger")
            return render_template("login.html", username=identifier), 400

        user = _find_user(identifier)
        if user is None or not user.check_password(password):
            flash("Wrong username or password. Try again.", "danger")
            return render_template("login.html", username=identifier), 401

        if not user.is_active:
            flash("This account has been disabled. Ask your teacher for help.", "warning")
            return render_template("login.html", username=identifier), 403

        login_user(user)
        flash("Welcome back, {}.".format(user.display_name), "success")
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("auth.index"))

    return render_template("login.html", username="")


def _find_user(identifier):
    """Students may sign in with their username OR their register number."""
    user = User.query.filter(db.func.lower(User.username) == identifier.lower()).first()
    if user:
        return user
    student = Student.query.filter(
        db.func.upper(Student.register_number) == identifier.upper()
    ).first()
    return student.user if student else None


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


# ----------------------------------------------------------------------
def ensure_default_teacher(app):
    """Create the admin / Admin@123 teacher the first time the app runs."""
    username = app.config["DEFAULT_TEACHER_USERNAME"]
    if User.query.filter_by(username=username).first():
        return False

    user = User(username=username, role=ROLE_TEACHER)
    user.set_password(app.config["DEFAULT_TEACHER_PASSWORD"])
    db.session.add(user)
    db.session.flush()

    db.session.add(
        Teacher(
            user_id=user.id,
            name=app.config["DEFAULT_TEACHER_NAME"],
            email=app.config["DEFAULT_TEACHER_EMAIL"],
            department="Computer Science",
        )
    )
    db.session.commit()
    return True
