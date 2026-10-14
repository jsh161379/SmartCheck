"""Manual hardware demonstration of all SmartCheck RGB states."""
from time import sleep
from rgb_led import StatusRGBLED

STATES = [
    ('READY', 2), ('CHECKING', 4), ('PASS', 2), ('WORKING', 2),
    ('FAIL', 2), ('RECHECK', 4), ('COMPLETED', 3),
    ('CANCELED', 3), ('ERROR', 2), ('OFFLINE', 4),
]

def main():
    indicator = StatusRGBLED()
    try:
        for state, duration in STATES:
            print(f'{state} ({duration}s)')
            indicator.set_state(state)
            sleep(duration)
        print('Test complete')
    except KeyboardInterrupt:
        print('\nTest interrupted')
    finally:
        indicator.close()

if __name__ == '__main__':
    main()
