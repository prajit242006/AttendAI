-- ======================================================================
-- AttendAI - MySQL schema
-- ----------------------------------------------------------------------
-- You do NOT have to run this file: `python run.py` creates the same
-- tables through SQLAlchemy. It is here so the structure can be shown
-- during the viva and so the database can be rebuilt by hand.
--
-- Run it with:
--     mysql -u root -p < database/schema.sql
-- ======================================================================

CREATE DATABASE IF NOT EXISTS attendai_db
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE attendai_db;

-- ----------------------------------------------------------------------
-- users : one row per login (TEACHER or STUDENT)
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(64)  NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(16)  NOT NULL DEFAULT 'STUDENT',
  is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_users_role (role)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------
-- teachers
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teachers (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT          NOT NULL UNIQUE,
  name       VARCHAR(120) NOT NULL,
  email      VARCHAR(120) UNIQUE,
  department VARCHAR(80),
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_teachers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------
-- students
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT         NOT NULL UNIQUE,
  register_number VARCHAR(30) NOT NULL UNIQUE,
  name            VARCHAR(120) NOT NULL,
  department      VARCHAR(80)  NOT NULL,
  year            INT          NOT NULL,
  section         VARCHAR(10),
  email           VARCHAR(120) UNIQUE,
  face_registered BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX ix_students_face (face_registered)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------
-- subjects
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subjects (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  code       VARCHAR(20)  NOT NULL UNIQUE,
  name       VARCHAR(120) NOT NULL,
  department VARCHAR(80)  NOT NULL,
  year       INT          NOT NULL,
  semester   INT          NOT NULL,
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------
-- student_subjects : which students attend which subject
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_subjects (
  student_id INT NOT NULL,
  subject_id INT NOT NULL,
  PRIMARY KEY (student_id, subject_id),
  CONSTRAINT fk_ss_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  CONSTRAINT fk_ss_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------
-- face_profiles : bookkeeping for the samples in face_data/
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS face_profiles (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  student_id   INT          NOT NULL UNIQUE,
  label        INT,
  sample_count INT          NOT NULL DEFAULT 0,
  samples_dir  VARCHAR(255) NOT NULL,
  trained      BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_face_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  INDEX ix_face_label (label)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------
-- attendance_sessions : one class hour
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance_sessions (
  id                     INT AUTO_INCREMENT PRIMARY KEY,
  subject_id             INT      NOT NULL,
  teacher_id             INT      NOT NULL,
  session_date           DATE     NOT NULL,
  class_start_time       TIME     NOT NULL,
  late_threshold_minutes INT      NOT NULL DEFAULT 10,
  presence_threshold     FLOAT    NOT NULL DEFAULT 75,
  recognition_threshold  FLOAT    NOT NULL DEFAULT 70,
  check_interval_seconds INT      NOT NULL DEFAULT 10,
  status                 VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  started_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ended_at               DATETIME,
  last_check_at          DATETIME,
  total_checks           INT      NOT NULL DEFAULT 0,
  CONSTRAINT fk_session_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
  CONSTRAINT fk_session_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id),
  INDEX ix_session_date (session_date),
  INDEX ix_session_status (status)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------
-- attendance_records : one row per student per session
-- The UNIQUE key below is what makes duplicate attendance impossible.
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance_records (
  id                     INT AUTO_INCREMENT PRIMARY KEY,
  student_id             INT      NOT NULL,
  subject_id             INT      NOT NULL,
  attendance_session_id  INT      NOT NULL,
  session_date           DATE     NOT NULL,
  first_detection_time   DATETIME,
  last_detection_time    DATETIME,
  status                 VARCHAR(20) NOT NULL DEFAULT 'ABSENT',
  liveness_verified      BOOLEAN  NOT NULL DEFAULT FALSE,
  presence_count         INT      NOT NULL DEFAULT 0,
  total_checks           INT      NOT NULL DEFAULT 0,
  presence_percentage    FLOAT    NOT NULL DEFAULT 0,
  last_presence_tick     DATETIME,
  recognition_confidence FLOAT,
  manually_modified      BOOLEAN  NOT NULL DEFAULT FALSE,
  remarks                VARCHAR(255),
  created_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_student_session UNIQUE (student_id, attendance_session_id),
  CONSTRAINT fk_record_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  CONSTRAINT fk_record_subject FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
  CONSTRAINT fk_record_session FOREIGN KEY (attendance_session_id)
    REFERENCES attendance_sessions(id) ON DELETE CASCADE,
  INDEX ix_record_date_status (session_date, status)
) ENGINE=InnoDB;
