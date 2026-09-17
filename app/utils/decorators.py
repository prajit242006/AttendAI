"""Role-based access control decorators.

teacher_required  -> only a logged-in TEACHER may open the view
student_required  -> only a logged-in STUDENT may open the view

A student who types a teacher URL by hand gets the friendly 403 page,
never a teacher screen.
"""

from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user


def teacher_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_teacher:
            abort(403)
        return view(*args, **kwargs)

    return wrapper


def student_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_student:
            abort(403)
        return view(*args, **kwargs)

    return wrapper


def role_required(*roles):
    """Generic version, e.g. @role_required('TEACHER', 'STUDENT')."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator
