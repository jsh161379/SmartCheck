
from ultralytics import YOLO
import torch

def main():
    print("=== SmartCheck YOLO 테스트 ===")

    # CPU 실행 환경 확인
    print(f"PyTorch 버전: {torch.__version__}")
    print(f"실행 장치: CPU")

    # COCO 사전 학습 YOLO 모델 불러오기
    model = YOLO("yolo11n.pt")

    # Ultralytics 제공 예제 이미지로 추론
    results = model.predict(
        source="https://ultralytics.com/images/bus.jpg",
        device="cpu",
        imgsz=640,
        conf=0.25,
        verbose=False
    )

    # 탐지 결과 출력
    for result in results:
        print("\n탐지된 객체:")

        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            name = model.names[class_id]

            print(f"- {name}: {confidence:.2f}")

    print("\nYOLO 테스트 완료!")


if __name__ == "__main__":
    main()
