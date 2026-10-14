
# inspection.py
# SmartCheck 다중 프레임 검사 판정

TARGET_ITEMS = {"book", "cell phone", "scissors"}

FRAME_COUNT = 5
PRESENT_THRESHOLD = 4
MISSING_THRESHOLD = 1


def inspect_items(selected_items, frame_results):
    """
    selected_items:
        사용자가 선택한 검사 대상 목록

    frame_results:
        YOLO 추론 5회의 탐지 결과
        예: [{"book"}, {"book", "scissors"}, ...]
    """

    selected = set(selected_items)

    # 검사 대상 유효성 검사
    if not selected:
        raise ValueError("검사 대상이 선택되지 않았습니다.")

    if not selected.issubset(TARGET_ITEMS):
        raise ValueError("지원하지 않는 검사 대상이 포함되어 있습니다.")

    # 유효한 프레임 5회가 필요
    if len(frame_results) != FRAME_COUNT:
        raise ValueError("검사에는 정확히 5회의 탐지 결과가 필요합니다.")

    # 물품별 탐지 횟수 초기화
    counts = {item: 0 for item in sorted(selected)}

    # 각 프레임의 탐지 결과 집계
    for frame in frame_results:
        if not isinstance(frame, (set, list, tuple)):
            raise ValueError("탐지 결과 형식이 올바르지 않습니다.")

        detected = set(frame)

        if not detected.issubset(TARGET_ITEMS):
            raise ValueError("알 수 없는 물품이 탐지 결과에 포함되어 있습니다.")

        for item in selected:
            if item in detected:
                counts[item] += 1

    # 물품별 상태 분류
    detected_items = []
    uncertain_items = []
    missing_items = []

    for item, count in counts.items():
        if count >= PRESENT_THRESHOLD:
            detected_items.append(item)
        elif count <= MISSING_THRESHOLD:
            missing_items.append(item)
        else:
            uncertain_items.append(item)

    # 최종 검사 결과
    if missing_items:
        result = "FAIL"
    elif uncertain_items:
        result = "RECHECK"
    else:
        result = "PASS"

    return {
        "result": result,
        "selected_items": sorted(selected),
        "detected_items": detected_items,
        "uncertain_items": uncertain_items,
        "missing_items": missing_items,
        "counts": counts,
        "total_frames": FRAME_COUNT
    }
