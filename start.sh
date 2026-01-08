#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

clear

echo -e "${GREEN}"
echo "   ____  _                           _   "
echo "  / ___|| |___ _ __   __ _ _ __   ___| |  "
echo " | |   | / __| '_ \ / _\` | '_ \ / _ \ |  "
echo " | |___| \__ \ |_) | (_| | | | |  __/ |  "
echo "  \____|_|___/ .__/ \__,_|_| |_|\___|_|  "
echo "             |_|                          "
echo -e "${NC}"
echo "============================================"
echo -e "  ${CYAN}Advanced Device Control Panel v1.0${NC}"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python3 is not installed!${NC}"
    echo "Please install Python 3.10+ first"
    exit 1
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}[*] Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}[+] Virtual environment created!${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}[*] Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}[*] Installing dependencies...${NC}"
pip install -r requirements.txt -q

# Clear and show banner
clear
echo -e "${GREEN}"
echo "   ____  _                           _   "
echo "  / ___|| |___ _ __   __ _ _ __   ___| |  "
echo " | |   | / __| '_ \ / _\` | '_ \ / _ \ |  "
echo " | |___| \__ \ |_) | (_| | | | |  __/ |  "
echo "  \____|_|___/ .__/ \__,_|_| |_|\___|_|  "
echo "             |_|                          "
echo -e "${NC}"
echo "============================================"
echo -e "  ${GREEN}[+] All systems ready!${NC}"
echo -e "  ${CYAN}[*] Starting server...${NC}"
echo "============================================"
echo ""
echo -e "  Access Panel at: ${CYAN}http://localhost:5000${NC}"
echo ""
echo "  Default Credentials:"
echo -e "  Username: ${YELLOW}Chetancj${NC}"
echo -e "  Password: ${YELLOW}Chetancj${NC}"
echo ""
echo "  Press Ctrl+C to stop the server"
echo "============================================"
echo ""

# Start server
python main.py
