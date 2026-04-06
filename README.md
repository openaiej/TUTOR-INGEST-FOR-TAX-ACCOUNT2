# tutor-ingest

교재 PDF → 청크·임베딩 → PostgreSQL 저장  
→ 에이전트 시스템 프롬프트 자동 생성  
→ FastAPI로 tutor-agent 에 제공

```
tutor-ingest/
├── db/
│   ├── schema.sql          PostgreSQL 테이블 + pgvector 인덱스
│   └── connection.py       psycopg2 연결 헬퍼
├── ingest/
│   ├── parser.py           PDF 파싱 + 청크 분할
│   ├── embedder.py         OpenAI 임베딩 + DB 저장 + RAG 검색
│   └── prompt_builder.py   에이전트 시스템 프롬프트 생성·저장
├── api/
│   └── server.py           FastAPI (RAG 검색 / 프롬프트 조회 / 교재 목록)
├── admin/
│   └── app.py              Streamlit 관리 UI
├── tools/
│   └── ingest_client.py    tutor-agent 에 복사해서 쓰는 API 클라이언트
├── pyproject.toml
└── .env.example
```

---

## 설치

```bash
cd tutor-ingest
uv sync
cp .env.example .env
```

`.env` 에서 `DATABASE_URL` 을 Supabase **Direct connection** URI로 설정:
```
# 대시보드 → Project Settings → Database → Connection string → Direct connection
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
```

## DB 초기화 (Supabase)

Supabase 프로젝트가 없다면 https://supabase.com 에서 무료로 생성하세요.

**스키마 적용 방법 (둘 중 하나):**

**A) Supabase SQL Editor (추천)**
1. 대시보드 → SQL Editor → New query
2. `db/schema.sql` 내용을 붙여넣고 실행

**B) psql 직접 연결**
```bash
# Supabase 대시보드 → Project Settings → Database
# → Connection string → "Direct connection" URI 복사
psql "postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres?sslmode=require" \
     -f db/schema.sql
```

> **주의**: psycopg2는 반드시 **Direct connection** URI를 사용하세요.  
> Pooler(PgBouncer) URL(`*.pooler.supabase.com`)은 SCRAM 인증 오류가 납니다.

---

## 실행

### Streamlit 관리 UI (교재 업로드·프롬프트 관리)
```bash
uv run streamlit run app.py
```

### FastAPI 서버 (tutor-agent 가 조회)
```bash
uv run uvicorn api.server:app --host 0.0.0.0 --port 8100 --reload
```

API 문서: http://localhost:8100/docs

---

## tutor-agent 연동

`tools/ingest_client.py` 를 tutor-agent 프로젝트의 `tools/` 에 복사한 뒤
`.env` 에 추가:

```
INGEST_API_URL=http://localhost:8100
INGEST_API_KEY=your-secret-key-here
```

에이전트 교체 예시 (`agents/tax/teacher_agent.py`):

```python
from tools.ingest_client import IngestClient, make_rag_agent
from langchain_openai import ChatOpenAI

client = IngestClient()
llm = ChatOpenAI(model="gpt-4o-mini")
teacher_agent = make_rag_agent(llm, client, course="tax", agent_name="teacher_agent")
```

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스 체크 |
| GET | `/search?query=&course=&top_k=` | RAG 청크 검색 |
| GET | `/prompt/{course}/{agent_name}` | 활성 프롬프트 조회 |
| GET | `/textbooks?course=` | 교재 목록 |

모든 엔드포인트(health 제외)는 `Authorization: Bearer <INGEST_API_KEY>` 필요.


# 04-06
수고하셨습니다! 오늘 해결한 것들 정리하면:

문제	원인	해결
utf-8 codec 0xab (PDF)	pdfplumber/pdfminer 한국어 인코딩	pymupdf로 교체
utf-8 codec 0xab (DB)	psycopg2가 %aB# 포함 URL을 libpq에 넘김	Python으로 직접 파싱 → kwargs 전달
int() invalid literal	비밀번호 ?가 쿼리스트링으로 잘림	rfind("@") 먼저, 그 후 ? 분리
Name not known	IPv6만 있는 direct connection	Session Pooler URL로 교체
password auth failed	unquote가 %aB를 «로 디코딩	unquote 제거, 리터럴 그대로 전달

# api 서버 실행
uvicorn api.server:app --port 8100 --reload