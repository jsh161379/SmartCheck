
import cv2
import time
from ultralytics import YOLO


# 검사 대상: COCO 클래스 ID
TARGET_CLASSES = {
    73: "book",
    67: "cell phone",
    76: "scissors"
}


def main():
    print("=== SmartCheck 웹캠 탐지 테스트 ===")

    # YOLO 모델 로드
    model = YOLO("yolo11n.pt")

    # Windows 웹캠 연결
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("오류: 웹캠을 열 수 없습니다.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    previous_time = time.perf_counter()

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("오류: 웹캠 영상 입력 실패")
                break

            # YOLO CPU 추론
            results = model.predict(
                frame,
                device="cpu",
                imgsz=640,
                conf=0.25,
                classes=list(TARGET_CLASSES.keys()),
                verbose=False
            )

            # 탐지 결과 표시
            for box in results[0].boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])

                x1, y1, x2, y2 = map(
                    int, box.xyxy[0].tolist()
                )

                name = TARGET_CLASSES[class_id]

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
                    (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            # 실제 처리 FPS
            current_time = time.perf_counter()
            fps = 1.0 / max(
                current_time - previous_time, 0.000001
            )
            previous_time = current_time

            cv2.putText(
                frame,
                f"FPS: {fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )

            cv2.imshow("SmartCheck - YOLO Webcam", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("사용자가 검사를 종료했습니다.")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("웹캠 종료 완료")


if __name__ == "__main__":
    main()
