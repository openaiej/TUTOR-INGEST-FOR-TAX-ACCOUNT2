from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

SYSTEM_PROMPT = """당신은 전산회계 2급(국가기술자격) 학습 시스템의 라우터입니다.
사용자의 메시지를 분석하여 가장 적합한 에이전트로 라우팅하세요.

에이전트 목록:
- teacher_agent: 개념 설명 요청 (예: "~가 뭐야?", "~를 설명해줘", "회계처리 알려줘")
- feynman_agent: 쉬운 설명 요청 (예: "쉽게 설명해줘", "비유로 설명해줘", "초보자도 이해하게")
- quiz_agent: 문제 풀이/출제 요청 (예: "문제 내줘", "퀴즈", "연습문제", "객관식")
- exam_agent: 기출·출제 경향 요청 (예: "기출", "시험에 나오는", "출제 비중", "자주 나오는 유형")
- wrong_note_agent: 오답·취약점 (예: "틀렸어", "오답", "왜 틀렸지", "취약점")
- calculator_agent: 숫자·분개·원가·감가상각 등 회계 계산 (예: "계산해줘", "분개", "감가상각", "원가")

반드시 아래 중 하나만 정확히 출력하세요 (다른 텍스트 없이):
teacher_agent
feynman_agent
quiz_agent
exam_agent
wrong_note_agent
calculator_agent

과목 범위: 회계원리, 재무회계, 원가회계 기초, 전산회계 실무(스프레드시트·전표·결산 흐름 등). 세법·세무 실무는 이 과정의 중심이 아닙니다.
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
