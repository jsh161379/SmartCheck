"""SmartCheck Raspberry Pi RGB status indicator (common cathode HW-479)."""
import threading
import time
from gpiozero import RGBLED

COLORS = {
    'OFF': (0, 0, 0), 'BLUE': (0, 0, 1), 'GREEN': (0, 1, 0),
    'RED': (1, 0, 0), 'YELLOW': (1, 1, 0), 'PURPLE': (1, 0, 1),
}
VALID_STATES = {
    'READY', 'CHECKING', 'PASS', 'WORKING', 'FAIL', 'RECHECK',
    'COMPLETED', 'CANCELED', 'ERROR', 'OFFLINE',
}

class StatusRGBLED:
    def __init__(self, red=22, green=27, blue=17, blink_interval=0.5):
        self.led = RGBLED(red=red, green=green, blue=blue,
                          active_high=True, pwm=False)
        self.blink_interval = blink_interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.state = None
        self.led.off()

    def set_state(self, state):
        state = state.upper()
        if state not in VALID_STATES:
            raise ValueError(f'Unknown LED state: {state}')
        with self._lock:
            if state == self.state:
                return
            self._stop_pattern()
            self.state = state
            self._stop = threading.Event()
            if state == 'READY':
                self.led.color = COLORS['BLUE']
            elif state in ('PASS', 'WORKING'):
                self.led.color = COLORS['GREEN']
            elif state == 'FAIL':
                self.led.color = COLORS['RED']
            elif state == 'ERROR':
                self.led.color = COLORS['RED']
            elif state in ('CHECKING', 'RECHECK', 'OFFLINE'):
                color = {'CHECKING': 'BLUE', 'RECHECK': 'YELLOW',
                         'OFFLINE': 'PURPLE'}[state]
                self._start_pattern(self._blink, COLORS[color])
            elif state in ('COMPLETED', 'CANCELED'):
                color = 'GREEN' if state == 'COMPLETED' else 'RED'
                count = 3 if state == 'COMPLETED' else 2
                self._start_pattern(self._flash_then_hold, COLORS[color], count)

    def _start_pattern(self, target, *args):
        self._thread = threading.Thread(target=target, args=args,
                                        daemon=True)
        self._thread.start()

    def _stop_pattern(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.blink_interval * 2 + 0.2)
        self._thread = None
        self.led.off()

    def _blink(self, color):
        while not self._stop.is_set():
            self.led.color = color
            if self._stop.wait(self.blink_interval):
                break
            self.led.off()
            if self._stop.wait(self.blink_interval):
                break

    def _flash_then_hold(self, color, count):
        for _ in range(count):
            if self._stop.is_set():
                return
            self.led.color = color
            if self._stop.wait(0.25):
                return
            self.led.off()
            if self._stop.wait(0.25):
                return
        if not self._stop.is_set():
            self.led.color = color

    def close(self):
        with self._lock:
            self._stop_pattern()
            self.state = None
            self.led.close()
