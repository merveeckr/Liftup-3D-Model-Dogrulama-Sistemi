import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'history.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT    NOT NULL,
            model         TEXT    NOT NULL,
            n_points      INTEGER,
            noise_std     REAL,
            defect_count  INTEGER,
            conformance   REAL,
            verdict       TEXT,
            overall_risk  TEXT,
            rms           REAL,
            max_deviation REAL,
            result_json   TEXT    NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def save_analysis(model: str, n_points: int, noise_std: float,
                  defect_count: int, result: dict) -> int:
    stats = result['stats']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        '''INSERT INTO analyses
           (timestamp, model, n_points, noise_std, defect_count,
            conformance, verdict, overall_risk, rms, max_deviation, result_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            datetime.now().isoformat(),
            model,
            n_points,
            noise_std,
            defect_count,
            stats['conformance'],
            stats['verdict'],
            stats['overall_risk'],
            stats['rms'],
            stats['max_deviation'],
            json.dumps(result, ensure_ascii=False),
        )
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def list_analyses(limit: int = 100) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        '''SELECT id, timestamp, model, n_points, noise_std, defect_count,
                  conformance, verdict, overall_risk, rms, max_deviation
           FROM analyses ORDER BY id DESC LIMIT ?''',
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_analysis(analysis_id: int) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        'SELECT * FROM analyses WHERE id = ?', (analysis_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d['result'] = json.loads(d.pop('result_json'))
    return d


def delete_analysis(analysis_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('DELETE FROM analyses WHERE id = ?', (analysis_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def clear_all() -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('DELETE FROM analyses')
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected
