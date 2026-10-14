
import cv2
from ultralytics import YOLO

TARGET_CLASSES = {
    73: "book",
    67: "cell phone",
    76: "scissors"
}

TEST_FRAMES = 30


def main():
    print("=== SmartCheck 탐지 안정성 테스트 ===")

    model = YOLO("yolo11n.pt")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("웹캠 연결 실패")
        return

    counts = {name: 0 for name in TARGET_CLASSES.values()}
    valid_frames = 0

    print("세 물품을 카메라 앞에 놓으세요.")
    input("준비되면 Enter를 누르세요...")

    try:
        for i in range(TEST_FRAMES):
            ret, frame = cap.read()

            if not ret:
                print("프레임 읽기 실패")
                break

            results = model.predict(
                frame,
                device="cpu",
                imgsz=640,
                conf=0.25,
                classes=list(TARGET_CLASSES.keys()),
                verbose=False
            )

            detected = {
                TARGET_CLASSES[int(box.cls[0])]
                for box in results[0].boxes
            }

            for name in detected:
                counts[name] += 1

            valid_frames += 1

            print(
                f"{i + 1}/{TEST_FRAMES} "
                f"탐지: {', '.join(sorted(detected)) or '없음'}"
            )

    finally:
        cap.release()
        cv2.destroyAllWindows()

    print("\n=== 탐지 결과 ===")

    if valid_frames == 0:
        print("유효한 프레임이 없어 결과를 계산할 수 없습니다.")
        return

    for name, count in counts.items():
        ratio = count / valid_frames * 100

        print(
            f"{name}: {count}/{valid_frames} "
            f"({ratio:.1f}%)"
        )


if __name__ == "__main__":
    main()
