"""SmartCheck hand gesture classifier (MediaPipe 21 normalized landmarks).

Classification is deliberately conservative for CANCEL (fist). The existing
GestureController handles the 0.7 s hold and re-arm policy separately.
"""
import math

THUMBS_UP = 'THUMBS_UP'
OPEN_PALM = 'OPEN_PALM'
FIST = 'FIST'
NONE = 'NONE'


def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def calculate_angle(a, b, c):
    ab = (a.x - b.x, a.y - b.y)
    cb = (c.x - b.x, c.y - b.y)
    norm = math.hypot(*ab) * math.hypot(*cb)
    if norm < 1e-9:
        return 0.0
    cosine = max(-1.0, min(1.0, (ab[0]*cb[0] + ab[1]*cb[1]) / norm))
    return math.degrees(math.acos(cosine))


def finger_state(landmarks, mcp, pip, dip, tip):
    """Use both joint bend and fingertip-to-knuckle distance.

    Distances are ratios of the same finger, so hand size is irrelevant.
    """
    p = landmarks
    pip_angle = calculate_angle(p[mcp], p[pip], p[dip])
    dip_angle = calculate_angle(p[pip], p[dip], p[tip])
    tip_to_mcp = distance(p[tip], p[mcp])
    pip_to_mcp = max(distance(p[pip], p[mcp]), 1e-6)
    ratio = tip_to_mcp / pip_to_mcp
    if pip_angle >= 148 and (dip_angle >= 132 or ratio >= 2.05) and ratio >= 1.75:
        return 'EXTENDED'
    if pip_angle <= 128 or ratio <= 1.55:
        return 'FOLDED'
    return 'UNKNOWN'


def thumb_state(landmarks):
    """Thumb spread + joint straightness; tolerate mildly bent thumb."""
    p = landmarks
    ip_angle = calculate_angle(p[2], p[3], p[4])
    mcp_angle = calculate_angle(p[1], p[2], p[3])
    spread = distance(p[4], p[5]) / max(distance(p[2], p[5]), 1e-6)
    # An extended thumb can have a somewhat bent MCP depending on camera angle.
    if ip_angle >= 145 and mcp_angle >= 115 and spread >= 1.18:
        return 'EXTENDED'
    if ip_angle <= 125 or spread <= 0.95:
        return 'FOLDED'
    return 'UNKNOWN'


def is_thumb_pointing_up(landmarks):
    # Require visible upward displacement, but tolerate hand tilt.
    tip, base = landmarks[4], landmarks[2]
    dx, dy = tip.x - base.x, tip.y - base.y
    return dy < -max(0.025, abs(dx) * 0.20)


def classify_gesture(landmarks):
    if landmarks is None or len(landmarks) != 21:
        return NONE
    fingers = [finger_state(landmarks, *indices) for indices in (
        (5, 6, 7, 8), (9, 10, 11, 12),
        (13, 14, 15, 16), (17, 18, 19, 20)
    )]
    extended = fingers.count('EXTENDED')
    folded = fingers.count('FOLDED')
    thumb = thumb_state(landmarks)

    # Palm: all four long fingers extended; thumb position varies by user.
    if extended == 4:
        return OPEN_PALM

    # Thumbs-up: three folded fingers suffice, but none may be extended.
    if folded >= 3 and extended == 0 and thumb == 'EXTENDED' and is_thumb_pointing_up(landmarks):
        return THUMBS_UP

    # Fist: avoid accidental CANCEL on an ambiguous thumb or a thumbs-up.
    # Four folded fingers plus a tucked thumb (or thumb near the index base).
    thumb_tucked = distance(landmarks[4], landmarks[5]) <= distance(landmarks[2], landmarks[5]) * 1.15
    if folded == 4 and extended == 0 and (thumb == 'FOLDED' or (thumb == 'UNKNOWN' and thumb_tucked)):
        return FIST

    return NONE
