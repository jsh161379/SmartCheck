
import time
from pathlib import Path

import cv2
import mediapipe as mp


MODEL_PATH = (
    Path(__file__).resolve().parent
    / "models"
    / "hand_landmarker.task"
)

# 손 관절을 연결하는 선
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

    points = []

    for landmark in landmarks:
        x = int(landmark.x * width)
        y = int(landmark.y * height)
        points.append((x, y))

    # 관절 연결선
    for start, end in HAND_CONNECTIONS:
        cv2.line(
            frame,
            points[start],
            points[end],
            (0, 255, 0),
            2
        )

    # 관절 위치
    for point in points:
        cv2.circle(
            frame,
            point,
            4,
            (0, 0, 255),
            -1
        )


def main():
    print("=== SmartCheck MediaPipe 테스트 ===")

    if not MODEL_PATH.is_file():
        print(f"모델 파일이 없습니다: {MODEL_PATH}")
        return

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("오류: 웹캠을 열 수 없습니다.")
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
                    print("오류: 영상 입력 실패")
                    break

                # OpenCV BGR → MediaPipe RGB
                rgb_frame = cv2.cvtColor(
                    frame, cv2.COLOR_BGR2RGB
                )

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb_frame
                )

                # VIDEO 모드에서는 증가하는 타임스탬프 필요
                timestamp_ms = int(
                    (time.monotonic() - start_time) * 1000
                )
                timestamp_ms = max(
                    timestamp_ms, previous_timestamp + 1
                )
                previous_timestamp = timestamp_ms

                result = landmarker.detect_for_video(
                    mp_image,
                    timestamp_ms
                )

                hand_count = len(result.hand_landmarks)

                for hand in result.hand_landmarks:
                    draw_hand(frame, hand)

                cv2.putText(
                    frame,
                    f"Hands: {hand_count}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2
                )

                cv2.imshow(
                    "SmartCheck - MediaPipe Hands",
                    frame
                )

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except Exception as error:
        print(f"MediaPipe 오류: {error}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("테스트 종료")


if __name__ == "__main__":
    main()
