"""SmartCheck PC↔Pi 통신 끊김 및 재연결 통합 테스트.

Windows PC에서 실행. Pi의 Flask 서버는 테스트 내내 실행해야 한다.
PC PiClient의 heartbeat만 중지해 Pi watchdog(10초)을 검증한다.
"""
import json
import time
from urllib.request import urlopen

from task_controller import TaskState
from task_pi_bridge import TaskPiBridge

BASE_URL = 'http://192.168.0.222:5000'


def pi_status():
    with urlopen(BASE_URL + '/api/status', timeout=3) as response:
        return json.load(response)


def wait_for(predicate, timeout=12, interval=0.5, description='조건'):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = pi_status()
        if predicate(last):
            return last
        time.sleep(interval)
    raise AssertionError(f'{description} 확인 실패: {last}')


def main():
    print('=== SmartCheck 통신 장애·복구 테스트 ===')
    print('Pi Flask 서버는 종료하지 마세요. 이 테스트는 PC의 전송만 중단합니다.')
    print('Pi API:', BASE_URL)
    print('초기 Pi 응답:', pi_status())

    bridge = TaskPiBridge()
    try:
        bridge.start()
        assert bridge.set_selected_items(['book']), '검사 대상 선택 실패'
        assert bridge.handle_command('START', source='GUI'), 'START 실패'
        assert bridge.finish_inspection('PASS'), 'PASS 검사 처리 실패'
        assert bridge.controller.state == TaskState.WORKING
        print('[1] PC 상태: WORKING')

        status = wait_for(
            lambda s: s.get('task_state') == 'WORKING'
            and s.get('display_state') == 'WORKING'
            and not s.get('communication_timeout'),
            timeout=12, description='WORKING 전달')
        print('[2] Pi WORKING 수신:', status['display_state'])

        print('[3] PC heartbeat 전송을 13초간 중단합니다.')
        bridge.client.stop()
        time.sleep(13)
        status = pi_status()
        print('    Pi 표시:', status.get('display_state'),
              '/ 작업 상태:', status.get('task_state'),
              '/ timeout:', status.get('communication_timeout'))
        assert status.get('display_state') == 'OFFLINE', 'Pi OFFLINE 표시 실패'
        assert status.get('communication_timeout') is True, '통신 타임아웃 감지 실패'
        assert bridge.controller.state == TaskState.WORKING, 'PC 작업 상태가 변경됨'
        print('[4] PC WORKING 유지 + Pi OFFLINE 전환 확인')

        print('[5] PC heartbeat 전송 재개')
        bridge.client.start()
        bridge.sync()
        status = wait_for(
            lambda s: s.get('task_state') == 'WORKING'
            and s.get('display_state') == 'WORKING'
            and s.get('communication_timeout') is False,
            timeout=12, description='WORKING 복구')
        print('[6] Pi WORKING 자동 복구:', status['display_state'])
        assert bridge.controller.state == TaskState.WORKING

        assert bridge.handle_command('COMPLETE', source='GUI'), 'COMPLETE 실패'
        status = wait_for(lambda s: s.get('task_state') == 'COMPLETED',
                          timeout=12, description='COMPLETED 전달')
        print('[7] 완료 상태 전달:', status['task_state'])
        print('PASS: OFFLINE 감지, PC 상태 보존, 최신 상태 재동기화, 완료 전달')
        print('COMPLETED를 READY로 자동 전환하지 않습니다.')
    finally:
        bridge.stop()


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, TimeoutError, ConnectionError) as exc:
        print('FAIL:', exc)
        raise SystemExit(1)
