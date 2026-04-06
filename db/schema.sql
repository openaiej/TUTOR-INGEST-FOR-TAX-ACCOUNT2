-- ============================================================
-- tutor-ingest DB 스키마 (Supabase 전용)
--
-- 실행 방법 (둘 중 하나):
--   A) Supabase 대시보드 → SQL Editor → 붙여넣고 실행
--   B) psql "[Direct Connection URI]" -f db/schema.sql
--
-- pgvector(vector 확장)는 Supabase에 기본 탑재되어 있습니다.
-- ============================================================

-- Supabase에는 이미 활성화되어 있지만, 안전하게 IF NOT EXISTS 유지
CREATE EXTENSION IF NOT EXISTS vector;

-- ── 교재 원본 메타데이터 ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS textbooks (
    id           SERIAL PRIMARY KEY,
    course       VARCHAR(32)  NOT NULL CHECK (course IN ('tax', 'accounting')),
    title        TEXT         NOT NULL,
    file_name    TEXT         NOT NULL,
    total_pages  INT,
    status       VARCHAR(16)  NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','processing','done','error')),
    error_msg    TEXT,
    created_at   TIMESTAMPTZ  DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- ── 청크 (텍스트 + 임베딩) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS chunks (
    id           SERIAL PRIMARY KEY,
    textbook_id  INT          NOT NULL REFERENCES textbooks(id) ON DELETE CASCADE,
    course       VARCHAR(32)  NOT NULL,
    chapter      TEXT,
    page_start   INT,
    page_end     INT,
    content      TEXT         NOT NULL,
    token_count  INT,
    embedding    vector(1536),          -- text-embedding-3-large
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS chunks_course_idx ON chunks (course);
CREATE INDEX IF NOT EXISTS chunks_textbook_idx ON chunks (textbook_id);

-- ── 에이전트 시스템 프롬프트 (버전 관리) ────────────────────
CREATE TABLE IF NOT EXISTS agent_prompts (
    id           SERIAL PRIMARY KEY,
    course       VARCHAR(32)  NOT NULL,
    agent_name   VARCHAR(64)  NOT NULL,
    prompt_text  TEXT         NOT NULL,
    version      INT          NOT NULL DEFAULT 1,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (course, agent_name, version)
);

CREATE INDEX IF NOT EXISTS agent_prompts_active_idx
    ON agent_prompts (course, agent_name) WHERE is_active = TRUE;

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS textbooks_updated_at ON textbooks;
CREATE TRIGGER textbooks_updated_at
    BEFORE UPDATE ON textbooks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
