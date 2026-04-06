"""OpenAI 임베딩 + PostgreSQL 저장."""
from __future__ import annotations

import os, time
from typing import Sequence
from openai import OpenAI
from ingest.parser import Chunk
from db.connection import get_cur

MODEL = "text-embedding-3-small"
BATCH = 64

_client: OpenAI | None = None


def _cli() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    result = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i: i + BATCH]
        for attempt in range(3):
            try:
                resp = _cli().embeddings.create(model=MODEL, input=batch)
                result.extend(x.embedding for x in resp.data)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
    return result


# ── textbooks ────────────────────────────────────────────────

def create_textbook(course: str, title: str, file_name: str, total_pages: int | None) -> int:
    with get_cur() as cur:
        cur.execute(
            "INSERT INTO textbooks (course,title,file_name,total_pages,status) "
            "VALUES (%s,%s,%s,%s,'processing') RETURNING id",
            (course, title, file_name, total_pages),
        )
        return cur.fetchone()[0]


def update_textbook_status(tb_id: int, status: str, error_msg: str | None = None):
    with get_cur() as cur:
        cur.execute(
            "UPDATE textbooks SET status=%s, error_msg=%s WHERE id=%s",
            (status, error_msg, tb_id),
        )


# ── chunks ───────────────────────────────────────────────────

def save_chunks(tb_id: int, course: str, chunks: Sequence[Chunk], embed: bool = True) -> int:
    vectors = embed_texts([c.content for c in chunks]) if embed else [None] * len(chunks)
    with get_cur() as cur:
        cur.executemany(
            "INSERT INTO chunks "
            "(textbook_id,course,chapter,page_start,page_end,content,token_count,embedding) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                (tb_id, course, c.chapter, c.page_start, c.page_end,
                 c.content, c.token_count, v)
                for c, v in zip(chunks, vectors)
            ],
        )
    return len(chunks)


def delete_chunks_by_textbook(tb_id: int):
    with get_cur() as cur:
        cur.execute("DELETE FROM chunks WHERE textbook_id=%s", (tb_id,))


# ── RAG 검색 (API 서버에서 호출) ─────────────────────────────

def search(query: str, course: str, top_k: int = 5) -> list[dict]:
    q_vec = embed_texts([query])[0]
    with get_cur(dict_row=True) as cur:
        cur.execute(
            """
            SELECT id, chapter, page_start, page_end, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM chunks
            WHERE course=%s AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (q_vec, course, q_vec, top_k),
        )
        return [dict(r) for r in cur.fetchall()]
