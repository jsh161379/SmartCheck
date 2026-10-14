# SmartCheck

**YOLO 기반 준비물 누락 감지 및 비접촉 작업 관리 시스템**

SmartCheck는 작업 시작 전 필수 준비물의 누락 여부를 검사하고, 검사 결과에 따라 작업 진행을 제어하는 시스템입니다.

Windows PC에서 YOLO 객체 탐지와 MediaPipe 손동작 인식을 수행하며, Raspberry Pi의 OLED·RGB LED·부저를 통해 작업자에게 현재 상태를 안내합니다. 관리자는 PySide6 GUI에서 작업 상태와 검사 이력, 통계 및 PDF 보고서를 확인할 수 있습니다.

## 1. 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 개발 형태 | 개인 프로젝트 |
| 개발 목표 | 준비물 누락 방지 및 비접촉 작업 관리 |
| 개발 환경 | Windows PC, Raspberry Pi 4B |
| 검사 대상 | 책, 휴대폰, 가위 |
| 통신 방식 | HTTP/JSON 기반 REST API |
| 데이터 저장 | SQLite |

## 2. 기술 스택

| 구분 | 기술 |
|---|---|
| 언어 | Python |
| 객체 탐지 | Ultralytics YOLO11n |
| 영상 처리 | OpenCV |
| 손동작 인식 | MediaPipe Hands Tasks API |
| Windows GUI | PySide6 (Qt) |
| 데이터베이스 | SQLite |
| 보고서 | ReportLab |
| Raspberry Pi 서버 | Flask |
| 하드웨어 | SSD1306 OLED, RGB LED, 부저 |
| 통신 | HTTP/JSON REST API |

## 3. 시스템 구성

```text
                 웹캠
                  │
                  ▼
             Windows PC
       ┌──────────────────────┐
       │ YOLO 준비물 검사     │
       │ MediaPipe 손동작 인식│
       │ TaskController       │
       │ PySide6 관리자 GUI   │
       │ SQLite / PDF 보고서  │
       └──────────┬───────────┘
                  │
             HTTP / JSON
                  │
                  ▼
            Raspberry Pi 4B
       ┌──────────────────────┐
       │ Flask REST API       │
       │ SSD1306 OLED         │
       │ RGB LED              │
       │ 부저                 │
       └──────────────────────┘
```

Windows PC가 작업 상태를 결정하고, Raspberry Pi는 전달받은 상태를 표시합니다.

## 4. 주요 기능

### 준비물 누락 검사

- YOLO11n을 이용한 책·휴대폰·가위 탐지
- 검사 대상 선택 및 탐지 신뢰도 설정
- 5프레임 기반 PASS / FAIL / RECHECK 판정
- 누락 및 불확실 물품 구분
- 검사 증거 이미지 저장
- 검사 프리셋 저장·불러오기·삭제

### 비접촉 작업 제어

| 손동작 | 기능 |
|---|---|
| 엄지척 | 검사 시작 및 재검사 |
| 손바닥 | 작업 완료 |
| 주먹 | 검사 또는 작업 취소 |

동일한 손동작을 약 0.7초 이상 유지하면 명령을 실행하며, 연속 입력으로 인한 중복 실행을 방지합니다.

### 작업 상태 관리

```text
READY → CHECKING → PASS → WORKING → COMPLETED
            │                    └→ CANCELED
            ├→ FAIL → 재검사
            ├→ RECHECK → 재검사
            └→ CANCELED
```

- 모든 필수 물품이 확인된 경우에만 작업 진행 허용
- 작업 시작부터 완료 또는 취소까지 소요 시간 관리
- 작업 완료·취소 후 관리자 조작으로 다음 작업 준비
- 시스템 오류와 물품 누락을 별도 처리

### Raspberry Pi 작업자 안내

- OLED: 작업 상태, 누락 물품 및 작업 시간 표시
- RGB LED: 상태별 색상 및 점멸 패턴
- 부저: 검사 결과 및 작업 종료 알림
- 통신 장애 감지 및 재연결 후 상태 동기화

### 관리자 GUI 및 이력 관리

- 실시간 카메라 및 객체 탐지 결과 확인
- 검사 대상과 프리셋 관리
- 작업 상태 및 Raspberry Pi 연결 상태 모니터링
- 검사·작업 이력 조회
- PASS / FAIL / RECHECK 통계
- 물품별 누락·불확실 발생 횟수 집계
- PDF 보고서 생성

## 5. 프로젝트 구조

```text
SmartCheck/
├── windows/             # Windows PC 프로그램
├── raspberry_pi/        # Raspberry Pi 프로그램
├── docs/                # 화면 캡처 및 프로젝트 자료
├── .gitignore
└── README.md
```

## 6. 실행 환경

### Windows PC

```powershell
cd windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main_gui.py
```

별도로 YOLO11n 및 MediaPipe 모델 파일을 준비해야 합니다.

### Raspberry Pi

```bash
cd raspberry_pi
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install -r requirements.txt
python api_server.py
```

Raspberry Pi에서는 사용 중인 OLED·RGB LED·부저의 실제 배선과 GPIO 설정을 확인해야 합니다. Windows PC와 Raspberry Pi는 동일한 로컬 네트워크에 연결해야 합니다.

## 7. 테스트 및 검증

- YOLO 객체 탐지 및 5프레임 검사
- 손동작 인식과 작업 상태 전이
- PASS / FAIL / RECHECK 및 재검사
- 작업 완료·취소와 SQLite 이력 저장
- 비정상 종료 후 진행 중 작업의 INTERRUPTED 처리
- 모델 오류 발생 후 관리자 복구
- Raspberry Pi 통신 장애 및 재연결

장시간 연속 실행 안정성 검증은 별도 추가 테스트 항목입니다.

## 8. 실행 화면 및 시연 영상

Windows GUI, Raspberry Pi 하드웨어 동작, 검사·작업 이력 및 통계 화면을 추가할 예정입니다.

- 시연 영상: 추후 링크 추가
- Windows GUI 캡처: 추후 추가
- Raspberry Pi 동작 사진: 추후 추가
