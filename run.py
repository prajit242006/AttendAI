"""
AttendAI - application entry point.

    python run.py

Creates the tables if they do not exist, makes sure the default teacher
account is present and starts the development server on
http://localhost:5000
"""

import sys

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app import create_app, db
from app.routes.auth import ensure_default_teacher

# Importing the models package registers every table with SQLAlchemy.
import app.models  # noqa: F401

application = create_app()


def initialise_database():
    """Create the tables and the default teacher on first run."""
    with application.app_context():
        try:
            db.create_all()
        except OperationalError as error:
            print("\n[AttendAI] Could not connect to the database.")
            print("  Check DATABASE_URL in your .env file and make sure MySQL is running.")
            print("  Details:", error.orig if hasattr(error, "orig") else error)
            sys.exit(1)
        except SQLAlchemyError as error:
            print("\n[AttendAI] Database error:", error)
            sys.exit(1)

        if ensure_default_teacher(application):
            print("[AttendAI] Default teacher created -> {} / {}".format(
                application.config["DEFAULT_TEACHER_USERNAME"],
                application.config["DEFAULT_TEACHER_PASSWORD"],
            ))


if __name__ == "__main__":
    initialise_database()
    print("[AttendAI] Smart. Secure. Automated Attendance.")
    print("[AttendAI] Running on http://localhost:5000")
    application.run(host="0.0.0.0", port=5000, debug=application.config.get("DEBUG", True))
