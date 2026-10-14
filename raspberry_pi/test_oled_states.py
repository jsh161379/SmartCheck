"""Manual OLED state preview. Run on Raspberry Pi."""
from time import sleep
from oled_display import OledDisplay


def main():
    oled = OledDisplay()
    examples = [
        ("READY", {}),
        ("CHECKING", {}),
        ("PASS", {}),
        ("FAIL", {"missing": ["scissors"]}),
        ("RECHECK", {"uncertain": ["cell phone"]}),
        ("WORKING", {"elapsed_seconds": 35}),
        ("COMPLETED", {"elapsed_seconds": 80}),
        ("CANCELED", {}),
        ("ERROR", {}),
        ("DISCONNECTED", {}),
    ]
    try:
        for state, kwargs in examples:
            print(f"Showing {state}: {kwargs}")
            oled.show(state, **kwargs)
            sleep(3)
        print("All OLED state previews displayed.")
    except KeyboardInterrupt:
        print("Interrupted.")
    finally:
        oled.clear()


if __name__ == "__main__":
    main()
