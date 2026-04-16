-- Run once in the Supabase SQL editor (Dashboard → SQL Editor → New query)
-- Creates the analyses table for AI-generated weekly reports

CREATE TABLE IF NOT EXISTS public.analyses (
    id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    brand_id     uuid        REFERENCES public.brands(id) ON DELETE CASCADE,
    platform     text        NOT NULL,          -- youtube | instagram | tiktok | facebook | all
    analysis_type text       NOT NULL DEFAULT 'weekly_summary',
    period_start date        NOT NULL,
    period_end   date        NOT NULL,
    title        text,
    content      text,                          -- AI-generated narrative text
    data         jsonb,                         -- structured metrics, top posts, etc.
    model        text,                          -- which Claude model was used
    created_at   timestamptz DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.analyses ENABLE ROW LEVEL SECURITY;

-- Allow service role (used by scripts) full access
CREATE POLICY "Service role full access" ON public.analyses
    FOR ALL USING (true);

-- Unique constraint so upsert (on_conflict) works correctly
ALTER TABLE public.analyses
    ADD CONSTRAINT analyses_unique_period
    UNIQUE (brand_id, platform, analysis_type, period_start);

-- Indexes for fast dashboard queries
CREATE INDEX IF NOT EXISTS analyses_brand_platform_idx ON public.analyses(brand_id, platform);
CREATE INDEX IF NOT EXISTS analyses_period_idx ON public.analyses(period_end DESC);
