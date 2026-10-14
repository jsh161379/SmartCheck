"""SmartCheck v5.2 작업 상태 제어기 (검사/GUI/제스처 공통)."""
import time
from enum import Enum


class TaskState(str, Enum):
    READY = 'READY'
    CHECKING = 'CHECKING'
    PASS = 'PASS'
    FAIL = 'FAIL'
    RECHECK = 'RECHECK'
    WORKING = 'WORKING'
    COMPLETED = 'COMPLETED'
    CANCELED = 'CANCELED'
    ERROR = 'ERROR'


class TaskController:
    VALID_ITEMS = frozenset({'book', 'cell phone', 'scissors'})

    def __init__(self, clock=None):
        self._clock = clock if clock is not None else time.monotonic
        self.state = TaskState.READY
        self.selected_items = set()
        self.last_result = None
        self.work_start_time = None
        self.work_end_time = None
        self.work_duration = None

    def set_selected_items(self, items):
        items = set(items)
        if self.state != TaskState.READY or not items or not items.issubset(self.VALID_ITEMS):
            return False
        self.selected_items = items
        return True

    def handle_command(self, command, source='GESTURE'):
        """허용된 상태/입력 출처만 처리한다. GUI만 NEXT_TASK/RECOVER 허용."""
        if command == 'START' and self.state in (TaskState.READY, TaskState.FAIL, TaskState.RECHECK):
            if not self.selected_items:
                return False
            self.last_result = None
            self.state = TaskState.CHECKING
            return True
        if command == 'COMPLETE' and self.state == TaskState.WORKING:
            self.work_end_time = self._clock()
            self.work_duration = max(0.0, self.work_end_time - self.work_start_time)
            self.state = TaskState.COMPLETED
            return True
        if command == 'CANCEL' and self.state in (TaskState.CHECKING, TaskState.WORKING):
            if self.state == TaskState.WORKING:
                self.work_end_time = self._clock()
                self.work_duration = max(0.0, self.work_end_time - self.work_start_time)
            self.state = TaskState.CANCELED
            return True
        if command == 'NEXT_TASK' and source == 'GUI' and self.state in (TaskState.COMPLETED, TaskState.CANCELED):
            self.state = TaskState.READY
            self.last_result = None
            self.work_start_time = None
            self.work_end_time = None
            self.work_duration = None
            return True
        if command == 'RECOVER' and source == 'GUI' and self.state == TaskState.ERROR:
            self.state = TaskState.READY
            self.last_result = None
            self.work_start_time = None
            self.work_end_time = None
            self.work_duration = None
            return True
        return False

    def finish_inspection(self, result):
        if self.state != TaskState.CHECKING or result not in ('PASS', 'FAIL', 'RECHECK'):
            return False
        self.last_result = result
        if result == 'PASS':
            self.state = TaskState.PASS
            self.work_start_time = self._clock()
            self.work_end_time = None
            self.work_duration = None
            self.state = TaskState.WORKING
        else:
            self.state = TaskState(result)
        return True

    def elapsed_seconds(self):
        if self.state == TaskState.WORKING and self.work_start_time is not None:
            return max(0.0, self._clock() - self.work_start_time)
        return self.work_duration

    def set_error(self):
        self.state = TaskState.ERROR
