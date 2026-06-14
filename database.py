import sqlite3
from datetime import datetime, timedelta

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

    c.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            plan TEXT DEFAULT 'free',
            start_date DATETIME,
            expire_date DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            months INTEGER,
            screenshot_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Smart Reminders
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reminder_type TEXT,
            value TEXT,
            note TEXT,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Expense Tracker
    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            amount INTEGER,
            note TEXT,
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

# --- USER ---
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

# --- SUBSCRIPTION ---
def get_plan(uid):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT plan, expire_date FROM subscriptions WHERE user_id = ?", (uid,))
    res = c.fetchone()
    conn.close()
    if not res:
        return "free"
    plan, expire_date = res
    if plan == "premium" and expire_date:
        if datetime.now() > datetime.fromisoformat(expire_date):
            return "free"
    return plan

def is_premium(uid):
    return get_plan(uid) == "premium"

def activate_premium(uid, months=1):
    conn = connect_db()
    c = conn.cursor()
    get_or_create_user(uid)
    now = datetime.now()
    c.execute("SELECT expire_date FROM subscriptions WHERE user_id = ?", (uid,))
    res = c.fetchone()
    if res and res[0]:
        try:
            current_expire = datetime.fromisoformat(res[0])
            new_expire = current_expire + timedelta(days=30*months) if current_expire > now else now + timedelta(days=30*months)
        except:
            new_expire = now + timedelta(days=30*months)
    else:
        new_expire = now + timedelta(days=30*months)
    c.execute("INSERT OR REPLACE INTO subscriptions (user_id, plan, start_date, expire_date) VALUES (?, 'premium', ?, ?)",
              (uid, now.isoformat(), new_expire.isoformat()))
    conn.commit()
    conn.close()
    return new_expire

def get_expire_date(uid):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT expire_date FROM subscriptions WHERE user_id = ?", (uid,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

def get_premium_users_count():
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM subscriptions WHERE plan='premium' AND expire_date > ?", (datetime.now().isoformat(),))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

def get_total_users_count():
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

# --- PENDING PAYMENTS ---
def add_pending_payment(uid, amount, months, screenshot_file_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("INSERT INTO pending_payments (user_id, amount, months, screenshot_file_id) VALUES (?, ?, ?, ?)",
              (uid, amount, months, screenshot_file_id))
    payment_id = c.lastrowid
    conn.commit()
    conn.close()
    return payment_id

def get_pending_payment(payment_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT * FROM pending_payments WHERE id = ?", (payment_id,))
    res = c.fetchone()
    conn.close()
    return res

def update_payment_status(payment_id, status):
    conn = connect_db()
    c = conn.cursor()
    c.execute("UPDATE pending_payments SET status = ? WHERE id = ?", (status, payment_id))
    conn.commit()
    conn.close()

def get_all_pending_payments():
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT * FROM pending_payments WHERE status='pending' ORDER BY created_at DESC")
    res = c.fetchall()
    conn.close()
    return res

# --- CARS ---
def add_car(uid, car_name, model, cap, frange, charge_rate=50):
    conn = connect_db()
    c = conn.cursor()
    get_or_create_user(uid)
    c.execute("SELECT COUNT(*) FROM cars WHERE user_id = ?", (uid,))
    count = c.fetchone()[0]
    is_active = 1 if count == 0 else 0
    c.execute("INSERT INTO cars (user_id, car_name, car_model, battery_cap, full_range, charge_rate, is_active) VALUES (?,?,?,?,?,?,?)",
              (uid, car_name, model, cap, frange, charge_rate, is_active))
    conn.commit()
    conn.close()

def get_cars_count(uid):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cars WHERE user_id = ?", (uid,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

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
        c.execute("INSERT INTO logs (user_id, car_id, action, value) VALUES (?,?,?,?)",
                  (uid, car[0], 'update_pct', pct))
    conn.commit()
    conn.close()

def get_logs(uid, days=None):
    conn = connect_db()
    c = conn.cursor()
    car = get_active_car(uid)
    if not car:
        conn.close()
        return []
    if days:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        c.execute("SELECT * FROM logs WHERE user_id=? AND car_id=? AND date>? ORDER BY date DESC LIMIT 10",
                  (uid, car[0], since))
    else:
        c.execute("SELECT * FROM logs WHERE user_id=? AND car_id=? ORDER BY date DESC LIMIT 10",
                  (uid, car[0]))
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

# --- FAVORITES ---
def add_favorite(uid, name, address, lat, lon):
    conn = connect_db()
    c = conn.cursor()
    get_or_create_user(uid)
    c.execute("INSERT INTO favorites (user_id, station_name, address, latitude, longitude) VALUES (?,?,?,?,?)",
              (uid, name, address, lat, lon))
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
    c.execute("DELETE FROM favorites WHERE id=? AND user_id=?", (fav_id, uid))
    conn.commit()
    conn.close()

# --- REMINDERS ---
def add_reminder(uid, reminder_type, value, note=""):
    conn = connect_db()
    c = conn.cursor()
    get_or_create_user(uid)
    c.execute("INSERT INTO reminders (user_id, reminder_type, value, note) VALUES (?,?,?,?)",
              (uid, reminder_type, value, note))
    conn.commit()
    conn.close()

def get_reminders(uid):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT * FROM reminders WHERE user_id=? AND is_active=1", (uid,))
    res = c.fetchall()
    conn.close()
    return res

def delete_reminder(uid, reminder_id):
    conn = connect_db()
    c = conn.cursor()
    c.execute("UPDATE reminders SET is_active=0 WHERE id=? AND user_id=?", (reminder_id, uid))
    conn.commit()
    conn.close()

# --- EXPENSES ---


init_db()

# --- BATTERY HEALTH ---
def save_battery_health(uid, soh, mileage):
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS battery_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            soh REAL,
            mileage INTEGER,
            date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("INSERT INTO battery_health (user_id, soh, mileage) VALUES (?,?,?)",
              (uid, soh, mileage))
    conn.commit()
    conn.close()

def get_battery_health_history(uid):
    conn = connect_db()
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM battery_health WHERE user_id=? ORDER BY date DESC LIMIT 10", (uid,))
        res = c.fetchall()
    except:
        res = []
    conn.close()
    return res

# --- EXPENSES ---
def add_expense(uid, category, amount, note=""):
    conn = connect_db()
    c = conn.cursor()
    get_or_create_user(uid)
    c.execute("INSERT INTO expenses (user_id, category, amount, note) VALUES (?,?,?,?)",
              (uid, category, amount, note))
    conn.commit()
    conn.close()

def get_monthly_expenses(uid, year, month):
    conn = connect_db()
    c = conn.cursor()
    try:
        # Fixed date formatting to match SQLite strftime
        c.execute("""SELECT * FROM expenses WHERE user_id=?
                     AND strftime('%Y', date)=? AND strftime('%m', date)=?
                     ORDER BY date DESC""",
                  (uid, str(year), f"{month:02d}"))
        res = c.fetchall()
    except:
        res = []
    conn.close()
    return res

def get_weekly_stats(uid):
    """Last 7 days battery logs for weekly summary"""
    conn = connect_db()
    c = conn.cursor()
    car = get_active_car(uid)
    if not car:
        conn.close()
        return []
    try:
        since = (datetime.now() - timedelta(days=7)).isoformat()
        c.execute("SELECT * FROM logs WHERE user_id=? AND car_id=? AND date>? ORDER BY date ASC",
                  (uid, car[0], since))
        res = c.fetchall()
    except:
        res = []
    conn.close()
    return res

# --- STATION COMMUNITY REPORTS ---
def init_station_reports():
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS station_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT,
            station_name TEXT,
            status TEXT,
            reported_by INTEGER,
            reported_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_station_report(station_id, station_name, status, user_id):
    init_station_reports()
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO station_reports (station_id, station_name, status, reported_by)
        VALUES (?, ?, ?, ?)
    """, (station_id, station_name, status, user_id))
    conn.commit()
    conn.close()

def get_station_last_report(station_id):
    init_station_reports()
    conn = connect_db()
    c = conn.cursor()
    c.execute("""
        SELECT status, reported_at FROM station_reports
        WHERE station_id = ?
        ORDER BY reported_at DESC LIMIT 1
    """, (station_id,))
    res = c.fetchone()
    conn.close()
    return res

def get_station_report_summary(station_id):
    """Last 24hr reports summary"""
    init_station_reports()
    conn = connect_db()
    c = conn.cursor()
    since = (datetime.now() - timedelta(hours=24)).isoformat()
    c.execute("""
        SELECT status, COUNT(*) as cnt FROM station_reports
        WHERE station_id = ? AND reported_at > ?
        GROUP BY status ORDER BY cnt DESC
    """, (station_id, since))
    res = c.fetchall()
    conn.close()
    return res
