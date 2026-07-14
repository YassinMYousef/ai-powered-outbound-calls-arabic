"""Structure-aware text chunking for embedding.

Module: Conversation/RAG. Pure and tokenizer-free: sizes are in characters
(1500 chars ≈ 400–500 Arabic tokens), defaults come from settings at the call
site so this module stays dependency-free.

Oversized blocks are split along progressively finer structure — paragraphs
(blank line), lines (list items, PDF line wraps), sentences (Arabic and Latin
terminal punctuation), words — falling back to fixed character windows only
for text with no boundaries at all. Overlap seeds likewise start on a sentence
or word boundary when one exists, so chunks never open mid-word.
"""
import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?؟؛…])\s+")
_WHITESPACE = re.compile(r"\s+")

# (split pattern, join separator) from coarsest to finest structure.
_LEVELS = [
    (re.compile(r"\n\s*\n"), "\n\n"),  # paragraphs
    (re.compile(r"\n"), "\n"),  # lines
    (_SENTENCE_BOUNDARY, " "),  # sentences
    (_WHITESPACE, " "),  # words
]


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Fixed character windows — last resort for text with no boundaries."""
    step = chunk_size - overlap
    pieces = []
    for start in range(0, len(text), step):
        piece = text[start : start + chunk_size].strip()
        if piece:
            pieces.append(piece)
        if start + chunk_size >= len(text):
            break
    return pieces


def _overlap_tail(text: str, overlap: int) -> str:
    """Trailing ≤ `overlap` chars of text, trimmed forward to a sentence or
    word boundary when the raw window would open mid-sentence/mid-word."""
    if not overlap:
        return ""
    tail = text[-overlap:]
    if len(tail) == len(text) or text[-overlap - 1].isspace():
        return tail
    boundary = _SENTENCE_BOUNDARY.search(tail)
    if boundary and boundary.end() < len(tail):
        return tail[boundary.end() :]
    space = _WHITESPACE.search(tail)
    if space and space.end() < len(tail):
        return tail[space.end() :]
    return tail


def _chunk_level(text: str, level: int, chunk_size: int, overlap: int) -> list[str]:
    if level == len(_LEVELS):
        return _hard_split(text, chunk_size, overlap)
    pattern, sep = _LEVELS[level]
    parts = [p.strip() for p in pattern.split(text) if p.strip()]

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(part) > chunk_size:
            sub = _chunk_level(part, level + 1, chunk_size, overlap)
            chunks.extend(sub[:-1])
            current = sub[-1] if sub else ""
            continue
        tail = _overlap_tail(chunks[-1], overlap) if chunks else ""
        seeded = f"{tail}{sep}{part}" if tail else part
        current = seeded if len(seeded) <= chunk_size else part
    if current:
        chunks.append(current)
    return chunks


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Split text into chunks of at most chunk_size characters.

    Paragraphs (blank-line separated) are greedily packed; a block that can't
    fit is split along the finest structure that fits — lines, then sentences
    (. ! ? ؟ ؛ …), then words, then raw character windows. A chunk opened
    after a full one is seeded with the previous chunk's last `overlap`
    characters trimmed to a sentence or word boundary (dropped if seeding
    would overflow).
    """
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    return _chunk_level(text or "", 0, chunk_size, overlap)
