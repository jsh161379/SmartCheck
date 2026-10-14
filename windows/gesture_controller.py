
import time

from gesture import (
    THUMBS_UP,
    OPEN_PALM,
    FIST,
    NONE
)


GESTURE_DURATION = 0.7
RELEASE_DURATION = 0.3

GESTURE_COMMANDS = {
    THUMBS_UP: "START",
    OPEN_PALM: "COMPLETE",
    FIST: "CANCEL"
}


class GestureController:
    def __init__(self):
        self.candidate = NONE
        self.candidate_start = None

        self.locked = False
        self.release_start = None

    def update(self, gesture, now=None):
        """
        제스처 입력을 받아 명령을 반환한다.

        반환값:
            START / COMPLETE / CANCEL / None
        """
        if now is None:
            now = time.monotonic()

        if gesture not in GESTURE_COMMANDS:
            gesture = NONE

        # 명령 실행 후 잠금 상태
        if self.locked:
            if gesture == NONE:
                if self.release_start is None:
                    self.release_start = now

                if now - self.release_start >= RELEASE_DURATION:
                    self.locked = False
                    self.candidate = NONE
                    self.candidate_start = None
                    self.release_start = None
            else:
                self.release_start = None

            return None

        # 중립 상태
        if gesture == NONE:
            self.candidate = NONE
            self.candidate_start = None
            return None

        # 새로운 제스처 후보
        if gesture != self.candidate:
            self.candidate = gesture
            self.candidate_start = now
            return None

        # 동일 제스처 유지 시간 확인
        if (
            self.candidate_start is not None
            and now - self.candidate_start >= GESTURE_DURATION
        ):
            command = GESTURE_COMMANDS[gesture]

            self.locked = True
            self.release_start = None

            return command

        return None
