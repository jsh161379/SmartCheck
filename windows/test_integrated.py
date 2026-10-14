
import time
from pathlib import Path

import cv2
import mediapipe as mp
from ultralytics import YOLO

from inspection import inspect_items, FRAME_COUNT
from gesture import classify_gesture
from gesture_controller import GestureController
from task_controller import TaskController, TaskState


# --------------------------------------------------
# 설정
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / "models" / "hand_landmarker.task"
YOLO_MODEL_PATH = BASE_DIR / "yolo11n.pt"

TARGET_CLASSES = {
    73: "book",
    67: "cell phone",
    76: "scissors"
}

ITEM_OPTIONS = {
    "1": "book",
    "2": "cell phone",
    "3": "scissors"
}

# 검사 시작 후 최소 대기 시간
PREPARATION_SECONDS = 1.0

# 손이 연속으로 감지되지 않아야 하는 시간
HAND_CLEAR_SECONDS = 1.0


# --------------------------------------------------
# 검사 대상 선택
# --------------------------------------------------

def select_items():
    print("\n=== SmartCheck 검사 대상 선택 ===")
    print("1. 책")
    print("2. 휴대폰")
    print("3. 가위")
    print("예: 1,2,3 (가위가 없으면 1,2)")

    choice = input("검사할 물품 번호: ").strip()

    numbers = [
        part.strip()
        for part in choice.split(",")
    ]

    if not choice or any(
        number not in ITEM_OPTIONS
        for number in numbers
    ):
        print("오류: 검사 대상을 올바르게 선택해 주세요.")
        return None

    selected_items = {
        ITEM_OPTIONS[number]
        for number in numbers
    }

    print("선택된 검사 대상:", sorted(selected_items))

    return selected_items


# --------------------------------------------------
# 메인 프로그램
# --------------------------------------------------

def main():

    selected_items = select_items()

    if not selected_items:
        return

    print("키보드: SPACE 시작 / C 취소 / P 완료 / N 다음 작업 / E 오류 복구 / Q 종료")

    # MediaPipe 모델 확인
    if not MODEL_PATH.is_file():
        print(f"MediaPipe 모델 파일 없음: {MODEL_PATH}")
        return

    # 검사 상태 제어
    controller = TaskController()
    controller.set_selected_items(selected_items)

    # 제스처 지속 시간 및 중복 방지
    gesture_controller = GestureController()

    print("\nYOLO 모델 로딩 중...")

    yolo = YOLO(str(YOLO_MODEL_PATH))

    # 웹캠 열기
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("오류: 웹캠 연결 실패")
        return

    # MediaPipe 설정
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(MODEL_PATH)
        ),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )

    start_time = time.monotonic()
    previous_timestamp = -1

    # CHECKING 상태 내부 진행 단계: PREPARING / INSPECTING
    inspection_phase = None

    # 검사 준비 시간
    preparation_start = None

    # 손이 사라진 시점
    hand_clear_start = None

    # 5회 검사 결과 저장
    frame_results = []

    # 화면 표시용
    last_gesture = "NONE"
    last_command = "NONE"

    # --------------------------------------------------
    # 공통 명령 처리
    # --------------------------------------------------

    def execute_command(command, source="GESTURE"):

        nonlocal preparation_start
        nonlocal hand_clear_start
        nonlocal frame_results
        nonlocal last_command
        nonlocal inspection_phase

        accepted = controller.handle_command(command, source=source)

        if not accepted:
            print(
                f"명령 무시: {command} / "
                f"{controller.state.value}"
            )
            return

        last_command = command

        if command == "START":

            inspection_phase = "PREPARING"
            preparation_start = time.monotonic()
            hand_clear_start = None
            frame_results = []

            print("\n검사 준비: 손을 치워 주세요.")

        elif command == "CANCEL":

            frame_results = []
            preparation_start = None
            hand_clear_start = None

            inspection_phase = None
            print("작업 취소: 관리자 NEXT_TASK 입력 전까지 CANCELED 유지")

        elif command == "COMPLETE":
            print(f"작업 완료: {controller.work_duration:.1f}초")

        elif command == "NEXT_TASK":
            inspection_phase = None
            print("관리자 입력: 다음 작업 대기(READY)")

        elif command == "RECOVER":
            inspection_phase = None
            print("관리자 입력: 오류 복구(READY)")

    # --------------------------------------------------
    # 영상 처리
    # --------------------------------------------------

    try:

        with mp.tasks.vision.HandLandmarker.create_from_options(
            options
        ) as landmarker:

            while True:

                ret, frame = cap.read()

                if not ret:
                    print("오류: 영상 입력 실패")
                    controller.set_error()
                    break

                now = time.monotonic()

                # ------------------------------------------
                # 1. YOLO 객체 탐지
                # ------------------------------------------

                results = yolo.predict(
                    frame,
                    device="cpu",
                    imgsz=640,
                    conf=0.25,
                    classes=list(TARGET_CLASSES.keys()),
                    verbose=False
                )

                detected = set()

                for box in results[0].boxes:

                    class_id = int(box.cls[0])

                    if class_id not in TARGET_CLASSES:
                        continue

                    name = TARGET_CLASSES[class_id]
                    confidence = float(box.conf[0])

                    detected.add(name)

                    x1, y1, x2, y2 = map(
                        int,
                        box.xyxy[0].tolist()
                    )

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        f"{name} {confidence:.2f}",
                        (x1, max(20, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )

                # ------------------------------------------
                # 2. MediaPipe 손 관절 인식
                # ------------------------------------------

                rgb = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb
                )

                timestamp_ms = int(
                    (now - start_time) * 1000
                )

                timestamp_ms = max(
                    timestamp_ms,
                    previous_timestamp + 1
                )

                previous_timestamp = timestamp_ms

                hand_result = landmarker.detect_for_video(
                    mp_image,
                    timestamp_ms
                )

                hand_detected = bool(
                    hand_result.hand_landmarks
                )

                gesture = "NONE"

                if hand_detected:

                    landmarks = hand_result.hand_landmarks[0]

                    gesture = classify_gesture(
                        landmarks
                    )

                last_gesture = gesture

                # ------------------------------------------
                # 3. 제스처 명령 처리
                # ------------------------------------------

                command = gesture_controller.update(
                    gesture,
                    time.monotonic()
                )

                if command:
                    execute_command(command)

                
                # ------------------------------------------
                # 4. 검사 준비
                # ------------------------------------------

                if controller.state == TaskState.CHECKING and inspection_phase == "PREPARING":

                    current_time = time.monotonic()
                    elapsed = current_time - preparation_start

                    # 손이 감지되면 손 치우기 확인 시간 초기화
                    if hand_detected:
                        hand_clear_start = None

                    # 최소 준비 시간이 지난 후 손 없음 확인
                    elif elapsed >= PREPARATION_SECONDS:

                        if hand_clear_start is None:
                            hand_clear_start = current_time
                            print("손 미감지: 연속 확인 시작")

                        clear_elapsed = (
                            current_time - hand_clear_start
                        )

                        if clear_elapsed >= HAND_CLEAR_SECONDS:

                            print(
                                "[검사 시작 조건 확인] "
                                f"hand_detected={hand_detected}, "
                                f"손 미감지 시간={clear_elapsed:.2f}초"
                            )

                            if controller.state == TaskState.CHECKING:
                                inspection_phase = "INSPECTING"
                                frame_results = []
                                hand_clear_start = None

                                print(
                                    "손 치우기 확인 완료. "
                                    "검사를 시작합니다."
                                )

                # ------------------------------------------
                # 5. 다중 프레임 검사
                # ------------------------------------------

                elif controller.state == TaskState.CHECKING and inspection_phase == "INSPECTING":

                    if hand_detected:

                        print(
                            "손 감지: 검사 프레임 수집 대기"
                        )

                    else:

                        frame_results.append(
                            detected.copy()
                        )

                        print(
                            f"[검사 {len(frame_results)}/{FRAME_COUNT}] "
                            f"탐지: {sorted(detected)}"
                        )

                        # 5회 수집 완료
                        if len(frame_results) >= FRAME_COUNT:

                            result = inspect_items(
                                selected_items,
                                frame_results
                            )

                            if controller.finish_inspection(result["result"]):
                                inspection_phase = None
                                if controller.state == TaskState.WORKING:
                                    print("PASS: 작업 시작 / 타이머 작동")
                                else:
                                    print(f"{controller.state.value}: 엄지척으로 재검사 가능")

                            print("\n=== 검사 결과 ===")
                            print(
                                "결과:",
                                result["result"]
                            )
                            print(
                                "탐지 횟수:",
                                result["counts"]
                            )
                            print(
                                "누락 물품:",
                                result["missing_items"]
                            )
                            print(
                                "불확실 물품:",
                                result["uncertain_items"]
                            )

                            frame_results = []

                # ------------------------------------------
                # 6. 화면 표시
                # ------------------------------------------

                state_text = controller.state.value
                result_text = controller.last_result or "-"

                cv2.putText(
                    frame,
                    f"State: {state_text}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2
                )

                cv2.putText(
                    frame,
                    f"Gesture: {last_gesture}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 255),
                    2
                )

                cv2.putText(
                    frame,
                    f"Command: {last_command}",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 255),
                    2
                )

                cv2.putText(
                    frame,
                    f"Result: {result_text}",
                    (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 0),
                    2
                )

                # 검사 준비 상태 표시
                if controller.state == TaskState.CHECKING and inspection_phase == "PREPARING":

                    remaining = max(
                        0,
                        PREPARATION_SECONDS -
                        (time.monotonic() - preparation_start)
                    )

                    if remaining > 0:
                        message = (
                            f"Remove hand: {remaining:.1f}s"
                        )

                    elif hand_detected:
                        message = "Waiting for hand removal"

                    else:
                        message = "Checking hand clearance"

                    cv2.putText(
                        frame,
                        message,
                        (10, 150),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (0, 255, 255),
                        2
                    )

                # 검사 진행 상태 표시
                elif controller.state == TaskState.CHECKING and inspection_phase == "INSPECTING":

                    cv2.putText(
                        frame,
                        f"Frames: {len(frame_results)}/{FRAME_COUNT}",
                        (10, 150),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (0, 255, 255),
                        2
                    )

                # 작업 경과 시간 표시
                elapsed_work = controller.elapsed_seconds()
                if elapsed_work is not None:
                    cv2.putText(
                        frame, f"Work: {elapsed_work:.1f}s", (10, 210),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
                    )

                # 현재 손 감지 여부
                cv2.putText(
                    frame,
                    f"Hand detected: {hand_detected}",
                    (10, 180),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2
                )

                cv2.imshow(
                    "SmartCheck - Integrated Test",
                    frame
                )

                # ------------------------------------------
                # 7. 키보드 명령
                # ------------------------------------------

                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break

                elif key == 32:
                    execute_command("START", source="GUI")

                elif key == ord("c"):
                    execute_command("CANCEL", source="GUI")

                elif key == ord("p"):
                    execute_command("COMPLETE", source="GUI")

                elif key == ord("n"):
                    execute_command("NEXT_TASK", source="GUI")

                elif key == ord("e"):
                    execute_command("RECOVER", source="GUI")

    except Exception as error:

        controller.set_error()
        print(f"통합 테스트 오류: {error}")

    finally:

        cap.release()
        cv2.destroyAllWindows()

        print("SmartCheck 종료")


if __name__ == "__main__":
    main()
