# Daily Draw Bot 🎨

**Mai-san** — A GPT-5.2 powered Discord bot inspired by Sakurajima Mai from "Rascal Does Not Dream of Bunny Girl Senpai." She helps run your art channel with daily drawing prompts, remembers things about your community, and can even critique your artwork!

## Example Conversations

```
You: @Mai-san what's today's prompt?
Mai: Today you're drawing "A cozy ramen shop on a rainy evening" 🍜
     Don't slack off now.

You: @Mai-san [uploads drawing] how did I do?
Mai: *examines your work*
     The composition is solid — you've captured the atmosphere well.
     The lighting on the left side creates nice depth.
     If I had to nitpick... the proportions could use some work.
     But overall? 7/10. I expect improvement tomorrow. ✨
```

## Features

### 💬 Pure Conversation

Just @mention Mai-san and chat naturally — no commands to memorize.

```
You: @Mai-san hey, how are you?
Mai: I'm doing fine, thanks for asking. Though I'd be doing better
     if you were drawing instead of chatting... Just saying.
```

### 🎨 Daily Prompts

Scheduled drawing prompts posted automatically at your preferred time, with customizable themes.

```
[9:00 AM in #art-prompts]
Mai: Good morning, artists~ ✨
     Today's prompt: "A forgotten library where books float in mid-air"
     Let's see what you've got.
```

### 🖼️ Art Grading

Upload your drawing and Mai-san will give detailed feedback using GPT-5.2 vision.

```
You: @Mai-san [attaches drawing] thoughts on this?
Mai: *studies your work carefully*
     Strengths: The color palette is cohesive and the mood is clear.
     Your brushwork on the background creates nice depth.
     Areas to improve: The foreground figure's proportions are off —
     the head is slightly too large for the body.
     Overall: 7.5/10. You're improving. Keep it up.
```

### 🧠 Long-Term Memory

Mai-san remembers things about you and your server — preferences, fun facts, milestones.

```
You: @Mai-san I really love drawing dragons
Mai: Noted! I'll remember that about you~ 🐉

[A week later]
You: @Mai-san what should I draw?
Mai: Well, since you love dragons... how about a dragon
     guarding a treasure hoard in a moonlit cave?
```

### 🎭 Customizable Themes

Set the vibe for your prompts — fantasy, horror, sci-fi, slice of life, and more.

```
You: @Mai-san set the theme to cozy slice of life
Mai: Got it! Switched to cozy slice of life~
     Expect more warm, everyday moments in your prompts. ☕
```

### ⏸️ Pause & Resume

Taking a break? Pause prompts for a few days.

```
You: @Mai-san pause prompts for a week
Mai: Alright, daily prompts paused for 7 days.
     Enjoy your break... but don't forget to draw! 🎨
```

### 📜 Prompt History

Ask about past prompts anytime.

```
You: @Mai-san what did we draw on Monday?
Mai: Monday's prompt was "A street musician playing for ghosts."
     ...Did you actually draw it, or are you just asking? 👀
```

### ⏰ Flexible Scheduling

Change the posting time and timezone through natural conversation.

```
You: @Mai-san can you post at 8am PST?
Mai: Alright, I'll post daily prompts at 8:00 AM Pacific time.
     Early bird gets the... better art skills? Something like that.
```

## Getting Started

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → name it → **Create**
3. Go to **Bot** → **Add Bot**
4. Enable **Message Content Intent** (required for @mentions)
5. Click **Reset Token** → copy it (you'll need this)
6. Go to **OAuth2** → **URL Generator**
7. Select scopes: `bot`
8. Select permissions: `Send Messages`, `Read Message History`, `Embed Links`
9. Copy the URL → open it → invite bot to your server

### 2. Get an OpenAI API Key

1. Go to [platform.openai.com](https://platform.openai.com)
2. Create an account or sign in
3. Go to **API Keys** → **Create new secret key**
4. Copy the key (you'll need this)

### 3. Set Up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run the contents of `supabase_schema.sql`
3. Copy your project URL and anon key from **Settings → API**

### 4. Install & Run

```bash
git clone <your-repo-url>
cd daily-draw-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
DISCORD_TOKEN=your_discord_token_here
OPENAI_API_KEY=your_openai_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

Run the bot:

```bash
python main.py
```

### 5. Configure Daily Prompts

Once the bot is running, go to your Discord server and tell Mai-san where to post:

```
@Mai-san post daily prompts in #art-prompts
```

That's it! Mai-san will now post a drawing prompt every day at 9:00 AM EST.

Optionally set a different time and timezone:

```
@Mai-san post prompts at 10:00 AM PST
```

## Capabilities

Just @mention Mai-san and talk naturally. Here's what she can do:

| What you want       | Example                                          |
| ------------------- | ------------------------------------------------ |
| Get today's prompt  | "@Mai-san what should I draw today?"             |
| Change schedule     | "@Mai-san post prompts at 10am PST"              |
| Set prompt channel  | "@Mai-san post daily prompts in #art-prompts"    |
| Set theme           | "@Mai-san set theme to dark fantasy"             |
| View history        | "@Mai-san what did we draw last week?"           |
| Get feedback        | "@Mai-san [attach image] how's my drawing?"      |
| Pause prompts       | "@Mai-san pause for a week"                      |
| Resume prompts      | "@Mai-san resume prompts"                        |

Mai-san also remembers things automatically — your preferences, fun facts you share, and important events in the server.

## How It Works

1. **Message Handler** — When you @mention Mai-san, your message goes to GPT-5.2
2. **Function Calling** — GPT-5.2 understands your intent and calls appropriate functions (set channel, set schedule, save memory, etc.)
3. **Vision** — If you attach an image, GPT-5.2 can see and critique it
4. **APScheduler** — Efficient cron-based scheduling that fires at the exact time instead of polling
5. **Memory System** — Short-term (in-RAM conversation history) + long-term (Supabase) for persistent memories
6. **Supabase** — All prompts, settings, and memories are stored in Supabase (PostgreSQL)

See [MEMORY_SYSTEM.md](./MEMORY_SYSTEM.md) for a detailed breakdown of how Mai remembers things.

## Project Structure

```
daily-draw-bot/
├── main.py              # Bot entry, message handler, function executor
├── bot/                 # All bot modules
│   ├── config.py        # Centralized configuration constants
│   ├── personality.py   # Mai's character & function definitions
│   ├── gpt.py           # OpenAI integration (GPT-5.2)
│   ├── database.py      # Supabase storage for prompts, settings, memories
│   ├── handlers.py      # Function execution handlers
│   ├── scheduler.py     # APScheduler-based daily prompt scheduling
│   ├── memory.py        # Short-term memory helpers
│   └── utils.py         # Image download & utilities
├── assets/
│   └── Mai-san.png      # Bot avatar
├── supabase_schema.sql  # Database schema for Supabase setup
└── requirements.txt     # Dependencies
```

## Deploying to a Cloud Server

To keep Mai-san running 24/7, deploy to a cloud server. Here are a few options:

### Railway (Recommended — Easy)

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Select your repo
4. Add environment variables:
   - `DISCORD_TOKEN`
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
5. Railway auto-detects Python and deploys

**Cost:** ~$5/month for always-on

### Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login and launch
fly auth login
fly launch

# Set secrets
fly secrets set DISCORD_TOKEN=your_token OPENAI_API_KEY=your_key SUPABASE_URL=your_url SUPABASE_KEY=your_key

# Deploy
fly deploy
```

Add a `fly.toml` to your project:

```toml
app = "daily-draw-bot"
primary_region = "ord"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8080"
```

**Cost:** Free tier available, ~$3-5/month for always-on

### VPS (DigitalOcean, Linode, etc.)

For a simple VPS setup:

```bash
# SSH into your server
ssh user@your-server

# Clone and setup
git clone <your-repo-url>
cd daily-draw-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env file with your tokens
nano .env

# Run with screen (keeps running after disconnect)
screen -S mai-san
python main.py
# Press Ctrl+A then D to detach
```

To reattach: `screen -r mai-san`

**Cost:** ~$4-6/month for a small droplet

## License

MIT
