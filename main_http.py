#!/usr/bin/env python3
"""
Cjspanel HTTP Server for Ngrok Tunneling
Run this version when using ngrok (which provides its own HTTPS)
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app from main.py
from main import app, ensure_directories, get_settings, LOGIN_USERNAME, LOGIN_PASSWORD, DEVICES_DIR

if __name__ == '__main__':
    ensure_directories()
    
    print("🦁 Cjspanel V1 Starting (HTTP Mode for Ngrok)...")
    print("Developer: https://t.me/ondork")
    settings = get_settings()
    print("Login Credentials:")
    print(f"Username: {settings.get('username', LOGIN_USERNAME)}")
    print(f"Password: {settings.get('password', LOGIN_PASSWORD)}")
    print(f"Data Storage: {DEVICES_DIR}")
    print("\n⚠️  Running in HTTP mode - Use ngrok for HTTPS!")
    print("\nAccess URLs:")
    print(f"Local: http://localhost:5000")
    print(f"Dashboard: http://localhost:5000/dashboard")
    print("\nGenerate hooks from dashboard!")
    
    # Run without SSL - ngrok will provide HTTPS
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
