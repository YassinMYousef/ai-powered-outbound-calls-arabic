"""Render the 'First Call Resolutions' report as a branded, templated PDF.

Module: Backend/Data & Reporting. Server-side generation (ReportLab) is the
portable path for Arabic: it needs no system libraries (unlike WeasyPrint's
pango/cairo). Arabic is shaped with arabic_reshaper + python-bidi and drawn with
the embedded Amiri font (OFL, app/data/assets/fonts). The layout is a reusable
template — header/logo/footer are fixed chrome; every figure and table row comes
from the FCRReport + resolved calls passed in, so the content varies per report.
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.data.models import CallLog, FCRReport

_ASSETS = Path(__file__).parent / "assets"
_FONTS = _ASSETS / "fonts"
_LOGO = _ASSETS / "logo.png"  # optional; a vector badge is drawn if absent

BRAND = colors.HexColor(0x1E40AF)
BRAND_SOFT = colors.HexColor(0x3B82F6)
INK = colors.HexColor(0x0F172A)
MUTED = colors.HexColor(0x64748B)
LINE = colors.HexColor(0xE2E8F0)
CARD_BG = colors.HexColor(0xF1F5F9)

_FONT = "Amiri"
_FONT_BOLD = "Amiri-Bold"
_fonts_ready = False


def _ensure_fonts() -> None:
    """Register the embedded Amiri faces once per process."""
    global _fonts_ready
    if _fonts_ready:
        return
    pdfmetrics.registerFont(TTFont(_FONT, str(_FONTS / "Amiri-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(_FONTS / "Amiri-Bold.ttf")))
    pdfmetrics.registerFontFamily(_FONT, normal=_FONT, bold=_FONT_BOLD)
    _fonts_ready = True


def _has_arabic(text: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in text)


def _shape(text: str) -> str:
    """Shape + reorder Arabic to visual order; leave Latin/number strings as-is."""
    text = str(text)
    return get_display(arabic_reshaper.reshape(text)) if _has_arabic(text) else text


# --- Header / footer chrome (drawn on every page) -------------------------


def _draw_logo(c, x: float, y: float, size: float) -> None:
    """The brand mark: an embedded logo.png if present, else a drawn badge."""
    if _LOGO.exists():
        c.drawImage(str(_LOGO), x, y, width=size, height=size, mask="auto", preserveAspectRatio=True)
        return
    # Vector fallback: a brand rounded square with a simple white phone glyph.
    c.setFillColor(BRAND)
    c.roundRect(x, y, size, size, size * 0.22, stroke=0, fill=1)
    c.setFillColor(colors.white)
    r = size * 0.18
    c.saveState()
    c.translate(x + size / 2, y + size / 2)
    c.rotate(-35)
    # handset: two rounded ends joined by a bar
    c.roundRect(-r * 1.7, -r * 0.5, r, r, r * 0.4, stroke=0, fill=1)
    c.roundRect(r * 0.7, -r * 0.5, r, r, r * 0.4, stroke=0, fill=1)
    c.setLineWidth(size * 0.06)
    c.setStrokeColor(colors.white)
    c.line(-r * 1.2, r * 0.1, r * 1.2, r * 0.1)
    c.restoreState()


def _page_chrome(c, doc) -> None:
    """Header (logo + wordmark + kicker) and footer (page no. + confidentiality)."""
    w, h = A4
    m = doc.leftMargin
    # Header
    badge = 12 * mm
    top = h - 14 * mm
    _draw_logo(c, m, top - badge + 3 * mm, badge)
    c.setFillColor(INK)
    c.setFont(_FONT_BOLD, 13)
    c.drawString(m + badge + 4 * mm, top - 2 * mm, "CallCenter Ops")
    c.setFillColor(MUTED)
    c.setFont(_FONT, 8.5)
    c.drawString(m + badge + 4 * mm, top - 6.5 * mm, "Quality & Reporting")
    # Right kicker (Arabic, right-aligned)
    c.setFillColor(BRAND)
    c.setFont(_FONT_BOLD, 11)
    c.drawRightString(w - m, top - 2 * mm, _shape("تقرير الجودة"))
    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.line(m, top - badge, w - m, top - badge)
    # Footer
    c.setStrokeColor(LINE)
    c.line(m, 14 * mm, w - m, 14 * mm)
    c.setFillColor(MUTED)
    c.setFont(_FONT, 8)
    c.drawString(m, 10 * mm, "Confidential — internal use only")
    c.drawCentredString(w / 2, 10 * mm, f"{doc.page}")
    c.drawRightString(w - m, 10 * mm, _shape("سرّي — للاستخدام الداخلي"))


# --- Paragraph styles -----------------------------------------------------


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title_ar": ParagraphStyle("title_ar", fontName=_FONT_BOLD, fontSize=18, leading=24, textColor=INK, alignment=TA_RIGHT),
        "subtitle": ParagraphStyle("subtitle", fontName=_FONT, fontSize=10, leading=14, textColor=MUTED, alignment=TA_LEFT),
        "h2_ar": ParagraphStyle("h2_ar", fontName=_FONT_BOLD, fontSize=12, leading=18, textColor=BRAND, alignment=TA_RIGHT),
        "cell_ar": ParagraphStyle("cell_ar", fontName=_FONT, fontSize=9, leading=13, textColor=INK, alignment=TA_RIGHT),
        "cell_num": ParagraphStyle("cell_num", fontName=_FONT, fontSize=9, leading=13, textColor=INK, alignment=TA_CENTER),
        "muted_r": ParagraphStyle("muted_r", fontName=_FONT, fontSize=9, leading=13, textColor=MUTED, alignment=TA_RIGHT),
    }


def _pct(rate: float | None) -> str:
    return "—" if rate is None else f"{rate * 100:.1f}%"


def _kpi_cards(report: FCRReport, st: dict) -> Table:
    """Four stat tiles: total calls, FCR, completion, average handle time."""
    aht = report.average_handle_time_seconds
    aht_str = "—" if aht is None else (f"{int(aht // 60)}m {int(aht % 60)}s" if aht >= 60 else f"{aht:.0f}s")
    cards = [
        (_shape("إجمالي المكالمات"), str(report.total_calls)),
        (_shape("نسبة الحل من أول محاولة"), _pct(report.fcr_rate)),
        (_shape("الإنجاز الآلي"), _pct(report.completion_rate)),
        (_shape("متوسط زمن المعالجة"), aht_str),
    ]
    label_st = ParagraphStyle("kpi_l", fontName=_FONT, fontSize=8, leading=11, textColor=MUTED, alignment=TA_CENTER)
    value_st = ParagraphStyle("kpi_v", fontName=_FONT_BOLD, fontSize=15, leading=19, textColor=INK, alignment=TA_CENTER)
    # each tile is a mini 2-row table (value on top, label below)
    tiles = [Table([[Paragraph(v, value_st)], [Paragraph(lbl, label_st)]], rowHeights=[16 * mm * 0.55, 16 * mm * 0.45]) for lbl, v in cards]
    for t in tiles:
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
    outer = Table([tiles], colWidths=[42.5 * mm] * 4)
    outer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return outer


def _cases_table(resolved: list[CallLog], st: dict) -> Table:
    """RTL table of resolved cases: columns run right→left (date is rightmost)."""
    # Headers in RTL reading order, then reversed for ReportLab's LTR columns.
    headers_rtl = [_shape("التاريخ"), _shape("رقم التذكرة"), _shape("الهاتف"), _shape("المدة (ث)")]
    header_st = ParagraphStyle("th", fontName=_FONT_BOLD, fontSize=9, leading=12, textColor=colors.white, alignment=TA_CENTER)
    rows = [[Paragraph(h, header_st) for h in reversed(headers_rtl)]]
    for call in resolved:
        date = call.created_at.date().isoformat() if call.created_at else "—"
        ticket = call.ticket_id or "—"
        phone = _mask_phone(call.customer_phone)
        dur = str(call.duration_seconds) if call.duration_seconds is not None else "—"
        cells_rtl = [
            Paragraph(_shape(date), st["cell_num"]),
            Paragraph(_shape(ticket), st["cell_num"]),
            Paragraph(_shape(phone), st["cell_num"]),
            Paragraph(_shape(dur), st["cell_num"]),
        ]
        rows.append(list(reversed(cells_rtl)))
    table = Table(rows, colWidths=[42 * mm, 55 * mm, 45 * mm, 28 * mm], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CARD_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    table.setStyle(TableStyle(style))
    return table


def _mask_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"****{digits[-4:]}" if len(digits) >= 4 else "****"


def render_fcr_pdf(report: FCRReport, resolved: list[CallLog]) -> bytes:
    """Render one FCRReport (+ its resolved calls) to PDF bytes."""
    _ensure_fonts()
    st = _styles()
    buf = io.BytesIO()

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=30 * mm, bottomMargin=20 * mm,
        title="First Call Resolutions Report", author="CallCenter Ops",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_page_chrome)])

    generated = report.created_at or datetime.utcnow()
    period = f"{report.period_start.date().isoformat()} — {report.period_end.date().isoformat()}"

    story: list = [
        Paragraph(_shape("تقرير حالات الحل من أول مكالمة"), st["title_ar"]),
        Paragraph("First Call Resolutions Report", st["subtitle"]),
        Spacer(1, 4 * mm),
    ]

    # Metadata block (label: value), RTL.
    meta_rows = [
        [Paragraph(period, st["cell_num"]), Paragraph(_shape("الفترة"), st["muted_r"])],
        [Paragraph(generated.strftime("%Y-%m-%d %H:%M"), st["cell_num"]), Paragraph(_shape("تاريخ الإصدار"), st["muted_r"])],
        [Paragraph(str(len(resolved)), st["cell_num"]), Paragraph(_shape("عدد الحالات المُنجَزة"), st["muted_r"])],
    ]
    meta = Table(meta_rows, colWidths=[120 * mm, 50 * mm], hAlign="RIGHT")
    meta.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [meta, Spacer(1, 6 * mm)]

    story += [_kpi_cards(report, st), Spacer(1, 8 * mm)]

    story += [Paragraph(_shape(f"الحالات التي تم حلها ({len(resolved)})"), st["h2_ar"]), Spacer(1, 2 * mm)]
    if resolved:
        story.append(_cases_table(resolved, st))
    else:
        story.append(Paragraph(_shape("لا توجد حالات تم حلها في هذه الفترة."), st["cell_ar"]))

    doc.build(story)
    return buf.getvalue()
