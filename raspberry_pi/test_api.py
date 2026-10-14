"""API behavior test without touching Raspberry Pi GPIO."""
from api_server import create_app


class FakeHardware:
    def __init__(self):
        self.calls = []

    def set_state(self, state, **kwargs):
        self.calls.append((state, kwargs))


def main():
    fake = FakeHardware()
    app = create_app(hardware=fake, start_watchdog=False)
    client = app.test_client()

    response = client.post('/api/work-state', json={'state': 'READY', 'sequence': 1})
    assert response.status_code == 200, response.json
    response = client.post('/api/work-state', json={'state': 'PASS', 'sequence': 2})
    assert response.status_code == 200, response.json
    response = client.post('/api/work-state', json={'state': 'FAIL', 'sequence': 1})
    assert response.status_code == 409, response.json
    response = client.post('/api/work-state', json={'state': 'WORKING', 'sequence': 2})
    assert response.status_code == 409, response.json
    response = client.post('/api/work-state', json={'state': 'WORKING', 'sequence': 3, 'elapsed_seconds': 5})
    assert response.status_code == 200, response.json
    response = client.post('/api/work-state', json={'state': 'WORKING', 'sequence': 3, 'elapsed_seconds': 6})
    assert response.status_code == 200, response.json
    response = client.get('/api/status')
    assert response.status_code == 200 and response.json['task_state'] == 'WORKING'
    assert response.json['sequence'] == 3
    assert len(fake.calls) == 4
    print('PASS: API validation, stale requests, same-sequence refresh, status')
    print('Note: real GPIO and network were not tested.')


if __name__ == '__main__':
    main()
