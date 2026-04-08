"""psycopg3 연결 헬퍼 — Supabase Pooler(Session mode) 호환.

비밀번호에 #·?·% 특수문자가 있어도 URL 파서를 거치지 않도록
Python으로 직접 파싱 후 kwargs로 전달합니다.

DATABASE_URL: Supabase → Project Settings → Database
              → Connection pooling → Session mode → port 5432
"""
from __future__ import annotations
import os
from contextlib import contextmanager
import psycopg
import psycopg.rows

_RAW_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres",
)


def _parse_pg_url(url: str) -> dict:
    """URL을 직접 파싱해 psycopg.connect() kwargs 반환.
    비밀번호의 %·#·? 등 특수문자를 디코딩하지 않고 리터럴 그대로 전달.
    """
    rest = url.split("://", 1)[1]           # user:pass@host:port/db
    at = rest.rfind("@")                    # 마지막 @ 기준 분리
    userinfo, hostinfo = rest[:at], rest[at + 1:]

    colon = userinfo.index(":")
    user = userinfo[:colon]
    password = userinfo[colon + 1:]         # 디코딩 안 함

    hostinfo_base, _, query = hostinfo.partition("?")
    sslmode = "require"
    for part in query.split("&"):
        if part.startswith("sslmode="):
            sslmode = part.split("=", 1)[1]

    host_port, _, dbname = hostinfo_base.partition("/")
    host, _, port = host_port.partition(":")

    return dict(
        user=user,
        password=password,
        host=host,
        port=int(port) if port else 5432,
        dbname=dbname,
        sslmode=sslmode,
    )


_CONN_KWARGS = _parse_pg_url(_RAW_DSN)


@contextmanager
def get_conn():
    with psycopg.connect(**_CONN_KWARGS) as conn:
        yield conn


@contextmanager
def get_cur(dict_row: bool = False):
    factory = psycopg.rows.dict_row if dict_row else None
    with psycopg.connect(**_CONN_KWARGS, row_factory=factory) as conn:
        with conn.cursor() as cur:
            yield cur
            conn.commit()
