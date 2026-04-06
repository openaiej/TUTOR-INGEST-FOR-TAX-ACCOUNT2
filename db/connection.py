"""psycopg2 연결 헬퍼 — Supabase Direct Connection 전용.

Supabase 대시보드 → Project Settings → Database → Connection string
→ "Direct connection" 탭의 URI를 DATABASE_URL 에 설정하세요.
Pooler(PgBouncer) URL은 psycopg2 SCRAM 인증 오류를 유발합니다.
"""
from __future__ import annotations
import os
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor

_RAW_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres",
)


def _parse_pg_url(url: str) -> dict:
    """URL 파싱을 Python 문자열 연산으로 직접 수행.
    비밀번호에 #·?·% 같은 특수문자가 있어도 libpq URL 파서를 거치지 않으므로 안전.
    """
    rest = url.split("://", 1)[1]           # user:pass@host:port/db?query

    # @ 를 먼저 찾아야 함 — ? 로 먼저 자르면 비밀번호 속 ?가 호스트 쪽으로 넘어감
    at = rest.rfind("@")                    # 마지막 @ 기준으로 userinfo / hostinfo 분리
    userinfo, hostinfo = rest[:at], rest[at + 1:]

    colon = userinfo.index(":")
    user = userinfo[:colon]
    password = userinfo[colon + 1:]  # URL 디코딩 안 함 — 리터럴 비밀번호 그대로 전달

    # hostinfo 에서 쿼리스트링(sslmode 등) 분리
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
    conn = psycopg2.connect(**_CONN_KWARGS)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cur(dict_row: bool = False):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor if dict_row else None) as cur:
            yield cur
