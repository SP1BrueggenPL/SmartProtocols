import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, make_response, g
)
from werkzeug.security import check_password_hash, generate_password_hash

from database import init_db, get_db, generate_doc_number
from pdf_gen import generate_pdf
from email_sender import send_email

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def db():
    if 'db' not in g:
        g.db = get_db()
    return g.db


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'user_id' in session else url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = db().execute(
            'SELECT * FROM users WHERE username=? AND is_active=1', (username,)
        ).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            return redirect(url_for('dashboard'))
        error = 'Nieprawidłowa nazwa użytkownika lub hasło.'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    doc_type = request.args.get('type', '')
    status = request.args.get('status', '')

    query = 'SELECT * FROM documents WHERE 1=1'
    params = []
    if doc_type:
        query += ' AND doc_type=?'
        params.append(doc_type)
    if status == 'draft':
        query += ' AND sig_issuer IS NULL'
    elif status == 'signed':
        query += ' AND sig_issuer IS NOT NULL AND email_sent_at IS NULL'
    elif status == 'sent':
        query += ' AND email_sent_at IS NOT NULL'

    query += ' ORDER BY created_at DESC'
    documents = db().execute(query, params).fetchall()
    return render_template('dashboard.html', documents=documents,
                           filter_type=doc_type, filter_status=status)


# ---------------------------------------------------------------------------
# New document
# ---------------------------------------------------------------------------
@app.route('/documents/new')
@login_required
def document_new():
    return render_template('document_form.html', document=None, items=[], mode='new')


@app.route('/documents', methods=['POST'])
@login_required
def document_create():
    d = request.form
    doc_type = d.get('doc_type', 'office')
    operation = d.get('operation', 'wydanie')
    doc_date = d.get('doc_date', datetime.now().strftime('%Y-%m-%d'))
    issuer_name = d.get('issuer_name', '').strip()
    receiver_name = d.get('receiver_name', '').strip()
    receiver_email = d.get('receiver_email', '').strip()
    network_name = d.get('network_name', '').strip() if doc_type == 'office' else None

    conn = db()
    doc_number = generate_doc_number(conn, doc_type)

    cur = conn.execute(
        '''INSERT INTO documents
           (doc_number, doc_type, operation, doc_date, issuer_name,
            receiver_name, receiver_email, network_name, created_by)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (doc_number, doc_type, operation, doc_date, issuer_name,
         receiver_name, receiver_email, network_name, session['user_id'])
    )
    doc_id = cur.lastrowid
    _save_items(conn, doc_id, doc_type, d)
    conn.commit()

    flash(f'Protokół {doc_number} został utworzony.', 'success')
    return redirect(url_for('document_view', doc_id=doc_id))


# ---------------------------------------------------------------------------
# View document
# ---------------------------------------------------------------------------
@app.route('/documents/<int:doc_id>')
@login_required
def document_view(doc_id):
    doc = db().execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not doc:
        flash('Dokument nie istnieje.', 'danger')
        return redirect(url_for('dashboard'))
    items = db().execute(
        'SELECT * FROM document_items WHERE document_id=? ORDER BY sort_order', (doc_id,)
    ).fetchall()
    return render_template('document_view.html', document=doc, items=items)


# ---------------------------------------------------------------------------
# Edit document
# ---------------------------------------------------------------------------
@app.route('/documents/<int:doc_id>/edit', methods=['GET', 'POST'])
@login_required
def document_edit(doc_id):
    conn = db()
    doc = conn.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not doc:
        flash('Dokument nie istnieje.', 'danger')
        return redirect(url_for('dashboard'))
    if doc['sig_issuer']:
        flash('Dokument jest już podpisany i nie może być edytowany.', 'warning')
        return redirect(url_for('document_view', doc_id=doc_id))

    if request.method == 'POST':
        d = request.form
        doc_type = doc['doc_type']
        operation = d.get('operation', 'wydanie')
        doc_date = d.get('doc_date', '')
        issuer_name = d.get('issuer_name', '').strip()
        receiver_name = d.get('receiver_name', '').strip()
        receiver_email = d.get('receiver_email', '').strip()
        network_name = d.get('network_name', '').strip() if doc_type == 'office' else None

        conn.execute(
            '''UPDATE documents SET operation=?, doc_date=?, issuer_name=?,
               receiver_name=?, receiver_email=?, network_name=? WHERE id=?''',
            (operation, doc_date, issuer_name, receiver_name, receiver_email, network_name, doc_id)
        )
        conn.execute('DELETE FROM document_items WHERE document_id=?', (doc_id,))
        _save_items(conn, doc_id, doc_type, d)
        conn.commit()

        flash('Dokument został zaktualizowany.', 'success')
        return redirect(url_for('document_view', doc_id=doc_id))

    items = conn.execute(
        'SELECT * FROM document_items WHERE document_id=? ORDER BY sort_order', (doc_id,)
    ).fetchall()
    return render_template('document_form.html', document=doc, items=items, mode='edit')


# ---------------------------------------------------------------------------
# Sign document
# ---------------------------------------------------------------------------
@app.route('/documents/<int:doc_id>/sign', methods=['GET', 'POST'])
@login_required
def document_sign(doc_id):
    conn = db()
    doc = conn.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not doc:
        flash('Dokument nie istnieje.', 'danger')
        return redirect(url_for('dashboard'))

    items = conn.execute(
        'SELECT * FROM document_items WHERE document_id=? ORDER BY sort_order', (doc_id,)
    ).fetchall()

    if request.method == 'POST':
        sig_issuer = request.form.get('sig_issuer', '').strip()
        sig_receiver = request.form.get('sig_receiver', '').strip()

        if not sig_issuer or not sig_receiver:
            flash('Oba podpisy są wymagane.', 'warning')
            return render_template('document_sign.html', document=doc, items=items)

        conn.execute(
            'UPDATE documents SET sig_issuer=?, sig_receiver=?, signed_at=? WHERE id=?',
            (sig_issuer, sig_receiver, datetime.now().isoformat(), doc_id)
        )
        conn.commit()
        flash('Podpisy zostały zapisane pomyślnie.', 'success')
        return redirect(url_for('document_view', doc_id=doc_id))

    return render_template('document_sign.html', document=doc, items=items)


# ---------------------------------------------------------------------------
# Download PDF
# ---------------------------------------------------------------------------
@app.route('/documents/<int:doc_id>/pdf')
@login_required
def document_pdf(doc_id):
    conn = db()
    doc = conn.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not doc:
        flash('Dokument nie istnieje.', 'danger')
        return redirect(url_for('dashboard'))
    items = conn.execute(
        'SELECT * FROM document_items WHERE document_id=? ORDER BY sort_order', (doc_id,)
    ).fetchall()

    pdf_bytes = generate_pdf(doc, items)
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename="{doc["doc_number"]}.pdf"'
    return resp


# ---------------------------------------------------------------------------
# Send email
# ---------------------------------------------------------------------------
@app.route('/documents/<int:doc_id>/send', methods=['POST'])
@login_required
def document_send(doc_id):
    conn = db()
    doc = conn.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not doc:
        flash('Dokument nie istnieje.', 'danger')
        return redirect(url_for('dashboard'))

    if not doc['sig_issuer'] or not doc['sig_receiver']:
        flash('Dokument musi być podpisany przed wysłaniem.', 'warning')
        return redirect(url_for('document_view', doc_id=doc_id))

    items = conn.execute(
        'SELECT * FROM document_items WHERE document_id=? ORDER BY sort_order', (doc_id,)
    ).fetchall()

    settings_rows = conn.execute('SELECT key, value FROM settings').fetchall()
    settings = {row['key']: row['value'] for row in settings_rows}

    accounting_email = settings.get('accounting_email', '').strip()
    receiver_email = doc['receiver_email']

    pdf_bytes = generate_pdf(doc, items)
    op_label = 'wydania' if doc['operation'] == 'wydanie' else 'zwrotu'
    type_label = {'office': 'Office', 'telefon': 'Telefon', 'produkcja': 'Produkcja'}.get(
        doc['doc_type'], doc['doc_type']
    )

    subject = f'Protokół {op_label} sprzętu IT ({type_label}) – {doc["doc_number"]}'
    body = (
        f'Szanowni Państwo,\n\n'
        f'W załączniku przesyłamy podpisany protokół {op_label} sprzętu IT ({type_label}).\n\n'
        f'Numer dokumentu: {doc["doc_number"]}\n'
        f'Data: {doc["doc_date"]}\n'
        f'Przekazujący: {doc["issuer_name"]}\n'
        f'Przyjmujący: {doc["receiver_name"]}\n\n'
        f'Z poważaniem,\nDział IT Brueggen Polska Sp. z o.o.'
    )

    to_list = [e for e in [receiver_email, accounting_email] if e]
    success, message = send_email(
        settings=settings,
        to_emails=to_list,
        subject=subject,
        body=body,
        pdf_bytes=pdf_bytes,
        pdf_filename=f'{doc["doc_number"]}.pdf',
    )

    if success:
        conn.execute(
            'UPDATE documents SET email_sent_at=? WHERE id=?',
            (datetime.now().isoformat(), doc_id)
        )
        conn.commit()
        sent_to = ', '.join(to_list)
        flash(f'Protokół wysłany do: {sent_to}', 'success')
    else:
        flash(f'Błąd wysyłki email: {message}', 'danger')

    return redirect(url_for('document_view', doc_id=doc_id))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    conn = db()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'email_settings':
            for key in ['accounting_email', 'smtp_host', 'smtp_port', 'smtp_user',
                        'smtp_pass', 'smtp_from', 'smtp_from_name', 'smtp_use_tls']:
                value = request.form.get(key, '')
                conn.execute('INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)', (key, value))
            conn.commit()
            flash('Ustawienia email zostały zapisane.', 'success')

        elif action == 'test_email':
            settings_data = {r['key']: r['value'] for r in conn.execute('SELECT key,value FROM settings').fetchall()}
            test_addr = request.form.get('test_email', '').strip()
            if test_addr:
                ok, msg = send_email(
                    settings=settings_data,
                    to_emails=[test_addr],
                    subject='Test – IT Protokoly Brueggen Polska',
                    body='Wiadomość testowa z systemu IT Protokoly.',
                    pdf_bytes=None,
                    pdf_filename=None,
                )
                flash(f'Wysłano do {test_addr}' if ok else f'Błąd: {msg}',
                      'success' if ok else 'danger')

        elif action == 'add_user':
            username = request.form.get('new_username', '').strip()
            full_name = request.form.get('new_full_name', '').strip()
            password = request.form.get('new_password', '').strip()
            if username and full_name and password:
                try:
                    conn.execute(
                        'INSERT INTO users (username, password_hash, full_name) VALUES (?,?,?)',
                        (username, generate_password_hash(password), full_name)
                    )
                    conn.commit()
                    flash(f'Użytkownik {username} został dodany.', 'success')
                except sqlite3.IntegrityError:
                    flash(f'Użytkownik "{username}" już istnieje.', 'danger')
            else:
                flash('Wypełnij wszystkie pola nowego użytkownika.', 'warning')

        elif action == 'change_password':
            user_id = request.form.get('user_id')
            new_pw = request.form.get('new_password', '').strip()
            if user_id and new_pw:
                conn.execute(
                    'UPDATE users SET password_hash=? WHERE id=?',
                    (generate_password_hash(new_pw), user_id)
                )
                conn.commit()
                flash('Hasło zostało zmienione.', 'success')

        elif action == 'toggle_user':
            user_id = request.form.get('user_id')
            if user_id and int(user_id) != session['user_id']:
                conn.execute(
                    'UPDATE users SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?',
                    (user_id,)
                )
                conn.commit()
                flash('Status użytkownika zmieniony.', 'success')
            else:
                flash('Nie możesz dezaktywować własnego konta.', 'warning')

        return redirect(url_for('settings'))

    settings_data = {r['key']: r['value'] for r in conn.execute('SELECT key,value FROM settings').fetchall()}
    users = conn.execute('SELECT * FROM users ORDER BY full_name').fetchall()
    return render_template('settings.html', settings=settings_data, users=users)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _save_items(conn, doc_id, doc_type, form):
    if doc_type == 'telefon':
        conn.execute(
            '''INSERT INTO document_items
               (document_id, sort_order, phone_type, imei, serial_number,
                internal_name, phone_number, sim_number, pin_phone, pin_sim,
                acc_foil, acc_case, acc_charger, acc_headphones, notes)
               VALUES (?,0,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (
                doc_id,
                form.get('phone_type', ''),
                form.get('imei', ''),
                form.get('serial_number', ''),
                form.get('internal_name', ''),
                form.get('phone_number', ''),
                form.get('sim_number', ''),
                form.get('pin_phone', ''),
                form.get('pin_sim', ''),
                1 if form.get('acc_foil') else 0,
                1 if form.get('acc_case') else 0,
                1 if form.get('acc_charger') else 0,
                1 if form.get('acc_headphones') else 0,
                form.get('notes', ''),
            )
        )
    else:
        eq_types = form.getlist('equipment_type[]')
        mfr_models = form.getlist('manufacturer_model[]')
        serials = form.getlist('serial_number[]')
        quantities = form.getlist('quantity[]')
        internals = form.getlist('internal_number[]')

        for i, eq_type in enumerate(eq_types):
            if eq_type.strip():
                conn.execute(
                    '''INSERT INTO document_items
                       (document_id, sort_order, equipment_type,
                        manufacturer_model, serial_number, quantity, internal_number)
                       VALUES (?,?,?,?,?,?,?)''',
                    (
                        doc_id, i, eq_type.strip(),
                        mfr_models[i] if i < len(mfr_models) else '',
                        serials[i] if i < len(serials) else '',
                        int(quantities[i]) if i < len(quantities) and quantities[i].isdigit() else 1,
                        internals[i] if i < len(internals) else '',
                    )
                )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    init_db()
    print('Uruchamianie IT Protokoly...')
    print('Adres: http://localhost:5000')
    print('Login: admin / admin123')
    app.run(debug=False, host='0.0.0.0', port=5000)
