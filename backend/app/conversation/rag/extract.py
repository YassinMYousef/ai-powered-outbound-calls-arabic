"""Text extraction for uploaded KB documents.

Module: Conversation/RAG. Pure bytes-in/text-out — no config, no I/O beyond
parsing. Scanned or heavily formatted Arabic PDFs may extract sparsely (pypdf
has no OCR); that's accepted for now — re-export such docs as text/DOCX.
"""
import io
from pathlib import Path

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


def extract_text(data: bytes, filename: str) -> str:
    """Extract plain text from an uploaded file, keyed on its extension.

    Raises ValueError for unsupported extensions.
    """
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md"):
        return data.decode("utf-8", errors="replace")
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if ext == ".docx":
        import docx

        document = docx.Document(io.BytesIO(data))
        return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())
    raise ValueError(
        f"unsupported file type {ext or filename!r} — supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )
