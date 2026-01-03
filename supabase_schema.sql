-- Mai-san Discord Bot Schema (MVP)
-- Run this in Supabase SQL Editor

-- Server settings
CREATE TABLE settings (
    server_id TEXT PRIMARY KEY,
    channel_id TEXT,
    post_time TEXT DEFAULT '09:00',
    timezone TEXT DEFAULT 'America/New_York',
    paused_until TIMESTAMPTZ DEFAULT NULL,  -- NULL = not paused, datetime = paused until then
    theme TEXT DEFAULT 'anime and video game inspired'
);

-- If you already have the table, run these instead:
-- ALTER TABLE settings ADD COLUMN paused_until TIMESTAMPTZ DEFAULT NULL;
-- ALTER TABLE settings ADD COLUMN theme TEXT DEFAULT 'anime and video game inspired';

-- Daily prompts
CREATE TABLE prompts (
    id BIGSERIAL PRIMARY KEY,
    server_id TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prompts_server ON prompts(server_id);
CREATE INDEX idx_prompts_date ON prompts(created_at DESC);
