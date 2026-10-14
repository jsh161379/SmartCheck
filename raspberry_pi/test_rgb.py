from gpiozero import RGBLED
from time import sleep

led = RGBLED(
    red=22,
    green=27,
    blue=17,
    active_high=True,
    pwm=False
)

try:
    colors = [
        ("RED", (1, 0, 0)),
        ("GREEN", (0, 1, 0)),
        ("BLUE", (0, 0, 1)),
        ("YELLOW", (1, 1, 0)),
        ("PURPLE", (1, 0, 1)),
        ("OFF", (0, 0, 0)),
    ]

    for name, color in colors:
        print(f"Testing: {name}")
        led.color = color
        sleep(2)

finally:
    led.off()
    led.close()
    print("RGB LED test finished")
