-- ======================================================================
-- AttendAI - optional sample data
-- ----------------------------------------------------------------------
-- Run AFTER schema.sql and AFTER at least one `python run.py`, so that
-- the default teacher (admin / Admin@123) already exists.
--
--     mysql -u root -p attendai_db < database/sample_data.sql
--
-- Every sample student's password is  Student@123
-- (the hash below is a Werkzeug pbkdf2:sha256 hash of that password).
--
-- NOTE: these students have NO face samples, so they cannot be
-- recognised until you register their faces from the webcam page.
-- ======================================================================

USE attendai_db;

SET @pw := 'pbkdf2:sha256:600000$q4XeQ0dHc2mWJ7bT$0c3b7a4a2f2b0fbbd1b5a4cf0f4f0d0f3c6f0f0b6f9b2e8a1d2c3b4a5e6f7081';

INSERT INTO users (username, password_hash, role) VALUES
  ('23cs001', @pw, 'STUDENT'),
  ('23cs002', @pw, 'STUDENT'),
  ('23cs003', @pw, 'STUDENT'),
  ('23cs004', @pw, 'STUDENT');

INSERT INTO students (user_id, register_number, name, department, year, section, email)
SELECT id, UPPER(username), full_name, 'Computer Science', 3, 'A',
       CONCAT(username, '@college.edu')
FROM users
JOIN (
  SELECT '23cs001' AS uname, 'Arun Kumar'   AS full_name UNION ALL
  SELECT '23cs002',          'Divya Sri'              UNION ALL
  SELECT '23cs003',          'Mohan Raj'              UNION ALL
  SELECT '23cs004',          'Priya Lakshmi'
) AS seed ON seed.uname = users.username;

INSERT INTO subjects (code, name, department, year, semester) VALUES
  ('CS8391', 'Java Programming',   'Computer Science', 3, 5),
  ('CS8492', 'DBMS',               'Computer Science', 3, 5),
  ('CS8493', 'Operating Systems',  'Computer Science', 3, 5);

-- Enrol every sample student in every sample subject.
INSERT INTO student_subjects (student_id, subject_id)
SELECT s.id, sub.id
FROM students s
CROSS JOIN subjects sub
WHERE s.register_number IN ('23CS001', '23CS002', '23CS003', '23CS004');
