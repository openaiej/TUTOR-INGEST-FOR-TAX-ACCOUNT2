"""로컬 ingest 함수를 직접 호출하는 클라이언트.

HTTP 대신 같은 프로세스의 ingest.embedder / ingest.prompt_builder 를 직접 호출합니다.
인터페이스는 기존 HTTP 버전과 동일하여 에이전트 코드 변경 없이 사용 가능합니다.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ingest.embedder import search as _search
from ingest.prompt_builder import load_prompt as _load_prompt

logger = logging.getLogger(__name__)


class IngestClient:
    """로컬 ingest 함수 래퍼 — HTTP 클라이언트와 동일한 인터페이스."""

    # ── RAG 검색 ─────────────────────────────────────────────
    def search(self, query: str, course: str, top_k: int = 5) -> list[dict]:
        return _search(query, course, top_k=top_k)

    # ── 프롬프트 조회 (캐시: 같은 course+agent 는 재요청 안 함) ─
    @lru_cache(maxsize=32)
    def get_prompt(self, course: str, agent_name: str) -> str | None:
        return _load_prompt(course, agent_name)

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
        db_prompt = client.get_prompt(course, agent_name)
        sys_prompt = db_prompt or fallback_prompt
        prompt_source = "DB" if db_prompt else "FALLBACK"

        messages = state.get("messages", [])
        last_human = next(
            (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
        )

        logger.info("[%s/%s] prompt_source=%s", course, agent_name, prompt_source)
        logger.debug("[%s/%s] system_prompt=%.200s", course, agent_name, sys_prompt)

        rag_ctx = ""
        if last_human:
            q = last_human.content if isinstance(last_human.content, str) else str(last_human.content)
            chunks = client.search(q, course, top_k=rag_top_k)
            if chunks:
                parts = [c['content'] for c in chunks]
                rag_ctx = (
                    "📚 교재 참고 내용 (아래는 내부 참고용입니다):\n\n"
                    + "\n\n".join(parts)
                    + "\n\n"
                    "⚠️ 저작권 준수 지침:\n"
                    "- 위 내용을 문장 단위로 그대로 복사·인용하지 마세요.\n"
                    "- 개념·원리를 이해한 뒤 반드시 자신의 언어로 재구성하여 설명하세요.\n"
                    "- 문제를 출제할 때 교재의 고유명사(회사명·인명·상호 등)와 수치는 "
                    "유사하지만 다른 예시(예: '(주)한국' → '(주)미래', 금액도 임의 변경)로 바꾸세요.\n"
                    "- 교재 페이지·챕터 번호를 답변에 직접 노출하지 마세요.\n"
                )

        response = llm.invoke(
            [SystemMessage(content=sys_prompt + rag_ctx)] + list(messages)
        )

        # 정답 표기 정규화
        import re
        raw = response.content
        cleaned = raw
        # **정답: X** 또는 **정답:** X → [ 정답 ] X
        cleaned = re.sub(r'\*\*정답\s*:\s*([^*\n]+?)\*\*', r'[ 정답 ] \1', cleaned)
        cleaned = re.sub(r'\*\*정답\s*:\*\*\s*([^\n]+)', r'[ 정답 ] \1', cleaned)
        # [ 정답 ] 앞의 이중 줄바꿈을 단일 줄바꿈으로 정규화
        cleaned = re.sub(r'\n{2,}(\[\s*정답\s*\])', r'\n\1', cleaned)
        if raw != cleaned:
            logger.info("[%s/%s] 후처리 적용 전: %.200s", course, agent_name, repr(raw))
            logger.info("[%s/%s] 후처리 적용 후: %.200s", course, agent_name, repr(cleaned))
        else:
            logger.info("[%s/%s] 후처리 변환 없음 (원본 유지): %.200s", course, agent_name, repr(raw[:200]))
        response = response.model_copy(update={"content": cleaned})

        logger.info("[%s/%s] llm_response=%.300s", course, agent_name, response.content)
        return {"messages": list(messages) + [response], "current_agent": agent_name}

    agent.__name__ = agent_name
    return agent
