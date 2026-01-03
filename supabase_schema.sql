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

-- Long-term memories (things Mai decides to remember)
CREATE TABLE memories (
    id BIGSERIAL PRIMARY KEY,
    server_id TEXT NOT NULL,
    user_id TEXT,  -- Optional: who this memory is about (NULL = server-wide)
    memory TEXT NOT NULL,  -- "Alice loves drawing dragons"
    category TEXT DEFAULT 'general',  -- user_fact, preference, event, conversation, general
    importance INTEGER DEFAULT 3,  -- 1-5, higher = more important (5 = permanent)
    expires_at TIMESTAMPTZ,  -- NULL = never expires, set based on category
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_memories_server ON memories(server_id);
CREATE INDEX idx_memories_user ON memories(user_id);
CREATE INDEX idx_memories_category ON memories(category);
CREATE INDEX idx_memories_importance ON memories(importance DESC);

-- Migration for existing memories table:
-- ALTER TABLE memories ADD COLUMN category TEXT DEFAULT 'general';
-- ALTER TABLE memories ADD COLUMN importance INTEGER DEFAULT 3;
-- ALTER TABLE memories ADD COLUMN expires_at TIMESTAMPTZ;
