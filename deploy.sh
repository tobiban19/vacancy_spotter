#!/usr/bin/env bash
# Automated Deployment Script for Vacancy Spotter SaaS Backend on Ubuntu 22.04 / 24.04 VPS

set -e

echo "🚀 Starting Vacancy Spotter SaaS Server Setup..."

# 1. Update system packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl pm2 || true

# Install nodejs & pm2 if not installed
if ! command -v pm2 &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
    sudo npm install -g pm2
fi

# 2. Setup project directory
mkdir -p /opt/vacancy-spotter
cd /opt/vacancy-spotter

if [ ! -d "/opt/vacancy-spotter/.git" ]; then
    git clone https://github.com/tobiban19/vacancy_spotter.git .
else
    git pull origin main
fi

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install backend dependencies
cd /opt/vacancy-spotter/backend
pip install --upgrade pip
pip install -r requirements.txt

# 5. Start app via PM2
pm2 stop vacancy-spotter-backend || true
pm2 start "python3 server.py" --name vacancy-spotter-backend
pm2 save
pm2 startup || true

echo "✅ Vacancy Spotter SaaS Backend successfully deployed & running 24/7 via PM2!"
