import io

import docx
import pytest

from app.conversation.rag.extract import extract_text


def _minimal_pdf(text: str) -> bytes:
    """A one-page PDF with a single text operator — keeps binary fixtures out of git."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode()
    return bytes(out)


def _docx_bytes(*paragraphs: str) -> bytes:
    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize("filename", ["notes.txt", "notes.md", "NOTES.TXT"])
def test_extract_plain_text_utf8(filename: str) -> None:
    assert extract_text("إجراءات خدمة العملاء".encode(), filename) == "إجراءات خدمة العملاء"


def test_extract_docx_paragraphs() -> None:
    data = _docx_bytes("الفقرة الأولى", "الفقرة الثانية")
    text = extract_text(data, "guide.docx")
    assert "الفقرة الأولى" in text
    assert "الفقرة الثانية" in text


def test_extract_pdf_text() -> None:
    assert "Hello KB" in extract_text(_minimal_pdf("Hello KB"), "doc.pdf")


@pytest.mark.parametrize("filename", ["malware.exe", "archive.zip", "noextension"])
def test_unsupported_extension_raises(filename: str) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        extract_text(b"data", filename)
