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
            charge_rate INTEGER DEFAULT 50,
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

    # Migration: ဟောင်းသော DB မှာ charge_rate column မရှိသေးရင် ထည့်တယ်
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN charge_rate INTEGER DEFAULT 50")
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.commit()
    conn.close()

def save_user(uid, model, cap, frange, charge_rate=50):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (id, car_model, battery_cap, full_range, charge_rate) VALUES (?,?,?,?,?)",
        (uid, model, cap, frange, charge_rate)
    )
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
    cursor.execute(
        "INSERT INTO logs (user_id, action, value) VALUES (?, ?, ?)",
        (uid, 'update_pct', pct)
    )
    conn.commit()
    conn.close()

def get_logs(uid):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM logs WHERE user_id = ? ORDER BY date DESC LIMIT 10",
        (uid,)
    )
    res = cursor.fetchall()
    conn.close()
    return res

def get_all_user_ids():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    res = cursor.fetchall()
    conn.close()
    return [row[0] for row in res]

init_db()
