"""psycopg3 연결 헬퍼 — Supabase Pooler(Session mode) 호환.

DATABASE_URL 에 Supabase Pooler URL을 설정하세요.
(Project Settings → Database → Connection pooling → Session mode, port 5432)
"""
from __future__ import annotations
import os
from contextlib import contextmanager
import psycopg
import psycopg.rows

_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres",
)


@contextmanager
def get_conn():
    with psycopg.connect(_DSN) as conn:
        yield conn


@contextmanager
def get_cur(dict_row: bool = False):
    factory = psycopg.rows.dict_row if dict_row else None
    with psycopg.connect(_DSN, row_factory=factory) as conn:
        with conn.cursor() as cur:
            yield cur
            conn.commit()