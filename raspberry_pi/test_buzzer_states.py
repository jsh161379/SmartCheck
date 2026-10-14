"""Manual SmartCheck buzzer state test on Raspberry Pi."""
from time import sleep
from buzzer import StatusBuzzer


def main():
    buzzer = StatusBuzzer(pin=18, frequency=2000)
    states = ["READY", "PASS", "FAIL", "RECHECK", "WORKING",
              "COMPLETED", "CANCELED", "ERROR", "OFFLINE"]
    try:
        for state in states:
            print(f"Testing {state} ...", flush=True)
            buzzer.set_state(state)
            sleep(2)
        print("Buzzer state test finished")
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        buzzer.close()


if __name__ == "__main__":
    main()
