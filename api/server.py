"""FastAPI — 튜터 앱이 RAG·프롬프트를 조회하는 API 서버.

실행:
    uvicorn api.server:app --host 0.0.0.0 --port 8100 --reload
"""
from __future__ import annotations

import os
from typing import Annotated
from dotenv import load_dotenv

load_dotenv(encoding="utf-8-sig")

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from ingest.embedder import search
from ingest.prompt_builder import load_prompt, AGENT_META
from db.connection import get_cur

# ── API 키 인증 ──────────────────────────────────────────────
_API_KEY = os.getenv("INGEST_API_KEY", "change-me")
_bearer = HTTPBearer()


def verify(cred: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)]):
    if cred.credentials != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


app = FastAPI(
    title="Tutor Ingest API",
    description="RAG 검색·프롬프트 조회 엔드포인트",
    version="1.0.0",
)


# ── 응답 모델 ────────────────────────────────────────────────
class ChunkResult(BaseModel):
    id: int
    chapter: str | None
    page_start: int | None
    page_end: int | None
    content: str
    similarity: float


class SearchResponse(BaseModel):
    course: str
    query: str
    results: list[ChunkResult]


class PromptResponse(BaseModel):
    course: str
    agent_name: str
    prompt_text: str | None


class TextbookSummary(BaseModel):
    id: int
    course: str
    title: str
    total_pages: int | None
    status: str
    chunk_count: int


# ── 엔드포인트 ───────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get(
    "/search",
    response_model=SearchResponse,
    dependencies=[Depends(verify)],
    summary="RAG 청크 검색",
)
def rag_search(
    query: str,
    course: str = Query(..., pattern="^(tax|accounting)$"),
    top_k: int = Query(5, ge=1, le=20),
):
    results = search(query, course, top_k)
    return SearchResponse(
        course=course,
        query=query,
        results=[ChunkResult(**r) for r in results],
    )


@app.get(
    "/prompt/{course}/{agent_name}",
    response_model=PromptResponse,
    dependencies=[Depends(verify)],
    summary="에이전트 시스템 프롬프트 조회",
)
def get_prompt(course: str, agent_name: str):
    if course not in ("tax", "accounting"):
        raise HTTPException(400, "course must be 'tax' or 'accounting'")
    if agent_name not in AGENT_META:
        raise HTTPException(400, f"Unknown agent: {agent_name}")
    text = load_prompt(course, agent_name)
    return PromptResponse(course=course, agent_name=agent_name, prompt_text=text)


@app.get(
    "/textbooks",
    response_model=list[TextbookSummary],
    dependencies=[Depends(verify)],
    summary="등록된 교재 목록",
)
def list_textbooks(course: str | None = None):
    sql = """
        SELECT t.id, t.course, t.title, t.total_pages, t.status,
               COUNT(c.id) AS chunk_count
        FROM textbooks t
        LEFT JOIN chunks c ON c.textbook_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY t.id DESC
    """
    if course:
        with get_cur(dict_row=True) as cur:
            cur.execute(sql.format(where="WHERE t.course=%s"), (course,))
            rows = cur.fetchall()
    else:
        with get_cur(dict_row=True) as cur:
            cur.execute(sql.format(where=""))
            rows = cur.fetchall()
    return [TextbookSummary(**r) for r in rows]
