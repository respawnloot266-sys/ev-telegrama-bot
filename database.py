
import sqlite3
from datetime import datetime
from config import DATABASE_NAME

def connect_db():
    """Connects to the SQLite database."""
    return sqlite3.connect(DATABASE_NAME)
    def get_logs(uid):
    conn = connect_db()
    cursor = conn.cursor()
    # နောက်ဆုံးပို့ခဲ့တဲ့ မှတ်တမ်း ၁၀ ခုကို ပြပါမယ်
    cursor.execute("SELECT * FROM logs WHERE user_id = ? ORDER BY date DESC LIMIT 10", (uid,))
    res = cursor.fetchall()
    conn.close()
    return res


def init_db():
    """Initializes the database with necessary tables."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            car_model TEXT NOT NULL,
            battery_capacity_kwh REAL NOT NULL,
            full_charge_range_km REAL NOT NULL,
            current_battery_percent INTEGER DEFAULT 0,
            low_battery_threshold INTEGER DEFAULT 20,
            last_location_lat REAL,
            last_location_lon REAL,
            registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS charge_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            start_battery_percent INTEGER NOT NULL,
            end_battery_percent INTEGER NOT NULL,
            kwh_charged REAL,
            cost REAL,
            station_name TEXT,
            station_id TEXT,
            charger_type TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorite_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            station_name TEXT NOT NULL,
            station_address TEXT,
            station_lat REAL NOT NULL,
            station_lon REAL NOT NULL,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS car_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL UNIQUE,
            supported_chargers TEXT,
            max_charge_rate_kw REAL,
            battery_capacity_kwh REAL
        );
    """)
    conn.commit()
    conn.close()

def register_user(user_id, car_model, battery_capacity_kwh, full_charge_range_km):
    """Registers a new user or updates existing user's car info."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (id, car_model, battery_capacity_kwh, full_charge_range_km)
        VALUES (?, ?, ?, ?)
    """, (user_id, car_model, battery_capacity_kwh, full_charge_range_km))
    conn.commit()
    conn.close()

def get_user(user_id):
    """Retrieves user information by user_id."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_battery_status(user_id, battery_percent):
    """Updates the current battery percentage for a user."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET current_battery_percent = ? WHERE id = ?", (battery_percent, user_id))
    conn.commit()
    conn.close()

def update_user_location(user_id, lat, lon):
    """Updates the last known location for a user."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_location_lat = ?, last_location_lon = ? WHERE id = ?", (lat, lon))
    conn.commit()
    conn.close()

def add_charge_history(user_id, start_time, end_time, start_battery_percent, end_battery_percent, kwh_charged=None, cost=None, station_name=None, station_id=None, charger_type=None):
    """Adds a new charge history record."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO charge_history (
            user_id, start_time, end_time, start_battery_percent, end_battery_percent,
            kwh_charged, cost, station_name, station_id, charger_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, start_time, end_time, start_battery_percent, end_battery_percent,
        kwh_charged, cost, station_name, station_id, charger_type
    ))
    conn.commit()
    conn.close()

def get_charge_history(user_id, limit=10):
    """Retrieves charge history for a user."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM charge_history WHERE user_id = ? ORDER BY end_time DESC LIMIT ?", (user_id, limit))
    history = cursor.fetchall()
    conn.close()
    return history

def add_favorite_station(user_id, station_name, station_address, station_lat, station_lon):
    """Adds a charge station to user's favorites."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO favorite_stations (user_id, station_name, station_address, station_lat, station_lon)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, station_name, station_address, station_lat, station_lon))
    conn.commit()
    conn.close()

def get_favorite_stations(user_id):
    """Retrieves favorite stations for a user."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM favorite_stations WHERE user_id = ?", (user_id,))
    favorites = cursor.fetchall()
    conn.close()
    return favorites

def add_car_model_info(model_name, supported_chargers=None, max_charge_rate_kw=None, battery_capacity_kwh=None):
    """Adds or updates car model specific information."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO car_models (model_name, supported_chargers, max_charge_rate_kw, battery_capacity_kwh)
        VALUES (?, ?, ?, ?)
    """, (model_name, supported_chargers, max_charge_rate_kw, battery_capacity_kwh))
    conn.commit()
    conn.close()

def get_car_model_info(model_name):
    """Retrieves car model specific information."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM car_models WHERE model_name = ?", (model_name,))
    model_info = cursor.fetchone()
    conn.close()
    return model_info