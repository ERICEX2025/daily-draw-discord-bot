# Mai-san Bot Architecture

## File Structure

```
daily-draw-bot/
├── main.py              ← Entry point, Discord events, scheduler
├── .env                 ← Secrets (DISCORD_TOKEN, OPENAI_API_KEY, SUPABASE_*)
├── requirements.txt     ← Python dependencies
├── supabase_schema.sql  ← Database tables (run in Supabase)
│
└── bot/
    ├── personality.py   ← WHO Mai is + WHAT tools she has
    ├── gpt.py           ← OpenAI API calls
    ├── handlers.py      ← Tool execution logic
    ├── database.py      ← Supabase queries
    └── utils.py         ← Image processing
```

---

## Data Flow

### User Mentions Mai

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Discord                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  User: @Mai-san set the prompt channel to #art-prompts          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  main.py → on_message()                                                  │
│                                                                          │
│  1. Check if bot is @mentioned                                          │
│  2. Extract message text                                                │
│  3. Get server settings from database                                   │
│  4. Download any attached images                                        │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  gpt.py → chat_with_mai()                                               │
│                                                                          │
│  Send to OpenAI:                                                        │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │ System: "You are Sakurajima Mai..."                            │     │
│  │ Context: Current time, settings                                │     │
│  │ User: "set the prompt channel to #art-prompts"                 │     │
│  │ Tools: [set_channel, set_schedule, ...]                        │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                          │
│  GPT Response: "Call set_channel(channel_name='art-prompts')"           │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  main.py → execute_function()                                            │
│                           │                                              │
│                           ▼                                              │
│  handlers.py → handle_set_channel()                                      │
│                           │                                              │
│                           ▼                                              │
│  database.py → update_settings(channel_id="123456789")                   │
│                           │                                              │
│                           ▼                                              │
│                      Supabase                                            │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  gpt.py → get_mai_response_after_function()                              │
│                                                                          │
│  "The function succeeded. Respond naturally."                            │
│                                                                          │
│  Mai: "Done~ I'll post daily prompts to #art-prompts from now on."      │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Discord                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Mai-san: Done~ I'll post daily prompts to #art-prompts...     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Scheduled Daily Prompt

```
┌─────────────────────────────────────────────────────────────────────────┐
│  main.py → daily_prompt_check()  (runs every minute)                     │
│                                                                          │
│  Current time: 09:00 EST                                                │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  database.py → get_all_servers_for_posting()                             │
│                                                                          │
│  Returns servers where:                                                  │
│  - channel_id is set                                                    │
│  - post_time matches current time (09:00)                               │
│  - no prompt posted today yet                                           │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  gpt.py → generate_daily_prompt()                                        │
│                                                                          │
│  Mai creates a prompt based on:                                         │
│  - Her anime/video game taste                                           │
│  - Past prompts (to avoid repeats)                                      │
│                                                                          │
│  Output: "Today's prompt: A samurai sharing ramen with a ghost 🍜"      │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  database.py → save_prompt()                                             │
│                           │                                              │
│                           ▼                                              │
│                      Supabase                                            │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │ prompts table:                                                  │     │
│  │ id=42, server_id="123", prompt_text="A samurai..."             │     │
│  └────────────────────────────────────────────────────────────────┘     │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Discord #art-prompts                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Mai-san: Good morning~ ✨                                      │    │
│  │  Today's prompt: "A samurai sharing ramen with a ghost" 🍜      │    │
│  │  Let's see what you've got.                                     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Art Feedback (Vision)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Discord                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  User: @Mai-san [attached image] how did I do?                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  main.py                                                                 │
│                                                                          │
│  1. Detect image attachment                                             │
│  2. Download image → convert to base64                                  │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  gpt.py → chat_with_mai(image_urls=[base64_image])                       │
│                                                                          │
│  GPT-5.2 Vision sees the image and responds:                            │
│                                                                          │
│  "The composition is solid. Your use of warm colors creates a nice      │
│   atmosphere. The proportions on the left figure are a bit off though.  │
│   7/10. Not bad... but I expect better next time."                      │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Discord                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Mai-san: The composition is solid...                           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema (Supabase)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  settings                                                                │
│  ─────────────────────────────────────────────────────────────────────  │
│  server_id          TEXT PRIMARY KEY    Discord server ID               │
│  channel_id         TEXT                Where to post daily prompts     │
│  post_time          TEXT                "09:00" (24hr format)           │
│  timezone           TEXT                "America/New_York"              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  prompts                                                                 │
│  ─────────────────────────────────────────────────────────────────────  │
│  id                 BIGSERIAL PRIMARY KEY                               │
│  server_id          TEXT                Discord server ID               │
│  prompt_text        TEXT                The actual prompt               │
│  created_at         TIMESTAMPTZ         When it was created             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Available Tools

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DAILY PROMPT SETUP                                                      │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  set_channel(channel_name)                                               │
│      "Set daily prompts to #art-prompts"                                │
│      → Saves channel_id to settings                                     │
│                                                                          │
│  set_schedule(time)                                                      │
│      "Post prompts at 9am" → time="09:00"                               │
│      → Saves post_time to settings                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  INFO                                                                    │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  get_history(count=7)                                                    │
│      "What did we draw last week?"                                      │
│      → Returns list of past prompts                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Environment Variables Needed

```
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```
