"""Windows에서 실행하는 Pi 연결 및 수동 상태 변경 테스트.

실제 Pi OLED/RGB/부저가 반응하므로 테스트 전 장치 주변을 확인하세요.
"""
import time
from pi_client import PiClient


def main():
    client = PiClient('http://192.168.0.222:5000', interval=3, timeout=2)
    status = client.check_connection()
    if status is None:
        print('연결 실패:', client.last_error)
        return
    print('Pi 연결 성공:', status)
    client.start()
    try:
        tests = [
            ('READY', {}),
            ('CHECKING', {}),
            ('FAIL', {'missing': ['scissors']}),
            ('RECHECK', {'uncertain': ['cell phone']}),
            ('WORKING', {'elapsed_seconds': 12}),
            ('COMPLETED', {'elapsed_seconds': 18}),
        ]
        for state, details in tests:
            print('전송:', state)
            client.set_state(state, **details)
            time.sleep(5)
            print('연결 상태:', client.connected, client.last_error)
        print('테스트 종료: 마지막 상태를 유지합니다. READY 자동 전환 없음.')
    except KeyboardInterrupt:
        print('사용자 중단')
    finally:
        client.stop()


if __name__ == '__main__':
    main()
