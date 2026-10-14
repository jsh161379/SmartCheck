"""SmartCheck SQLite persistence. Uses wall-clock UTC timestamps; durations come from TaskController."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'data' / 'smartcheck.db'


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


class SmartCheckDB:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                selected_items TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'CHECKING',
                work_started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL,
                last_result TEXT,
                error_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL REFERENCES tasks(id),
                inspected_at TEXT NOT NULL,
                result TEXT NOT NULL CHECK(result IN ('PASS','FAIL','RECHECK')),
                selected_items TEXT NOT NULL,
                missing_items TEXT NOT NULL,
                uncertain_items TEXT NOT NULL,
                detection_counts TEXT NOT NULL,
                confidence REAL NOT NULL,
                total_frames INTEGER NOT NULL DEFAULT 5,
                evidence_path TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_inspections_task ON inspections(task_id);
            CREATE TABLE IF NOT EXISTS pi_delivery_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER REFERENCES tasks(id),
                attempted_at TEXT NOT NULL,
                state TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK(outcome IN ('SUCCESS','FAILED')),
                error_message TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_pi_delivery_task ON pi_delivery_events(task_id);
            CREATE TABLE IF NOT EXISTS presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                selected_items TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL
            );
        ''')
        # A process restart cannot count as a successful completion.
        self.conn.execute("UPDATE tasks SET status='INTERRUPTED', finished_at=? WHERE status IN ('CHECKING','WORKING','FAIL','RECHECK','PASS')", (now_iso(),))
        self.conn.commit()

    def begin_task(self, selected):
        with self.conn:
            cur = self.conn.execute('INSERT INTO tasks(created_at,selected_items,status) VALUES(?,?,?)',
                                    (now_iso(), json.dumps(sorted(selected)), 'CHECKING'))
            return cur.lastrowid

    def mark_checking(self, task_id):
        with self.conn:
            self.conn.execute("UPDATE tasks SET status='CHECKING' WHERE id=?", (task_id,))

    def save_inspection(self, task_id, result, confidence, evidence_path=None):
        with self.conn:
            self.conn.execute('''INSERT INTO inspections(task_id,inspected_at,result,selected_items,missing_items,uncertain_items,detection_counts,confidence,total_frames,evidence_path)
                VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                task_id, now_iso(), result['result'], json.dumps(result['selected_items']),
                json.dumps(result['missing_items']), json.dumps(result['uncertain_items']),
                json.dumps(result['counts']), confidence, result['total_frames'], evidence_path))
            started = now_iso() if result['result'] == 'PASS' else None
            self.conn.execute('''UPDATE tasks SET status=?, last_result=?, work_started_at=COALESCE(work_started_at, ?) WHERE id=?''',
                              ('WORKING' if started else result['result'], result['result'], started, task_id))

    def get_work_started_at(self, task_id):
        """Return the persisted local-offset ISO timestamp for a task, if started."""
        row = self.conn.execute(
            'SELECT work_started_at FROM tasks WHERE id=?', (task_id,)
        ).fetchone()
        return row['work_started_at'] if row is not None else None

    def finish_task(self, task_id, status, duration):
        if status not in ('COMPLETED', 'CANCELED'):
            raise ValueError('Invalid final status')
        with self.conn:
            self.conn.execute('UPDATE tasks SET status=?, finished_at=?, duration_seconds=? WHERE id=?',
                              (status, now_iso(), duration, task_id))

    def mark_error(self, task_id, reason):
        with self.conn:
            self.conn.execute("UPDATE tasks SET status='ERROR', error_reason=? WHERE id=?", (reason, task_id))

    def list_tasks(self, limit=300):
        return self.conn.execute('''SELECT t.id, t.created_at, t.status, t.last_result,
            t.work_started_at, t.finished_at, t.duration_seconds, t.selected_items,
            (SELECT COUNT(*) FROM inspections i WHERE i.task_id=t.id) AS inspection_count
            FROM tasks t ORDER BY t.id DESC LIMIT ?''', (limit,)).fetchall()

    def list_inspections(self, limit=500):
        return self.conn.execute('''SELECT i.id, i.task_id, i.inspected_at, i.result,
            i.selected_items, i.missing_items, i.uncertain_items, i.detection_counts,
            i.confidence, i.evidence_path FROM inspections i ORDER BY i.id DESC LIMIT ?''', (limit,)).fetchall()

    def get_statistics(self):
        """Aggregate all stored records; never fabricate counts."""
        task_rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
        ).fetchall()
        inspection_rows = self.conn.execute(
            "SELECT result, COUNT(*) AS n FROM inspections GROUP BY result"
        ).fetchall()
        durations = self.conn.execute("""
            SELECT COUNT(*) AS n, AVG(duration_seconds) AS avg_seconds,
                   MIN(duration_seconds) AS min_seconds,
                   MAX(duration_seconds) AS max_seconds
            FROM tasks WHERE status='COMPLETED' AND duration_seconds IS NOT NULL
        """).fetchone()
        missing = {name: 0 for name in ('book', 'cell phone', 'scissors')}
        uncertain = dict(missing)
        for row in self.conn.execute('SELECT missing_items, uncertain_items FROM inspections'):
            for item in json.loads(row['missing_items']):
                missing[item] = missing.get(item, 0) + 1
            for item in json.loads(row['uncertain_items']):
                uncertain[item] = uncertain.get(item, 0) + 1
        return {
            'total_tasks': sum(row['n'] for row in task_rows),
            'total_inspections': sum(row['n'] for row in inspection_rows),
            'tasks': {row['status']: row['n'] for row in task_rows},
            'inspections': {row['result']: row['n'] for row in inspection_rows},
            'completed_durations': dict(durations),
            'missing_by_item': missing,
            'uncertain_by_item': uncertain,
        }

    def list_presets(self):
        return self.conn.execute('SELECT id, name, selected_items, confidence FROM presets ORDER BY name COLLATE NOCASE').fetchall()

    def save_preset(self, name, selected_items, confidence):
        name = name.strip()
        allowed = {'book', 'cell phone', 'scissors'}
        selected = set(selected_items)
        if not name or len(name) > 40:
            raise ValueError('프리셋 이름은 1~40자로 입력하세요.')
        if not selected or not selected.issubset(allowed):
            raise ValueError('검사 물품을 하나 이상 선택하세요.')
        if not 0.05 <= float(confidence) <= 0.95:
            raise ValueError('신뢰도는 0.05~0.95여야 합니다.')
        with self.conn:
            self.conn.execute('INSERT INTO presets(name, selected_items, confidence, created_at) VALUES(?,?,?,?)',
                              (name, json.dumps(sorted(selected)), float(confidence), now_iso()))

    def delete_preset(self, preset_id):
        with self.conn:
            self.conn.execute('DELETE FROM presets WHERE id=?', (int(preset_id),))

    def save_pi_delivery(self, task_id, state, success, error_message=None):
        """HTTP 상태 전달 결과만 저장. 실제 GPIO 출력 성공을 의미하지 않는다."""
        with self.conn:
            self.conn.execute(
                'INSERT INTO pi_delivery_events(task_id,attempted_at,state,outcome,error_message) VALUES(?,?,?,?,?)',
                (task_id, now_iso(), state, 'SUCCESS' if success else 'FAILED',
                 None if success else str(error_message or '통신 오류')))

    def list_pi_deliveries(self, limit=100):
        return self.conn.execute(
            'SELECT * FROM pi_delivery_events ORDER BY id DESC LIMIT ?', (limit,)).fetchall()

    def close(self):
        self.conn.close()
