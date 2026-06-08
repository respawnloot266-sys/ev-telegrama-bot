import sqlite3
from datetime import datetime

DATABASE_NAME = "ev_bot.db"

def connect_db():
    return sqlite3.connect(DATABASE_NAME)

def init_db():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            car_model TEXT,
            battery_cap REAL,
            full_range REAL,
            current_pct INTEGER DEFAULT 100,
            reg_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            value REAL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_user(uid, model, cap, frange):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (id, car_model, battery_cap, full_range) VALUES (?,?,?,?)", (uid, model, cap, frange))
    conn.commit()
    conn.close()

def get_user(uid):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))
    res = cursor.fetchone()
    conn.close()
    return res

def update_pct(uid, pct):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET current_pct = ? WHERE id = ?", (pct, uid))
    cursor.execute("INSERT INTO logs (user_id, action, value) VALUES (?, 'update_pct', ?)", (uid, pct))
    conn.commit()
    conn.close()

init_db()
