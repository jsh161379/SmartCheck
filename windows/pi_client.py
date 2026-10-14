"""SmartCheck Windows -> Raspberry Pi 상태 통신 클라이언트.

표준 라이브러리만 사용. TaskController를 직접 변경하지 않는다.
주의: Pi 서버는 동일 sequence 재전송을 허용해야 heartbeat가 작동한다.
"""
import json
import queue
import threading
import time
from urllib import error, request

VALID_STATES = frozenset({
    'READY', 'CHECKING', 'PASS', 'FAIL', 'RECHECK', 'WORKING',
    'COMPLETED', 'CANCELED', 'ERROR', 'OFFLINE'
})


class PiClient:
    def __init__(self, base_url='http://192.168.0.222:5000', interval=3.0, timeout=1.5):
        self.base_url = base_url.rstrip('/')
        self.interval = float(interval)
        self.timeout = float(timeout)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._payload = None
        self._sequence = -1
        self.connected = False
        self.last_error = None
        self.delivery_events = queue.Queue()
        self._last_delivery_key = None

    def _request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        req = request.Request(
            self.base_url + path,
            data=data,
            headers={'Content-Type': 'application/json'} if data is not None else {},
            method='POST' if data is not None else 'GET',
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ConnectionError(str(exc)) from exc

    def check_connection(self):
        try:
            status = self._request('/api/status')
            with self._lock:
                self._sequence = max(self._sequence, int(status.get('sequence', -1)))
                self.connected = True
                self.last_error = None
            return status
        except (ConnectionError, TypeError) as exc:
            with self._lock:
                self.connected = False
                self.last_error = str(exc)
            return None

    def set_state(self, state, missing=None, uncertain=None, elapsed_seconds=None, error=None):
        """최신 상태를 보관한다. HTTP 전송은 백그라운드 스레드에서 수행한다."""
        state = getattr(state, 'value', state)
        if state not in VALID_STATES or state == 'OFFLINE':
            raise ValueError('PC 작업 상태는 READY~ERROR 중 하나여야 합니다.')
        payload = {'state': state}
        if missing is not None:
            payload['missing'] = list(missing)
        if uncertain is not None:
            payload['uncertain'] = list(uncertain)
        if elapsed_seconds is not None:
            payload['elapsed_seconds'] = float(elapsed_seconds)
        if error is not None:
            payload['error'] = str(error)
        with self._lock:
            # sequence는 최초 연결에서 서버의 최신 번호를 읽은 뒤 배정한다.
            self._payload = payload
            self._sequence += 1
            self._payload['sequence'] = self._sequence

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        # 서버에 기존 sequence가 있을 수 있으므로 시작 시 조회한다.
        status = self.check_connection()
        if status is None:
            # 오프라인에서도 시작 가능. 재연결 시 서버 sequence 재동기화.
            pass
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name='PiClient')
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            with self._lock:
                payload = dict(self._payload) if self._payload is not None else None
            if payload is not None:
                try:
                    # 서버 재시작/이전 높은 sequence 이후에도 동기화.
                    status = self._request('/api/status')
                    server_seq = int(status.get('sequence', -1))
                    with self._lock:
                        if self._payload is not None and server_seq > self._payload['sequence']:
                            self._sequence = max(self._sequence, server_seq) + 1
                            self._payload['sequence'] = self._sequence
                        payload = dict(self._payload) if self._payload is not None else None
                    if payload is not None:
                        response = self._request('/api/work-state', payload)
                        if isinstance(response, dict) and response.get('error'):
                            raise ConnectionError(str(response['error']))
                    with self._lock:
                        self.connected = True
                        self.last_error = None
                    self._record_delivery(payload, True)
                except (ConnectionError, ValueError, TypeError) as exc:
                    if payload is not None:
                        self._record_delivery(payload, False, exc)
                    with self._lock:
                        self.connected = False
                        self.last_error = str(exc)
            self._stop.wait(self.interval)

    def take_delivery_events(self):
        """GUI 스레드가 호출. 백그라운드 HTTP 결과를 안전하게 전달한다."""
        events = []
        while True:
            try:
                events.append(self.delivery_events.get_nowait())
            except queue.Empty:
                return events

    def _record_delivery(self, payload, success, message=None):
        # 경과 시간과 heartbeat sequence 변화는 새 알림으로 기록하지 않는다.
        key = (payload['state'], tuple(payload.get('missing', ())),
               tuple(payload.get('uncertain', ())), payload.get('error'), bool(success))
        if key != self._last_delivery_key:
            self._last_delivery_key = key
            self.delivery_events.put({
                'state': payload['state'], 'success': bool(success),
                'error': str(message) if message else None,
            })

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.timeout * 2 + 1)
            self._thread = None
