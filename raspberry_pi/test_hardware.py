"""Manual Raspberry Pi integration test for SmartCheck indicators."""
from time import sleep
from hardware_controller import HardwareController


CASES = [
    ('READY', {}, 2),
    ('CHECKING', {}, 3),
    ('PASS', {}, 2),
    ('WORKING', {'elapsed_seconds': 5}, 2),
    ('WORKING', {'elapsed_seconds': 7}, 2),  # refresh without another alert
    ('FAIL', {'missing': ['scissors']}, 3),
    ('RECHECK', {'uncertain': ['cell phone']}, 3),
    ('COMPLETED', {'elapsed_seconds': 25}, 3),
    ('CANCELED', {}, 3),
    ('ERROR', {'detail': 'Camera error'}, 3),
    ('OFFLINE', {}, 3),
    ('READY', {}, 2),
]


def main():
    hardware = HardwareController()
    try:
        for state, options, seconds in CASES:
            print(f'Hardware: {state}, options={options}')
            hardware.set_state(state, **options)
            sleep(seconds)
        print('Hardware integration test finished.')
    except KeyboardInterrupt:
        print('\nStopped by user.')
    finally:
        hardware.close()


if __name__ == '__main__':
    main()
