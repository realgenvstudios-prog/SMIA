-- ─────────────────────────────────────────────────────────────────────────────
-- SMIP Analyses Table
-- Run this in Supabase SQL Editor AFTER running schema.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS analyses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id            UUID REFERENCES brands(id),
    analysis_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    period_start        TIMESTAMPTZ,
    period_end          TIMESTAMPTZ,
    platforms           TEXT[],              -- which platforms were included
    total_posts         INTEGER DEFAULT 0,
    total_comments      INTEGER DEFAULT 0,
    total_likes         BIGINT DEFAULT 0,
    total_views         BIGINT DEFAULT 0,
    total_shares        BIGINT DEFAULT 0,
    sentiment_score     FLOAT,               -- -1.0 (negative) to 1.0 (positive)
    sentiment_label     TEXT,                -- 'positive' | 'neutral' | 'negative'
    top_topics          JSONB DEFAULT '[]',  -- [{"topic": "...", "count": N, "sentiment": "..."}]
    crisis_flag         BOOLEAN DEFAULT false,
    crisis_reason       TEXT,
    recommended_actions JSONB DEFAULT '[]',  -- ["action 1", "action 2", ...]
    summary             TEXT,                -- 2-3 sentence narrative
    platform_breakdown  JSONB DEFAULT '{}',  -- per-platform stats
    top_posts           JSONB DEFAULT '[]',  -- top 5 posts by engagement
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (brand_id, analysis_date)         -- one analysis per brand per day
);

CREATE INDEX IF NOT EXISTS idx_analyses_brand ON analyses(brand_id);
CREATE INDEX IF NOT EXISTS idx_analyses_date  ON analyses(analysis_date DESC);
