# TaxTutor Backend

교재 PDF 인제스트 + LangGraph 튜터 에이전트 + FastAPI 서버

```
TaxTutor-Backend/
├── agents/
│   ├── tax/                    전산세무 2급 에이전트 (7종)
│   └── accounting/             전산회계 2급 에이전트 (7종)
├── db/
│   ├── schema.sql              PostgreSQL 테이블 + pgvector 인덱스
│   └── connection.py           psycopg3 연결 헬퍼
├── ingest/
│   ├── parser.py               PDF 파싱 + 청크 분할
│   ├── embedder.py             OpenAI 임베딩 + DB 저장 + RAG 검색
│   └── prompt_builder.py       에이전트 시스템 프롬프트 생성·저장
├── api/
│   └── server.py               FastAPI 서버 (RAG / 프롬프트 / 채팅 API)
├── graph_builder.py            LangGraph 튜터 그래프 컴파일
├── main.py                     GRAPHS_BY_COURSE 초기화 (tax / accounting)
├── app.py                      Streamlit 관리 UI
└── tools/
    └── ingest_client.py        에이전트에서 RAG·프롬프트 호출 클라이언트
```

---

## 아키텍처

```
클라이언트
  └─ POST /api/threads          thread_id 발급
  └─ POST /api/runs/stream      LangGraph 그래프 실행 + SSE 스트리밍
  └─ GET  /search               RAG 청크 검색
  └─ GET  /prompt/{course}/...  에이전트 프롬프트 조회

FastAPI (8100)
  ├─ LangGraph 그래프 (인프로세스 실행)
  │    ├─ classification_agent  → 의도 분류 + 다음 에이전트 결정
  │    ├─ teacher_agent         → 개념 설명
  │    ├─ feynman_agent         → 파인만 기법 설명
  │    ├─ quiz_agent            → 퀴즈 생성
  │    ├─ exam_agent            → 기출 문제 풀이
  │    ├─ wrong_note_agent      → 오답 노트
  │    └─ calculator_agent      → 계산 문제
  └─ PostgreSQL (Supabase)
       ├─ textbooks             교재 메타데이터
       ├─ chunks                PDF 청크 + pgvector 임베딩
       └─ agent_prompts         에이전트별 시스템 프롬프트 버전 관리

Streamlit (8501)
  └─ 교재 업로드 / 청크 확인 / 프롬프트 관리 / RAG 검색 테스트
```

> LangGraph 서버(`langgraph dev`)를 별도로 띄울 필요 없음.  
> 그래프를 FastAPI 프로세스 안에서 직접 실행하며 LangGraph 호환 API를 제공합니다.

---

## 설치

```bash
uv sync
cp .env.example .env  # .env 편집
```

---

## 환경변수 (.env)

```
DATABASE_URL=postgresql://...   # Supabase Pooler URL (Session mode, port 5432)
OPENAI_API_KEY=sk-...
INGEST_API_KEY=your-secret-key
```

> **Supabase**: Project Settings → Database → Connection pooling → Session mode → port 5432 URL 사용  
> Direct connection은 Railway 환경에서 IPv6 문제로 연결 불가

---

## 로컬 실행

```bash
# API 서버 (채팅 + RAG + 관리 엔드포인트)
.venv/Scripts/python.exe -m uvicorn api.server:app --host 0.0.0.0 --port 8100 --reload

# 관리 UI (PDF 업로드·프롬프트 관리)
streamlit run app.py   # http://localhost:8501
```

> Windows + 한글 경로에서 `uvicorn` 직접 실행 시 uv trampoline 오류 발생 → `.venv/Scripts/python.exe -m uvicorn` 으로 실행

---

## API 엔드포인트

### 인증
모든 엔드포인트(health 제외)는 `Authorization: Bearer <INGEST_API_KEY>` 헤더 필요.

### 기본

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스 체크 |
| GET | `/search?query=&course=&top_k=` | RAG 청크 검색 |
| GET | `/prompt/{course}/{agent_name}` | 활성 프롬프트 조회 |
| GET | `/textbooks?course=` | 교재 목록 |

### 채팅 (기존)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/chat/{course}` | SSE 스트리밍 채팅 |

### LangGraph 호환 API

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/threads` | thread_id 발급 |
| POST | `/api/runs/stream` | 그래프 실행 + SSE 스트리밍 |

#### `POST /api/threads` 응답
```json
{
  "thread_id": "uuid",
  "created_at": "2026-...",
  "updated_at": "2026-...",
  "metadata": {},
  "status": "idle",
  "values": null
}
```

#### `POST /api/runs/stream` 요청
```json
{
  "assistant_id": "tax",
  "input": {
    "messages": [{ "role": "human", "content": "부가가치세란?" }],
    "current_agent": "classification_agent"
  }
}
```

#### SSE 스트림 형식 (LangGraph 표준)
```
event: metadata
data: {"run_id": "uuid"}

event: messages/partial
data: [{"type": "AIMessageChunk", "content": "토큰..."}]

event: end
data: {"agent": "teacher_agent"}
```

- `assistant_id`: `"tax"` (전산세무 2급) 또는 `"accounting"` (전산회계 2급)
- `current_agent`: 생략 시 `classification_agent`가 의도를 분류해 다음 에이전트로 라우팅

---

## 에이전트 목록

| agent_name | 역할 |
|---|---|
| `classification_agent` | 사용자 의도 분류 → 적절한 에이전트로 라우팅 |
| `teacher_agent` | 개념 설명 |
| `feynman_agent` | 파인만 기법으로 설명 |
| `quiz_agent` | 퀴즈 생성 |
| `exam_agent` | 기출 문제 풀이 |
| `wrong_note_agent` | 오답 노트 정리 |
| `calculator_agent` | 계산 문제 |

---

## 배포 (Railway / Render)

**Railway**
```bash
npm i -g @railway/cli
railway login
railway up
```

**Render**: `render.yaml` 포함되어 있음 → GitHub 연동 후 자동 배포

환경변수 (`DATABASE_URL`, `OPENAI_API_KEY`, `INGEST_API_KEY`)는 각 플랫폼 대시보드에서 설정.

---

## 트러블슈팅

| 문제 | 원인 | 해결 |
|------|------|------|
| `Network is unreachable` | Railway → Supabase Direct connection IPv6 불가 | Pooler URL (Session mode) 사용 |
| `SCRAM auth failed` | psycopg2 + Pooler URL | psycopg3(`psycopg[binary]`)으로 교체 |
| `uv trampoline failed` | Windows 한글 경로 | `.venv/Scripts/python.exe -m uvicorn` 사용 |
| `Could not import module "main"` | Railway Start Command 미설정 | 대시보드 Settings에서 직접 입력 |
