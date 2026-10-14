"""Standalone SmartCheck melody preview."""
from time import sleep
from buzzer import StatusBuzzer

STATES = ("PASS", "FAIL", "RECHECK", "COMPLETED", "CANCELED", "ERROR", "OFFLINE")

buzzer = StatusBuzzer()
try:
    for state in STATES:
        print(f"Melody: {state}")
        buzzer.set_state(state)
        sleep(2)
    buzzer.set_state("READY")
    print("Finished")
except KeyboardInterrupt:
    print("Interrupted")
finally:
    buzzer.close()
