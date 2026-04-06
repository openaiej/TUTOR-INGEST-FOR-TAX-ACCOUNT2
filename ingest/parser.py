"""PDF → 청크 분할.

전략:
  1. pdfplumber 로 페이지별 텍스트 추출
  2. 헤딩 패턴(숫자·제N장·I. 등)으로 섹션 경계 감지
  3. max_tokens 초과 섹션은 문장 단위로 재분할 + overlap
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # pymupdf

_HEADING_RE = re.compile(
    r"^(?:"
    r"\d{1,2}[.\s].{0,60}"
    r"|제\s*\d+\s*[장절편]"
    r"|[IVXLC]+\.\s"
    r"|[가나다라마바사]\.\s"
    r"|Chapter\s+\d+"
    r")",
    re.IGNORECASE,
)


def _tokens(text: str) -> int:
    """한국어 포함 대략적 토큰 추정."""
    kor = sum(1 for c in text if "\uAC00" <= c <= "\uD7A3")
    return int(kor * 0.6 + (len(text) - kor) * 0.25)


@dataclass
class Chunk:
    chapter: str
    page_start: int
    page_end: int
    content: str
    token_count: int = field(init=False)

    def __post_init__(self):
        self.token_count = _tokens(self.content)


def _split_sentences(text: str, max_tok: int, overlap: int) -> list[str]:
    sents = re.split(r"(?<=[.!?。])\s+", text)
    result, buf, cur_tok, tail = [], [], 0, []
    for s in sents:
        t = _tokens(s)
        if cur_tok + t > max_tok and buf:
            result.append((" ".join(tail + buf)).strip())
            tail = buf[-overlap:] if overlap else []
            buf, cur_tok = [], 0
        buf.append(s)
        cur_tok += t
    if buf:
        result.append((" ".join(tail + buf)).strip())
    return result


def parse_pdf(
    path: str | Path,
    max_tokens: int = 500,
    overlap: int = 2,
) -> list[Chunk]:
    path = Path(path)
    pages: list[tuple[int, str]] = []
    doc = fitz.open(str(path))
    for i, page in enumerate(doc, 1):
        try:
            text = page.get_text("text").strip()
        except Exception:
            text = ""
        pages.append((i, text))
    doc.close()

    # 섹션 감지
    sections: list[dict] = []
    cur: dict = {"title": "서문", "page_start": 1, "lines": []}
    for pg, text in pages:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if _HEADING_RE.match(line):
                if cur["lines"]:
                    sections.append({**cur, "page_end": pg - 1 or pg})
                cur = {"title": line, "page_start": pg, "lines": []}
            else:
                cur["lines"].append(line)
    if cur["lines"]:
        sections.append({**cur, "page_end": pages[-1][0] if pages else 1})

    # 섹션 → 청크
    chunks: list[Chunk] = []
    for sec in sections:
        body = "\n".join(sec["lines"]).strip()
        if not body:
            continue
        kwargs = dict(
            chapter=sec["title"],
            page_start=sec["page_start"],
            page_end=sec.get("page_end", sec["page_start"]),
        )
        if _tokens(body) <= max_tokens:
            chunks.append(Chunk(content=body, **kwargs))
        else:
            for sub in _split_sentences(body, max_tokens, overlap):
                if sub:
                    chunks.append(Chunk(content=sub, **kwargs))
    return chunks


def get_page_count(path: str | Path) -> int:
    doc = fitz.open(str(path))
    count = len(doc)
    doc.close()
    return count
