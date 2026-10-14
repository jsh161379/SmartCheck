from gpiozero import PWMOutputDevice
from time import sleep

buzzer = PWMOutputDevice(
    pin=18,
    frequency=2000,
    initial_value=0
)

try:
    for i in range(3):
        print(f"부저 알림 {i + 1}/3")
        buzzer.value = 0.5
        sleep(0.3)
        buzzer.value = 0
        sleep(0.4)

finally:
    buzzer.off()
    buzzer.close()