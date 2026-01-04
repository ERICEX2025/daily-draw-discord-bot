# Daily Draw Bot 🎨

**Mai-san** — A GPT-powered Discord bot that runs your art channel with daily drawing prompts, remembers your community, and critiques artwork.

## Quick Start

```bash
git clone https://github.com/ERICEX2025/daily-draw-discord-bot.git
cd daily-draw-discord-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```
DISCORD_TOKEN=your_discord_token
OPENAI_API_KEY=your_openai_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

Run the bot:

```bash
python main.py
```

Then in Discord:

```
@Mai-san post daily prompts in #art-prompts
```

---

## Features

| Feature                  | Example                                                |
| ------------------------ | ------------------------------------------------------ |
| **Daily Prompts**        | Automatic drawing prompts at your preferred time       |
| **Art Critique**         | Upload a drawing, get detailed feedback via GPT vision |
| **Long-Term Memory**     | Remembers preferences, facts, and milestones           |
| **Customizable Themes**  | Fantasy, horror, slice of life, etc.                   |
| **Natural Conversation** | Just @mention and chat — no commands                   |

---

## Architecture

```
bot/
├── config.py                    # All settings
│
├── chat/                        # Feature: Chat with Mai
│   ├── executor.py              # Chat loop orchestration
│   ├── generator.py             # GPT response generation
│   └── handlers.py              # Function implementations
│
├── daily/                       # Feature: Daily prompts
│   ├── executor.py              # Post flow orchestration
│   ├── generator.py             # GPT prompt generation
│   ├── scheduler.py             # APScheduler jobs
│   └── daily_prompt.py          # Prompt templates
│
├── mai/                         # Mai's identity
│   ├── prompt.py                # System prompt (personality)
│   └── tools.py                 # Function definitions (schemas)
│
├── memory/                      # Memory systems
│   ├── short_term.py            # In-memory conversation history
│   └── long_term.py             # Supabase persistent memories
│
└── services/                    # External APIs
    ├── db.py                    # Supabase client
    ├── openai.py                # OpenAI client
    ├── langfuse.py              # Observability
    ├── search.py                # Web/image search
    └── http.py                  # HTTP utilities

main.py                          # Discord entry point
```

**Flow:**

1. User @mentions Mai → `main.py` handles the event
2. `chat/executor.py` runs the chat loop (GPT + tools)
3. `chat/generator.py` calls GPT with context
4. If GPT requests tools → `chat/handlers.py` executes them
5. Response sent back to Discord

---

## Setup Details

### Discord Bot

1. [Discord Developer Portal](https://discord.com/developers/applications) → New Application
2. **Bot** → Add Bot → Enable **Message Content Intent**
3. **OAuth2** → URL Generator → Scopes: `bot` → Permissions: `Send Messages`, `Read Message History`
4. Copy invite URL → add bot to your server

### Supabase

1. Create project at [supabase.com](https://supabase.com)
2. Run `supabase_schema.sql` in SQL Editor
3. Copy URL and anon key from **Settings → API**

### Optional: Langfuse (Observability)

Add to `.env`:

```
LANGFUSE_PUBLIC_KEY=your_key
LANGFUSE_SECRET_KEY=your_secret
```

---

## Deployment

For 24/7 uptime, deploy to Oracle Cloud (free tier) or any VPS:

```bash
# Create systemd service
sudo nano /etc/systemd/system/mai-san.service
```

```ini
[Unit]
Description=Mai-san Discord Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/daily-draw-bot
ExecStart=/path/to/daily-draw-bot/.venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable mai-san && sudo systemctl start mai-san
```

---

## Docs

- [Memory System](./docs/MEMORY_SYSTEM.md) — How Mai remembers things
- [Langfuse](./docs/LANGFUSE.md) — Observability setup
- [Deployment](./docs/DEPLOYMENT.md) — Full deployment guide

---

## License

MIT
