
# test_live_inspection.py

import cv2
from ultralytics import YOLO
from inspection import inspect_items, FRAME_COUNT

TARGET_CLASSES = {
    73: "book",
    67: "cell phone",
    76: "scissors"
}


def select_items():
    print("\n=== 검사 대상 선택 ===")
    print("1. 책 (book)")
    print("2. 휴대폰 (cell phone)")
    print("3. 가위 (scissors)")
    print("예: 1,2 또는 1,2,3")

    choice = input("검사할 물품 번호: ").strip()

    options = {
        "1": "book",
        "2": "cell phone",
        "3": "scissors"
    }

    numbers = [num.strip() for num in choice.split(",")]

    if not choice or any(num not in options for num in numbers):
        print("오류: 올바른 검사 대상을 선택하세요.")
        return None

    return {options[num] for num in numbers}


def main():
    print("=== SmartCheck 실제 웹캠 검사 ===")

    selected_items = select_items()

    if not selected_items:
        print("검사 대상이 없어 프로그램을 종료합니다.")
        return

    print("선택한 검사 대상:", sorted(selected_items))

    model = YOLO("yolo11n.pt")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("오류: 웹캠 연결 실패")
        return

    print("SPACE: 검사 실행 / Q: 종료")

    inspecting = False
    frame_results = []
    last_result = "READY"

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("오류: 영상 입력 중단")
                break

            results = model.predict(
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
                name = TARGET_CLASSES[class_id]
                confidence = float(box.conf[0])

                detected.add(name)

                x1, y1, x2, y2 = map(
                    int, box.xyxy[0].tolist()
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
                    (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            if inspecting:
                frame_results.append(detected)

                progress = len(frame_results)
                print(
                    f"검사 {progress}/{FRAME_COUNT}: "
                    f"{sorted(detected)}"
                )

                if progress == FRAME_COUNT:
                    result = inspect_items(
                        selected_items,
                        frame_results
                    )

                    last_result = result["result"]

                    print("\n=== 검사 결과 ===")
                    print("최종 판정:", last_result)
                    print("선택 물품:", result["selected_items"])
                    print("탐지 횟수:", result["counts"])
                    print("누락 물품:", result["missing_items"])
                    print("불확실 물품:", result["uncertain_items"])
                    print("================\n")

                    inspecting = False
                    frame_results = []

            status = (
                f"INSPECTING {len(frame_results)}/{FRAME_COUNT}"
                if inspecting else f"RESULT: {last_result}"
            )

            cv2.putText(
                frame,
                status,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

            cv2.imshow("SmartCheck Live Inspection", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == 32 and not inspecting:
                inspecting = True
                frame_results = []
                print("\n검사 시작!")

    except KeyboardInterrupt:
        print("사용자가 종료했습니다.")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("웹캠 종료 완료")


if __name__ == "__main__":
    main()
