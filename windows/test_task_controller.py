import unittest
from task_controller import TaskController, TaskState


class TestTaskController(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.ctrl = TaskController(clock=lambda: self.now)
        self.assertTrue(self.ctrl.set_selected_items({'book'}))

    def test_start_requires_items(self):
        ctrl = TaskController()
        self.assertFalse(ctrl.handle_command('START'))

    def test_pass_and_complete_timing(self):
        self.assertTrue(self.ctrl.handle_command('START'))
        self.assertTrue(self.ctrl.finish_inspection('PASS'))
        self.assertEqual(self.ctrl.state, TaskState.WORKING)
        self.now = 112.5
        self.assertEqual(self.ctrl.elapsed_seconds(), 12.5)
        self.assertTrue(self.ctrl.handle_command('COMPLETE'))
        self.assertEqual(self.ctrl.state, TaskState.COMPLETED)
        self.assertEqual(self.ctrl.work_duration, 12.5)
        self.assertFalse(self.ctrl.handle_command('START'))
        self.assertFalse(self.ctrl.handle_command('NEXT_TASK'))
        self.assertTrue(self.ctrl.handle_command('NEXT_TASK', source='GUI'))
        self.assertEqual(self.ctrl.state, TaskState.READY)

    def test_fail_and_recheck(self):
        for result in ('FAIL', 'RECHECK'):
            self.assertTrue(self.ctrl.handle_command('START'))
            self.assertTrue(self.ctrl.finish_inspection(result))
            self.assertEqual(self.ctrl.state, TaskState(result))
            self.assertFalse(self.ctrl.handle_command('COMPLETE'))
        self.assertTrue(self.ctrl.handle_command('START'))

    def test_cancel_checking_and_manual_reset(self):
        self.ctrl.handle_command('START')
        self.assertTrue(self.ctrl.handle_command('CANCEL'))
        self.assertEqual(self.ctrl.state, TaskState.CANCELED)
        self.assertFalse(self.ctrl.handle_command('START'))
        self.assertTrue(self.ctrl.handle_command('NEXT_TASK', source='GUI'))

    def test_cancel_working_duration(self):
        self.ctrl.handle_command('START')
        self.ctrl.finish_inspection('PASS')
        self.now += 5
        self.assertTrue(self.ctrl.handle_command('CANCEL'))
        self.assertEqual(self.ctrl.work_duration, 5)
        self.assertEqual(self.ctrl.state, TaskState.CANCELED)

    def test_invalid_transitions(self):
        self.assertFalse(self.ctrl.finish_inspection('PASS'))
        self.assertFalse(self.ctrl.handle_command('COMPLETE'))
        self.ctrl.handle_command('START')
        self.assertFalse(self.ctrl.finish_inspection('BAD'))
        self.assertFalse(self.ctrl.set_selected_items({'scissors'}))

    def test_error_requires_gui_recovery(self):
        self.ctrl.set_error()
        self.assertFalse(self.ctrl.handle_command('START'))
        self.assertFalse(self.ctrl.handle_command('RECOVER'))
        self.assertTrue(self.ctrl.handle_command('RECOVER', source='GUI'))
        self.assertEqual(self.ctrl.state, TaskState.READY)


if __name__ == '__main__':
    unittest.main()
