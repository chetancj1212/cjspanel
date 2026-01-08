#!/bin/bash
echo "Installing Cjspanel..."

# Update packages
pkg update && pkg upgrade -y

# Install required packages
pkg install python -y
pkg install openssl-tool -y

# Install pip
python -m ensurepip --upgrade

# Install Python packages
pip install flask flask-sslify pyopenssl

# Create directories
mkdir -p Cjspanel/templates Cjspanel/static Cjspanel/data/devices

# Generate SSL certificate
cd Cjspanel
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

echo "Installation complete!"
echo "To start Cjspanel:"
echo "cd Cjspanel && python main.py"
