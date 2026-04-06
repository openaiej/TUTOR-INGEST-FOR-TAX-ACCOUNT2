"""Streamlit 관리 UI — 교재 업로드·청크 확인·프롬프트 관리."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(encoding="utf-8-sig")  # utf-8-sig: BOM 포함 UTF-8 및 일반 UTF-8 모두 처리

from db.connection import get_cur
from ingest.parser import parse_pdf, get_page_count
from ingest.embedder import (
    create_textbook, save_chunks, update_textbook_status, delete_chunks_by_textbook
)
from ingest.prompt_builder import (
    generate_all, load_prompt, save_prompt, AGENT_META, COURSE_LABELS
)

st.set_page_config(page_title="Tutor Ingest 관리", page_icon="🗂️", layout="wide")
st.title("🗂️ Tutor Ingest 관리 대시보드")

COURSES = {"accounting": "전산회계 2급","tax": "전산세무 2급"}

# ── 사이드바 ─────────────────────────────────────────────────
page = st.sidebar.radio(
    "메뉴",
    ["📤 교재 업로드", "📋 교재 목록", "🤖 프롬프트 관리", "🔍 RAG 검색 테스트"],
)

# ═══════════════════════════════════════════════════════════
# 1. 교재 업로드
# ═══════════════════════════════════════════════════════════
if page == "📤 교재 업로드":
    st.header("교재 PDF 업로드")

    col1, col2 = st.columns(2)
    course = col1.selectbox("과정", list(COURSES.keys()), format_func=COURSES.get)
    max_tokens = col2.number_input("청크 최대 토큰", 200, 1000, 500, 50)
    embed = st.checkbox("임베딩 생성 (OpenAI API 호출)", value=True)
    gen_prompt = st.checkbox("완료 후 프롬프트 자동 재생성", value=True)

    uploaded = st.file_uploader("PDF 파일 선택", type=["pdf"])

    if uploaded and st.button("🚀 인제스트 시작", type="primary"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded.read())
            tmp_path = Path(tmp.name)

        tb_id = None
        try:
            pages = get_page_count(tmp_path)
            st.info(f"📖 {pages}페이지 감지")

            # textbook 등록
            tb_id = create_textbook(
                course=course,
                title=uploaded.name.rsplit(".", 1)[0],
                file_name=uploaded.name,
                total_pages=pages,
            )

            # 파싱
            with st.spinner("PDF 파싱 중…"):
                chunks = parse_pdf(tmp_path, max_tokens=int(max_tokens))
            st.success(f"✂️ {len(chunks)}개 청크 생성")

            # 임베딩 + 저장
            progress = st.progress(0, text="청크 저장 중…")
            saved = save_chunks(tb_id, course, chunks, embed=embed)
            progress.progress(1.0, text=f"💾 {saved}개 저장 완료")

            update_textbook_status(tb_id, "done")

            # 프롬프트 재생성
            if gen_prompt:
                st.info("🤖 프롬프트 생성 중…")
                prog2 = st.progress(0)
                log = st.empty()

                def cb(name, done, total):
                    prog2.progress(done / total)
                    log.text(f"  ✅ {name}")

                generate_all(course, progress_cb=cb)
                st.success("프롬프트 생성 완료!")

            st.balloons()

        except Exception as e:
            import traceback
            if tb_id:
                update_textbook_status(tb_id, "error", str(e))
            st.error(f"❌ 오류: {e}")
            st.code(traceback.format_exc())
        finally:
            tmp_path.unlink(missing_ok=True)

# ═══════════════════════════════════════════════════════════
# 2. 교재 목록
# ═══════════════════════════════════════════════════════════
elif page == "📋 교재 목록":
    st.header("등록된 교재")

    with get_cur(dict_row=True) as cur:
        cur.execute("""
            SELECT t.id, t.course, t.title, t.file_name, t.total_pages,
                   t.status, t.error_msg, t.created_at,
                   COUNT(c.id) AS chunk_count
            FROM textbooks t
            LEFT JOIN chunks c ON c.textbook_id = t.id
            GROUP BY t.id ORDER BY t.id DESC
        """)
        rows = cur.fetchall()

    if not rows:
        st.info("등록된 교재가 없습니다.")
    else:
        for r in rows:
            status_icon = {"done": "✅", "error": "❌", "processing": "⏳", "pending": "⏸️"}.get(r["status"], "❓")
            with st.expander(f"{status_icon} [{COURSES.get(r['course'], r['course'])}] {r['title']}  (id={r['id']})"):
                col1, col2, col3 = st.columns(3)
                col1.metric("페이지", r["total_pages"] or "-")
                col2.metric("청크 수", r["chunk_count"])
                col3.metric("상태", r["status"])
                st.caption(f"파일: {r['file_name']} | 등록: {r['created_at']}")
                if r["error_msg"]:
                    st.error(r["error_msg"])

                if r["status"] == "done":
                    if st.button(f"🗑️ 삭제 (id={r['id']})", key=f"del_{r['id']}"):
                        delete_chunks_by_textbook(r["id"])
                        with get_cur() as cur:
                            cur.execute("DELETE FROM textbooks WHERE id=%s", (r["id"],))
                        st.rerun()

# ═══════════════════════════════════════════════════════════
# 3. 프롬프트 관리
# ═══════════════════════════════════════════════════════════
elif page == "🤖 프롬프트 관리":
    st.header("에이전트 시스템 프롬프트")

    col1, col2 = st.columns(2)
    course = col1.selectbox("과정", list(COURSES.keys()), format_func=COURSES.get, key="pm_course")
    agent = col2.selectbox("에이전트", list(AGENT_META.keys()), key="pm_agent")

    current = load_prompt(course, agent)

    st.subheader("현재 활성 프롬프트")
    edited = st.text_area("내용 (수정 후 저장 가능)", value=current or "", height=400)

    col_a, col_b = st.columns(2)
    if col_a.button("💾 수동 저장", type="primary"):
        if edited.strip():
            pid = save_prompt(course, agent, edited.strip())
            st.success(f"저장 완료 (id={pid})")
        else:
            st.warning("내용을 입력하세요.")

    if col_b.button("🔄 GPT-4o 로 재생성"):
        with st.spinner("생성 중…"):
            from ingest.prompt_builder import _generate, _toc
            toc = _toc(course)
            new_text = _generate(course, agent, toc)
            pid = save_prompt(course, agent, new_text)
        st.success(f"재생성 완료 (id={pid})")
        st.rerun()

    # 버전 이력
    st.subheader("버전 이력")
    with get_cur(dict_row=True) as cur:
        cur.execute(
            "SELECT id, version, is_active, created_at, LEFT(prompt_text,80) AS preview "
            "FROM agent_prompts WHERE course=%s AND agent_name=%s ORDER BY version DESC",
            (course, agent),
        )
        rows = cur.fetchall()

    for r in rows:
        active = "✅ 활성" if r["is_active"] else ""
        st.text(f"v{r['version']} {active}  |  {r['created_at']}  |  {r['preview']}…")

# ═══════════════════════════════════════════════════════════
# 4. RAG 검색 테스트
# ═══════════════════════════════════════════════════════════
elif page == "🔍 RAG 검색 테스트":
    st.header("RAG 검색 테스트")

    col1, col2 = st.columns([3, 1])
    course = col1.selectbox("과정", list(COURSES.keys()), format_func=COURSES.get, key="rag_course")
    top_k = col2.number_input("Top K", 1, 20, 5)

    query = st.text_input("검색 쿼리")
    if st.button("🔍 검색") and query:
        from ingest.embedder import search
        with st.spinner("검색 중…"):
            results = search(query, course, top_k=int(top_k))

        st.markdown(f"**{len(results)}개 결과**")
        for r in results:
            with st.expander(f"[{r['chapter']}] p.{r['page_start']}~{r['page_end']}  유사도: {r['similarity']:.3f}"):
                st.write(r["content"])
