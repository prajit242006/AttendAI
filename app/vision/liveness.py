"""
Basic liveness / anti-proxy check (challenge-response head movement).

How it works
------------
1. When a student is recognised for the first time in a session the
   server picks a random challenge (TURN HEAD LEFT / TURN HEAD RIGHT /
   MOVE CLOSER) and stores the position of the face box in that frame
   as the baseline.
2. The browser keeps sending frames. For each frame the server compares
   the new face box with the baseline:
      - TURN HEAD LEFT  : the face centre must move left  by at least
                          LIVENESS_MOVE_RATIO * face width
      - TURN HEAD RIGHT : the same, to the right
      - MOVE CLOSER     : the face box must grow by LIVENESS_SCALE_RATIO
3. Only when the movement really happened in the camera frames is the
   challenge marked as passed.

IMPORTANT: this is a demonstration-level check. It proves that the face
in front of the camera moves; it is NOT production-grade biometric
anti-spoofing (a video replay could still pass it).
"""

import random
import threading
from datetime import datetime, timedelta

CHALLENGE_LEFT = "TURN HEAD LEFT"
CHALLENGE_RIGHT = "TURN HEAD RIGHT"
CHALLENGE_CLOSER = "MOVE CLOSER"

CHALLENGES = [CHALLENGE_LEFT, CHALLENGE_RIGHT, CHALLENGE_CLOSER]

PENDING = "PENDING"
PASSED = "PASSED"
FAILED = "FAILED"


class LivenessChallenge:
    """State of one student's liveness attempt inside one session."""

    def __init__(self, challenge, box, frame_width, timeout_seconds=25):
        self.challenge = challenge
        x, y, w, h = box
        self.baseline_center_x = x + w / 2.0
        self.baseline_width = float(w)
        self.baseline_area = float(w * h)
        self.frame_width = float(frame_width)
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(seconds=timeout_seconds)
        self.state = PENDING
        self.attempts = 0

    @property
    def expired(self):
        return datetime.now() > self.expires_at

    def evaluate(self, box, move_ratio=0.18, scale_ratio=1.15):
        """Compare a new face box against the baseline."""
        self.attempts += 1
        x, y, w, h = box
        center_x = x + w / 2.0
        area = float(w * h)
        needed_shift = self.baseline_width * move_ratio

        if self.challenge == CHALLENGE_LEFT:
            # The webcam preview is mirrored, so the student turning left
            # moves the face box to the RIGHT of the raw camera frame.
            passed = (center_x - self.baseline_center_x) >= needed_shift
        elif self.challenge == CHALLENGE_RIGHT:
            passed = (self.baseline_center_x - center_x) >= needed_shift
        else:  # MOVE CLOSER
            passed = area >= self.baseline_area * scale_ratio

        if passed:
            self.state = PASSED
        elif self.expired:
            self.state = FAILED
        return self.state


class LivenessManager:
    """
    Keeps the pending challenges in memory, keyed by
    (session_id, register_number). Nothing is written to the database
    until the challenge is passed.
    """

    def __init__(self):
        self._challenges = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(session_id, register_number):
        return "{}::{}".format(session_id, register_number)

    def start(self, session_id, register_number, box, frame_width, timeout_seconds=25):
        challenge = LivenessChallenge(
            random.choice(CHALLENGES), box, frame_width, timeout_seconds
        )
        with self._lock:
            self._challenges[self._key(session_id, register_number)] = challenge
        return challenge

    def get(self, session_id, register_number):
        return self._challenges.get(self._key(session_id, register_number))

    def clear(self, session_id, register_number):
        with self._lock:
            self._challenges.pop(self._key(session_id, register_number), None)

    def clear_session(self, session_id):
        prefix = "{}::".format(session_id)
        with self._lock:
            for key in [k for k in self._challenges if k.startswith(prefix)]:
                self._challenges.pop(key, None)

    def check(self, session_id, register_number, box, frame_width,
              move_ratio=0.18, scale_ratio=1.15, timeout_seconds=25):
        """
        Main entry point used by the attendance API.

        Returns (state, challenge_text):
          PENDING - keep sending frames, show challenge_text to the student
          PASSED  - liveness verified
          FAILED  - the student did not move in time
        """
        challenge = self.get(session_id, register_number)
        if challenge is None or (challenge.state == FAILED and challenge.expired):
            challenge = self.start(
                session_id, register_number, box, frame_width, timeout_seconds
            )
            return PENDING, challenge.challenge

        state = challenge.evaluate(box, move_ratio, scale_ratio)
        if state == PASSED:
            self.clear(session_id, register_number)
        return state, challenge.challenge


# Shared manager used by the attendance API.
liveness_manager = LivenessManager()
