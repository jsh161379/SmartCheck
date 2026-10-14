
import unittest

from controller import (
    InspectionController,
    InspectionState
)


class TestInspectionController(unittest.TestCase):

    def setUp(self):
        self.controller = InspectionController()

    def test_initial_state(self):
        self.assertEqual(
            self.controller.state,
            InspectionState.IDLE
        )

    def test_start_without_items(self):
        self.assertFalse(
            self.controller.handle_command("START")
        )
        self.assertEqual(
            self.controller.state,
            InspectionState.IDLE
        )

    def test_start_with_items(self):
        self.controller.set_selected_items({"book"})

        self.assertTrue(
            self.controller.handle_command("START")
        )
        self.assertEqual(
            self.controller.state,
            InspectionState.PREPARING
        )

    def test_duplicate_start(self):
        self.controller.set_selected_items({"book"})
        self.controller.handle_command("START")

        self.assertFalse(
            self.controller.handle_command("START")
        )

    def test_cancel_during_preparing(self):
        self.controller.set_selected_items({"book"})
        self.controller.handle_command("START")

        self.assertTrue(
            self.controller.handle_command("CANCEL")
        )
        self.assertEqual(
            self.controller.state,
            InspectionState.CANCELLED
        )

    def test_cancel_during_inspection(self):
        self.controller.set_selected_items({"book"})
        self.controller.handle_command("START")
        self.controller.begin_inspection()

        self.assertTrue(
            self.controller.handle_command("CANCEL")
        )
        self.assertEqual(
            self.controller.state,
            InspectionState.CANCELLED
        )

    def test_finish_inspection(self):
        self.controller.set_selected_items({"book"})
        self.controller.handle_command("START")
        self.controller.begin_inspection()

        self.assertTrue(
            self.controller.finish_inspection("PASS")
        )
        self.assertEqual(
            self.controller.state,
            InspectionState.COMPLETED
        )
        self.assertEqual(
            self.controller.last_result,
            "PASS"
        )

    def test_reset_during_inspection(self):
        self.controller.set_selected_items({"book"})
        self.controller.handle_command("START")
        self.controller.begin_inspection()

        self.assertFalse(
            self.controller.handle_command("RESET")
        )

    def test_cancel_when_idle(self):
        self.assertFalse(
            self.controller.handle_command("CANCEL")
        )

    def test_return_to_idle_after_cancel(self):
        self.controller.set_selected_items({"book"})
        self.controller.handle_command("START")
        self.controller.handle_command("CANCEL")

        self.assertTrue(
            self.controller.return_to_idle()
        )
        self.assertEqual(
            self.controller.state,
            InspectionState.IDLE
        )

    def test_change_items_during_inspection(self):
        self.controller.set_selected_items({"book"})
        self.controller.handle_command("START")
        self.controller.begin_inspection()

        self.assertFalse(
            self.controller.set_selected_items(
                {"cell phone"}
            )
        )

    def test_restart_after_completion(self):
        self.controller.set_selected_items({"book"})
        self.controller.handle_command("START")
        self.controller.begin_inspection()
        self.controller.finish_inspection("PASS")

        self.assertTrue(
            self.controller.handle_command("START")
        )
        self.assertEqual(
            self.controller.state,
            InspectionState.PREPARING
        )


if __name__ == "__main__":
    unittest.main()
