
import unittest

from gesture import (
    THUMBS_UP,
    OPEN_PALM,
    FIST,
    NONE
)
from gesture_controller import GestureController


class TestGestureController(unittest.TestCase):

    def setUp(self):
        self.controller = GestureController()

    def test_short_gesture(self):
        self.assertIsNone(
            self.controller.update(THUMBS_UP, 0.0)
        )
        self.assertIsNone(
            self.controller.update(THUMBS_UP, 0.5)
        )

    def test_start_after_duration(self):
        self.controller.update(THUMBS_UP, 0.0)

        self.assertEqual(
            self.controller.update(THUMBS_UP, 0.7),
            "START"
        )

    def test_no_duplicate_command(self):
        self.controller.update(THUMBS_UP, 0.0)
        self.controller.update(THUMBS_UP, 0.7)

        self.assertIsNone(
            self.controller.update(THUMBS_UP, 1.5)
        )

    def test_release_and_restart(self):
        self.controller.update(THUMBS_UP, 0.0)
        self.controller.update(THUMBS_UP, 0.7)

        # 중립 상태 유지
        self.controller.update(NONE, 1.0)
        self.controller.update(NONE, 1.4)

        # 다시 엄지척
        self.controller.update(THUMBS_UP, 2.0)

        self.assertEqual(
            self.controller.update(THUMBS_UP, 2.7),
            "START"
        )

    def test_complete_command(self):
        self.controller.update(OPEN_PALM, 0.0)

        self.assertEqual(
            self.controller.update(OPEN_PALM, 0.7),
            "COMPLETE"
        )

    def test_cancel_command(self):
        self.controller.update(FIST, 0.0)

        self.assertEqual(
            self.controller.update(FIST, 0.7),
            "CANCEL"
        )

    def test_gesture_change_resets_timer(self):
        self.controller.update(THUMBS_UP, 0.0)
        self.controller.update(FIST, 0.4)

        self.assertIsNone(
            self.controller.update(FIST, 0.8)
        )

        self.assertEqual(
            self.controller.update(FIST, 1.1),
            "CANCEL"
        )


if __name__ == "__main__":
    unittest.main()
