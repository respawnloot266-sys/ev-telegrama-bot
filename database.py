import sqlite3
import os

DB_PATH = "evbot.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        car_model TEXT,
        battery_capacity REAL,
        battery_percent REAL DEFAULT 100,
        full_range REAL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS charge_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        start_percent REAL,
        end_percent REAL,
        kwh REAL,
        cost REAL
    )''')
    conn.commit()
    conn.close()

def register_user(user_id, username, car_model, battery, full_range):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users 
        (user_id, username, car_model, battery_capacity, battery_percent, full_range)
        VALUES (?, ?, ?, ?, 100, ?)''', (user_id, username, car_model, battery, full_range))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_battery(user_id, percent):
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE users SET battery_percent = ? WHERE user_id = ?', (percent, user_id))
    conn.commit()
    conn.close()

def get_history(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM charge_history WHERE user_id = ? ORDER BY id DESC', (user_id,))
    records = c.fetchall()
    conn.close()
    return records

init_db()