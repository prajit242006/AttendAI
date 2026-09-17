# AttendAI — AI-Based Smart Student Attendance Management System

**Smart. Secure. Automated Attendance.**

A Flask web application that marks student attendance from a webcam. A face is
detected with OpenCV, identified with an LBPH face recognizer trained on the
students you register, checked with a head-movement liveness challenge, and then
written to MySQL — once per session, with late detection, continuous presence
tracking, analytics and CSV reports.

---

## 1. Project overview

| | |
|---|---|
| Language | Python 3.11 / 3.12 |
| Web framework | Flask (blueprints, Jinja2) |
| AI / vision | OpenCV (Haar cascade detection + LBPH recognition) |
| Database | MySQL via Flask-SQLAlchemy and PyMySQL |
| Frontend | Bootstrap 5, Bootstrap Icons, Chart.js, vanilla JS |
| Security | Flask-Login sessions, Werkzeug password hashing, CSRF protection, role checks |
| Runs at | http://localhost:5000 |
| Default teacher | `admin` / `Admin@123` |

Two roles exist. A **teacher** manages students, subjects, faces, sessions and
reports. A **student** can only see their own attendance.

---

## 2. What makes this project different

1. **Real face recognition, not a lookup.** Samples are cropped, equalised and
   used to train an LBPH model; identification comes from the model's prediction
   and its distance score, never from a form field or a filename.
2. **Basic liveness check.** Before a student's first attendance mark, the server
   issues a random challenge (turn head left / right / move closer) and verifies
   the movement by comparing face-box positions across actual camera frames.
3. **Continuous presence verification.** A student who walks out after being
   marked is caught: the server ticks every few seconds, counts how often each
   student is still recognised, and computes
   `presence % = presence_count / total_checks × 100`. Below the threshold the
   status becomes `REVIEW_REQUIRED`.
4. **Duplicate-proof by database design.** `UNIQUE(student_id, attendance_session_id)`
   makes a second attendance row impossible; repeat sightings only update timings
   and presence.
5. **Automatic absentees.** Ending a session marks every enrolled student who was
   never recognised as `ABSENT`.

---

## 3. Architecture

```
Browser (webcam)                Flask server                      MySQL
────────────────                ────────────                      ─────
getUserMedia  ──base64 JPEG──►  /api/attendance/recognize
                                  │
                                  ├─ OpenCV  Haar cascade → face box
                                  ├─ LBPH    predict → register number
                                  ├─ liveness challenge → PASSED / PENDING
                                  └─ attendance_service ──────────► attendance_records
                                  ◄── JSON (state, student, confidence)
```

The browser owns the camera, so no server-side `cv2.VideoCapture` is needed and
the app works on any laptop that can open a webcam in Chrome or Edge.

### Folder structure

```
AttendAI/
├── run.py                  entry point: creates tables + default teacher, starts the server
├── config.py               every setting, read from .env
├── requirements.txt
├── README.md
├── .env.example            copy to .env
├── .gitignore
│
├── database/
│   ├── schema.sql          MySQL tables (optional - run.py can create them)
│   └── sample_data.sql     optional demo students and subjects
│
├── face_data/              face samples: face_data/23CS001/sample_*.png
├── models_data/            lbph_model.yml + labels.json (created after training)
│
├── app/
│   ├── __init__.py         application factory, extensions, error handlers
│   ├── models/             user.py student.py subject.py attendance.py face_profile.py
│   ├── routes/             auth.py teacher.py student.py attendance.py api.py
│   ├── services/           attendance_service.py analytics_service.py report_service.py
│   ├── vision/             face_detector.py face_trainer.py face_recognizer.py liveness.py
│   ├── utils/              decorators.py helpers.py
│   ├── templates/          base.html login.html teacher/ student/ errors/
│   └── static/             css/style.css  js/{app,camera,attendance,charts}.js
│
└── tests/                  test_vision.py  test_helpers.py
```

### The modules that matter in a viva

| File | What it does |
|---|---|
| `app/vision/face_detector.py` | Loads the Haar cascade from `cv2.data.haarcascades`, decodes base64 frames, crops and equalises faces |
| `app/vision/face_trainer.py` | Saves samples to `face_data/`, builds the dataset, trains LBPH, writes `lbph_model.yml` + `labels.json` |
| `app/vision/face_recognizer.py` | Loads the model (and reloads it after retraining), predicts, applies the distance threshold |
| `app/vision/liveness.py` | Random challenge, baseline face box, movement comparison |
| `app/services/attendance_service.py` | Marking, duplicate handling, presence ticks, ending a session |
| `app/services/analytics_service.py` | Every dashboard number and chart, straight from SQL |
| `app/routes/api.py` | The JSON endpoints the camera pages talk to |

---

## 4. Prerequisites (Windows 11)

1. **Python 3.11 or 3.12** — <https://www.python.org/downloads/>
   Tick **“Add python.exe to PATH”** during installation. Check it:
   ```
   python --version
   ```
2. **MySQL 8** — MySQL Installer for Windows (MySQL Server + MySQL Workbench).
   Remember the root password you set.
3. **VS Code** (optional but convenient).
4. A working **webcam** and a **Chrome or Edge** browser.

---

## 5. Setup, step by step

Open a terminal in the `AttendAI` folder (in VS Code: *Terminal → New Terminal*).

### 5.1 Virtual environment

```
python -m venv venv
venv\Scripts\activate
```

The prompt now starts with `(venv)`. If PowerShell blocks the script, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` once, or use
`venv\Scripts\activate.bat` in Command Prompt.

### 5.2 Install the dependencies

```
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`opencv-contrib-python` is required — the LBPH recognizer lives in `cv2.face`,
which plain `opencv-python` does not ship. If you already installed
`opencv-python`, remove it first:

```
pip uninstall opencv-python
pip install opencv-contrib-python
```

Check OpenCV:

```
python -c "import cv2; print(cv2.__version__, hasattr(cv2, 'face'))"
```

You should see a version number and `True`.

### 5.3 Create the database

Easiest way — one command in Command Prompt:

```
mysql -u root -p -e "CREATE DATABASE attendai_db CHARACTER SET utf8mb4;"
```

Or in MySQL Workbench: *File → Open SQL Script → database/schema.sql → Execute*.

You do **not** have to run `schema.sql`: `run.py` creates the same tables through
SQLAlchemy the first time it starts. The SQL file is there so you can show and
rebuild the schema by hand.

### 5.4 Configure `.env`

Copy `.env.example` to `.env` and put your own MySQL password in it:

```
copy .env.example .env
```

```
SECRET_KEY=any-long-random-string
DATABASE_URL=mysql+pymysql://root:YOUR_MYSQL_PASSWORD@localhost/attendai_db
FLASK_ENV=development
```

If your MySQL password contains `@`, `:` or `/`, URL-encode it (`@` → `%40`).

### 5.5 Run

```
python run.py
```

Open <http://localhost:5000> and sign in with **admin / Admin@123**.
The default teacher is created automatically on the first run and the password
is stored only as a Werkzeug hash.

---

## 6. Demo walkthrough

1. **Add a student** — *Students → Add student*. Register number (e.g. `23CS001`)
   and username must be unique; the register number doubles as a student login.
2. **Add a subject** — *Subjects → Add subject* (e.g. `CS8391 / Java Programming`)
   and tick the students who attend it. **Only enrolled students are marked absent
   when a session ends**, so this step matters.
3. **Register the face** — *Face registration*, pick the student, allow the camera,
   press **Capture** 10–15 times while the student slightly changes angle, then
   **Save face profile**. Frames without exactly one clear face are rejected, so
   every stored sample is a real cropped face. The model retrains automatically and
   the page shows **FACE REGISTERED SUCCESSFULLY**.
4. **Start attendance** — *Start attendance*: choose the subject, the date, the
   class start time, the late threshold (e.g. 10 min), the presence threshold
   (75%) and the check interval (10 s).
5. **Live attendance** — the camera opens and frames are sent every few seconds.
   You will see, in order: `FACE VERIFIED` → a liveness challenge such as
   **TURN HEAD LEFT** → `LIVENESS VERIFIED` → the student appears in the table as
   `PRESENT` (or `LATE` past the threshold). Show the same student again: the
   answer becomes **ATTENDANCE ALREADY MARKED / PRESENCE UPDATED** and no second
   row is created. Point the camera at somebody unregistered: **UNKNOWN PERSON**.
6. **End session** — press **End session**. Presence percentages are finalised,
   students below the presence threshold become `REVIEW_REQUIRED`, and everybody
   enrolled who was never seen is written as `ABSENT`.
7. **Look at the results** — the dashboard and *Analytics* update from the new
   records; *Low attendance* lists everybody below 75%; *Reports* downloads CSVs.
8. **Student view** — sign out, sign in as the student (register number or
   username with the password you set) and show their own dashboard, subject-wise
   percentages and shortage warning.

---

## 7. How the AI parts work

### Detection
`cv2.CascadeClassifier` with `haarcascade_frontalface_default.xml`, loaded from
`cv2.data.haarcascades` — the file ships inside the installed OpenCV package, so
there is no model file to download and none is missing from the project. The
detector reports `NO_FACE`, `MULTIPLE_FACES` or `OK`.

### Registration and training
Each accepted frame is converted to grayscale, the face is cropped, resized to
200×200 and histogram-equalised, then saved as
`face_data/<REGISTER_NUMBER>/sample_*.png`. Training walks those folders, gives
each folder a numeric label, calls `cv2.face.LBPHFaceRecognizer_create().train()`
and writes:

* `models_data/lbph_model.yml` — the trained model
* `models_data/labels.json` — `{"0": "23CS001", "1": "23CS002", ...}`

Training happens automatically after every save; the **Train face model** button
on the face-registration page forces a retrain (useful if you copied images into
`face_data/` yourself).

### Recognition
LBPH returns a **distance** — smaller is a better match. A prediction is accepted
only when `distance <= recognition_threshold` (default 70, editable per session
and in `.env`). The UI shows a friendlier `confidence = 100 - distance`. Above the
threshold the result is **UNKNOWN PERSON**.

Tuning: if a registered student is not recognised, raise the threshold (e.g. 85)
or capture more samples in the room's real lighting. If strangers get recognised,
lower it (e.g. 55).

### Liveness — and its limits
The server picks a random challenge, stores the face box of the frame where the
student was first recognised, then compares later frames: the face centre must
shift sideways by at least 18% of the face width, or the box must grow 15% for
“move closer”. Only then is attendance marked.

> **This is a basic demonstration-level liveness mechanism and not
> production-grade biometric anti-spoofing.** It proves that the face in front of
> the camera moves. A video replay of a moving person could still defeat it.
> Real systems use depth cameras, infrared, texture analysis or trained
> anti-spoofing models.

### Continuous presence
`run_presence_tick()` fires at most once per `check_interval_seconds`. Each tick
increases `total_checks` for every record in the session; a student recognised
during that tick also gains `presence_count`. Example: seen 8 times out of 10
checks → 80% ≥ 75% → stays `PRESENT`. Recognition is not run per millisecond —
the browser samples a frame every couple of seconds and the counting is
interval-based.

---

## 8. Database

Tables: `users`, `teachers`, `students`, `subjects`, `student_subjects`,
`face_profiles`, `attendance_sessions`, `attendance_records`.

Key constraints:

* `users.username`, `students.register_number`, `subjects.code` are **UNIQUE**
* `attendance_records` has **UNIQUE (student_id, attendance_session_id)** — the
  duplicate-attendance guard
* foreign keys cascade, so deleting a student removes their records and face rows
* indexes on `session_date`, `status`, `role` and `face_registered`

Statuses: `PRESENT`, `LATE`, `ABSENT`, `REVIEW_REQUIRED`.

---

## 9. Security

* Passwords hashed with `werkzeug.security.generate_password_hash`; nothing is
  stored in plain text and `.env` is git-ignored.
* Sessions handled by Flask-Login; every blueprint has a `before_request` role
  gate, so a student who types `/teacher/dashboard` gets the 403 page.
* Student pages query by `current_user.student.id` only — there is no student id
  in any student URL, so attendance cannot be read by editing the address bar.
* CSRF protection via Flask-WTF on every form and on the JSON API (the JS sends
  the token in the `X-CSRFToken` header).
* All input is validated in `app/utils/helpers.py`; duplicates raise a friendly
  message instead of a database error.
* Error handlers return the 403 / 404 / 500 pages instead of a traceback.

---

## 10. Reports

*Reports* downloads CSV (opens directly in Excel):
daily attendance, subject attendance, student attendance, and the below-75%
shortage report. *Low attendance* has its own download button.

---

## 11. Tests

```
venv\Scripts\activate
python -m unittest discover -s tests -v
```

14 tests cover the cascade loading, base64 decoding, sample storage, a full
LBPH train-and-predict round trip, threshold rejection, the liveness challenge
and the validation helpers. They need no database and no camera.

Syntax check:

```
python -m compileall .
```

---

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `Can't connect to MySQL server` | Start MySQL (`services.msc` → MySQL80), check `DATABASE_URL` in `.env` |
| `Access denied for user 'root'` | Wrong password in `DATABASE_URL`; URL-encode `@` as `%40` |
| `No module named 'MySQLdb'` | Keep the `mysql+pymysql://` prefix in `DATABASE_URL` |
| `cv2.face is missing` / `TrainingError` | `pip uninstall opencv-python` then `pip install opencv-contrib-python` |
| Camera permission denied | Click the camera icon in the address bar → Allow → reload. Windows: *Settings → Privacy → Camera → Allow apps* |
| Camera is black or "already in use" | Close Teams / Zoom / the Camera app and reload |
| "Face model is not trained yet" | Register at least one face, then press **Train face model** |
| Nobody is recognised | Raise `RECOGNITION_THRESHOLD` to 85, add more samples, improve lighting |
| Everybody is recognised as one student | Lower the threshold to ~55 and re-register faces with more varied angles |
| Liveness never passes | Move your head further sideways, or lower `LIVENESS_MOVE_RATIO` to 0.12 |
| Students marked absent who attended | They were not assigned to the subject — edit the subject and tick them |
| Port 5000 already in use | Change the port at the bottom of `run.py` |

---

## 13. Honest limitations

* LBPH is a classical algorithm: good enough for a classroom demo with clear,
  front-facing images, far less accurate than deep-learning embeddings.
* The liveness check is demonstration level, as described in section 7.
* Recognition runs on the Flask development server, one frame at a time. It is
  not built for hundreds of simultaneous cameras.
* Face samples are personal biometric data. `face_data/` and `models_data/` are
  git-ignored; delete them after the demo if the images are not yours to keep.
