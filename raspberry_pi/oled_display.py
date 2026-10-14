"""SmartCheck SSD1306 OLED display: larger, two-line status messages."""
from PIL import ImageFont
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
WIDTH, HEIGHT = 128, 64
TITLES = {
    'READY': 'READY', 'CHECKING': 'CHECKING', 'PASS': 'PASS',
    'FAIL': 'FAIL', 'RECHECK': 'RECHECK', 'WORKING': 'WORKING',
    'COMPLETED': 'DONE', 'CANCELED': 'CANCELED', 'ERROR': 'ERROR',
    'DISCONNECTED': 'OFFLINE',
}
MESSAGES = {
    'READY': 'Show thumbs up', 'CHECKING': 'Checking items',
    'PASS': 'All items OK', 'FAIL': 'Missing items',
    'RECHECK': 'Check again', 'WORKING': 'Task in progress',
    'COMPLETED': 'Task completed', 'CANCELED': 'Task canceled',
    'ERROR': 'System error', 'DISCONNECTED': 'Connection lost',
}


def _width(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _font_to_fit(draw, text, max_width, preferred, minimum):
    for size in range(preferred, minimum - 1, -1):
        font = ImageFont.truetype(FONT_PATH, size)
        if _width(draw, text, font) <= max_width:
            return font
    return ImageFont.truetype(FONT_PATH, minimum)


def _shorten(draw, text, font, max_width):
    if _width(draw, text, font) <= max_width:
        return text
    while text and _width(draw, text + '...', font) > max_width:
        text = text[:-1]
    return text + '...'


def _lines(draw, message, font, max_width=120):
    # Wrap at spaces, but split long words when necessary.
    words = str(message).split()
    lines = []
    current = ''
    for word in words:
        candidate = (current + ' ' + word).strip()
        if _width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ''
        while word and _width(draw, word, font) > max_width:
            cut = len(word)
            while cut > 1 and _width(draw, word[:cut], font) > max_width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    if not lines:
        return ['']
    if len(lines) > 2:
        lines = [lines[0], _shorten(draw, ' '.join(lines[1:]), font, max_width)]
    return lines


class OledDisplay:
    def __init__(self, address=0x3C):
        serial = i2c(port=1, address=address)
        self.device = ssd1306(serial, width=WIDTH, height=HEIGHT)

    def show(self, state, missing=None, uncertain=None, elapsed_seconds=None, detail=None):
        state = str(state).upper()
        if state not in TITLES:
            raise ValueError(f'Unsupported OLED state: {state}')

        message = MESSAGES[state]
        if state == 'FAIL' and missing:
            message = 'Missing: ' + ', '.join(missing)
        elif state == 'RECHECK' and uncertain:
            message = 'Uncertain: ' + ', '.join(uncertain)
        elif state in ('WORKING', 'COMPLETED') and elapsed_seconds is not None:
            seconds = max(0, int(elapsed_seconds))
            message = f'Time: {seconds // 60:02d}:{seconds % 60:02d}'
        elif detail:
            message = str(detail)

        with canvas(self.device) as draw:
            title = TITLES[state]
            title_font = _font_to_fit(draw, title, 120, 24, 16)
            title_box = draw.textbbox((0, 0), title, font=title_font)
            title_x = (WIDTH - _width(draw, title, title_font)) // 2
            title_y = 3 - title_box[1]
            draw.text((title_x, title_y), title, font=title_font, fill='white')
            draw.line((5, 33, 123, 33), fill='white')

            # 13px bold text, up to two lines, centered below divider.
            message_font = ImageFont.truetype(FONT_PATH, 13)
            lines = _lines(draw, message, message_font)
            line_ys = [37] if len(lines) == 1 else [35, 49]
            for line, y in zip(lines, line_ys):
                line = _shorten(draw, line, message_font, 120)
                box = draw.textbbox((0, 0), line, font=message_font)
                x = (WIDTH - _width(draw, line, message_font)) // 2
                draw.text((x, y - box[1]), line, font=message_font, fill='white')

    def clear(self):
        self.device.clear()
