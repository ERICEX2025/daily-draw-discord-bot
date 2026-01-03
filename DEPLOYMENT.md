# Mai-san Bot Deployment Guide

## Server Info

| Item | Value |
|------|-------|
| Provider | Oracle Cloud (Free Tier) |
| OS | Ubuntu 24.04 ARM |
| IP | 129.213.22.126 |
| User | ubuntu |

---

## Connect to Server

```bash
ssh mai-server
```

(Configured in `~/.ssh/config`)

---

## Bot Management Commands

| Command | What it does |
|---------|--------------|
| `sudo systemctl status maibot` | Check if bot is running |
| `sudo systemctl start maibot` | Start the bot |
| `sudo systemctl stop maibot` | Stop the bot |
| `sudo systemctl restart maibot` | Restart the bot |
| `sudo journalctl -u maibot -f` | View live logs |
| `sudo journalctl -u maibot --since "1 hour ago"` | View recent logs |

---

## Deploy Code Updates

After making changes locally and pushing to GitHub:

```bash
# 1. Connect to server
ssh mai-server

# 2. Go to project folder
cd daily-draw-discord-bot

# 3. Pull latest code
git pull

# 4. Restart bot to apply changes
sudo systemctl restart maibot

# 5. Check it's running
sudo systemctl status maibot
```

---

## First-Time Setup (Reference)

If you ever need to set up a fresh server:

```bash
# Update system
sudo apt update && sudo apt install python3-venv python3-pip git -y

# Clone repo
git clone https://github.com/ERICEX2025/daily-draw-discord-bot.git
cd daily-draw-discord-bot

# Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env file with secrets
nano .env

# Test run
python main.py
```

---

## Systemd Service File

Located at `/etc/systemd/system/maibot.service`:

```ini
[Unit]
Description=Mai-san Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/daily-draw-discord-bot
ExecStart=/home/ubuntu/daily-draw-discord-bot/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

If you modify this file, reload systemd:
```bash
sudo systemctl daemon-reload
sudo systemctl restart maibot
```

---

## SSH Config (on your Mac)

Located at `~/.ssh/config`:

```
Host mai-server
    HostName 129.213.22.126
    User ubuntu
    IdentityFile ~/.ssh/ssh-key-2026-01-03.key
```

---

## Troubleshooting

### Bot not responding?
```bash
sudo systemctl status maibot
sudo journalctl -u maibot --since "10 min ago"
```

### Need to update .env on server?
```bash
ssh mai-server
cd daily-draw-discord-bot
nano .env
sudo systemctl restart maibot
```

### Server rebooted?
The bot auto-starts! Just check status:
```bash
sudo systemctl status maibot
```

