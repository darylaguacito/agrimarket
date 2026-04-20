import sqlite3
import os
from flask import g

DB_PATH = os.path.join(os.path.dirname(__file__), 'agrimarket.db')

def get_db():
    if 'db' not in g:
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row   # dict-like rows
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        g.db = db
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query(sql, params=None, fetchone=False, fetchall=False, commit=False):
    # SQLite uses ? placeholders; replace MySQL %s
    sql = sql.replace('%s', '?')
    db  = get_db()
    cur = db.execute(sql, params or ())
    result = None
    if fetchone:
        row = cur.fetchone()
        result = dict(row) if row else None
    elif fetchall:
        rows = cur.fetchall()
        result = [dict(r) for r in rows]
    if commit:
        db.commit()
        result = cur.lastrowid
    return result
