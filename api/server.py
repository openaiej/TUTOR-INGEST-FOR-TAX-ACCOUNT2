"""FastAPI — RAG·프롬프트 조회 + LangGraph 튜터 채팅 API 서버.

실행:
    uvicorn api.server:app --host 0.0.0.0 --port 8100 --reload
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal
from dotenv import load_dotenv

load_dotenv(encoding="utf-8-sig")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from ingest.embedder import search
from ingest.prompt_builder import load_prompt, AGENT_META
from db.connection import get_cur

# ── API 키 인증 ──────────────────────────────────────────────
_API_KEY = os.getenv("INGEST_API_KEY", "change-me-jWHUGj-AJ3sEiW6MC6C6zT8yZ")
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


# ── 채팅 엔드포인트 ──────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["human", "ai"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    current_agent: str | None = None

    def to_langchain_messages(self):
        result = []
        for m in self.messages:
            if m.role == "human":
                result.append(HumanMessage(content=m.content))
            else:
                result.append(AIMessage(content=m.content))
        return result


def _get_graphs():
    """순환 import 방지를 위해 지연 import."""
    from main import GRAPHS_BY_COURSE
    return GRAPHS_BY_COURSE


@app.post(
    "/chat/{course}",
    dependencies=[Depends(verify)],
    summary="튜터 채팅 (SSE 스트리밍)",
)
async def chat(course: str, req: ChatRequest):
    if course not in ("tax", "accounting"):
        raise HTTPException(400, "course must be 'tax' or 'accounting'")

    graphs = _get_graphs()
    graph = graphs[course]

    state = {
        "messages": req.to_langchain_messages(),
        "current_agent": req.current_agent or "classification_agent",
    }

    async def event_stream():
        agent_name = ""
        try:
            async for event in graph.astream_events(state, version="v2"):
                kind = event["event"]

                # 에이전트 이름 추적
                if kind == "on_chain_start" and event.get("name", "").endswith("_agent"):
                    agent_name = event["name"]

                # LLM 토큰 스트리밍
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'agent': agent_name}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── LangGraph 호환 API ───────────────────────────────────────

_threads: dict[str, dict] = {}


@app.post("/api/threads", dependencies=[Depends(verify)])
async def create_thread():
    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    thread = {
        "thread_id": thread_id,
        "created_at": now,
        "updated_at": now,
        "metadata": {},
        "status": "idle",
        "values": None,
    }
    _threads[thread_id] = thread
    return thread


class RunStreamRequest(BaseModel):
    assistant_id: str          # course: "tax" | "accounting"
    input: dict
    config: dict | None = None
    stream_mode: list[str] | str | None = None
    thread_id: str | None = None


@app.post("/api/runs/stream", dependencies=[Depends(verify)])
async def runs_stream(req: RunStreamRequest):
    course = req.assistant_id
    if course not in ("tax", "accounting"):
        raise HTTPException(400, "assistant_id must be 'tax' or 'accounting'")

    graphs = _get_graphs()
    graph = graphs[course]
    run_id = str(uuid.uuid4())

    messages_raw = req.input.get("messages", [])
    current_agent = req.input.get("current_agent", "classification_agent")

    lc_messages = []
    for m in messages_raw:
        role = m.get("role") or m.get("type", "human")
        content = m.get("content", "")
        if role in ("human", "user"):
            lc_messages.append(HumanMessage(content=content))
        else:
            lc_messages.append(AIMessage(content=content))

    state = {"messages": lc_messages, "current_agent": current_agent}

    async def event_stream():
        yield f"event: metadata\ndata: {json.dumps({'run_id': run_id})}\n\n"

        agent_name = ""
        ai_msg_id = str(uuid.uuid4())

        try:
            async for event in graph.astream_events(state, version="v2"):
                kind = event["event"]

                if kind == "on_chain_start" and event.get("name", "").endswith("_agent"):
                    agent_name = event["name"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        msg_chunk = {
                            "type": "AIMessageChunk",
                            "content": chunk.content,
                            "id": ai_msg_id,
                        }
                        yield f"event: messages/partial\ndata: {json.dumps([msg_chunk], ensure_ascii=False)}\n\n"

            yield f"event: end\ndata: {json.dumps({'agent': agent_name})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
