import sqlite3
from datetime import datetime

# ============================================================
# CONNECTION
# ============================================================

def get_connection(path: str):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# INIT DATABASE
# ============================================================

def init_db(path: str):
    conn = get_connection(path)
    cur = conn.cursor()

    # ---------- USERS ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            full_name TEXT,
            role TEXT NOT NULL DEFAULT 'user'
        )
    """)

    # ---------- CARS ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vin TEXT UNIQUE NOT NULL,
            mileage INTEGER NOT NULL,
            year INTEGER,
            owner_company TEXT,
            model TEXT,
            plate TEXT UNIQUE,
            fuel_type TEXT
        )
    """)

    # ---------- SERVICES ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            mechanic_tg_id INTEGER,
            admin_tg_id INTEGER,
            created_by_tg_id INTEGER NOT NULL,
            created_by_role TEXT NOT NULL,
            description TEXT NOT NULL,
            desired_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_admin',
            final_mileage INTEGER,
            cost_net REAL,
            comments TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (car_id) REFERENCES cars(id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# USERS
# ============================================================

def add_user(path, tg_id, full_name):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (tg_id, full_name) VALUES (?, ?)",
        (tg_id, full_name)
    )
    conn.commit()
    conn.close()


def set_user_role(path, tg_id, role):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("UPDATE users SET role = ? WHERE tg_id = ?", (role, tg_id))
    conn.commit()
    conn.close()


def get_user_role(path, tg_id):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE tg_id = ?", (tg_id,))
    row = cur.fetchone()
    conn.close()
    return row["role"] if row else None


def list_users_by_role(path, role):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("SELECT tg_id, full_name FROM users WHERE role = ?", (role,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ============================================================
# CARS
# ============================================================

def list_cars(path):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM cars ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def find_car_by_identifier(path, identifier):
    ident = identifier.strip().upper()
    conn = get_connection(path)
    cur = conn.cursor()

    if ident.isdigit():
        cur.execute("SELECT * FROM cars WHERE id = ?", (int(ident),))
        car = cur.fetchone()
        if car:
            conn.close()
            return car

    cur.execute(
        "SELECT * FROM cars WHERE UPPER(vin)=? OR UPPER(plate)=?",
        (ident, ident)
    )
    car = cur.fetchone()
    conn.close()
    return car


# ============================================================
# SERVICES
# ============================================================

def create_service(path, car_id, creator_tg_id, creator_role,
                   description, desired_at, mechanic_tg_id=None):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO services (
            car_id, mechanic_tg_id,
            created_by_tg_id, created_by_role,
            description, desired_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (car_id, mechanic_tg_id, creator_tg_id, creator_role,
          description, desired_at))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def assign_mechanic(path, service_id, mechanic_tg_id):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("""
        UPDATE services
        SET mechanic_tg_id = ?, status='approved'
        WHERE id = ?
    """, (mechanic_tg_id, service_id))
    conn.commit()
    conn.close()


def admin_approve_service(path, service_id, admin_tg_id):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("""
        UPDATE services
        SET status='approved', admin_tg_id=?
        WHERE id = ?
    """, (admin_tg_id, service_id))
    conn.commit()
    conn.close()


def admin_reject_service(path, service_id, admin_tg_id):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("""
        UPDATE services
        SET status='rejected', admin_tg_id=?
        WHERE id = ?
    """, (admin_tg_id, service_id))
    conn.commit()
    conn.close()


def list_pending_services(path):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*, c.*
        FROM services s
        JOIN cars c ON c.id = s.car_id
        WHERE s.status IN ('pending_admin', 'approved')
        ORDER BY s.created_at
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_services_for_mechanic(path, mechanic_tg_id):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*, c.*
        FROM services s
        JOIN cars c ON c.id = s.car_id
        WHERE s.mechanic_tg_id = ?
          AND s.status = 'approved'
        ORDER BY s.desired_at
    """, (mechanic_tg_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def set_service_result(path, svc_id, final_mileage, cost_net, comments):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("""
        UPDATE services
        SET final_mileage = ?,
            cost_net = ?,
            comments = ?,
            status = 'completed',
            completed_at = ?
        WHERE id = ?
    """, (final_mileage, cost_net, comments,
          datetime.now().isoformat(), svc_id))
    conn.commit()
    conn.close()


def list_service_history(path, mechanic_tg_id=None):
    conn = get_connection(path)
    cur = conn.cursor()

    if mechanic_tg_id:
        cur.execute("""
            SELECT s.*, c.*
            FROM services s
            JOIN cars c ON c.id = s.car_id
            WHERE s.mechanic_tg_id = ?
              AND s.status = 'completed'
            ORDER BY s.completed_at DESC
        """, (mechanic_tg_id,))
    else:
        cur.execute("""
            SELECT s.*, c.*
            FROM services s
            JOIN cars c ON c.id = s.car_id
            WHERE s.status = 'completed'
            ORDER BY s.completed_at DESC
        """)

    rows = cur.fetchall()
    conn.close()
    return rows


def sum_service_cost(path, date_from, date_to):
    conn = get_connection(path)
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(cost_net),0) as total
        FROM services
        WHERE status='completed'
          AND completed_at BETWEEN ? AND ?
    """, (date_from, date_to))
    total = cur.fetchone()["total"]
    conn.close()
    return total
