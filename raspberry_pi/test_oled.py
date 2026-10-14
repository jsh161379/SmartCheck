from time import sleep

from PIL import ImageFont
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas


OLED_WIDTH = 128
OLED_HEIGHT = 64

# Raspberry Pi 기본 글꼴
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def main():
    serial = i2c(port=1, address=0x3C)
    device = ssd1306(serial, width=OLED_WIDTH, height=OLED_HEIGHT)

    # 글자 크기
    title_font = ImageFont.truetype(FONT_PATH, 25)
    message_font = ImageFont.truetype(FONT_PATH, 10)

    title = "READY"
    message = "Waiting for start"

    with canvas(device) as draw:
        # 제목 가운데 정렬
        title_box = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_box[2] - title_box[0]
        title_x = (OLED_WIDTH - title_width) // 2

        draw.text(
            (title_x, 5),
            title,
            font=title_font,
            fill="white"
        )

        # 구분선
        draw.line((8, 40, 120, 40), fill="white")

        # 안내 문구 가운데 정렬
        msg_box = draw.textbbox((0, 0), message, font=message_font)
        msg_width = msg_box[2] - msg_box[0]
        msg_x = (OLED_WIDTH - msg_width) // 2

        draw.text(
            (msg_x, 47),
            message,
            font=message_font,
            fill="white"
        )

    print("OLED READY 화면 표시 중...")

    try:
        while True:
            sleep(1)

    except KeyboardInterrupt:
        print("\nOLED 테스트 종료")

    finally:
        device.clear()


if __name__ == "__main__":
    main()
