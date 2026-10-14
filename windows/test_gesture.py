
import time
from pathlib import Path

import cv2
import mediapipe as mp

from gesture import classify_gesture


MODEL_PATH = (
    Path(__file__).resolve().parent
    / "models"
    / "hand_landmarker.task"
)

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17)
]


def draw_hand(frame, landmarks):
    height, width = frame.shape[:2]

    points = [
        (int(p.x * width), int(p.y * height))
        for p in landmarks
    ]

    for start, end in HAND_CONNECTIONS:
        cv2.line(
            frame, points[start], points[end],
            (0, 255, 0), 2
        )

    for point in points:
        cv2.circle(
            frame, point, 4,
            (0, 0, 255), -1
        )


def main():
    if not MODEL_PATH.is_file():
        print(f"모델 파일 없음: {MODEL_PATH}")
        return

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("웹캠 연결 실패")
        return

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

    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(
            options
        ) as landmarker:

            while True:
                ret, frame = cap.read()

                if not ret:
                    print("영상 입력 실패")
                    break

                rgb = cv2.cvtColor(
                    frame, cv2.COLOR_BGR2RGB
                )

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb
                )

                timestamp_ms = int(
                    (time.monotonic() - start_time) * 1000
                )
                timestamp_ms = max(
                    timestamp_ms,
                    previous_timestamp + 1
                )
                previous_timestamp = timestamp_ms

                result = landmarker.detect_for_video(
                    mp_image, timestamp_ms
                )

                gesture = "NO_HAND"

                if result.hand_landmarks:
                    landmarks = result.hand_landmarks[0]

                    gesture = classify_gesture(landmarks)
                    draw_hand(frame, landmarks)

                cv2.putText(
                    frame,
                    f"Gesture: {gesture}",
                    (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 255),
                    2
                )

                cv2.imshow(
                    "SmartCheck - Gesture Test",
                    frame
                )

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except Exception as error:
        print(f"오류: {error}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("테스트 종료")


if __name__ == "__main__":
    main()
