import sqlite3
import os
from werkzeug.security import generate_password_hash

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
DB_PATH = os.path.join(DATA_DIR, 'protokoly.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_number TEXT UNIQUE NOT NULL,
            doc_type TEXT NOT NULL CHECK(doc_type IN ('office','telefon','produkcja')),
            operation TEXT NOT NULL CHECK(operation IN ('wydanie','zwrot')),
            doc_date TEXT NOT NULL,
            issuer_name TEXT NOT NULL,
            receiver_name TEXT NOT NULL,
            receiver_email TEXT NOT NULL,
            network_name TEXT,
            sig_issuer TEXT,
            sig_receiver TEXT,
            signed_at DATETIME,
            email_sent_at DATETIME,
            created_by INTEGER REFERENCES users(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS document_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            sort_order INTEGER DEFAULT 0,
            equipment_type TEXT,
            manufacturer_model TEXT,
            serial_number TEXT,
            quantity INTEGER DEFAULT 1,
            internal_number TEXT,
            phone_type TEXT,
            imei TEXT,
            internal_name TEXT,
            phone_number TEXT,
            sim_number TEXT,
            pin_phone TEXT,
            pin_sim TEXT,
            acc_foil INTEGER DEFAULT 0,
            acc_case INTEGER DEFAULT 0,
            acc_charger INTEGER DEFAULT 0,
            acc_headphones INTEGER DEFAULT 0,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
    ''')

    user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if user_count == 0:
        conn.execute(
            'INSERT INTO users (username, password_hash, full_name) VALUES (?,?,?)',
            ('admin', generate_password_hash('admin123'), 'Administrator IT')
        )
        print('Utworzono domyslnego uzytkownika: admin / admin123')

    default_settings = [
        ('accounting_email', ''),
        ('smtp_host', ''),
        ('smtp_port', '587'),
        ('smtp_user', ''),
        ('smtp_pass', ''),
        ('smtp_from', ''),
        ('smtp_from_name', 'Dzial IT Brueggen Polska'),
        ('smtp_use_tls', '1'),
    ]
    for key, value in default_settings:
        conn.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)', (key, value))

    conn.commit()
    conn.close()


def generate_doc_number(conn, doc_type):
    from datetime import datetime
    year = datetime.now().year
    prefix = {'office': 'OFF', 'telefon': 'TEL', 'produkcja': 'PRD'}.get(doc_type, 'DOC')
    count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE doc_type=? AND strftime('%Y', created_at)=?",
        (doc_type, str(year))
    ).fetchone()[0]
    return f'IT-{prefix}-{year}-{str(count + 1).zfill(3)}'
