"""SmartCheck industrial-style operator/administrator dashboard.

GUI integration milestone: camera and inference run in CameraWorker QThread.
Keep existing task_controller.py / pi_client.py / bridge untouched.
"""
import sys
import json
from pathlib import Path
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog, QDateEdit, QComboBox, QInputDialog
from database import SmartCheckDB
from pdf_report import export_task_report, export_period_report
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QPixmap
from camera_worker import CameraWorker
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QLineEdit, QFrame,
    QGridLayout, QSizePolicy, QStackedWidget
)

STYLE = """
QMainWindow, QWidget#central { background: #F2F5F9; }
QWidget { font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; color: #223348; font-size: 12px; }
QFrame#sidebar { background: #14283F; border: none; }
QLabel#brand { color: #FFFFFF; font-size: 24px; font-weight: 800; }
QLabel#brandSub { color: #93A9C0; font-size: 11px; }
QLabel#sideSection { color: #829AB2; font-size: 10px; font-weight: 700; }
QPushButton#navButton { background: transparent; color: #A7BAD0; border: none; border-left: 3px solid transparent; border-radius: 4px; text-align: left; padding: 11px 8px; font-weight: 600; }
QPushButton#navButton:hover { background: #1C3853; color: #FFFFFF; }
QPushButton#navButton:checked { background: #234360; color: #FFFFFF; border-left: 3px solid #52B5F5; }
QLabel#sideFooter { color: #8FA7BF; font-size: 10px; }
QFrame#panel, QFrame#metric { background: #FFFFFF; border: 1px solid #DCE4ED; border-radius: 9px; }
QLabel#pageTitle { color: #172B42; font-size: 19px; font-weight: 800; }
QLabel#subtitle { color: #7C8C9E; font-size: 11px; }
QLabel#panelTitle { color: #22374E; font-size: 13px; font-weight: 800; }
QLabel#small { color: #8190A1; font-size: 11px; }
QLabel#metricLabel { color: #77899C; font-size: 11px; }
QLabel#metricValue { color: #20354C; font-size: 17px; font-weight: 800; }
QLabel#cameraPlaceholder { background: #17283A; border-radius: 6px; color: #B6C7D8; font-size: 15px; font-weight: 700; }
QLabel#cameraHint { color: #91A9C1; font-size: 11px; }
QLabel#eventText { color: #526477; font-size: 11px; }
QLabel#statusPill { background: transparent; border: none; padding: 0; font-size: 22px; font-weight: 800; }
QCheckBox { spacing: 7px; padding: 2px 0; font-size: 12px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QLineEdit#confidenceInput { background: #F8FAFD; border: 1px solid #CCD8E5; border-radius: 5px; padding: 5px 10px; color: #223348; }
QPushButton { background: #22669A; color: white; border: 1px solid #22669A; border-radius: 6px; padding: 7px 9px; font-weight: 700; }
QPushButton:hover:!disabled { background: #1C5684; }
QPushButton:disabled { background: #EDF1F5; color: #99A8B7; border: 1px solid #DDE4EC; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 8px; background: #F2F5F9; }
QScrollBar::handle:vertical { background: #C8D3DE; border-radius: 4px; }
QStatusBar { background: #FFFFFF; color: #6D7D8E; border-top: 1px solid #DCE4ED; }
"""


def label(text, name=None, alignment=None):
    item = QLabel(text)
    if name:
        item.setObjectName(name)
    if alignment is not None:
        item.setAlignment(alignment)
    return item


def pill(text, foreground='#276CA0', background='#E7F2FC'):
    item = label(text, 'statusPill')
    item.setStyleSheet(f'color: {foreground}; background: transparent; border: none;')
    item.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return item


def panel(title, subtitle=None):
    frame = QFrame()
    frame.setObjectName('panel')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(5)
    heading = QHBoxLayout()
    heading.addWidget(label(title, 'panelTitle'))
    heading.addStretch()
    if subtitle:
        heading.addWidget(label(subtitle, 'small'))
    layout.addLayout(heading)
    return frame, layout


def metric(title, value, value_color=None):
    frame = QFrame()
    frame.setObjectName('metric')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(11, 8, 11, 8)
    layout.setSpacing(2)
    layout.addWidget(label(title, 'metricLabel'))
    value_label = label(value, 'metricValue')
    if value_color:
        value_label.setStyleSheet(f'color: {value_color};')
    layout.addWidget(value_label)
    return frame, value_label


class CameraViewport(QFrame):
    """Fill the camera card without a second background or letterboxing.

    When live frames are connected, scale the pixmap with KeepAspectRatio
    inside this single label, rather than adding black background bands.
    """
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.image_label = QLabel('CAMERA OFFLINE\n\n실시간 영상 연결 대기')
        self.image_label.setObjectName('cameraPlaceholder')
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.image_label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SmartCheck | Inspection Control Center')
        self.resize(1450, 850)
        self.setMinimumSize(1190, 800)
        self.setStyleSheet(STYLE)
        self.bridge = None
        self.db = SmartCheckDB()
        self._active_task_id = None
        self._work_start_display = "-"
        self._last_camera_image = None
        self.camera_worker = None
        self._recovering_camera = False
        self._closing = False
        self._build_ui()
        self._init_bridge()
        self._init_camera()
        self._log('시스템', '관리자 화면 실행')
        self.statusBar().clearMessage()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName('central')
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(174)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(9, 14, 9, 10)
        side.setSpacing(8)
        side.addWidget(label('SmartCheck', 'brand'))
        side.addSpacing(15)
        self.nav_buttons = []
        for index, text in enumerate(('실시간 모니터링', '검사·작업 이력', '통계·보고서')):
            button = QPushButton(text)
            button.setObjectName('navButton')
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.clicked.connect(lambda checked=False, idx=index: self._switch_page(idx))
            side.addWidget(button)
            self.nav_buttons.append(button)
        side.addStretch()
        side.addWidget(label('SmartCheck v5.3', 'sideFooter'))
        shell.addWidget(sidebar)

        self.pages = QStackedWidget()
        shell.addWidget(self.pages, 1)
        page = QWidget()
        self.pages.addWidget(page)
        self.pages.addWidget(self._build_history_page())
        self.pages.addWidget(self._build_statistics_page())
        root = QVBoxLayout(page)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(5)


        body = QHBoxLayout()
        body.setSpacing(7)
        root.addLayout(body, 1)
        left = QVBoxLayout()
        left.setSpacing(5)
        body.addLayout(left, 8)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(4)
        body.addLayout(right, 4)


        camera_panel, camera_layout = panel('실시간 카메라')
        self.camera_viewport = CameraViewport()
        self.camera_label = self.camera_viewport.image_label
        camera_layout.addWidget(self.camera_viewport, 1)
        left.addWidget(camera_panel, 1)

        # 카메라 옆 관리자 정보: 검사 데이터가 아직 연결되지 않은 항목은 '-'로 표시
        self.work_time_label = label('--:--:--')
        self.work_time_label.setStyleSheet('font-size: 23px; font-weight: 800; color: #20354C;')
        self.start_time_label = label('-')
        self.state_pill = pill('READY')
        self.result_pill = pill('검사 전', '#697D90', '#EDF1F5')
        self.result_info = label('-')
        self.missing_label = label('-')
        self.uncertain_label = label('-')
        self.selected_label = label('-')
        self.pi_metric = label('연결 확인 중')
        self.camera_metric = label('미연결')
        self.gesture_metric = label('미연결')
        self.model_metric = label('미연결')
        self.error_metric = label('-')
        self.state_metric = label('READY')
        self.log_label = label('', 'eventText')
        self.detection_labels = {}
        self._detection_counts = None
        self._gesture_status = '미연결'
        self._camera_status = '미연결'
        self._model_status = '미연결'
        self._error_reason = '-'

        config_panel, config_layout = panel('검사 설정')
        config_panel.setMinimumWidth(295)
        self.items = {}
        for key, title in [('book', '책'), ('cell phone', '휴대폰'), ('scissors', '가위')]:
            check = QCheckBox(title)
            check.setChecked(True)
            check.stateChanged.connect(self._on_setting_changed)
            self.items[key] = check
            config_layout.addWidget(check)
        conf_row = QHBoxLayout()
        conf_row.addWidget(label('YOLO 탐지 신뢰도'))
        conf_row.addStretch()
        # 자유로운 문자 입력 후 완료 시 범위 검사: QDoubleSpinBox의 중간값 제한 회피
        self.confidence = QLineEdit('0.50')
        self.confidence.setObjectName('confidenceInput')
        self.confidence.setFixedSize(92, 30)
        self.confidence.setAlignment(Qt.AlignCenter)
        self.confidence.setToolTip('0.05부터 0.95까지 입력 후 Enter를 누르세요.')
        self.confidence.editingFinished.connect(self._commit_confidence)
        self._confidence_value = 0.50
        conf_row.addWidget(self.confidence)
        config_layout.addLayout(conf_row)
        config_layout.setContentsMargins(11, 8, 11, 8)
        config_layout.setSpacing(5)
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(75)
        self.preset_combo.setToolTip('저장된 검사 설정 선택')
        preset_row.addWidget(self.preset_combo, 1)
        self.preset_buttons = {}
        for text, callback in (('저장', self._save_preset), ('불러오기', self._load_preset), ('삭제', self._delete_preset)):
            button = QPushButton(text)
            button.setFixedWidth(72 if text == '불러오기' else 43)
            button.setFixedHeight(28)
            button.setStyleSheet('QPushButton { padding: 3px 2px; }')
            button.clicked.connect(callback)
            preset_row.addWidget(button)
            self.preset_buttons[text] = button
        config_layout.addWidget(label('검사 프리셋', 'metricLabel'))
        config_layout.addLayout(preset_row)
        config_layout.addSpacing(8)  # 프리셋 버튼 하단이 카드 경계에 닿지 않도록 여백 확보
        self._refresh_presets()
        right.addWidget(config_panel, 0)
        work_panel, work_layout = panel('작업 현황')
        work_layout.addWidget(self.state_pill)
        work_row = QHBoxLayout()
        work_row.addWidget(label('작업 시간', 'metricLabel'))
        work_row.addStretch()
        work_row.addWidget(self.work_time_label)
        work_layout.addLayout(work_row)
        start_row = QHBoxLayout()
        start_row.addWidget(label('시작 시각', 'metricLabel'))
        start_row.addStretch()
        start_row.addWidget(self.start_time_label)
        work_layout.addLayout(start_row)
        work_layout.setContentsMargins(11, 8, 11, 8)
        work_layout.setSpacing(7)
        right.addWidget(work_panel, 0)
        result_panel, result_layout = panel('검사 결과')
        result_panel.setMinimumHeight(225)  # 물품별 탐지 3행이 잘리지 않도록 최소 높이만 확보
        result_layout.addWidget(self.result_pill)
        result_grid = QGridLayout()
        result_grid.setHorizontalSpacing(8)
        result_grid.setVerticalSpacing(5)
        for row, (name, widget) in enumerate((
            ('검사 대상', self.selected_label),
            ('누락 물품', self.missing_label),
            ('불확실 물품', self.uncertain_label),
        )):
            title_label = label(name, 'metricLabel')
            title_label.setMinimumWidth(82)
            result_grid.addWidget(title_label, row, 0)
            widget.setWordWrap(True)
            result_grid.addWidget(widget, row, 1)
        result_grid.setColumnStretch(1, 1)
        result_layout.addLayout(result_grid)
        result_layout.addWidget(label('물품별 탐지 (5프레임)', 'panelTitle'))
        detection_grid = QGridLayout()
        detection_grid.setVerticalSpacing(5)
        for row, (key, name) in enumerate((('book', '책'), ('cell phone', '휴대폰'), ('scissors', '가위'))):
            detection_grid.addWidget(label(name), row, 0)
            count_label = label('- / 5')
            count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            status_label = label('대기', 'metricLabel')
            status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            detection_grid.addWidget(count_label, row, 1)
            detection_grid.addWidget(status_label, row, 2)
            self.detection_labels[key] = (count_label, status_label)
        detection_grid.setColumnStretch(1, 1)
        result_layout.addLayout(detection_grid)
        result_layout.setContentsMargins(11, 8, 11, 8)
        result_layout.setSpacing(7)
        result_grid.setVerticalSpacing(5)
        detection_grid.setVerticalSpacing(5)
        right.addWidget(result_panel, 0)
        device_panel, device_layout = panel('시스템 상태')
        device_grid = QGridLayout()
        device_grid.setVerticalSpacing(6)
        for row, (name, widget) in enumerate((
            ('제스처', self.gesture_metric),
            ('카메라', self.camera_metric),
            ('YOLO', self.model_metric),
            ('Raspberry Pi', self.pi_metric),
            ('오류', self.error_metric),
        )):
            device_grid.addWidget(label(name, 'metricLabel'), row, 0)
            widget.setWordWrap(True)
            device_grid.addWidget(widget, row, 1)
        device_grid.setColumnStretch(1, 1)
        # 제목은 상단에 두고, 상태 정보와 버튼 묶음은 카드 안에서 세로 중앙에 배치한다.
        device_layout.addStretch(1)
        device_layout.addLayout(device_grid)
        controls_row = QHBoxLayout()
        self.control_buttons = {}
        for name in ('다음 작업 준비', '오류 복구'):
            button = QPushButton(name)
            button.setFixedHeight(36)  # 버튼 글자가 잘리지 않도록 높이 확보
            button.setEnabled(False)
            button.clicked.connect(lambda checked=False, action=name: self._admin_action(action))
            controls_row.addWidget(button)
            self.control_buttons[name] = button
        device_layout.addLayout(controls_row)
        device_layout.setContentsMargins(11, 3, 11, 3)
        device_layout.setSpacing(2)
        device_grid.setVerticalSpacing(1)
        # 위쪽과 아래쪽에 동일한 stretch를 두어 내용이 위로 몰리지 않게 한다.
        device_layout.addStretch(1)
        right.addWidget(device_panel, 1)

        # 관리자 대체 조작: 전체 화면 하단에 독립된 영역으로 배치
        manual_panel, manual_layout = panel('관리자 수동 조작', '손동작 인식 실패 시 사용')
        manual_row = QHBoxLayout()
        manual_row.setSpacing(9)
        self.manual_buttons = {}
        for name, command in (('검사 시작', 'START'), ('재검사', 'START'),
                              ('작업 완료', 'COMPLETE'), ('검사·작업 취소', 'CANCEL')):
            button = QPushButton(name)
            button.setMinimumHeight(35)
            button.setEnabled(False)
            button.clicked.connect(lambda checked=False, cmd=command: self._execute_task_command(cmd, 'GUI'))
            manual_row.addWidget(button, 1)
            self.manual_buttons[name] = button
        manual_layout.addLayout(manual_row)
        root.addWidget(manual_panel, 0)

    def _refresh_presets(self, select_name=None):
        current = select_name or self.preset_combo.currentText()
        self.preset_combo.clear()
        self.preset_combo.addItem('프리셋 선택', None)
        try:
            for item in self.db.list_presets():
                self.preset_combo.addItem(item['name'], item['id'])
            idx = self.preset_combo.findText(current)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
        except Exception as exc:
            self._db_error(exc)

    def _preset_ready(self):
        if self.bridge is None or self.bridge.controller.state.value != 'READY':
            QMessageBox.information(self, '프리셋 관리', '프리셋은 READY 상태에서만 변경할 수 있습니다.')
            return False
        return True

    def _save_preset(self):
        if not self._preset_ready():
            return
        self._commit_confidence()
        if not self._selected_items():
            QMessageBox.warning(self, '프리셋 저장', '검사 물품을 하나 이상 선택하세요.')
            return
        name, ok = QInputDialog.getText(self, '프리셋 저장', '프리셋 이름:')
        if not ok:
            return
        try:
            self.db.save_preset(name, self._selected_items(), self._confidence_value)
            self._refresh_presets(name.strip())
            self.statusBar().showMessage('프리셋 저장 완료', 5000)
        except Exception as exc:
            QMessageBox.warning(self, '프리셋 저장 실패', str(exc))

    def _load_preset(self):
        if not self._preset_ready():
            return
        preset_id = self.preset_combo.currentData()
        if preset_id is None:
            QMessageBox.information(self, '프리셋 불러오기', '프리셋을 선택하세요.')
            return
        try:
            preset = next(row for row in self.db.list_presets() if row['id'] == preset_id)
            selected = set(json.loads(preset['selected_items']))
            for key, checkbox in self.items.items():
                checkbox.blockSignals(True)
                checkbox.setChecked(key in selected)
                checkbox.blockSignals(False)
            self._confidence_value = float(preset['confidence'])
            self.confidence.setText(f'{self._confidence_value:.2f}')
            if self.camera_worker is not None:
                self.camera_worker.configure(selected=list(selected), confidence=self._confidence_value)
            if not self.bridge.set_selected_items(self._selected_items()):
                raise RuntimeError('검사 대상 설정에 실패했습니다.')
            self._refresh_status()
            self.statusBar().showMessage(f'프리셋 불러오기 완료: {preset["name"]}', 5000)
        except Exception as exc:
            QMessageBox.warning(self, '프리셋 불러오기 실패', str(exc))

    def _delete_preset(self):
        if not self._preset_ready():
            return
        preset_id = self.preset_combo.currentData()
        if preset_id is None:
            QMessageBox.information(self, '프리셋 삭제', '프리셋을 선택하세요.')
            return
        name = self.preset_combo.currentText()
        if QMessageBox.question(self, '프리셋 삭제', f'「{name}」 프리셋을 삭제할까요?',
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.db.delete_preset(preset_id)
            self._refresh_presets()
            self.statusBar().showMessage('프리셋 삭제 완료', 5000)
        except Exception as exc:
            self._db_error(exc)

    def _build_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(9)
        header = QHBoxLayout()
        header.addWidget(label('검사·작업 이력', 'pageTitle'))
        header.addStretch()
        refresh = QPushButton('새로고침')
        refresh.clicked.connect(self._load_history)
        header.addWidget(refresh)
        layout.addLayout(header)
        layout.addWidget(label('작업별 상태 및 검사별 결과를 각각 조회합니다.', 'small'))
        report_row = QHBoxLayout()
        report_row.addWidget(label('작업 이력에서 행을 선택한 후 개별 PDF를 출력할 수 있습니다.', 'small'))
        report_row.addStretch()
        task_pdf_button = QPushButton('선택 작업 PDF')
        task_pdf_button.clicked.connect(self._export_selected_task_pdf)
        report_row.addWidget(task_pdf_button)
        layout.addLayout(report_row)
        layout.addWidget(label('작업 이력', 'panelTitle'))
        self.task_table = QTableWidget(0, 7)
        self.task_table.setHorizontalHeaderLabels(['작업 ID', '생성 시각', '상태', '최종 검사', '검사 횟수', '작업 시작', '소요 시간(초)'])
        self.task_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.task_table, 1)
        layout.addWidget(label('검사 이력 (재검사 포함)', 'panelTitle'))
        self.inspection_table = QTableWidget(0, 8)
        self.inspection_table.setHorizontalHeaderLabels(['검사 ID', '작업 ID', '검사 시각', '결과', '누락', '불확실', '탐지 횟수', '신뢰도'])
        self.inspection_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.inspection_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.inspection_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.inspection_table, 1)
        return page

    def _load_history(self):
        try:
            tasks = self.db.list_tasks()
            self.task_table.setRowCount(len(tasks))
            for row, item in enumerate(tasks):
                values = [item['id'], item['created_at'], item['status'], item['last_result'] or '-',
                          item['inspection_count'], item['work_started_at'] or '-',
                          f"{item['duration_seconds']:.1f}" if item['duration_seconds'] is not None else '-']
                for col, value in enumerate(values):
                    self.task_table.setItem(row, col, QTableWidgetItem(str(value)))
            inspections = self.db.list_inspections()
            self.inspection_table.setRowCount(len(inspections))
            names = {'book':'책', 'cell phone':'휴대폰', 'scissors':'가위'}
            for row, item in enumerate(inspections):
                translated = lambda values: ', '.join(names.get(x,x) for x in json.loads(values)) or '-'
                counts = json.loads(item['detection_counts'])
                values = [item['id'], item['task_id'], item['inspected_at'], item['result'],
                          translated(item['missing_items']), translated(item['uncertain_items']),
                          ', '.join(f'{names.get(k,k)}:{v}/5' for k,v in counts.items()), f"{item['confidence']:.2f}"]
                for col, value in enumerate(values):
                    self.inspection_table.setItem(row, col, QTableWidgetItem(str(value)))
        except Exception as exc:
            self._db_error(exc)

    def _db_error(self, exc):
        self.statusBar().showMessage(f'데이터베이스 오류: {exc}', 10000)
        QMessageBox.warning(self, 'SQLite 오류', f'이력 저장 또는 조회 실패:\n{exc}')

    def _save_evidence(self):
        if self._last_camera_image is None:
            return None
        folder = Path(__file__).resolve().parent / 'data' / 'evidence'
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        path = folder / f'task_{self._active_task_id}_{stamp}.jpg'
        if not self._last_camera_image.save(str(path), 'JPG', 90):
            raise IOError(f'검사 증거 이미지 저장 실패: {path}')
        return str(path)

    def _build_statistics_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(label('통계·보고서', 'pageTitle'))
        header.addStretch()
        refresh = QPushButton('통계 새로고침')
        refresh.clicked.connect(self._load_statistics)
        header.addWidget(refresh)
        layout.addLayout(header)
        layout.addWidget(label('SQLite에 실제 저장된 전체 검사·작업 기록 기준', 'small'))
        pdf_row = QHBoxLayout()
        pdf_row.addWidget(label('보고 기간'))
        self.report_start_date = QDateEdit(QDate.currentDate().addMonths(-1))
        self.report_end_date = QDateEdit(QDate.currentDate())
        for picker in (self.report_start_date, self.report_end_date):
            picker.setCalendarPopup(True)
            picker.setDisplayFormat('yyyy-MM-dd')
            pdf_row.addWidget(picker)
        pdf_row.addStretch()
        period_pdf_button = QPushButton('기간별 PDF 저장')
        period_pdf_button.clicked.connect(self._export_period_pdf)
        pdf_row.addWidget(period_pdf_button)
        layout.addLayout(pdf_row)

        summary_panel, summary_layout = panel('검사 및 작업 현황')
        self.stat_labels = {}
        grid = QGridLayout()
        summary = [
            ('total_tasks', '전체 작업'), ('total_inspections', '전체 검사'),
            ('PASS', 'PASS'), ('FAIL', 'FAIL'), ('RECHECK', 'RECHECK'),
            ('COMPLETED', '작업 완료'), ('CANCELED', '작업 취소'),
            ('INTERRUPTED', '비정상 종료'), ('ERROR', '작업 오류'),
        ]
        for index, (key, name) in enumerate(summary):
            frame, value = metric(name, '0')
            self.stat_labels[key] = value
            grid.addWidget(frame, index // 3, index % 3)
        summary_layout.addLayout(grid)
        layout.addWidget(summary_panel)

        detail_panel, detail_layout = panel('물품별 누락·불확실 발생 횟수')
        self.stat_item_table = QTableWidget(3, 3)
        self.stat_item_table.setHorizontalHeaderLabels(['물품', '누락', '불확실'])
        self.stat_item_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stat_item_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stat_item_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stat_item_table.setMaximumHeight(150)
        detail_layout.addWidget(self.stat_item_table)
        layout.addWidget(detail_panel)

        duration_panel, duration_layout = panel('완료 작업 소요 시간')
        self.stat_duration = label('완료된 작업 기록 없음')
        duration_layout.addWidget(self.stat_duration)
        layout.addWidget(duration_panel)
        layout.addStretch()
        return page

    def _load_statistics(self):
        try:
            data = self.db.get_statistics()
            for key in ('total_tasks', 'total_inspections'):
                self.stat_labels[key].setText(str(data[key]))
            for key in ('PASS', 'FAIL', 'RECHECK'):
                self.stat_labels[key].setText(str(data['inspections'].get(key, 0)))
            for key in ('COMPLETED', 'CANCELED', 'INTERRUPTED', 'ERROR'):
                self.stat_labels[key].setText(str(data['tasks'].get(key, 0)))
            names = [('book', '책'), ('cell phone', '휴대폰'), ('scissors', '가위')]
            for row, (key, name) in enumerate(names):
                for col, value in enumerate((name, data['missing_by_item'].get(key, 0),
                                             data['uncertain_by_item'].get(key, 0))):
                    self.stat_item_table.setItem(row, col, QTableWidgetItem(str(value)))
            d = data['completed_durations']
            if d['n']:
                self.stat_duration.setText(
                    f"완료 {d['n']}건  |  평균 {d['avg_seconds']:.1f}초  |  "
                    f"최소 {d['min_seconds']:.1f}초  |  최대 {d['max_seconds']:.1f}초")
            else:
                self.stat_duration.setText('완료된 작업 기록 없음')
        except Exception as exc:
            self._db_error(exc)

    def _export_selected_task_pdf(self):
        selected = self.task_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, '작업 선택', '작업 이력에서 PDF로 출력할 작업 행을 선택해 주세요.')
            return
        task_id = int(self.task_table.item(selected[0].row(), 0).text())
        default = str(Path.home() / 'Documents' / f'SmartCheck_task_{task_id}.pdf')
        path, _ = QFileDialog.getSaveFileName(self, '개별 작업 PDF 저장', default, 'PDF 파일 (*.pdf)')
        if not path:
            return
        try:
            export_task_report(self.db, task_id, path)
            self.statusBar().showMessage(f'PDF 저장 완료: {path}', 10000)
            QMessageBox.information(self, 'PDF 저장 완료', f'개별 작업 보고서를 저장했습니다.\n{path}')
        except Exception as exc:
            QMessageBox.warning(self, 'PDF 저장 실패', str(exc))

    def _export_period_pdf(self):
        start = self.report_start_date.date().toString('yyyy-MM-dd')
        end = self.report_end_date.date().toString('yyyy-MM-dd')
        if start > end:
            QMessageBox.warning(self, '날짜 오류', '시작 날짜는 종료 날짜보다 늦을 수 없습니다.')
            return
        default = str(Path.home() / 'Documents' / f'SmartCheck_summary_{start}_{end}.pdf')
        path, _ = QFileDialog.getSaveFileName(self, '기간별 요약 PDF 저장', default, 'PDF 파일 (*.pdf)')
        if not path:
            return
        try:
            export_period_report(self.db, start, end, path)
            self.statusBar().showMessage(f'PDF 저장 완료: {path}', 10000)
            QMessageBox.information(self, 'PDF 저장 완료', f'기간별 요약 보고서를 저장했습니다.\n{path}')
        except Exception as exc:
            QMessageBox.warning(self, 'PDF 저장 실패', str(exc))

    def _pending_page(self, heading, notice):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(label(heading, 'pageTitle'))
        frame, inner = panel(heading)
        inner.addWidget(label(notice, 'small'))
        layout.addWidget(frame)
        layout.addStretch(1)
        return page

    def _switch_page(self, index):
        self.pages.setCurrentIndex(index)
        if index == 1:
            self._load_history()
        elif index == 2:
            self._load_statistics()
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    def _init_bridge(self):
        """Existing controller + PiClient; all HTTP runs in PiClient thread."""
        try:
            from task_pi_bridge import TaskPiBridge
            self.bridge = TaskPiBridge()
            self.bridge.set_selected_items(self._selected_items())
            self.bridge.start()
            self._log('연동', 'TaskController 및 PiClient 연결 시작')
        except Exception as exc:
            self.bridge = None
            self._log('오류', f'연동 실패: {exc}')
        self._last_elapsed_sync = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(500)
        self._refresh_status()

    def _init_camera(self):
        self.camera_worker = CameraWorker(self)
        self.camera_worker.frame_ready.connect(self._show_camera_frame)
        self.camera_worker.gesture_changed.connect(self._on_gesture)
        self.camera_worker.command_ready.connect(self._on_gesture_command)
        self.camera_worker.inspection_ready.connect(self._on_inspection)
        self.camera_worker.status_changed.connect(self._on_camera_status)
        self.camera_worker.error_occurred.connect(self._on_camera_error)
        self.camera_worker.configure(
            state=self.bridge.controller.state.value if self.bridge else 'READY',
            selected=self._selected_items(), confidence=self._confidence_value)
        self.camera_worker.start()

    def _show_camera_frame(self, image):
        self._last_camera_image = image
        self._resize_camera_frame()

    def _resize_camera_frame(self):
        if self._last_camera_image is None:
            return
        target = self.camera_label.size()
        if target.width() < 1 or target.height() < 1:
            return
        pixmap = QPixmap.fromImage(self._last_camera_image)
        self.camera_label.setPixmap(pixmap.scaled(
            target, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'camera_label'):
            self._resize_camera_frame()

    def _on_gesture(self, gesture):
        names = {'THUMBS_UP': '엄지척', 'OPEN_PALM': '손바닥',
                 'FIST': '주먹', 'NONE': '인식 없음'}
        self.update_device_status(gesture=names.get(gesture, gesture))

    def _on_gesture_command(self, command):
        self._execute_task_command(command, 'GESTURE')

    def _execute_task_command(self, command, source):
        """제스처와 관리자 버튼이 동일한 상태 전이 및 DB 기록 경로를 사용한다."""
        if self.bridge is None:
            return
        if command == 'START' and not self._selected_items():
            self.statusBar().showMessage('검사 물품을 하나 이상 선택하세요.', 5000)
            return
        if not self.bridge.handle_command(command, source=source):
            return
        try:
            if command == 'START':
                if self._active_task_id is None:
                    self._active_task_id = self.db.begin_task(self.bridge.controller.selected_items)
                else:
                    self.db.mark_checking(self._active_task_id)
            elif command in ('COMPLETE', 'CANCEL') and self._active_task_id is not None:
                controller = self.bridge.controller
                self.db.finish_task(self._active_task_id, controller.state.value, controller.work_duration)
        except Exception as exc:
            self._db_error(exc)
        self._log('관리자' if source == 'GUI' else '제스처', command)
        if self.camera_worker is not None:
            self.camera_worker.configure(state=self.bridge.controller.state.value)
        self._refresh_status()

    def _on_inspection(self, result):
        if self.bridge is None:
            return
        if self.bridge.finish_inspection(
                result['result'], missing=result['missing_items'],
                uncertain=result['uncertain_items']):
            try:
                if self._active_task_id is None:
                    raise RuntimeError('검사에 연결할 작업 ID가 없습니다.')
                evidence = self._save_evidence()
                self.db.save_inspection(self._active_task_id, result, self._confidence_value, evidence)
                if result['result'] == 'PASS':
                    stored_start = self.db.get_work_started_at(self._active_task_id)
                    self._work_start_display = (
                        datetime.fromisoformat(stored_start).strftime('%H:%M:%S')
                        if stored_start else '-'
                    )
            except Exception as exc:
                self._db_error(exc)
            self.update_inspection_details(result['counts'])
            self.camera_worker.configure(state=self.bridge.controller.state.value)
            self._refresh_status()

    def _on_camera_status(self, camera, model, error):
        # The worker only emits the ready status after both models and camera initialize.
        if self._closing:
            return
        if self._recovering_camera and camera == '연결됨' and model == '실행 중':
            self._recovering_camera = False
            if self.bridge is not None and self.bridge.controller.state.value == 'ERROR':
                if self.bridge.handle_command('RECOVER', source='GUI'):
                    self._active_task_id = None
                    self._work_start_display = '-'
                    self.bridge.set_selected_items(self._selected_items())
                    self._detection_counts = None
                    self._last_camera_image = None
                    self._gesture_status = '인식 없음'
                    self._log('관리자', '카메라 및 모델 복구 완료')
                    self.statusBar().showMessage('카메라 및 모델 재초기화 성공: READY', 5000)
        self.update_device_status(camera=camera, model=model, error=error)
        self._refresh_status()

    def _on_camera_error(self, reason):
        if self._closing:
            return
        self._recovering_camera = False
        self.update_device_status(camera='오류', model='오류', error=reason)
        if self.bridge is not None:
            if self._active_task_id is not None:
                try:
                    self.db.mark_error(self._active_task_id, reason)
                except Exception as exc:
                    self._db_error(exc)
            self.bridge.set_error()
            self._refresh_status()

    def _selected_items(self):
        return [key for key, checkbox in self.items.items() if checkbox.isChecked()]

    def _admin_action(self, name):
        if self.bridge is None:
            return
        if name == '오류 복구':
            self._begin_camera_recovery()
            return
        if self.bridge.handle_command('NEXT_TASK', source='GUI'):
            self._active_task_id = None
            self._work_start_display = '-'
            self._detection_counts = None
            self.bridge.set_selected_items(self._selected_items())
            self._log('관리자', f'{name} 실행')
            if self.camera_worker is not None:
                self.camera_worker.configure(state=self.bridge.controller.state.value)
            self._refresh_status()

    def _begin_camera_recovery(self):
        """Restart the worker while retaining ERROR until initialization succeeds."""
        if self._recovering_camera or self._closing or self.bridge is None:
            return
        if self.bridge.controller.state.value != 'ERROR':
            return
        self._recovering_camera = True
        self.statusBar().showMessage('카메라 및 모델 재초기화 중...', 0)
        self._log('관리자', '오류 복구 요청')
        old_worker = self.camera_worker
        if old_worker is not None and old_worker.isRunning():
            # Never start a second worker before the previous one releases the camera.
            old_worker.finished.connect(self._restart_camera_after_exit)
        else:
            self._restart_camera_after_exit()
        self._refresh_status()

    def _restart_camera_after_exit(self):
        if self._closing or not self._recovering_camera:
            return
        old_worker = self.camera_worker
        if old_worker is not None and old_worker.isRunning():
            return
        try:
            self._init_camera()
        except Exception as exc:
            self._recovering_camera = False
            self.update_device_status(camera='오류', model='오류', error=str(exc))
            self.statusBar().showMessage(f'오류 복구 실패: {exc}', 10000)
        self._refresh_status()

    def _refresh_status(self):
        if self.bridge is None:
            self.pi_metric.setText('연동 실패')
            self.control_buttons['다음 작업 준비'].setEnabled(False)
            self.control_buttons['오류 복구'].setEnabled(False)
            for button in self.manual_buttons.values():
                button.setEnabled(False)
            return
        # PiClient의 통신 스레드에서는 SQLite를 직접 사용하지 않는다.
        # GUI 스레드의 타이머에서 전달 결과를 꺼내 DB에 저장한다.
        for event in self.bridge.client.take_delivery_events():
            try:
                self.db.save_pi_delivery(
                    self._active_task_id, event['state'],
                    event['success'], event['error'])
            except Exception as exc:
                self.statusBar().showMessage(f'Pi 통신 기록 저장 오류: {exc}', 10000)
        controller = self.bridge.controller
        state = controller.state.value
        if self.camera_worker is not None:
            self.camera_worker.configure(state=state)
        colors = {
            'READY': '#216B9E', 'CHECKING': '#216B9E', 'PASS': '#26825C',
            'WORKING': '#26825C', 'COMPLETED': '#26825C',
            'FAIL': '#B64242', 'RECHECK': '#A66C13',
            'CANCELED': '#B64242', 'ERROR': '#B64242',
        }
        color = colors.get(state, '#216B9E')
        self.state_metric.setText(state)
        self.state_metric.setStyleSheet(f'color: {color};')
        self.state_pill.setText(state)
        self.state_pill.setStyleSheet(f'color: {color}; background: transparent; border: none;')
        client = self.bridge.client
        self.pi_metric.setText('연결됨' if client.connected else '연결 끊김')
        self.camera_metric.setText(self._camera_status)
        self.model_metric.setText(self._model_status)
        self.gesture_metric.setText(self._gesture_status)
        self.error_metric.setText(self._error_reason)
        self._refresh_detection_display()
        self.selected_label.setText(', '.join(
            {'book': '책', 'cell phone': '휴대폰', 'scissors': '가위'}.get(x, x)
            for x in sorted(controller.selected_items)
        ) or '-')
        self.result_pill.setText(controller.last_result or '검사 전')
        result_colors = {
            'PASS': ('#26825C', '#E6F5ED'),
            'FAIL': ('#B64242', '#FBECEC'),
            'RECHECK': ('#A66C13', '#FFF3DB'),
        }
        fg, bg = result_colors.get(controller.last_result, ('#697D90', '#EDF1F5'))
        self.result_pill.setStyleSheet(f'color: {fg}; background: transparent; border: none;')
        names = {'book': '책', 'cell phone': '휴대폰', 'scissors': '가위'}
        self.missing_label.setText(', '.join(names.get(x, x) for x in self.bridge.missing) or '-')
        self.uncertain_label.setText(', '.join(names.get(x, x) for x in self.bridge.uncertain) or '-')
        # PASS 이후 SQLite에 기록된 실제 작업 시작 시각을 유지해 표시한다.
        self.start_time_label.setText(self._work_start_display)

        self.control_buttons['다음 작업 준비'].setEnabled(state in ('COMPLETED', 'CANCELED'))
        self.control_buttons['오류 복구'].setEnabled(state == 'ERROR' and not self._recovering_camera)
        self.manual_buttons['검사 시작'].setEnabled(state == 'READY' and bool(self._selected_items()))
        self.manual_buttons['재검사'].setEnabled(state in ('FAIL', 'RECHECK'))
        self.manual_buttons['작업 완료'].setEnabled(state == 'WORKING')
        self.manual_buttons['검사·작업 취소'].setEnabled(state in ('CHECKING', 'WORKING'))
        editable = state == 'READY'
        for checkbox in self.items.values():
            checkbox.setEnabled(editable)
        self.preset_combo.setEnabled(editable)
        for button in self.preset_buttons.values():
            button.setEnabled(editable)
        elapsed = controller.elapsed_seconds()
        if elapsed is not None:
            seconds = int(elapsed)
            self.work_time_label.setText(f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}')
        else:
            self.work_time_label.setText('--:--:--')
        if state == 'WORKING':
            import time
            now = time.monotonic()
            if now - self._last_elapsed_sync >= 3.0:
                self.bridge.refresh_elapsed()
                self._last_elapsed_sync = now

    def _refresh_detection_display(self):
        selected = set(self._selected_items())
        for key, (count_label, status_label) in self.detection_labels.items():
            if key not in selected:
                count_label.setText('-')
                status_label.setText('제외')
            elif self._detection_counts is None or key not in self._detection_counts:
                count_label.setText('- / 5')
                status_label.setText('대기')
            else:
                count = self._detection_counts[key]
                count_label.setText(f'{count} / 5')
                status = '정상' if count >= 4 else '불확실' if count >= 2 else '누락'
                color = '#26825C' if count >= 4 else '#A66C13' if count >= 2 else '#B64242'
                status_label.setText(status)
                status_label.setStyleSheet(f'color: {color}; font-weight: 700;')

    def update_inspection_details(self, counts):
        """추후 실제 검사 완료 시 5프레임 탐지 횟수 전달. 예: {'book': 5}."""
        if not isinstance(counts, dict) or any(
            key not in self.items or type(value) is not int or not 0 <= value <= 5
            for key, value in counts.items()
        ):
            raise ValueError('counts는 물품별 0~5의 정수여야 합니다.')
        self._detection_counts = dict(counts)
        self._refresh_detection_display()

    def update_device_status(self, *, camera=None, model=None, gesture=None, error=None):
        """추후 카메라/YOLO/MediaPipe 작업 스레드의 Qt 시그널에서 호출."""
        if camera is not None:
            self._camera_status = str(camera)
        if model is not None:
            self._model_status = str(model)
        if gesture is not None:
            self._gesture_status = str(gesture)
        if error is not None:
            self._error_reason = str(error)
        self.camera_metric.setText(self._camera_status)
        self.model_metric.setText(self._model_status)
        self.gesture_metric.setText(self._gesture_status)
        self.error_metric.setText(self._error_reason)

    def closeEvent(self, event):
        self._closing = True
        if self.camera_worker is not None:
            self.camera_worker.stop()
        if self.bridge is not None:
            self.bridge.stop()
        if self.db is not None:
            # An unfinished task remains non-completed in SQLite; next startup marks INTERRUPTED.
            self.db.close()
        super().closeEvent(event)

    def _commit_confidence(self):
        raw = self.confidence.text().strip()
        try:
            value = float(raw)
            if not (0.05 <= value <= 0.95):
                raise ValueError('out of range')
        except ValueError:
            # 잘못된 입력은 마지막 유효한 값으로 복원
            self.confidence.setText(f'{self._confidence_value:.2f}')
            self.statusBar().showMessage('신뢰도는 0.05 ~ 0.95 사이의 숫자를 입력하세요.', 5000)
            return
        self._confidence_value = round(value, 2)
        if self.camera_worker is not None:
            self.camera_worker.configure(confidence=self._confidence_value)
        self.confidence.setText(f'{self._confidence_value:.2f}')
        self._on_setting_changed()

    def _on_setting_changed(self, *_args):
        selected = [key for key, checkbox in self.items.items() if checkbox.isChecked()]
        if self.camera_worker is not None:
            self.camera_worker.configure(selected=selected)
        if self.bridge is not None and self.bridge.controller.state.value == 'READY':
            if not self.bridge.set_selected_items(self._selected_items()):
                self.statusBar().showMessage('검사 물품을 하나 이상 선택해야 합니다.', 5000)

    def _log(self, category, message):
        stamp = datetime.now().strftime('%H:%M:%S')
        self.log_label.setText(f'[{stamp}]  {category}  |  {message}')


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
