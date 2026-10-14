"""Production entry point for the existing AttendAI Flask application."""

import os
import time
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from werkzeug.middleware.proxy_fix import ProxyFix


def configure_environment():
    secret = os.environ.get("SECRET_KEY", "")
    if len(secret) < 32 or secret == "attendai-dev-secret-change-me":
        raise RuntimeError("Set SECRET_KEY to a random value of at least 32 characters.")

    password = os.environ.get("DEFAULT_TEACHER_PASSWORD", "")
    if len(password) < 12 or password == "Admin@123":
        raise RuntimeError("Set DEFAULT_TEACHER_PASSWORD to a new password of at least 12 characters.")

    raw_url = os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL")
    if not raw_url:
        raise RuntimeError("Set MYSQL_URL to the Railway MySQL service reference.")
    try:
        database_url = make_url(raw_url)
    except Exception:
        raise RuntimeError("The database connection URL is invalid.") from None
    if database_url.get_backend_name() != "mysql":
        raise RuntimeError("This deployment expects a MySQL database.")
    database_url = database_url.set(drivername="mysql+pymysql")
    os.environ["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    os.environ["FLASK_ENV"] = "production"

    data_root = Path(os.environ.get("ATTENDAI_DATA_DIR", "/data"))
    os.environ.setdefault("FACE_DATA_DIR", str(data_root / "face_data"))
    os.environ.setdefault("MODELS_DIR", str(data_root / "models_data"))


configure_environment()

# Environment must be configured before importing AttendAI's config module.
from app import create_app, db  # noqa: E402
from app.routes.auth import ensure_default_teacher  # noqa: E402
import app.models  # noqa: E402,F401

application = create_app("production")
# Railway terminates HTTPS and supplies X-Forwarded-Proto.
application.wsgi_app = ProxyFix(application.wsgi_app, x_for=0, x_proto=1)

with application.app_context():
    for attempt in range(10):
        try:
            db.create_all()
            ensure_default_teacher(application)
            break
        except OperationalError:
            db.session.rollback()
            if attempt == 9:
                raise RuntimeError("Could not connect to MySQL. Check the service and MYSQL_URL.") from None
            application.logger.warning("Waiting for the MySQL service to become ready.")
            time.sleep(3)


@application.get("/healthz")
def healthz():
    return {"status": "ok"}
