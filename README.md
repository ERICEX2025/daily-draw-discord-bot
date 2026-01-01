# Daily Draw Bot 🎨

**Mai-san** — A GPT-5.2 powered Discord bot inspired by Sakurajima Mai from "Rascal Does Not Dream of Bunny Girl Senpai." She helps run your art channel with daily drawing prompts and can even critique your artwork!

## Features

- 💬 **Pure conversation** — Just @mention Mai-san and chat naturally
- 🎨 **Daily prompts** — Scheduled drawing prompts at your preferred time
- 🖼️ **Art grading** — Upload your drawing and Mai-san will give feedback (using GPT-4o vision)
- 🎯 **Custom themes** — Request specific prompt categories ("give me fantasy themes for a week")
- 📜 **Prompt history** — Ask about past prompts
- ⏰ **Flexible scheduling** — Change posting time through conversation

## Example Conversations

```
You: @Mai-san what's today's prompt?
Mai: Today you're drawing "A cozy ramen shop on a rainy evening" 🍜
     Don't slack off now.

You: @Mai-san can we do space themes this week?
Mai: Sure, I'll switch to space themes for the next 7 days.
     Tomorrow's preview: "An astronaut discovering ancient ruins on Mars" 🚀
     ...It's not like I'm excited to see what you'll draw or anything.

You: @Mai-san [uploads drawing] how did I do?
Mai: *examines your work*
     The composition is solid — you've captured the atmosphere well.
     The lighting on the left side creates nice depth.
     If I had to nitpick... the proportions could use some work.
     But overall? 7/10. I expect improvement tomorrow. ✨
```

## Setup

### 1. Clone & Create Virtual Environment

```bash
git clone <your-repo-url>
cd daily-draw-bot
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file in the project root:

```
DISCORD_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here
```

Get your tokens from:

- Discord: [Discord Developer Portal](https://discord.com/developers/applications)
- OpenAI: [platform.openai.com](https://platform.openai.com)

### 4. Run the Bot

```bash
python main.py
```

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to **Bot** → Add Bot
4. Enable **Message Content Intent** (required for natural conversation)
5. Copy the token to your `.env` file
6. Go to **OAuth2** → **URL Generator**
7. Select scopes: `bot`, `applications.commands`
8. Select permissions: `Administrator` (or specific permissions as needed)
9. Use the generated URL to invite the bot to your server

## How to Use

Just @mention Mai-san and talk naturally:

| What you want      | Example                                               |
| ------------------ | ----------------------------------------------------- |
| Get today's prompt | "@Mai-san what should I draw today?"                  |
| Set a theme        | "@Mai-san let's do nature themes for the next 5 days" |
| Change schedule    | "@Mai-san can you post prompts at 10am instead?"      |
| Set prompt channel | "@Mai-san post daily prompts in #art-prompts"         |
| View history       | "@Mai-san what did we draw last week?"                |
| Get feedback       | "@Mai-san [attach image] how's my drawing?"           |
| Check settings     | "@Mai-san what are the current settings?"             |

## Architecture

```
daily-draw-bot/
├── main.py          # Bot entry, message handler, scheduler
├── database.py      # SQLite storage for prompts & settings
├── gpt.py           # OpenAI integration (GPT-5.2 + vision)
├── mai_san.db       # Database (auto-created)
├── .env             # Your tokens (not committed)
└── requirements.txt # Dependencies
```

## How It Works

1. **Message Handler** — When you @mention Mai-san, your message goes to GPT-5.2
2. **Function Calling** — GPT-5.2 understands your intent and calls appropriate functions (generate prompt, set theme, etc.)
3. **Vision** — If you attach an image, GPT-5.2 can see and critique it with improved accuracy
4. **Scheduler** — A background task checks every minute if it's time to post daily prompts
5. **Database** — All prompts, settings, and conversation history are stored in SQLite

## License

MIT
