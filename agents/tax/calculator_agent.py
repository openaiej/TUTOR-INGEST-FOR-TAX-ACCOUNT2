from langchain_openai import ChatOpenAI
from tools.ingest_client import IngestClient, make_rag_agent

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

SYSTEM_PROMPT = """당신은 전산세무 2급 세무/회계 계산 전문가입니다.
정확한 계산 과정을 단계별로 보여주세요.

답변 형식:
1. 주어진 조건 정리
2. 적용 공식 명시
3. 단계별 계산 과정 (숫자를 명확하게)
4. 최종 답변
5. 관련 세법/회계기준 근거 (필요 시)

계산 결과는 원 단위로 표시하고, 천 단위 구분기호(,)를 사용하세요.
한국어로 답변하세요.
"""

_client = IngestClient()
calculator_agent = make_rag_agent(llm, _client, course="tax", agent_name="calculator_agent", fallback_prompt=SYSTEM_PROMPT)
