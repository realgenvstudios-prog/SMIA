-- ─────────────────────────────────────────────────────────────────────────────
-- SMIP Supabase Schema
-- Run this once in the Supabase SQL editor (Database > SQL Editor > New query)
-- ─────────────────────────────────────────────────────────────────────────────

-- ── brands ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS brands (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug       TEXT UNIQUE NOT NULL,    -- e.g. "eddys-pizza-ghana"
    name       TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ── posts ─────────────────────────────────────────────────────────────────────
-- Unified table for all platforms: YouTube, TikTok, Instagram, Facebook, Twitter
CREATE TABLE IF NOT EXISTS posts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id         UUID REFERENCES brands(id),
    platform         TEXT NOT NULL,           -- 'youtube' | 'tiktok' | 'instagram' | 'facebook' | 'twitter'
    platform_post_id TEXT NOT NULL,           -- native video_id / post_id / tweet_id
    author_name      TEXT,
    author_handle    TEXT,                    -- username / channel handle / @handle
    content          TEXT,                    -- caption / description / text / title
    post_url         TEXT,
    media_type       TEXT,                    -- 'video' | 'image' | 'reel' | 'tweet' etc.
    published_at     TIMESTAMPTZ,
    likes            BIGINT DEFAULT 0,
    comments_count   BIGINT DEFAULT 0,
    shares           BIGINT DEFAULT 0,
    views            BIGINT DEFAULT 0,
    extra_data       JSONB DEFAULT '{}',      -- platform-specific fields (reactions, retweets, music, etc.)
    scraped_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (platform, platform_post_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_brand     ON posts(brand_id);
CREATE INDEX IF NOT EXISTS idx_posts_platform  ON posts(platform);
CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_extra     ON posts USING gin(extra_data);

-- ── comments ─────────────────────────────────────────────────────────────────
-- Unified table for comments / replies across all platforms
CREATE TABLE IF NOT EXISTS comments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform            TEXT NOT NULL,
    platform_comment_id TEXT NOT NULL,
    platform_post_id    TEXT NOT NULL,        -- links back to posts.platform_post_id (by value, no UUID join)
    author_name         TEXT,
    author_handle       TEXT,
    text                TEXT,
    likes               BIGINT DEFAULT 0,
    published_at        TIMESTAMPTZ,
    is_reply            BOOLEAN DEFAULT false,
    parent_id           TEXT,                 -- platform-native parent comment/reply id
    extra_data          JSONB DEFAULT '{}',
    scraped_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (platform, platform_comment_id)
);

CREATE INDEX IF NOT EXISTS idx_comments_post     ON comments(platform, platform_post_id);
CREATE INDEX IF NOT EXISTS idx_comments_platform ON comments(platform);

-- ── seed brands ──────────────────────────────────────────────────────────────
INSERT INTO brands (slug, name)
VALUES ('konnected-minds', 'KonnectedMinds')
ON CONFLICT (slug) DO NOTHING;
