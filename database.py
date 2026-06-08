import sqlite3

DATABASE_NAME = "ev_bot.db"

def connect_db():
    return sqlite3.connect(DATABASE_NAME)

def init_db():
    conn = connect_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'MM',
            reg_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            car_name TEXT,
            car_model TEXT,
            battery_cap REAL,
            full_range REAL,
            charge_rate INTEGER DEFAULT 50,
            current_pct INTEGER DEFAULT 100,
            is_active INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            car_id INTEGER,
            action TEXT,
            value REAL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            station_name TEXT,
            address TEXT,
            latitude REAL,
            longitude REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

def get_or_create_user(uid):
    conn = connect_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (uid,))
    conn.commit()
    c.execute("SELECT * FROM users WHERE id = ?", (uid,))
    res = c.fetchone()
    conn.close()
    return res

def set_language(uid, lang):
    conn = connect_db()
    c = conn.cursor()
    get_or_create_user(uid)
    c.execute("UPDATE users SET language = ? WHERE id = ?", (lang, uid))
    conn.commit()
    conn.close()

def get_language(uid):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT language FROM users WHERE id = ?", (uid,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else "MM"

def add_car(uid, car_name, model, cap, frange, charge_rate=50):
    conn = connect_db()
    c = conn.cursor()
    get_or_create_user(uid)
    c.execute("SELECT COUNT(*) FROM cars WHERE user_id = ?", (uid,))
    count = c.fetchone()[0]
    is_active = 1 if count == 0 else 0
    c.execute("""
        INSERT INTO cars (user_id, car_name, car_model, battery_cap, full_range, charge_rate, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (uid, car_name, model, cap, frange, charge_rate, is_active))
    conn.commit()
    conn.close()

def get_active_car(uid):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT * FROM cars WHERE user_id = ? AND is_active = 1", (uid,))
    res = c.fetchone()
    conn.close()
    return res

def get_all_cars(uid):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT * FROM cars WHERE user_id = ?", (uid,))
    res = c.fetchall()
    conn.close()
    return res

def switch_car(uid, car_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("UPDATE cars SET is_active = 0 WHERE user_id = ?", (uid,))
    c.execute("UPDATE cars SET is_active = 1 WHERE id = ? AND user_id = ?", (car_id, uid))
    conn.commit()
    conn.close()

def delete_car(uid, car_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("DELETE FROM cars WHERE id = ? AND user_id = ?", (car_id, uid))
    conn.commit()
    conn.close()

def update_pct(uid, pct):
    conn = connect_db()
    c = conn.cursor()
    car = get_active_car(uid)
    if car:
        c.execute("UPDATE cars SET current_pct = ? WHERE id = ?", (pct, car[0]))
        c.execute(
            "INSERT INTO logs (user_id, car_id, action, value) VALUES (?, ?, ?, ?)",
            (uid, car[0], 'update_pct', pct)
        )
    conn.commit()
    conn.close()

def get_logs(uid):
    conn = connect_db()
    c = conn.cursor()
    car = get_active_car(uid)
    if not car:
        conn.close()
        return []
    c.execute(
        "SELECT * FROM logs WHERE user_id = ? AND car_id = ? ORDER BY date DESC LIMIT 10",
        (uid, car[0])
    )
    res = c.fetchall()
    conn.close()
    return res

def get_all_user_ids():
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users")
    res = c.fetchall()
    conn.close()
    return [r[0] for r in res]

def add_favorite(uid, name, address, lat, lon):
    conn = connect_db()
    c = conn.cursor()
    get_or_create_user(uid)
    c.execute("""
        INSERT INTO favorites (user_id, station_name, address, latitude, longitude)
        VALUES (?, ?, ?, ?, ?)
    """, (uid, name, address, lat, lon))
    conn.commit()
    conn.close()

def get_favorites(uid):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT * FROM favorites WHERE user_id = ?", (uid,))
    res = c.fetchall()
    conn.close()
    return res

def delete_favorite(uid, fav_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("DELETE FROM favorites WHERE id = ? AND user_id = ?", (fav_id, uid))
    conn.commit()
    conn.close()

init_db()
