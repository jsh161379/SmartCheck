
from enum import Enum


class InspectionState(str, Enum):
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    INSPECTING = "INSPECTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class InspectionController:
    def __init__(self):
        self.state = InspectionState.IDLE
        self.selected_items = set()
        self.last_result = None

    def set_selected_items(self, items):
        """검사 대상을 설정한다."""
        valid_items = {
            "book",
            "cell phone",
            "scissors"
        }

        items = set(items)

        if not items.issubset(valid_items):
            return False

        if self.state in (
            InspectionState.PREPARING,
            InspectionState.INSPECTING
        ):
            return False

        self.selected_items = items
        return True

    def handle_command(self, command):
        """
        GUI 버튼과 제스처가 공통으로 사용하는 명령 처리.

        반환값:
            True  - 명령 허용
            False - 명령 무시
        """
        if command == "START":
            if self.state not in (
                InspectionState.IDLE,
                InspectionState.COMPLETED
            ):
                return False

            if not self.selected_items:
                return False

            self.last_result = None
            self.state = InspectionState.PREPARING
            return True

        if command == "CANCEL":
            if self.state not in (
                InspectionState.PREPARING,
                InspectionState.INSPECTING
            ):
                return False

            self.state = InspectionState.CANCELLED
            return True

        if command == "RESET":
            return self.state in (
                InspectionState.IDLE,
                InspectionState.COMPLETED
            )

        return False

    def begin_inspection(self):
        """손을 치우는 대기 구간이 끝난 후 호출한다."""
        if self.state != InspectionState.PREPARING:
            return False

        self.state = InspectionState.INSPECTING
        return True

    def finish_inspection(self, result):
        """검사 판정이 완료되면 호출한다."""
        if self.state != InspectionState.INSPECTING:
            return False

        if result not in ("PASS", "FAIL", "RECHECK"):
            return False

        self.last_result = result
        self.state = InspectionState.COMPLETED
        return True

    def return_to_idle(self):
        """취소 또는 오류 처리 후 대기 상태로 복귀한다."""
        if self.state not in (
            InspectionState.CANCELLED,
            InspectionState.ERROR
        ):
            return False

        self.state = InspectionState.IDLE
        return True

    def set_error(self):
        """검사 진행이 불가능한 오류 발생."""
        self.state = InspectionState.ERROR
        return True
