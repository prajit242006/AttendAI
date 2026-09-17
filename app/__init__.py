"""
AttendAI application factory.

create_app() builds the Flask application, wires the extensions,
registers the blueprints and makes sure the folders / default teacher
account exist.
"""

import logging
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, CSRFError

from config import get_config

# ----------------------------------------------------------------------
# Extensions (created here, initialised inside create_app)
# ----------------------------------------------------------------------
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "warning"


def create_app(config_name=None):
    """Build and return a fully configured Flask application."""
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    _ensure_folders(app)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    _register_login_loader()
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_template_helpers(app)

    logging.basicConfig(level=logging.INFO)
    return app


def _ensure_folders(app):
    """face_data/ and models_data/ must exist before anything else runs."""
    for key in ("FACE_DATA_DIR", "MODELS_DIR"):
        Path(app.config[key]).mkdir(parents=True, exist_ok=True)


def _register_login_loader():
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))


def _register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.teacher import teacher_bp
    from app.routes.student import student_bp
    from app.routes.attendance import attendance_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(api_bp, url_prefix="/api")


def _wants_json():
    """True when the browser asked for JSON (our fetch() calls do)."""
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def _register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(error):
        if _wants_json():
            return jsonify(success=False, message="You are not allowed to do that."), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        if _wants_json():
            return jsonify(success=False, message="Not found."), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled server error")
        if _wants_json():
            return jsonify(success=False, message="Something went wrong on the server."), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        if _wants_json():
            return jsonify(success=False, message="Your session expired. Reload the page."), 400
        return render_template("errors/403.html", reason="Your session expired. Reload the page."), 400


def _register_template_helpers(app):
    """Small helpers every template can use."""
    from datetime import datetime

    @app.context_processor
    def inject_globals():
        return {
            "APP_NAME": "AttendAI",
            "APP_TAGLINE": "Smart. Secure. Automated Attendance.",
            "MIN_ATTENDANCE_PERCENT": app.config["MIN_ATTENDANCE_PERCENT"],
            "now": datetime.now(),
        }
