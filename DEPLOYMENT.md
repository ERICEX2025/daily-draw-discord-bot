# Mai-san Bot Deployment Guide

## Server Info

| Item     | Value                    |
| -------- | ------------------------ |
| Provider | Oracle Cloud (Free Tier) |
| OS       | Ubuntu 24.04 ARM         |
| IP       | 129.213.22.126           |
| User     | ubuntu                   |

---

## Connect to Server

```bash
ssh mai-server
```

(Configured in `~/.ssh/config`)

---

## Bot Management Commands

| Command                                          | What it does            |
| ------------------------------------------------ | ----------------------- |
| `sudo systemctl status maibot`                   | Check if bot is running |
| `sudo systemctl start maibot`                    | Start the bot           |
| `sudo systemctl stop maibot`                     | Stop the bot            |
| `sudo systemctl restart maibot`                  | Restart the bot         |
| `sudo journalctl -u maibot -f`                   | View live logs          |
| `sudo journalctl -u maibot --since "1 hour ago"` | View recent logs        |

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

---

## Environment Variables

| Variable              | Required | Description                                             |
| --------------------- | -------- | ------------------------------------------------------- |
| `DISCORD_TOKEN`       | Yes      | Discord bot token                                       |
| `OPENAI_API_KEY`      | Yes      | OpenAI API key                                          |
| `SUPABASE_URL`        | Yes      | Supabase project URL                                    |
| `SUPABASE_KEY`        | Yes      | Supabase anon/service key                               |
| `LANGFUSE_PUBLIC_KEY` | No       | Langfuse public key (for observability)                 |
| `LANGFUSE_SECRET_KEY` | No       | Langfuse secret key (for observability)                 |
| `LANGFUSE_HOST`       | No       | Langfuse host URL (default: https://cloud.langfuse.com) |

### Langfuse Setup (Optional)

Langfuse provides observability into all AI calls — see conversations, tool calls, token usage, and costs in a web UI.

1. Create a free account at [langfuse.com](https://langfuse.com)
2. Create a new project
3. Go to Settings → API Keys and create a new key pair
4. Add to your `.env`:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
# Optional: for self-hosted Langfuse
# LANGFUSE_HOST=https://your-langfuse-instance.com
```

5. Restart the bot — you'll see "🔍 Langfuse observability enabled" in the logs
6. View traces at [cloud.langfuse.com](https://cloud.langfuse.com)

### Server rebooted?

The bot auto-starts! Just check status:

```bash
sudo systemctl status maibot
```
