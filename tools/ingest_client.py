"""tutor-agent 프로젝트용 ingest API 클라이언트.

이 파일을 tutor-agent/tools/ingest_client.py 에 복사하세요.

사용 예 (agents/tax/teacher_agent.py):

    from tools.ingest_client import IngestClient, make_rag_agent
    from langchain_openai import ChatOpenAI

    client = IngestClient()   # INGEST_API_URL, INGEST_API_KEY 환경변수 읽음
    llm = ChatOpenAI(model="gpt-4o-mini")

    teacher_agent = make_rag_agent(llm, client, course="tax", agent_name="teacher_agent")
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Callable

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

_BASE = os.getenv("INGEST_API_URL", "http://localhost:8100")
_KEY  = os.getenv("INGEST_API_KEY", "change-me")
_TIMEOUT = 10.0


class IngestClient:
    """tutor-ingest FastAPI 클라이언트."""

    def __init__(self, base_url: str = _BASE, api_key: str = _KEY):
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    # ── RAG 검색 ─────────────────────────────────────────────
    def search(self, query: str, course: str, top_k: int = 5) -> list[dict]:
        resp = httpx.get(
            f"{self._base}/search",
            params={"query": query, "course": course, "top_k": top_k},
            headers=self._headers,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["results"]

    # ── 프롬프트 조회 (캐시: 같은 course+agent 는 재요청 안 함) ─
    @lru_cache(maxsize=32)
    def get_prompt(self, course: str, agent_name: str) -> str | None:
        resp = httpx.get(
            f"{self._base}/prompt/{course}/{agent_name}",
            headers=self._headers,
            timeout=_TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("prompt_text")

    def invalidate_prompt_cache(self):
        """프롬프트 재생성 후 캐시 초기화."""
        self.get_prompt.cache_clear()


# ── 에이전트 팩토리 ──────────────────────────────────────────

def make_rag_agent(
    llm: ChatOpenAI,
    client: IngestClient,
    course: str,
    agent_name: str,
    rag_top_k: int = 4,
    fallback_prompt: str = "당신은 유용한 세무·회계 튜터입니다.",
) -> Callable[[dict], dict]:
    """DB 프롬프트 + RAG를 주입하는 에이전트 함수 반환."""

    def agent(state: dict) -> dict:
        sys_prompt = client.get_prompt(course, agent_name) or fallback_prompt

        messages = state.get("messages", [])
        last_human = next(
            (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
        )

        rag_ctx = ""
        if last_human:
            q = last_human.content if isinstance(last_human.content, str) else str(last_human.content)
            chunks = client.search(q, course, top_k=rag_top_k)
            if chunks:
                parts = [c['content'] for c in chunks]
                rag_ctx = (
                    "\n\n---\n"
                    "📚 교재 참고 내용 (아래는 내부 참고용입니다):\n\n"
                    + "\n\n".join(parts)
                    + "\n\n"
                    "⚠️ 저작권 준수 지침:\n"
                    "- 위 내용을 문장 단위로 그대로 복사·인용하지 마세요.\n"
                    "- 개념·원리를 이해한 뒤 반드시 자신의 언어로 재구성하여 설명하세요.\n"
                    "- 문제를 출제할 때 교재의 고유명사(회사명·인명·상호 등)와 수치는 "
                    "유사하지만 다른 예시(예: '(주)한국' → '(주)미래', 금액도 임의 변경)로 바꾸세요.\n"
                    "- 교재 페이지·챕터 번호를 답변에 직접 노출하지 마세요.\n"
                    "---"
                )

        response = llm.invoke(
            [SystemMessage(content=sys_prompt + rag_ctx)] + list(messages)
        )
        return {"messages": list(messages) + [response], "current_agent": agent_name}

    agent.__name__ = agent_name
    return agent
