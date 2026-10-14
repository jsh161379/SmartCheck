"""SmartCheck TaskController -> PiClient bridge.

No modifications to the existing TaskController or PiClient.
All commands must pass through this bridge in this integration test.
"""
from task_controller import TaskController, TaskState
from pi_client import PiClient


class TaskPiBridge:
    def __init__(self, controller=None, client=None):
        self.controller = controller if controller is not None else TaskController()
        self.client = client if client is not None else PiClient()
        self.missing = []
        self.uncertain = []

    def start(self):
        self.client.start()
        self.sync()

    def sync(self):
        """Queue current PC state; PiClient performs HTTP in its worker thread."""
        state = self.controller.state
        elapsed = self.controller.elapsed_seconds()
        self.client.set_state(
            state,
            missing=self.missing if state == TaskState.FAIL else [],
            uncertain=self.uncertain if state == TaskState.RECHECK else [],
            elapsed_seconds=elapsed if elapsed is not None else None,
        )

    def set_selected_items(self, items):
        return self.controller.set_selected_items(items)

    def handle_command(self, command, source='GESTURE'):
        changed = self.controller.handle_command(command, source=source)
        if changed:
            if command in ('START', 'NEXT_TASK', 'RECOVER'):
                self.missing = []
                self.uncertain = []
            self.sync()
        return changed

    def finish_inspection(self, result, missing=None, uncertain=None):
        changed = self.controller.finish_inspection(result)
        if changed:
            self.missing = list(missing or []) if result == 'FAIL' else []
            self.uncertain = list(uncertain or []) if result == 'RECHECK' else []
            self.sync()
        return changed

    def set_error(self):
        self.controller.set_error()
        self.sync()

    def refresh_elapsed(self):
        """Call periodically during WORKING to refresh the OLED timer."""
        if self.controller.state == TaskState.WORKING:
            self.sync()

    def stop(self):
        self.client.stop()
