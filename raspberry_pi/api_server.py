"""SmartCheck Pi REST API, stage 1: work-state and status.

Run only on the Raspberry Pi. The Windows PC owns all task decisions.
"""
import os
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from hardware_controller import HardwareController, VALID_STATES

HEARTBEAT_TIMEOUT = 10.0


def create_app(hardware=None, start_watchdog=True, timeout=HEARTBEAT_TIMEOUT):
    app = Flask(__name__)
    device = hardware if hardware is not None else HardwareController()
    lock = threading.RLock()
    last_sequence = -1
    last_contact = None
    current_state = 'READY'
    offline = False
    last_error = None
    stop = threading.Event()

    def watchdog():
        nonlocal offline, last_error
        while not stop.wait(0.5):
            with lock:
                if last_contact is None or offline or time.monotonic() - last_contact <= timeout:
                    continue
                try:
                    device.set_state('OFFLINE')
                    offline = True
                except Exception as exc:
                    last_error = str(exc)

    if start_watchdog:
        thread = threading.Thread(target=watchdog, daemon=True)
        thread.start()

    @app.post('/api/work-state')
    def work_state():
        nonlocal last_sequence, last_contact, current_state, offline, last_error
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='JSON object required'), 400
        state = data.get('state')
        seq = data.get('sequence')
        if not isinstance(state, str) or state not in VALID_STATES - {'OFFLINE'}:
            return jsonify(error='Invalid task state'), 400
        if type(seq) is not int or seq < 0:
            return jsonify(error='sequence must be a nonnegative integer'), 400
        for key in ('missing', 'uncertain'):
            value = data.get(key)
            if value is not None and (not isinstance(value, list) or any(not isinstance(x, str) for x in value)):
                return jsonify(error=f'{key} must be a list of strings'), 400
        elapsed = data.get('elapsed_seconds')
        if elapsed is not None and (type(elapsed) not in (int, float) or elapsed < 0):
            return jsonify(error='Invalid elapsed_seconds'), 400
        detail = data.get('detail')
        if detail is not None and not isinstance(detail, str):
            return jsonify(error='detail must be a string'), 400
        with lock:
            if seq < last_sequence:
                return jsonify(error='Stale sequence', last_sequence=last_sequence), 409
            if seq == last_sequence and state != current_state:
                return jsonify(error='Same sequence cannot change state'), 409
            try:
                device.set_state(state, missing=data.get('missing'), uncertain=data.get('uncertain'),
                                 elapsed_seconds=elapsed, detail=detail)
            except Exception as exc:
                last_error = str(exc)
                return jsonify(error='Hardware update failed', detail=last_error), 503
            last_sequence = seq
            last_contact = time.monotonic()
            current_state = state
            offline = False
            last_error = None
            return jsonify(ok=True, state=state, sequence=seq)

    @app.get('/api/status')
    def status():
        with lock:
            return jsonify(connected=True, display_state='OFFLINE' if offline else current_state,
                           task_state=current_state, sequence=last_sequence,
                           received_state=last_contact is not None,
                           communication_timeout=offline, error=last_error,
                           timestamp=datetime.now(timezone.utc).isoformat())

    @app.post('/api/alert')
    def alert():
        return jsonify(error='Not implemented in stage 1; state-change melodies are handled by /api/work-state'), 501

    @app.post('/api/reset')
    def reset():
        return jsonify(error='Not implemented in stage 1; reset requires separate hardware-safe handling'), 501

    app.config['SMARTCHECK_SHUTDOWN'] = stop.set
    return app


if __name__ == '__main__':
    # Do not enable the Flask reloader: it would initialize GPIO twice.
    create_app().run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)
