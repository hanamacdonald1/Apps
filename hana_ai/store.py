import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def db():
    root = Path(os.getenv('HANA_DATA_DIR', str(Path.home() / '.hana-ai')))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(root / 'hana.db', timeout=30)
    connection.row_factory = sqlite3.Row
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS items (kind TEXT, id TEXT, data TEXT,
            updated TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, agent TEXT,
            status TEXT, detail TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE,
            payload TEXT, state TEXT DEFAULT 'pending', detail TEXT DEFAULT '',
            created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS leases (name TEXT PRIMARY KEY, expires REAL);
    ''')
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def setting(key, default=None):
    with db() as c:
        row = c.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return json.loads(row[0]) if row else default


def save_setting(key, value):
    with db() as c:
        c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))


def put(kind, identity, data):
    with db() as c:
        old = c.execute('SELECT data FROM items WHERE kind=? AND id=?', (kind, identity)).fetchone()
        if old:
            previous = json.loads(old[0])
            if 'stage' in previous:
                data['stage'] = previous['stage']
        c.execute('INSERT OR REPLACE INTO items(kind,id,data) VALUES (?,?,?)',
                  (kind, identity, json.dumps(data)))
    return old is None


def items(kind):
    with db() as c:
        return [dict(json.loads(r['data']), _id=r['id']) for r in c.execute(
            'SELECT * FROM items WHERE kind=? ORDER BY updated DESC LIMIT 1000', (kind,))]


def event(agent, status, detail):
    with db() as c:
        c.execute('INSERT INTO events(agent,status,detail) VALUES (?,?,?)', (agent, status, detail))


def events():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 100')]


def actions():
    with db() as c:
        return [dict(r, payload=json.loads(r['payload'])) for r in c.execute(
            'SELECT * FROM actions ORDER BY id DESC LIMIT 100')]
