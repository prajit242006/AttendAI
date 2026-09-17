"""
JSON API used by the browser JavaScript.

Supports:
- Face registration
- LBPH model training
- Single/multi-face live attendance
- Continuous presence monitoring
- Liveness verification
- Analytics
"""

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models.attendance import AttendanceSession
from app.models.face_profile import FaceProfile
from app.models.student import Student
from app.services import analytics_service
from app.services.attendance_service import (
    get_record,
    mark_attendance,
    run_presence_tick,
    session_live_rows,
    update_presence,
)
from app.utils.decorators import teacher_required
from app.vision.face_detector import (
    FaceDetectionError,
    decode_base64_image,
    get_detector,
    to_gray,
)
from app.vision.face_recognizer import (
    RecognitionError,
    get_recognizer,
    reset_recognizer,
)
from app.vision.face_trainer import (
    TrainingError,
    count_samples,
    extract_faces_from_images,
    model_info,
    save_face_samples,
    train_model,
)
from app.vision.liveness import FAILED, PENDING, liveness_manager


api_bp = Blueprint("api", __name__)


# ======================================================================
# Helpers
# ======================================================================

def ok(**payload):
    payload.setdefault("success", True)
    return jsonify(payload)


def fail(message, status=400, **payload):
    payload.update(
        success=False,
        message=message,
    )
    return jsonify(payload), status


# ======================================================================
# Face registration
# ======================================================================

@api_bp.route("/face/preview", methods=["POST"])
@login_required
@teacher_required
def face_preview():
    """
    Quick face check while teacher captures
    registration samples.

    Registration intentionally allows only one
    student in the frame.
    """

    data = request.get_json(silent=True) or {}

    try:
        image = decode_base64_image(
            data.get("image")
        )
    except FaceDetectionError as error:
        return fail(str(error))

    gray = to_gray(image)

    box, status = get_detector().detect_single(
        gray
    )

    messages = {
        "NO_FACE":
            "No face detected. Move into the centre of the frame.",

        "MULTIPLE_FACES":
            "More than one face in the frame. "
            "Only the student should be visible.",

        "OK":
            "Face detected.",
    }

    return ok(
        status=status,
        box=box,
        message=messages[status],
    )


@api_bp.route("/face/register", methods=["POST"])
@login_required
@teacher_required
def face_register():
    """
    Save captured face samples and retrain
    the LBPH model.
    """

    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id")
    frames = data.get("images") or []

    student = (
        Student.query.get(student_id)
        if student_id
        else None
    )

    if student is None:
        return fail(
            "Select a student before saving "
            "the face profile.",
            404,
        )

    minimum = current_app.config[
        "MIN_FACE_SAMPLES"
    ]

    if len(frames) < minimum:
        return fail(
            "Capture at least {} samples before "
            "saving.".format(minimum)
        )

    try:
        images = [
            decode_base64_image(frame)
            for frame in frames
        ]

    except FaceDetectionError as error:
        return fail(str(error))

    faces, skipped = extract_faces_from_images(
        images
    )

    if len(faces) < minimum:
        return fail(
            "Only {} of {} frames contained a "
            "single clear face. Improve the lighting "
            "and capture again.".format(
                len(faces),
                len(frames),
            ),
            data={
                "skipped": skipped
            },
        )

    samples_dir, stored = save_face_samples(
        current_app.config["FACE_DATA_DIR"],
        student.register_number,
        faces,
        reset=True,
    )

    profile = (
        student.face_profile
        or FaceProfile(
            student_id=student.id,
            samples_dir=str(samples_dir),
        )
    )

    profile.samples_dir = str(samples_dir)
    profile.sample_count = stored
    profile.trained = False
    profile.updated_at = datetime.now()

    db.session.add(profile)

    student.face_registered = True

    db.session.commit()

    # Retrain immediately.
    training = None
    warning = None

    try:

        training = train_model(
            current_app.config["FACE_DATA_DIR"],
            current_app.config["LBPH_MODEL_PATH"],
            current_app.config["LABELS_PATH"],
        )

        reset_recognizer()

        _sync_labels(
            training.get("labels", {})
        )

    except TrainingError as error:
        warning = str(error)

    return ok(
        message="FACE REGISTERED SUCCESSFULLY",
        stored=stored,
        skipped=skipped,
        student=student.to_dict(),
        training=training,
        warning=warning,
    )


# ======================================================================
# Face model training
# ======================================================================

@api_bp.route("/face/train", methods=["POST"])
@login_required
@teacher_required
def face_train():

    try:

        payload = train_model(
            current_app.config["FACE_DATA_DIR"],
            current_app.config["LBPH_MODEL_PATH"],
            current_app.config["LABELS_PATH"],
        )

    except TrainingError as error:
        return fail(str(error))

    reset_recognizer()

    _sync_labels(
        payload.get("labels", {})
    )

    return ok(
        message="Face model updated.",
        training=payload,
    )


@api_bp.route("/face/status")
@login_required
@teacher_required
def face_status():

    student_id = request.args.get(
        "student_id",
        type=int,
    )

    student = (
        Student.query.get(student_id)
        if student_id
        else None
    )

    samples = (
        count_samples(
            current_app.config[
                "FACE_DATA_DIR"
            ],
            student.register_number,
        )
        if student
        else 0
    )

    return ok(
        samples=samples,
        model=model_info(
            current_app.config[
                "LBPH_MODEL_PATH"
            ],
            current_app.config[
                "LABELS_PATH"
            ],
        ),
    )


def _sync_labels(label_map):

    for label, register_number in (
        label_map.items()
    ):

        student = Student.query.filter_by(
            register_number=register_number
        ).first()

        if (
            student
            and student.face_profile
        ):
            student.face_profile.label = int(
                label
            )

            student.face_profile.trained = True

    db.session.commit()


# ======================================================================
# MULTI-STUDENT LIVE ATTENDANCE
# ======================================================================

@api_bp.route(
    "/attendance/recognize",
    methods=["POST"],
)
@login_required
@teacher_required
def attendance_recognize():
    """
    Process one webcam frame.

    MULTI-FACE FLOW:

        Frame
          ↓
        Detect all faces
          ↓
        Recognise each face separately
          ↓
        Check subject enrollment
          ↓
        Run per-student liveness
          ↓
        Mark/update each student's attendance

    Intended for approximately 2-5 students
    in the same camera frame.
    """

    data = request.get_json(
        silent=True
    ) or {}

    session_id = data.get(
        "session_id"
    )

    session = (
        AttendanceSession.query.get(
            session_id
        )
        if session_id
        else None
    )

    # --------------------------------------------------------------
    # Validate session
    # --------------------------------------------------------------

    if session is None:
        return fail(
            "Attendance session not found.",
            404,
            state="INVALID_SESSION",
        )

    if not session.is_active:
        return fail(
            "This attendance session has "
            "already ended.",
            409,
            state="SESSION_ENDED",
        )

    # --------------------------------------------------------------
    # Decode browser webcam frame
    # --------------------------------------------------------------

    try:

        image = decode_base64_image(
            data.get("image")
        )

    except FaceDetectionError as error:

        return fail(
            str(error),
            state="BAD_FRAME",
        )

    # --------------------------------------------------------------
    # MULTI-FACE recognition
    # --------------------------------------------------------------

    recognizer = get_recognizer(
        current_app.config
    )

    try:

        result = recognizer.recognize_faces(
            image,
            threshold=session.recognition_threshold,
        )

    except RecognitionError as error:

        return fail(
            str(error),
            409,
            state="MODEL_NOT_TRAINED",
        )

    # Continuous presence counter.
    ticked = run_presence_tick(
        session
    )

    # --------------------------------------------------------------
    # No face
    # --------------------------------------------------------------

    if result["status"] == "NO_FACE":

        return ok(
            state="NO_FACE",
            message="No face detected",
            face_count=0,
            recognized_count=0,
            faces=[],
            ticked=ticked,
        )

    # --------------------------------------------------------------
    # Process every detected face
    # --------------------------------------------------------------

    processed_faces = []

    marked_count = 0
    presence_updated_count = 0
    unknown_count = 0
    not_enrolled_count = 0
    liveness_pending_count = 0
    liveness_failed_count = 0

    for face_result in result["faces"]:

        face_payload = {
            "box": face_result.get(
                "box"
            ),
            "status": face_result.get(
                "status"
            ),
            "recognized": face_result.get(
                "recognized",
                False,
            ),
            "register_number":
                face_result.get(
                    "register_number"
                ),
            "confidence":
                face_result.get(
                    "confidence"
                ),
            "distance":
                face_result.get(
                    "distance"
                ),
        }

        # ----------------------------------------------------------
        # Unknown / failed / duplicate face
        # ----------------------------------------------------------

        if not face_result.get(
            "recognized"
        ):

            face_status = face_result.get(
                "status"
            )

            if face_status == "DUPLICATE":

                face_payload[
                    "state"
                ] = "DUPLICATE"

                face_payload[
                    "message"
                ] = (
                    "Duplicate face ignored"
                )

            elif face_status == "ERROR":

                face_payload[
                    "state"
                ] = "ERROR"

                face_payload[
                    "message"
                ] = (
                    "Face could not be processed"
                )

            else:

                unknown_count += 1

                face_payload[
                    "state"
                ] = "UNKNOWN"

                face_payload[
                    "message"
                ] = "UNKNOWN PERSON"

            processed_faces.append(
                face_payload
            )

            continue

        # ----------------------------------------------------------
        # Find recognised student
        # ----------------------------------------------------------

        register_number = (
            face_result[
                "register_number"
            ]
        )

        student = Student.query.filter_by(
            register_number=register_number
        ).first()

        if student is None:

            unknown_count += 1

            face_payload.update(
                {
                    "state":
                        "UNKNOWN",

                    "message":
                        "UNKNOWN PERSON "
                        "(student record missing)",
                }
            )

            processed_faces.append(
                face_payload
            )

            continue

        face_payload[
            "student"
        ] = student.to_dict()

        # ----------------------------------------------------------
        # Subject enrollment check
        # ----------------------------------------------------------

        if (
            student
            not in session.subject.students
        ):

            not_enrolled_count += 1

            face_payload.update(
                {
                    "state":
                        "NOT_ENROLLED",

                    "message":
                        "{} is not enrolled in {}".format(
                            student.name,
                            session.subject.code,
                        ),
                }
            )

            processed_faces.append(
                face_payload
            )

            continue

        # ----------------------------------------------------------
        # Already marked?
        #
        # If yes, update continuous presence.
        # ----------------------------------------------------------

        existing = get_record(
            session,
            student,
        )

        if existing is not None:

            update_presence(
                session,
                existing,
                confidence=face_result[
                    "confidence"
                ],
            )

            presence_updated_count += 1

            face_payload.update(
                {
                    "state":
                        "ALREADY_MARKED",

                    "message":
                        "PRESENCE UPDATED",

                    "record":
                        existing.to_dict(),
                }
            )

            processed_faces.append(
                face_payload
            )

            continue

        # ----------------------------------------------------------
        # Per-student liveness
        # ----------------------------------------------------------

        if current_app.config[
            "LIVENESS_ENABLED"
        ]:

            state, challenge = (
                liveness_manager.check(
                    session.id,
                    register_number,
                    face_result["box"],
                    result[
                        "frame_width"
                    ],
                    move_ratio=current_app.config[
                        "LIVENESS_MOVE_RATIO"
                    ],
                    scale_ratio=current_app.config[
                        "LIVENESS_SCALE_RATIO"
                    ],
                    timeout_seconds=current_app.config[
                        "LIVENESS_TIMEOUT_SEC"
                    ],
                )
            )

            if state == PENDING:

                liveness_pending_count += 1

                face_payload.update(
                    {
                        "state":
                            "LIVENESS_PENDING",

                        "message":
                            "FACE VERIFIED - {}".format(
                                challenge
                            ),

                        "challenge":
                            challenge,
                    }
                )

                processed_faces.append(
                    face_payload
                )

                continue

            if state == FAILED:

                liveness_failed_count += 1

                liveness_manager.clear(
                    session.id,
                    register_number,
                )

                face_payload.update(
                    {
                        "state":
                            "LIVENESS_FAILED",

                        "message":
                            "LIVENESS CHECK FAILED - "
                            "ATTENDANCE NOT MARKED",

                        "challenge":
                            challenge,
                    }
                )

                processed_faces.append(
                    face_payload
                )

                continue

        # ----------------------------------------------------------
        # Mark attendance
        # ----------------------------------------------------------

        record, created = (
            mark_attendance(
                session,
                student,
                confidence=face_result[
                    "confidence"
                ],
                liveness_verified=True,
            )
        )

        if created:
            marked_count += 1
            state_name = "MARKED"

        else:
            presence_updated_count += 1
            state_name = "ALREADY_MARKED"

        face_payload.update(
            {
                "state":
                    state_name,

                "message":
                    "FACE VERIFIED - "
                    "LIVENESS VERIFIED - {}".format(
                        record.status
                    ),

                "record":
                    record.to_dict(),
            }
        )

        processed_faces.append(
            face_payload
        )

    # --------------------------------------------------------------
    # Build browser-friendly summary
    # --------------------------------------------------------------

    detected_count = result.get(
        "face_count",
        len(processed_faces),
    )

    recognized_count = sum(
        1
        for face in processed_faces
        if face.get("student")
    )

    student_names = []

    for face in processed_faces:

        student_data = face.get(
            "student"
        )

        if student_data:

            name = student_data.get(
                "name"
            )

            if (
                name
                and name
                not in student_names
            ):
                student_names.append(
                    name
                )

    if detected_count == 1:

        # Keep a friendly response for the
        # existing single-person UI.
        if processed_faces:

            first = processed_faces[0]

            summary_message = first.get(
                "message",
                "Face processed",
            )

            overall_state = first.get(
                "state",
                "PROCESSED",
            )

        else:

            summary_message = (
                "Face processed"
            )

            overall_state = "PROCESSED"

    else:

        overall_state = (
            "MULTI_FACE_PROCESSED"
        )

        summary_message = (
            "{} faces detected, "
            "{} recognised".format(
                detected_count,
                recognized_count,
            )
        )

        if student_names:

            summary_message += (
                " - "
                + ", ".join(
                    student_names
                )
            )

    return ok(
        state=overall_state,
        message=summary_message,

        face_count=detected_count,
        recognized_count=recognized_count,

        marked_count=marked_count,
        presence_updated_count=presence_updated_count,
        unknown_count=unknown_count,
        not_enrolled_count=not_enrolled_count,
        liveness_pending_count=liveness_pending_count,
        liveness_failed_count=liveness_failed_count,

        faces=processed_faces,
        ticked=ticked,
    )


# ======================================================================
# Attendance records
# ======================================================================

@api_bp.route(
    "/attendance/<int:session_id>/records"
)
@login_required
@teacher_required
def attendance_records(session_id):

    session = (
        AttendanceSession.query.get_or_404(
            session_id
        )
    )

    return ok(
        rows=session_live_rows(
            session
        ),
        total_checks=session.total_checks,
        enrolled=len(
            session.subject.students
        ),
        status=session.status,
        server_time=datetime.now().strftime(
            "%I:%M:%S %p"
        ),
    )


# ======================================================================
# Analytics
# ======================================================================

@api_bp.route(
    "/analytics/summary"
)
@login_required
@teacher_required
def analytics_summary():

    minimum = current_app.config[
        "MIN_ATTENDANCE_PERCENT"
    ]

    return ok(
        trend=analytics_service.daily_trend(
            7
        ),

        subject_wise=(
            analytics_service
            .subject_wise_attendance()
        ),

        status_distribution=(
            analytics_service
            .status_distribution()
        ),

        overall=(
            analytics_service
            .overall_attendance_percentage()
        ),

        today=(
            analytics_service
            .today_counts()["present"]
        ),

        below_minimum=len(
            analytics_service
            .low_attendance_students(
                minimum
            )
        ),
    )


# ======================================================================
# Student summary
# ======================================================================

@api_bp.route(
    "/student/summary"
)
@login_required
def student_summary():
    """
    A student may only read
    their own summary.
    """

    if not current_user.is_student:

        return fail(
            "Only students can use "
            "this endpoint.",
            403,
        )

    student = current_user.student

    return ok(
        subjects=(
            analytics_service
            .student_subject_percentages(
                student.id
            )
        ),

        counts=(
            analytics_service
            .student_status_counts(
                student.id
            )
        ),
    )