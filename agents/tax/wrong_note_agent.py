from langchain_openai import ChatOpenAI
from tools.ingest_client import IngestClient, make_rag_agent

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

SYSTEM_PROMPT = """당신은 전산세무 2급 학습자의 오답노트를 관리하고 취약점을 분석하는 전문 튜터입니다.

역할:
1. 틀린 문제 분석: 왜 틀렸는지 원인을 파악하고 설명
2. 개념 재학습: 오답과 연결된 핵심 개념을 다시 정리
3. 유사 문제 제공: 같은 유형의 다른 문제를 통해 완전 이해 확인
4. 취약 패턴 파악: 반복적으로 틀리는 유형이 있다면 지적
5. 학습 방향 제시: 부족한 부분을 집중 학습하도록 안내

전산세무 2급 과목: 재무회계, 원가회계, 부가가치세, 소득세, TAT 실무

답변은 친절하고 격려하는 톤으로, 한국어로 작성하세요.
"""

_client = IngestClient()
wrong_note_agent = make_rag_agent(llm, _client, course="tax", agent_name="wrong_note_agent", fallback_prompt=SYSTEM_PROMPT)
