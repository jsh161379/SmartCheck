"""SmartCheck camera/YOLO/MediaPipe worker. All capture and inference stay off the GUI thread."""
import threading
import time
from pathlib import Path

import cv2
import mediapipe as mp
from ultralytics import YOLO
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from gesture import classify_gesture
from gesture_controller import GestureController
from inspection import inspect_items, FRAME_COUNT

BASE_DIR = Path(__file__).resolve().parent
TARGET_CLASSES = {73: 'book', 67: 'cell phone', 76: 'scissors'}

# MediaPipe Hands: 손목부터 손끝까지 21개 관절 연결
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)


def draw_hand_landmarks(image, landmarks):
    """화면에만 손 관절을 표시한다. YOLO 추론용 원본 프레임은 수정하지 않는다."""
    height, width = image.shape[:2]
    points = [(max(0, min(width - 1, int(p.x * width))),
               max(0, min(height - 1, int(p.y * height)))) for p in landmarks]
    for a, b in HAND_CONNECTIONS:
        cv2.line(image, points[a], points[b], (255, 210, 40), 2, cv2.LINE_AA)
    for index, point in enumerate(points):
        cv2.circle(image, point, 4 if index in (4, 8, 12, 16, 20) else 3,
                   (40, 70, 255), -1, cv2.LINE_AA)



class CameraWorker(QThread):
    frame_ready = Signal(QImage)
    gesture_changed = Signal(str)
    command_ready = Signal(str)
    inspection_ready = Signal(object)
    status_changed = Signal(str, str, str)  # camera, YOLO, error
    error_occurred = Signal(str)

    def __init__(self, parent=None, camera_index=0):
        super().__init__(parent)
        self.camera_index = camera_index
        self._lock = threading.Lock()
        self._running = True
        self._state = 'READY'
        self._selected = {'book', 'cell phone', 'scissors'}
        self._confidence = 0.50
        self._phase = None
        self._phase_start = 0.0
        self._hand_clear_start = None
        self._frames = []

    def configure(self, *, state=None, selected=None, confidence=None):
        """Safe to call from GUI thread. Controller remains GUI-thread-owned."""
        with self._lock:
            if selected is not None:
                self._selected = set(selected)
            if confidence is not None:
                self._confidence = float(confidence)
            if state is not None and state != self._state:
                self._state = state
                self._frames = []
                self._hand_clear_start = None
                if state == 'CHECKING':
                    self._phase = 'PREPARING'
                    self._phase_start = time.monotonic()
                else:
                    self._phase = None

    def stop(self):
        with self._lock:
            self._running = False
        self.wait(5000)

    def run(self):
        cap = None
        try:
            hand_model = BASE_DIR / 'models' / 'hand_landmarker.task'
            yolo_model = BASE_DIR / 'yolo11n.pt'
            if not hand_model.is_file():
                raise FileNotFoundError(f'MediaPipe 모델 없음: {hand_model}')
            if not yolo_model.is_file():
                raise FileNotFoundError(f'YOLO 모델 없음: {yolo_model}')
            yolo = YOLO(str(yolo_model))
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                raise RuntimeError('웹캠을 열 수 없습니다.')
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(hand_model)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            gesture_controller = GestureController()
            initial = time.monotonic()
            previous_ms = -1
            last_gesture = None
            with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
                # Report readiness only after the hand model is initialized as well.
                self.status_changed.emit('연결됨', '실행 중', '-')
                while True:
                    with self._lock:
                        if not self._running:
                            break
                        state = self._state
                        selected = set(self._selected)
                        conf = self._confidence
                    ok, original = cap.read()
                    if not ok:
                        raise RuntimeError('웹캠 프레임 수신 실패')
                    now = time.monotonic()
                    rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
                    timestamp_ms = max(int((now - initial) * 1000), previous_ms + 1)
                    previous_ms = timestamp_ms
                    hand_result = landmarker.detect_for_video(
                        mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms
                    )
                    hand_present = bool(hand_result.hand_landmarks)
                    gesture = classify_gesture(hand_result.hand_landmarks[0]) if hand_present else 'NONE'
                    if gesture != last_gesture:
                        self.gesture_changed.emit(gesture)
                        last_gesture = gesture
                    command = gesture_controller.update(gesture, now)
                    if command:
                        self.command_ready.emit(command)
                    predictions = yolo.predict(
                        original, device='cpu', imgsz=640, conf=conf,
                        classes=list(TARGET_CLASSES), verbose=False
                    )
                    detected = set()
                    drawn = original.copy()
                    for box in predictions[0].boxes:
                        cls = int(box.cls[0])
                        if cls not in TARGET_CLASSES:
                            continue
                        name = TARGET_CLASSES[cls]
                        detected.add(name)
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        cv2.rectangle(drawn, (x1, y1), (x2, y2), (44, 174, 75), 2)
                        cv2.putText(drawn, f'{name} {float(box.conf[0]):.2f}',
                                    (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.55, (44, 174, 75), 2)
                    # YOLO 바운딩 박스를 그린 뒤 손 관절을 추가한다.
                    if hand_present:
                        draw_hand_landmarks(drawn, hand_result.hand_landmarks[0])
                    # Guard inspection transitions with the same lock as configure().
                    inspection = None
                    with self._lock:
                        if self._state == 'CHECKING':
                            if self._phase == 'PREPARING':
                                if hand_present:
                                    self._hand_clear_start = None
                                elif now - self._phase_start >= 1.0:
                                    if self._hand_clear_start is None:
                                        self._hand_clear_start = now
                                    elif now - self._hand_clear_start >= 1.0:
                                        self._phase = 'INSPECTING'
                                        self._frames = []
                            elif self._phase == 'INSPECTING' and not hand_present:
                                self._frames.append(detected.copy())
                                if len(self._frames) == FRAME_COUNT:
                                    inspection = inspect_items(self._selected, self._frames)
                                    self._phase = 'WAIT_RESULT'
                        # Never run inspection if state was changed to CANCELED.
                    if inspection is not None:
                        self.inspection_ready.emit(inspection)
                    h, w, _ = drawn.shape
                    qimage = QImage(drawn.data, w, h, drawn.strides[0], QImage.Format_BGR888).copy()
                    self.frame_ready.emit(qimage)
        except Exception as exc:
            self.status_changed.emit('오류', '오류', str(exc))
            self.error_occurred.emit(str(exc))
        finally:
            if cap is not None:
                cap.release()
