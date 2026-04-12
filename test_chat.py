"""채팅 API 간단 테스트.

실행:
    python test_chat.py
"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv(encoding="utf-8-sig")

BASE_URL = "http://localhost:8100"
API_KEY = os.getenv("INGEST_API_KEY", "change-me-jWHUGj-AJ3sEiW6MC6C6zT8yZ")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def test():
    # 1. thread 생성
    r = httpx.post(f"{BASE_URL}/api/threads", headers=HEADERS)
    r.raise_for_status()
    thread_id = r.json()["thread_id"]
    print(f"thread_id: {thread_id}\n")

    # 2. 스트리밍 채팅
    payload = {
        "assistant_id": "tax",
        "input": {
            "messages": [{"role": "human", "content": "부가가치세가 뭔가요?"}]
        },
        "thread_id": thread_id,
    }

    print("=== 응답 스트림 ===")
    with httpx.stream("POST", f"{BASE_URL}/api/runs/stream", json=payload, headers=HEADERS, timeout=60) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line.startswith("data:"):
                print(line[5:].strip())


if __name__ == "__main__":
    test()
