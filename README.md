# tutor-ingest

교재 PDF → 청크·임베딩 → PostgreSQL 저장 → 에이전트 시스템 프롬프트 자동 생성 → FastAPI로 tutor-agent에 제공

```
tutor-ingest/
├── db/
│   ├── schema.sql          PostgreSQL 테이블 + pgvector 인덱스
│   └── connection.py       psycopg3 연결 헬퍼
├── ingest/
│   ├── parser.py           PDF 파싱 + 청크 분할
│   ├── embedder.py         OpenAI 임베딩 + DB 저장 + RAG 검색
│   └── prompt_builder.py   에이전트 시스템 프롬프트 생성·저장
├── api/
│   └── server.py           FastAPI (RAG 검색 / 프롬프트 조회 / 교재 목록)
├── app.py                  Streamlit 관리 UI
├── tools/
│   └── ingest_client.py    tutor-agent에 복사해서 쓰는 API 클라이언트
└── pyproject.toml
```

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
# 관리 UI (PDF 업로드·프롬프트 관리)
streamlit run app.py                        # http://localhost:8501

# API 서버 (tutor-agent가 호출)
.venv/Scripts/python.exe -m uvicorn api.server:app --host 0.0.0.0 --port 8100 --reload
```

> Windows + 한글 경로에서 `uvicorn` 직접 실행 시 uv trampoline 오류 발생 → `.venv/Scripts/python.exe -m uvicorn` 으로 실행

---

## 구조

```
Streamlit (8501)   →  DB 직접 접근  →  PostgreSQL (Supabase)
FastAPI   (8100)   →  DB 직접 접근  ↗
```

두 서버는 서로 통신하지 않고 각각 DB에 직접 접근합니다.

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스 체크 (인증 불필요) |
| GET | `/search?query=&course=&top_k=` | RAG 청크 검색 |
| GET | `/prompt/{course}/{agent_name}` | 활성 프롬프트 조회 |
| GET | `/textbooks?course=` | 교재 목록 |

모든 엔드포인트(health 제외)는 `Authorization: Bearer <INGEST_API_KEY>` 필요.

---

## tutor-agent 연동

`tools/ingest_client.py`를 tutor-agent의 `tools/`에 복사 후 `.env`에 추가:

```
INGEST_API_URL=https://tutor-ingest-api.onrender.com  # 배포 URL
INGEST_API_KEY=your-secret-key
```

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
