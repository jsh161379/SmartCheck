"""SmartCheck Raspberry Pi hardware integration (OLED + RGB LED + buzzer).

This module does not decide task transitions; the Windows TaskController does.
"""
from oled_display import OledDisplay
from rgb_led import StatusRGBLED
from buzzer import StatusBuzzer

VALID_STATES = frozenset({
    'READY', 'CHECKING', 'PASS', 'FAIL', 'RECHECK', 'WORKING',
    'COMPLETED', 'CANCELED', 'ERROR', 'OFFLINE',
})


class HardwareController:
    def __init__(self):
        self.oled = None
        self.rgb = None
        self.buzzer = None
        self.state = None
        self._closed = False
        try:
            self.oled = OledDisplay()
            self.rgb = StatusRGBLED()
            self.buzzer = StatusBuzzer()
        except Exception:
            self.close()
            raise

    def set_state(self, state, missing=None, uncertain=None,
                  elapsed_seconds=None, detail=None):
        if self._closed:
            raise RuntimeError('HardwareController is closed')
        state = str(state).upper()
        if state == 'DISCONNECTED':
            state = 'OFFLINE'
        if state not in VALID_STATES:
            raise ValueError(f'Unsupported hardware state: {state}')

        # OLED uses DISCONNECTED; RGB LED and buzzer use OFFLINE.
        oled_state = 'DISCONNECTED' if state == 'OFFLINE' else state
        self.oled.show(oled_state, missing=missing, uncertain=uncertain,
                       elapsed_seconds=elapsed_seconds, detail=detail)
        # These modules already ignore repeated state values. The OLED can
        # still refresh WORKING elapsed time without replaying alert sounds.
        self.rgb.set_state(state)
        self.buzzer.set_state(state)
        self.state = state

    def close(self):
        if self._closed:
            return
        self._closed = True
        # Stop background GPIO patterns before clearing OLED.
        for component in (self.buzzer, self.rgb):
            if component is not None:
                try:
                    component.close()
                except Exception as exc:
                    print(f'Hardware shutdown warning: {exc}')
        if self.oled is not None:
            try:
                self.oled.clear()
            except Exception as exc:
                print(f'OLED shutdown warning: {exc}')
