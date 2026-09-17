"""
CSV report generation.

Four reports are offered on the Reports page:
  * daily     - every record for one date
  * subject   - every record for one subject
  * student   - every record for one student
  * shortage  - students below the required attendance percentage

Each function returns (filename, csv_text) so the route can hand it
straight to the browser as a download.
"""

import csv
import io
from datetime import date

from app.models.attendance import AttendanceRecord
from app.models.student import Student
from app.models.subject import Subject
from app.services.analytics_service import low_attendance_students

RECORD_HEADERS = [
    "Register Number",
    "Student Name",
    "Department",
    "Year",
    "Section",
    "Subject Code",
    "Subject Name",
    "Date",
    "First Detection",
    "Last Detection",
    "Presence %",
    "Liveness",
    "Status",
    "Manually Modified",
]


def _writer():
    buffer = io.StringIO()
    return buffer, csv.writer(buffer)


def _record_row(record):
    student = record.student
    subject = record.subject
    return [
        student.register_number if student else "",
        student.name if student else "",
        student.department if student else "",
        student.year if student else "",
        student.section if student else "",
        subject.code if subject else "",
        subject.name if subject else "",
        record.session_date.strftime("%Y-%m-%d") if record.session_date else "",
        record.first_detection_time.strftime("%H:%M:%S") if record.first_detection_time else "",
        record.last_detection_time.strftime("%H:%M:%S") if record.last_detection_time else "",
        record.presence_percentage,
        "YES" if record.liveness_verified else "NO",
        record.status,
        "YES" if record.manually_modified else "NO",
    ]


def _records_csv(records, title_rows=None):
    buffer, writer = _writer()
    for row in title_rows or []:
        writer.writerow(row)
    writer.writerow(RECORD_HEADERS)
    for record in records:
        writer.writerow(_record_row(record))
    return buffer.getvalue()


# ----------------------------------------------------------------------
def daily_report(report_date=None):
    report_date = report_date or date.today()
    records = (
        AttendanceRecord.query.filter_by(session_date=report_date)
        .join(Student)
        .order_by(Student.register_number)
        .all()
    )
    text = _records_csv(
        records,
        [["AttendAI - Daily Attendance Report"],
         ["Date", report_date.strftime("%Y-%m-%d")],
         []],
    )
    return "attendai_daily_{}.csv".format(report_date.strftime("%Y%m%d")), text


def subject_report(subject_id):
    subject = Subject.query.get(subject_id)
    if subject is None:
        return None, None
    records = (
        AttendanceRecord.query.filter_by(subject_id=subject_id)
        .join(Student)
        .order_by(AttendanceRecord.session_date.desc(), Student.register_number)
        .all()
    )
    text = _records_csv(
        records,
        [["AttendAI - Subject Attendance Report"],
         ["Subject", subject.label],
         []],
    )
    return "attendai_subject_{}.csv".format(subject.code), text


def student_report(student_id):
    student = Student.query.get(student_id)
    if student is None:
        return None, None
    records = (
        AttendanceRecord.query.filter_by(student_id=student_id)
        .order_by(AttendanceRecord.session_date.desc())
        .all()
    )
    text = _records_csv(
        records,
        [["AttendAI - Student Attendance Report"],
         ["Student", "{} ({})".format(student.name, student.register_number)],
         []],
    )
    return "attendai_student_{}.csv".format(student.register_number), text


def shortage_report(minimum=75.0):
    buffer, writer = _writer()
    writer.writerow(["AttendAI - Attendance Shortage Report"])
    writer.writerow(["Required percentage", minimum])
    writer.writerow([])
    writer.writerow(
        ["Register Number", "Student Name", "Department", "Year", "Section",
         "Classes Held", "Classes Attended", "Attendance %", "Remark"]
    )
    for row in low_attendance_students(minimum):
        student = row["student"]
        writer.writerow(
            [
                student.register_number,
                student.name,
                student.department,
                student.year,
                student.section,
                row["total"],
                row["attended"],
                row["percentage"],
                "ATTENDANCE SHORTAGE",
            ]
        )
    return "attendai_below_{}.csv".format(int(minimum)), buffer.getvalue()
