import sqlite3
from datetime import datetime
import os

DB_NAME = "ev_bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        car_model TEXT,
        battery_capacity_kwh REAL,
        current_battery_percent REAL DEFAULT 100,
        full_charge_range_km REAL,
        registered_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS charge_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        start_percent REAL,
        end_percent REAL,
        kwh_used REAL,
        total_cost REAL,
        station_name TEXT,
        charged_at TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS charge_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        start_percent REAL,
        end_percent REAL,
        start_time TEXT,
        end_time TEXT,
        status TEXT DEFAULT 'charging',
        station_name TEXT,
        charger_type TEXT,
        kwh_used REAL,
        total_cost REAL
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        user_id INTEGER PRIMARY KEY,
        low_battery_threshold INTEGER DEFAULT 20
    )''')
    
    conn.commit()
    conn.close()

def register_user(user_id, username, car_model, battery_capacity, full_range):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users 
                 (user_id, username, car_model, battery_capacity_kwh, 
                  current_battery_percent, full_charge_range_km, registered_at)
                 VALUES (?, ?, ?, ?, 100, ?, ?)''',
              (user_id, username, car_model, battery_capacity, 
               full_range, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_battery(user_id, percent):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET current_battery_percent = ? WHERE user_id = ?",
              (percent, user_id))
    conn.commit()
    conn.close()

def get_low_battery_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''SELECT u.user_id, u.username, u.current_battery_percent, a.low_battery_threshold
                 FROM users u
                 LEFT JOIN alerts a ON u.user_id = a.user_id
                 WHERE u.current_battery_percent <= COALESCE(a.low_battery_threshold, 20)''')
    users = c.fetchall()
    conn.close()
    return users

def log_charge_session(user_id, start_percent, end_percent, kwh_used, cost, station_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO charge_history 
                 (user_id, start_percent, end_percent, kwh_used, total_cost, station_name, charged_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, start_percent, end_percent, kwh_used, cost, 
               station_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_charge_history(user_id, limit=10):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''SELECT * FROM charge_history 
                 WHERE user_id = ? 
                 ORDER BY charged_at DESC LIMIT ?''',
              (user_id, limit))
    history = c.fetchall()
    conn.close()
    return history

def start_session(user_id, start_percent):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO charge_sessions 
                 (user_id, start_percent, start_time, status)
                 VALUES (?, ?, ?, 'charging')''',
              (user_id, start_percent, datetime.now().isoformat()))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def finish_session(session_id, end_percent, kwh_used, cost):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''UPDATE charge_sessions 
                 SET end_percent=?, end_time=?, status='completed', 
                     kwh_used=?, total_cost=?
                 WHERE id=?''',
              (end_percent, datetime.now().isoformat(), kwh_used, cost, session_id))
    conn.commit()
    conn.close()