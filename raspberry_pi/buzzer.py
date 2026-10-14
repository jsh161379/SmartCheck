"""SmartCheck: state-change melodies for a PWM-driven buzzer on BCM GPIO18.

Use only after confirming the 5V module I/O is safe for 3.3V Pi GPIO.
"""
import threading
from gpiozero import PWMOutputDevice


class StatusBuzzer:
    """Non-blocking state alerts; repeating a state does not replay its sound."""

    # (frequency in Hz, sounding duration in seconds, silence afterward in seconds)
    MELODIES = {
        "PASS": ((523, .13, .04), (659, .13, .04), (784, .22, 0)),
        "FAIL": ((784, .16, .06), (659, .16, .06), (523, .28, 0)),
        "RECHECK": ((659, .13, .08), (784, .13, .08), (659, .18, 0)),
        "COMPLETED": ((523, .12, .04), (659, .12, .04), (784, .12, .04), (1047, .35, 0)),
        "CANCELED": ((784, .14, .07), (523, .25, 0)),
        "ERROR": ((330, .24, .14), (330, .24, 0)),
        "OFFLINE": ((262, .12, .13), (262, .12, .13), (262, .12, 0)),
    }

    def __init__(self, pin=18, frequency=2000, duty_cycle=0.5):
        self._device = PWMOutputDevice(pin=pin, frequency=frequency, initial_value=0)
        self._duty_cycle = duty_cycle
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._state = None
        self._closed = False

    def set_state(self, state):
        state = str(state).upper()
        with self._lock:
            if self._closed:
                raise RuntimeError("Buzzer already closed")
            if state == self._state:
                return
            self._stop_current()
            self._state = state
            melody = self.MELODIES.get(state)
            if melody:
                self._stop = threading.Event()
                self._thread = threading.Thread(
                    target=self._play, args=(melody, self._stop), daemon=True
                )
                self._thread.start()

    def _play(self, melody, stop):
        try:
            for frequency, duration, pause in melody:
                if stop.is_set():
                    break
                self._device.frequency = frequency
                self._device.value = self._duty_cycle
                if stop.wait(duration):
                    break
                self._device.off()
                if pause and stop.wait(pause):
                    break
        finally:
            self._device.off()

    def _stop_current(self):
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join()  # All notes have bounded waits; stop interrupts them.
        self._thread = None
        self._device.off()

    def close(self):
        with self._lock:
            if not self._closed:
                self._stop_current()
                self._device.close()
                self._closed = True
