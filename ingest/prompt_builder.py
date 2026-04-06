"""교재 목차 → GPT-4o → 에이전트 시스템 프롬프트 생성 + DB 저장."""
from __future__ import annotations

import os, textwrap
from openai import OpenAI
from db.connection import get_cur

_client: OpenAI | None = None
def _cli() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client

COURSE_LABELS = {"tax": "전산세무 2급", "accounting": "전산회계 2급"}

AGENT_META: dict[str, dict] = {
    "classification_agent": {
        "role": "사용자 메시지를 분석해 적합한 에이전트로 라우팅하는 분류기",
        "instruction": textwrap.dedent("""\
            - 의도를 7가지 중 하나로 분류: teacher / feynman / quiz / exam /
              wrong_note / calculator / classification(모호).
            - 반드시 JSON { "next_agent": "<name>" } 만 출력.
            - 교재 목차를 참고해 과목 범위 내 질문인지 판단.
        """),
    },
    "teacher_agent": {
        "role": "개념을 체계적으로 설명하는 교사",
        "instruction": textwrap.dedent("""\
            - 교재 챕터 순서 유지: 정의 → 원리 → 예시 → 주의사항.
            - 한국 세무·회계 법령·기준을 정확히 인용.
            - 답변 끝에 "관련 챕터: <챕터명>" 표시.
        """),
    },
    "feynman_agent": {
        "role": "파인만 기법으로 쉽게 설명하는 튜터",
        "instruction": textwrap.dedent("""\
            - 전문 용어 최소화, 일상 비유 중심.
            - 마지막에 "이해됐나요? 더 쉽게 설명할 부분 있으면 말해주세요." 추가.
        """),
    },
    "quiz_agent": {
        "role": "교재 기반 퀴즈 출제 에이전트",
        "instruction": textwrap.dedent("""\
            - OX / 4지선다 / 빈칸 채우기 중 요청에 맞게 출제.
            - 각 문제에 챕터·난이도(하/중/상) 태그 포함.
            - 정답·해설은 "**정답:** ||해설||" 형식.
        """),
    },
    "exam_agent": {
        "role": "기출 경향 분석 + 예상 문제 제공 에이전트",
        "instruction": textwrap.dedent("""\
            - 빈출 주제를 교재 목차 기준으로 정리.
            - 유형(계산형/이론형/사례형)별로 분류.
            - 예상 문제마다 근거 챕터 명시.
        """),
    },
    "wrong_note_agent": {
        "role": "오답 분석 + 취약점 보완 에이전트",
        "instruction": textwrap.dedent("""\
            - 오답에서 오개념을 정확히 짚어 교정.
            - 유사 문제 1~2개 추가 제공.
            - 관련 챕터·핵심 키워드 안내.
        """),
    },
    "calculator_agent": {
        "role": "세무·회계 계산 문제를 단계별로 푸는 에이전트",
        "instruction": textwrap.dedent("""\
            - 수식과 함께 Step 1, Step 2… 로 과정 표시.
            - 사용한 세율·법령 조항 명시.
            - 최종 답은 **굵게** 별도 줄에 표시.
        """),
    },
}


def _toc(course: str, limit: int = 60) -> str:
    with get_cur() as cur:
        cur.execute(
            "SELECT DISTINCT chapter FROM chunks "
            "WHERE course=%s AND chapter IS NOT NULL ORDER BY chapter LIMIT %s",
            (course, limit),
        )
        rows = cur.fetchall()
    return "\n".join(f"- {r[0]}" for r in rows if r[0]) or "(목차 없음)"


def _generate(course: str, agent_name: str, toc: str) -> str:
    meta = AGENT_META[agent_name]
    label = COURSE_LABELS.get(course, course)
    prompt = textwrap.dedent(f"""\
        과정: {label}
        에이전트 역할: {meta['role']}

        교재 목차:
        {toc}

        위 과정과 목차를 기반으로 {agent_name} 용 시스템 프롬프트를 작성해주세요.
        반드시 포함할 지침:
        {meta['instruction']}

        출력: 시스템 프롬프트 텍스트만 (마크다운 코드블록 없이).
    """)
    resp = _cli().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system",
             "content": "당신은 AI 에이전트 시스템 프롬프트 전문가입니다. "
                        "주어진 과목·역할에 맞는 정확하고 구조적인 프롬프트를 한국어로 작성합니다."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def save_prompt(course: str, agent_name: str, text: str) -> int:
    with get_cur() as cur:
        cur.execute(
            "UPDATE agent_prompts SET is_active=FALSE "
            "WHERE course=%s AND agent_name=%s AND is_active=TRUE",
            (course, agent_name),
        )
        cur.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM agent_prompts "
            "WHERE course=%s AND agent_name=%s",
            (course, agent_name),
        )
        ver = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO agent_prompts (course,agent_name,prompt_text,version,is_active) "
            "VALUES (%s,%s,%s,%s,TRUE) RETURNING id",
            (course, agent_name, text, ver),
        )
        return cur.fetchone()[0]


def load_prompt(course: str, agent_name: str) -> str | None:
    with get_cur(dict_row=True) as cur:
        cur.execute(
            "SELECT prompt_text FROM agent_prompts "
            "WHERE course=%s AND agent_name=%s AND is_active=TRUE "
            "ORDER BY version DESC LIMIT 1",
            (course, agent_name),
        )
        row = cur.fetchone()
    return row["prompt_text"] if row else None


def generate_all(course: str, progress_cb=None) -> dict[str, int]:
    """모든 에이전트 프롬프트 생성·저장. progress_cb(agent_name, done, total) 선택."""
    toc = _toc(course)
    total = len(AGENT_META)
    result = {}
    for i, agent_name in enumerate(AGENT_META, 1):
        text = _generate(course, agent_name, toc)
        pid = save_prompt(course, agent_name, text)
        result[agent_name] = pid
        if progress_cb:
            progress_cb(agent_name, i, total)
    return result
