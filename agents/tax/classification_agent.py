from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

SYSTEM_PROMPT = """당신은 전산세무 2급 학습 시스템의 라우터입니다.
사용자의 메시지를 분석하여 가장 적합한 에이전트로 라우팅하세요.

에이전트 목록:
- teacher_agent: 개념 설명 요청 (예: "~가 뭐야?", "~를 설명해줘", "~의 정의는?")
- feynman_agent: 쉬운 설명 요청 (예: "쉽게 설명해줘", "비유로 설명해줘", "초등학생처럼")
- quiz_agent: 문제 풀이/출제 요청 (예: "문제 내줘", "퀴즈", "연습문제", "~를 풀어줘")
- exam_agent: 기출문제 분석 요청 (예: "기출", "시험 문제", "출제 경향", "자주 나오는")
- wrong_note_agent: 오답노트 관리 (예: "틀린 문제", "오답", "다시 보기", "취약점")
- calculator_agent: 세무·회계 계산 요청 (예: "계산해줘", "세액은?", "얼마야?", "부가세", "소득세 계산")

반드시 아래 중 하나만 정확히 출력하세요 (다른 텍스트 없이):
teacher_agent
feynman_agent
quiz_agent
exam_agent
wrong_note_agent
calculator_agent

과목 범위: 재무회계, 원가회계, 부가가치세, 소득세, TAT 실무(전산회계 프로그램)
"""

AGENT_DESTINATIONS = Literal[
    "teacher_agent",
    "feynman_agent",
    "quiz_agent",
    "exam_agent",
    "wrong_note_agent",
    "calculator_agent",
]


def classification_agent(state):
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=last_message),
        ]
    )

    destination = response.content.strip()

    valid_agents = [
        "teacher_agent",
        "feynman_agent",
        "quiz_agent",
        "exam_agent",
        "wrong_note_agent",
        "calculator_agent",
    ]

    if destination not in valid_agents:
        destination = "teacher_agent"

    return Command(
        goto=destination,
        update={"current_agent": destination},
    )
