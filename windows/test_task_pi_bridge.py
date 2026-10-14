"""First run without GPIO/network, then optional real-Pi demonstration."""
import time
from task_controller import TaskState
from task_pi_bridge import TaskPiBridge


class FakePiClient:
    def __init__(self):
        self.sent = []
    def start(self):
        pass
    def set_state(self, state, **kwargs):
        self.sent.append((getattr(state, 'value', state), kwargs))
    def stop(self):
        pass


def unit_test():
    fake = FakePiClient()
    bridge = TaskPiBridge(client=fake)
    bridge.start()
    assert fake.sent[-1][0] == 'READY'
    assert bridge.set_selected_items(['book', 'scissors'])
    assert bridge.handle_command('START', source='GESTURE')
    assert fake.sent[-1][0] == 'CHECKING'
    assert bridge.finish_inspection('FAIL', missing=['scissors'])
    assert fake.sent[-1][0] == 'FAIL'
    assert fake.sent[-1][1]['missing'] == ['scissors']
    assert bridge.handle_command('START', source='GESTURE')
    assert bridge.finish_inspection('RECHECK', uncertain=['book'])
    assert fake.sent[-1][0] == 'RECHECK'
    assert fake.sent[-1][1]['uncertain'] == ['book']
    assert bridge.handle_command('START', source='GESTURE')
    assert bridge.finish_inspection('PASS')
    assert bridge.controller.state == TaskState.WORKING
    assert fake.sent[-1][0] == 'WORKING'
    bridge.refresh_elapsed()
    assert bridge.handle_command('COMPLETE', source='GESTURE')
    assert fake.sent[-1][0] == 'COMPLETED'
    assert not bridge.handle_command('NEXT_TASK', source='GESTURE')
    assert fake.sent[-1][0] == 'COMPLETED'
    assert bridge.handle_command('NEXT_TASK', source='GUI')
    assert fake.sent[-1][0] == 'READY'
    bridge.stop()
    print('PASS: bridge state transitions, missing/uncertain, GUI-only READY')


def hardware_demo():
    bridge = TaskPiBridge()
    try:
        bridge.start()
        bridge.set_selected_items(['book', 'scissors'])
        cases = [
            ('START', None), ('FAIL', ['scissors']),
            ('START', None), ('RECHECK', ['book']),
            ('START', None), ('PASS', None),
        ]
        for command, items in cases:
            if command == 'START':
                assert bridge.handle_command('START', source='GESTURE')
            elif command == 'FAIL':
                assert bridge.finish_inspection('FAIL', missing=items)
            elif command == 'RECHECK':
                assert bridge.finish_inspection('RECHECK', uncertain=items)
            else:
                assert bridge.finish_inspection('PASS')
            print('PC state:', bridge.controller.state.value)
            time.sleep(5)  # allow 3s PiClient heartbeat to deliver each state
        bridge.refresh_elapsed()
        time.sleep(5)
        assert bridge.handle_command('COMPLETE', source='GESTURE')
        print('PC state: COMPLETED (not auto-reset)')
        time.sleep(5)
        print('Pi connected:', bridge.client.connected, 'error:', bridge.client.last_error)
        assert bridge.handle_command('NEXT_TASK', source='GUI')
        print('Admin NEXT_TASK -> READY')
        time.sleep(5)
    finally:
        bridge.stop()


if __name__ == '__main__':
    import sys
    unit_test()
    if '--hardware' in sys.argv:
        hardware_demo()
    else:
        print('Run with --hardware for live Raspberry Pi test.')
