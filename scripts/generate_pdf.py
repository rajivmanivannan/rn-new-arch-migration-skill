#!/usr/bin/env python3
"""
generate_pdf.py — React Native New Architecture Migration Audit PDF generator
Parses MIGRATION_AUDIT_YYYYMMDD.md and produces a styled PDF.

Usage:
    python3 generate_pdf.py --input MIGRATION_AUDIT_20260320.md --output MIGRATION_AUDIT_20260320.pdf
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether, PageBreak,
    )
    from reportlab.platypus.flowables import CondPageBreak
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
except ImportError:
    print(
        "ERROR: reportlab is not installed.\n"
        "  Install it with:  pip install reportlab\n"
        "  Then re-run this script.",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Palette ───────────────────────────────────────────────────────────────────
C_BLACK     = colors.HexColor('#111827')
C_GRAY_700  = colors.HexColor('#374151')
C_GRAY_500  = colors.HexColor('#6B7280')
C_GRAY_400  = colors.HexColor('#9CA3AF')
C_GRAY_200  = colors.HexColor('#E5E7EB')
C_GRAY_100  = colors.HexColor('#F3F4F6')
C_GRAY_50   = colors.HexColor('#F9FAFB')
C_RED_800   = colors.HexColor('#991B1B')
C_RED_100   = colors.HexColor('#FEE2E2')
C_AMBER_800 = colors.HexColor('#92400E')
C_AMBER_100 = colors.HexColor('#FEF3C7')
C_GREEN_800 = colors.HexColor('#166534')
C_GREEN_100 = colors.HexColor('#DCFCE7')
C_BLUE_700  = colors.HexColor('#1D4ED8')
C_BLUE_50   = colors.HexColor('#EFF6FF')
C_WHITE     = colors.white

PAGE_W, PAGE_H = A4          # 595 × 842 pt
ML  = 20 * mm                # left margin
MR  = 20 * mm                # right margin
MT  = 18 * mm                # top margin
MB  = 18 * mm                # bottom margin
CW  = PAGE_W - ML - MR      # content width ≈ 481 pt


# ── Markdown → ReportLab XML ─────────────────────────────────────────────────
# Emoji that Helvetica (WinAnsiEncoding) cannot render — map to ASCII labels.
_EMOJI_MAP = [
    ('\u26A0\uFE0F', '[!]'), ('\u26A0', '[!]'),   # ⚠️  ⚠
    ('\u2705', '[OK]'),                             # ✅
    ('\u2714\uFE0F', '[OK]'), ('\u2714', '[OK]'),  # ✔️  ✔
    ('\u274C', '[X]'),                              # ❌
    ('\u274E', '[X]'),                              # ❎
    ('\u2753', '[?]'),                              # ❓
    ('\U0001F195', '[NEW]'),                        # 🆕
    ('\u23F3', '[...]'),                            # ⏳
    ('\uFE0F', ''),                                 # variation selector — silently strip
]


def md2rl(text):
    # Strip emoji before XML-escaping so they don't become garbled squares.
    for emoji, repl in _EMOJI_MAP:
        text = text.replace(emoji, repl)
    # Strip any remaining 4-byte (surrogate-plane) chars Helvetica can't handle.
    text = re.sub(r'[\U00010000-\U0010FFFF]', '', text)
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]+)`',
                  r'<font name="Courier" color="#1D4ED8">\1</font>', text)
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
    # Markdown links [label](url) → clickable blue hyperlink.
    text = re.sub(
        r'\[([^\]]+)\]\((https?://[^\)]+)\)',
        r'<a href="\2" color="#1D4ED8">\1</a>',
        text,
    )
    # Bare URLs not already inside an <a> tag → clickable, scheme stripped for display.
    def _linkify(m):
        url = m.group(0)
        display = re.sub(r'^https?://', '', url)
        return f'<a href="{url}" color="#1D4ED8">{display}</a>'
    text = re.sub(r'(?<!href=")(https?://[^\s<>\])"]+)', _linkify, text)
    return text.strip()


# ── Style factory ─────────────────────────────────────────────────────────────
def S(name, **kw):
    d = dict(fontName='Helvetica', fontSize=10, textColor=C_GRAY_700, leading=14)
    d.update(kw)
    return ParagraphStyle(name, **d)


def make_styles():
    return {
        # Cover
        'eyebrow':      S('eyebrow', fontName='Helvetica-Bold', fontSize=7.5,
                          textColor=C_GRAY_400, leading=10,
                          letterSpacing=1.6),
        'cover_title':  S('cover_title', fontName='Helvetica-Bold', fontSize=22,
                          textColor=C_BLUE_700, leading=28, letterSpacing=-0.5),
        'meta_label':   S('meta_label', fontName='Helvetica-Bold', fontSize=7,
                          textColor=C_GRAY_400, leading=9, letterSpacing=0.8),
        'meta_value':   S('meta_value', fontName='Helvetica-Bold', fontSize=12,
                          textColor=C_BLACK, leading=15),
        # TOC
        'toc_label':    S('toc_label', fontName='Helvetica-Bold', fontSize=7,
                          textColor=C_GRAY_400, leading=9, letterSpacing=1.0),
        'toc_num':      S('toc_num', fontName='Helvetica-Bold', fontSize=8,
                          textColor=C_GRAY_500, leading=10, alignment=TA_CENTER),
        'toc_item':     S('toc_item', fontSize=10.5, textColor=C_GRAY_700, leading=13),
        'toc_page':     S('toc_page', fontName='Helvetica-Bold', fontSize=8,
                          textColor=C_GRAY_400, leading=10, alignment=TA_RIGHT),
        # Section
        'section_title': S('section_title', fontName='Helvetica-Bold', fontSize=13,
                           textColor=C_BLUE_700, leading=16, letterSpacing=-0.2),
        # Tables
        'th':           S('th', fontName='Helvetica-Bold', fontSize=7.5,
                          textColor=C_GRAY_500, leading=10, letterSpacing=0.6),
        'td':           S('td', fontSize=9.5, textColor=C_GRAY_700, leading=13),
        'td_pkg':       S('td_pkg', fontName='Courier', fontSize=8,
                          textColor=C_BLUE_700, leading=11),
        'td_code':      S('td_code', fontName='Courier', fontSize=8,
                          textColor=C_GRAY_700, leading=11),
        # Smaller Courier for the Pattern column where identifiers can be very long.
        'td_pattern':   S('td_pattern', fontName='Courier', fontSize=7,
                          textColor=C_GRAY_700, leading=10),
        'td_bold':      S('td_bold', fontName='Helvetica-Bold', fontSize=9.5,
                          textColor=C_BLACK, leading=13),
        'td_right':     S('td_right', fontSize=9.5, textColor=C_GRAY_700,
                          leading=13, alignment=TA_RIGHT),
        # Status badges
        'badge_block':  S('badge_block', fontName='Helvetica-Bold', fontSize=7.5,
                          textColor=C_RED_800, leading=10),
        'badge_interop':S('badge_interop', fontName='Helvetica-Bold', fontSize=7.5,
                          textColor=C_AMBER_800, leading=10),
        'badge_ok':     S('badge_ok', fontName='Helvetica-Bold', fontSize=7.5,
                          textColor=C_GREEN_800, leading=10),
        'badge_unk':    S('badge_unk', fontName='Helvetica-Bold', fontSize=7.5,
                          textColor=C_GRAY_500, leading=10),
        # Tag pill
        'tag_pill':     S('tag_pill', fontName='Courier-Bold', fontSize=7,
                          textColor=C_BLUE_700, leading=9),
        # Exec / notes
        'exec_body':    S('exec_body', fontName='Helvetica', fontSize=11,
                          textColor=C_GRAY_700, leading=18),
        'note':         S('note', fontName='Helvetica', fontSize=9.5,
                          textColor=C_GRAY_500, leading=14),
        # Metric cards
        'metric_num':   S('metric_num', fontName='Helvetica-Bold', fontSize=30,
                          leading=34),
        'metric_lbl':   S('metric_lbl', fontName='Helvetica-Bold', fontSize=7.5,
                          textColor=C_GRAY_500, leading=10, letterSpacing=0.6),
        # Scan coverage
        'scan_num':     S('scan_num', fontName='Helvetica-Bold', fontSize=20,
                          textColor=C_BLACK, leading=24, alignment=TA_CENTER),
        'scan_lbl':     S('scan_lbl', fontName='Helvetica-Bold', fontSize=7,
                          textColor=C_GRAY_400, leading=9, alignment=TA_CENTER,
                          letterSpacing=0.5),
        # Action plan
        'phase_label':  S('phase_label', fontName='Helvetica-Bold', fontSize=8,
                          textColor=C_WHITE, leading=10, letterSpacing=1.0),
        'step_num':     S('step_num', fontName='Helvetica-Bold', fontSize=9,
                          textColor=C_GRAY_700, leading=11, alignment=TA_CENTER),
        'step_title':   S('step_title', fontName='Helvetica-Bold', fontSize=10.5,
                          textColor=C_BLACK, leading=14),
        'step_desc':    S('step_desc', fontSize=9.5, textColor=C_GRAY_500, leading=14),
        # Effort estimate
        'effort_range': S('effort_range', fontName='Helvetica-Bold', fontSize=28,
                          leading=32),
        'effort_label_style': S('effort_label_style', fontName='Helvetica-Bold', fontSize=8,
                          leading=10, letterSpacing=1.2),
        'effort_desc':  S('effort_desc', fontSize=11, textColor=C_GRAY_700, leading=18),
        # Footer
        'footer':       S('footer', fontSize=7, textColor=C_GRAY_400, leading=9),
    }


# ── Page footer (drawn on canvas, not as flowable) ────────────────────────────
def on_page(canvas, doc, project, audit_date):
    canvas.saveState()
    y = MB - 6 * mm
    canvas.setStrokeColor(C_GRAY_200)
    canvas.setLineWidth(0.5)
    canvas.line(ML, y + 5 * mm, PAGE_W - MR, y + 5 * mm)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(C_GRAY_400)
    left = f'React Native New Architecture Migration Audit  ·  {project}  ·  {audit_date}'
    canvas.drawString(ML, y, left)
    canvas.drawRightString(PAGE_W - MR, y, f'Page {doc.page}')
    canvas.restoreState()


# ── Layout helpers ────────────────────────────────────────────────────────────

def section_header(num_text, title, ST):
    """Black filled badge + bold title."""
    badge = Paragraph(
        f'<font color="#FFFFFF"><b>{num_text}</b></font>',
        S('_sn', fontName='Helvetica-Bold', fontSize=10,
          textColor=C_WHITE, leading=12, alignment=TA_CENTER),
    )
    badge_tbl = Table([[badge]], colWidths=[22])
    badge_tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), C_BLUE_700),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('LEFTPADDING',  (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROUNDEDCORNERS', [4]),
    ]))
    title_p = Paragraph(title, ST['section_title'])
    row = Table([[badge_tbl, title_p]], colWidths=[30, CW - 30])
    row.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    return row


def group_bar(label_text, kind):
    """Colored full-width bar above a table group (like the HTML .table-group-header)."""
    palettes = {
        'block':  (C_RED_100,   C_RED_800,   colors.HexColor('#FECACA')),
        'interop':(C_AMBER_100, C_AMBER_800, colors.HexColor('#FDE68A')),
        'ok':     (C_GREEN_100, C_GREEN_800, colors.HexColor('#BBF7D0')),
        'unk':    (C_GRAY_100,  C_GRAY_500,  C_GRAY_200),
    }
    bg, fg, border = palettes.get(kind, palettes['unk'])
    icons = {'block': 'BLOCKED', 'interop': 'INTEROP-OK', 'ok': 'COMPATIBLE', 'unk': 'UNKNOWN'}
    icon = icons.get(kind, '')
    # Strip any leading converted-emoji token ([!], [X], [OK], [?]) that md2rl
    # may have introduced from the original markdown section heading so the
    # status indicator doesn't appear twice (once as icon, once in label text).
    label_clean = re.sub(r'^\[(?:!|X|OK|\?|NEW|\.\.\.)\]\s*', '', md2rl(label_text))
    # Also strip the redundant status keyword that mirrors the icon label so
    # the bar reads "INTEROP-OK  16 libraries" not "INTEROP-OK  Interop-OK — 16 libraries".
    _status_words = {'block': 'Blocking', 'interop': 'Interop-OK',
                     'ok': 'Compatible', 'unk': 'Unknown'}
    _sw = _status_words.get(kind, '')
    if _sw and label_clean.lower().startswith(_sw.lower()):
        label_clean = label_clean[len(_sw):].lstrip(' \u2014-').strip()
    p = Paragraph(f'<b>{icon}  {label_clean}</b>',
                  S('_gb', fontName='Helvetica-Bold', fontSize=8,
                    textColor=fg, leading=11))
    tbl = Table([[p]], colWidths=[CW])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), bg),
        ('BOX',          (0, 0), (-1, -1), 0.5, border),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
    ]))
    return tbl


def data_table(headers, rows, col_widths, ST):
    """Ruled table with grey header row, alternating body rows."""
    hrow = [Paragraph(h.upper(), ST['th']) for h in headers]
    data = [hrow] + rows
    cmds = [
        # Header
        ('BACKGROUND',    (0, 0), (-1, 0),  C_GRAY_100),
        ('LINEBELOW',     (0, 0), (-1, 0),  0.75, C_GRAY_200),
        # Body grid
        ('LINEBELOW',     (0, 1), (-1, -1), 0.3, C_GRAY_100),
        # Outer box
        ('BOX',           (0, 0), (-1, -1), 0.5, C_GRAY_200),
        # Padding
        ('LEFTPADDING',   (0, 0), (-1, -1), 9),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 9),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
    ]
    # Zebra stripe body
    for i in range(2, len(data), 2):
        cmds.append(('BACKGROUND', (0, i), (-1, i), C_GRAY_50))
    tbl = Table(data, colWidths=col_widths, repeatRows=1,
                splitByRow=True, hAlign='LEFT')
    tbl.setStyle(TableStyle(cmds))
    return tbl


def status_badge(text, ST):
    t = text.lower()
    if 'block' in t:   style = ST['badge_block']
    elif 'interop' in t: style = ST['badge_interop']
    elif 'compat' in t:  style = ST['badge_ok']
    else:                style = ST['badge_unk']
    return Paragraph(md2rl(text), style)


def tag_cell(text, ST):
    """Monospace blue tag in a light-blue-background cell."""
    return Paragraph(
        f'<font name="Courier-Bold" color="#1D4ED8">{md2rl(text)}</font>',
        ST['tag_pill'],
    )


def priority_cell(text, ST):
    t = text.lower()
    if 'block' in t:
        return Paragraph(f'<b>{md2rl(text)}</b>',
                         S('_pb', fontName='Helvetica-Bold', fontSize=8,
                           textColor=C_RED_800, leading=10))
    return Paragraph(f'<b>{md2rl(text)}</b>',
                     S('_pi', fontName='Helvetica-Bold', fontSize=8,
                       textColor=C_AMBER_800, leading=10))


def exec_box(texts, ST):
    """Exec summary with left accent bar. Accepts a string or list of strings."""
    if isinstance(texts, str):
        texts = [texts]
    parts = [md2rl(t) for t in texts if t.strip()]
    if not parts:
        return Spacer(1, 1)
    # Join paragraphs with a double line-break so each blockquote reads as its own block.
    content = '<br/><br/>'.join(parts)
    tbl = Table([[Paragraph(content, ST['exec_body'])]], colWidths=[CW])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), C_GRAY_50),
        ('LINEBEFORE',   (0, 0), (0, -1),  3, C_GRAY_400),
        ('LEFTPADDING',  (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING',   (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 12),
    ]))
    return tbl


def callout_box(items, ST):
    """Bottom callout with bold-key: plain-text lines."""
    lines = []
    for key, val in items:
        lines.append(f'<b>{md2rl(key)}:</b> {md2rl(val)}')
    p = Paragraph('<br/>'.join(lines), ST['note'])
    tbl = Table([[p]], colWidths=[CW])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), C_GRAY_50),
        ('BOX',          (0, 0), (-1, -1), 0.5, C_GRAY_200),
        ('LEFTPADDING',  (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING',   (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 10),
    ]))
    return tbl


def metric_cards(data_items, ST, col_weights=None):
    """Row of metric cards: (number_str, label, color_hex).

    col_weights — optional list of relative widths (default: equal).
    Pass a larger weight for the first card to give a long string like
    '~8–13 days' enough room to render at the same font size as short
    numbers on the other cards.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    n = len(data_items)
    if col_weights is None:
        col_weights = [1] * n
    total_w = sum(col_weights)
    # Outer column widths (include the 3pt gutter on each side)
    outer_cws = [CW * w / total_w for w in col_weights]
    # Inner card widths = outer minus gutter (3pt each side)
    inner_cws = [w - 6 for w in outer_cws]

    cards = []
    for i, (num, lbl, col) in enumerate(data_items):
        card_w  = inner_cws[i]
        inner_w = card_w - 28   # subtract 14pt padding each side
        # Auto-scale so the value always fits on one line.
        fs = 30
        while stringWidth(num, 'Helvetica-Bold', fs) > inner_w and fs > 14:
            fs -= 1
        num_p = Paragraph(num,
                          S('_mn', fontName='Helvetica-Bold', fontSize=fs,
                            textColor=col, leading=fs + 4))
        lbl_p = Paragraph(lbl.upper(), ST['metric_lbl'])
        inner = Table([[num_p], [lbl_p]], colWidths=[card_w])
        inner.setStyle(TableStyle([
            ('LEFTPADDING',  (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING',   (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 2),
        ]))
        cell = Table([[inner]], colWidths=[card_w])
        cell.setStyle(TableStyle([
            ('BOX',          (0, 0), (-1, -1), 0.5, C_GRAY_200),
            ('BACKGROUND',   (0, 0), (-1, -1), C_GRAY_50),
            ('LEFTPADDING',  (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
            ('TOPPADDING',   (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 12),
        ]))
        cards.append(cell)
    outer = Table([cards], colWidths=outer_cws)
    outer.setStyle(TableStyle([
        ('LEFTPADDING',  (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    return outer


def phase_bar(title, phase_index, ST):
    """Coloured phase label bar (PHASE 1 — UNBLOCK …)."""
    phase_colors = [
        colors.HexColor('#991B1B'),   # Phase 1 — red
        colors.HexColor('#166534'),   # Phase 2 — green
        colors.HexColor('#92400E'),   # Phase 3 — amber
        colors.HexColor('#1E40AF'),   # Phase 4 — blue
    ]
    bg = phase_colors[phase_index % len(phase_colors)]
    # Strip ALL inline formatting from md2rl (font tags, colors, Courier) —
    # phase bars must be uniform white bold text on a dark background.
    # Note: .upper() converts <font> to <FONT>, so use re.IGNORECASE.
    bar_text = md2rl(title).upper()
    bar_text = re.sub(r'<font[^>]*>', '', bar_text, flags=re.IGNORECASE)
    bar_text = re.sub(r'</font>', '', bar_text, flags=re.IGNORECASE)
    p = Paragraph(
        f'<font color="#FFFFFF"><b>{bar_text}</b></font>',
        ST['phase_label'],
    )
    tbl = Table([[p]], colWidths=[CW])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), bg),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('ROUNDEDCORNERS', [4]),
    ]))
    return tbl


def step_card(num, title, desc, ST):
    """Individual bordered step card: circle-num | bold title + desc."""
    num_p = Paragraph(f'<b>{num}</b>', ST['step_num'])
    num_cell = Table([[num_p]], colWidths=[24])
    num_cell.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), C_GRAY_100),
        ('TOPPADDING',   (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ('LEFTPADDING',  (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    title_p = Paragraph(f'<b>{md2rl(title)}</b>', ST['step_title'])
    content = [title_p]
    if desc.strip():
        content.append(Paragraph(md2rl(desc), ST['step_desc']))
    # Stack title + desc in a nested table.
    # splitByRow=False makes the card atomic so KeepTogether can reliably
    # keep a phase bar together with its first step for any dynamic content.
    desc_rows = [[item] for item in content]
    text_tbl = Table(desc_rows, colWidths=[CW - 46], splitByRow=False)
    text_tbl.setStyle(TableStyle([
        ('TOPPADDING',   (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 1),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    card = Table([[num_cell, text_tbl]], colWidths=[34, CW - 34])
    card.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 0.5, C_GRAY_200),
        ('BACKGROUND',   (0, 0), (-1, -1), C_GRAY_50),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING',   (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 9),
    ]))
    return card


# ── Markdown parsers ──────────────────────────────────────────────────────────

def parse_md(md_text):
    meta, body = {}, md_text
    cm = re.search(r'<!--\s*PDF_META\s*\n(.*?)\n\s*-->', md_text, re.DOTALL)
    if cm:
        yaml_src = cm.group(1).strip()
        meta = _simple_yaml(yaml_src)
        if HAS_YAML:
            try: meta = yaml.safe_load(yaml_src) or {}
            except: pass
        body = md_text[:cm.start()].strip()
        return meta, body
    if md_text.startswith('---'):
        end = md_text.find('\n---', 3)
        if end != -1:
            yaml_src = md_text[3:end].strip()
            meta = _simple_yaml(yaml_src)
            if HAS_YAML:
                try: meta = yaml.safe_load(yaml_src) or {}
                except: pass
            body = md_text[end + 4:].strip()
    return meta, body


def _simple_yaml(src):
    out = {}
    for line in src.splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def get_section(body, heading):
    """Extract section content by heading text. Ignores leading section numbers.
    e.g. get_section(body, 'Dependency Audit') matches '## 2. Dependency Audit'
    """
    # First try exact match (with number prefix)
    m = re.search(rf'##\s+{re.escape(heading)}(.*?)(?=\n##\s|\Z)', body, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Try matching by heading text only (ignoring any "N. " prefix)
    # Escape the heading but strip any leading "N. " from the search pattern too
    bare_heading = re.sub(r'^\d+\.\s*', '', heading)
    m = re.search(rf'##\s+\d*\.?\s*{re.escape(bare_heading)}(.*?)(?=\n##\s|\Z)', body, re.DOTALL)
    return m.group(1).strip() if m else ''


def parse_md_table(text):
    lines = [l.strip() for l in text.splitlines() if l.strip().startswith('|')]
    if len(lines) < 3:
        return [], []
    headers = [c.strip() for c in lines[0].split('|')[1:-1]]
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if cells:
            rows.append(cells)
    return headers, rows


def parse_exec(body):
    """Return a list of paragraph strings from the Executive Summary section.
    Each blockquote (> ...) becomes its own paragraph; blank lines are paragraph breaks.
    """
    sec = get_section(body, 'Executive Summary')
    paragraphs = []
    current = []
    for raw in sec.splitlines():
        l = raw.strip()
        if not l or l.startswith('|') or l.startswith('#') or l == '---':
            # Blank / structural line — flush current paragraph
            if current:
                paragraphs.append(' '.join(current))
                current = []
        else:
            l = re.sub(r'^>\s*', '', l)  # strip Markdown blockquote prefix
            if l:
                current.append(l)
    if current:
        paragraphs.append(' '.join(current))
    return paragraphs


def parse_dep_groups(body):
    sec = get_section(body, 'Dependency Audit')
    groups = []
    parts = re.split(r'\n###\s+', '\n' + sec)
    for part in parts[1:]:
        heading, _, rest = part.partition('\n')
        heading = heading.strip()
        h_lower = heading.lower()
        kind = ('block'   if 'block'   in h_lower else
                'interop' if 'interop' in h_lower else
                'ok'      if 'compat'  in h_lower else 'unk')
        for m in re.finditer(r'(\|[^\n]+\n(?:\|[-: |]+\n)(?:\|[^\n]+\n?)*)', rest):
            headers, rows = parse_md_table(m.group(1))
            if rows:
                groups.append((heading, kind, headers, rows))
            break
    return groups


def parse_findings(body, section_key):
    sec = get_section(body, section_key)
    # Fallback: try "Audit" if "Findings" not found, and vice versa
    if not sec:
        alt_key = section_key.replace('Findings', 'Audit') if 'Findings' in section_key else section_key.replace('Audit', 'Findings')
        sec = get_section(body, alt_key)
    results = []
    parts = re.split(r'\n###\s+', '\n' + sec)
    for part in parts[1:]:
        heading, _, rest = part.partition('\n')
        heading = heading.strip()
        kind = 'block' if 'block' in heading.lower() else 'warn'
        for m in re.finditer(r'(\|[^\n]+\n(?:\|[-: |]+\n)(?:\|[^\n]+\n?)*)', rest):
            headers, rows = parse_md_table(m.group(1))
            if rows:
                results.append((heading, kind, headers, rows))
            break
    if not results:
        for m in re.finditer(r'(\|[^\n]+\n(?:\|[-: |]+\n)(?:\|[^\n]+\n?)*)', sec):
            headers, rows = parse_md_table(m.group(1))
            if rows:
                results.append(('', 'block', headers, rows))
            break
    return results


def parse_action_plan(body):
    sec = get_section(body, 'Prioritized Action Plan')
    phases = []
    for pm in re.finditer(r'###\s+(Phase[^\n]*)\n(.*?)(?=###\s+Phase|\Z)',
                          sec, re.DOTALL):
        title   = pm.group(1).strip()
        content = pm.group(2).strip()
        steps   = []
        for sm in re.finditer(r'\d+\.\s+\*\*([^*\n]+)\*\*\s*\n\s+([^\n]+)', content):
            steps.append((sm.group(1).strip(), sm.group(2).strip()))
        if not steps:
            for sm in re.finditer(r'\d+\.\s+([^\n]+)(?:\n\s{3,}([^\n]+))?', content):
                steps.append((sm.group(1).strip(), (sm.group(2) or '').strip()))
        phases.append((title, steps))
    return phases


def parse_effort_table(body):
    """Parse any table in section 6 (Effort Estimate) for optional breakdown display."""
    sec = get_section(body, 'Effort Estimate')
    if not sec:
        sec = get_section(body, 'Migration Effort Score')  # backward compat
    for m in re.finditer(r'(\|[^\n]+\n(?:\|[-: |]+\n)(?:\|[^\n]+\n?)*)', sec):
        h, r = parse_md_table(m.group(1))
        if r:
            return h, r
    return [], []


def parse_effort_notes(body):
    sec = get_section(body, 'Effort Estimate')
    if not sec:
        sec = get_section(body, 'Migration Effort Score')  # backward compat
    notes = []
    for m in re.finditer(r'>\s*\*\*([^*]+)\*\*:?\s*(.+)', sec):
        notes.append((m.group(1).strip(), m.group(2).strip()))
    return notes


# ── Main build ────────────────────────────────────────────────────────────────

def build_pdf(meta, body, out_path):
    ST = make_styles()

    # ── Extract metadata ──────────────────────────────────────────────────────
    project   = str(meta.get('project',               'Unknown Project'))
    rn_ver    = str(meta.get('rn_version',             '?'))
    eligible  = str(meta.get('rn_eligible',            'true')).lower() not in ('false', '0', 'no')
    hermes    = str(meta.get('hermes',                 'Unknown'))
    new_arch  = str(meta.get('new_arch_enabled',       'false')).lower() in ('true', '1', 'yes', 'enabled')
    # Two-tier effort — fall back to legacy single-tier fields for older reports
    t1_effort = str(meta.get('tier1_effort', meta.get('effort_range', '?')))
    t1_label  = str(meta.get('tier1_label',  meta.get('effort_label', '?')))
    t2_effort = str(meta.get('tier2_effort', ''))
    t2_label  = str(meta.get('tier2_label',  ''))
    # Legacy compat
    effort_range = t1_effort
    effort_label = t1_label
    adt       = str(meta.get('audit_date',             datetime.today().strftime('%Y-%m-%d')))
    js_f      = str(meta.get('js_files_scanned',       '?'))
    ios_f     = str(meta.get('ios_files_scanned',      '?'))
    and_f     = str(meta.get('android_files_scanned',  '?'))
    deps_n    = str(meta.get('deps_audited',           '?'))
    blk_c     = str(meta.get('true_blockers', meta.get('blocking_count', '0')))
    int_c     = str(meta.get('interop_count',          '?'))
    cmp_c     = str(meta.get('compatible_count',       '?'))
    unk_c     = str(meta.get('unknown_count',          '?'))

    rn_label   = f'{rn_ver} — {"Eligible" if eligible else "Upgrade required"}'
    arch_label = 'Enabled' if new_arch else 'Disabled'
    effort_color = (C_RED_800   if effort_label in ('High', 'Very High') else
                    C_AMBER_800 if effort_label == 'Moderate' else C_GREEN_800)

    # ── Document ──────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB + 10 * mm,
        title=f'RN New Arch Audit — {project}',
    )

    def _on_page(c, d): on_page(c, d, project, adt)

    story = []
    SP = lambda n: Spacer(1, n * mm)

    # ════════════════════════════════════════════════════════════════
    # PAGE 1 — COVER
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph('MIGRATION AUDIT REPORT', ST['eyebrow']))
    story.append(SP(2))
    story.append(Paragraph('React Native \u00b7 New Architecture Migration Audit Report',
                           ST['cover_title']))
    story.append(SP(5))

    # 2-row × 4-col meta grid
    def meta_cell(label, value, val_color=C_BLACK):
        return Table([
            [Paragraph(label, ST['meta_label'])],
            [Paragraph(value, S('_mv', fontName='Helvetica-Bold', fontSize=12,
                                textColor=val_color, leading=15))],
        ], colWidths=[CW / 4 - 2])

    hermes_color  = C_GREEN_800 if hermes.lower() == 'enabled' else C_GRAY_500
    rn_color      = C_GREEN_800 if eligible else C_AMBER_800
    arch_color    = C_GREEN_800 if new_arch else C_RED_800

    row1 = [meta_cell('PROJECT',     project,   C_BLACK),
            meta_cell('AUDIT DATE',  adt,       C_GRAY_700),
            meta_cell('RN VERSION',  rn_label,  rn_color),
            meta_cell('HERMES',      hermes,    hermes_color)]
    row2 = [meta_cell('NEW ARCH',    arch_label,               arch_color),
            meta_cell('EFFORT', f'{effort_range} · {effort_label}', effort_color),
            meta_cell('BLOCKING LIBS', blk_c,   C_RED_800 if blk_c not in ('0', '?') else C_GREEN_800),
            meta_cell('COMPATIBLE',  cmp_c,     C_GREEN_800)]

    meta_grid = Table([row1, row2], colWidths=[CW / 4] * 4)
    meta_grid.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 0.5, C_GRAY_200),
        ('INNERGRID',    (0, 0), (-1, -1), 0.5, C_GRAY_200),
        ('LEFTPADDING',  (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING',   (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 10),
        ('BACKGROUND',   (0, 0), (-1, -1), C_WHITE),
    ]))
    story.append(meta_grid)
    story.append(SP(6))
    story.append(HRFlowable(width=CW, thickness=0.75, color=C_GRAY_200))
    story.append(SP(6))

    # TOC
    story.append(Paragraph('CONTENTS', ST['toc_label']))
    story.append(SP(3))

    toc_entries = [
        ('1', 'Dependency Audit',          '2'),
        ('2', 'JS / TS Source Findings',   '3'),
        ('3', 'iOS Native Findings',       '3'),
        ('4', 'Android Native Findings',   '4'),
        ('5', 'Prioritized Action Plan',   '5'),
        ('6', 'Effort Estimate',           '6'),
    ]
    toc_rows = []
    for num, label, pg in toc_entries:
        num_p   = Paragraph(f'<b>{num}</b>', ST['toc_num'])
        num_tbl = Table([[num_p]], colWidths=[20])
        num_tbl.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, -1), C_GRAY_100),
            ('TOPPADDING',   (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
            ('LEFTPADDING',  (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        label_p = Paragraph(label, ST['toc_item'])
        pg_p    = Paragraph(pg,    ST['toc_page'])
        toc_rows.append([num_tbl, label_p, pg_p])

    toc_tbl = Table(toc_rows, colWidths=[28, CW - 60, 32])
    toc_tbl.setStyle(TableStyle([
        ('LINEBELOW',    (0, 0), (-1, -2), 0.4, C_GRAY_100),
        ('TOPPADDING',   (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(toc_tbl)
    story.append(SP(6))
    story.append(HRFlowable(width=CW, thickness=0.5, color=C_GRAY_200))
    story.append(SP(6))

    # ── Executive Summary — on Page 1, below TOC ──────────────────
    story.append(Paragraph('EXECUTIVE SUMMARY', ST['toc_label']))
    story.append(SP(3))

    card_data = [
        (effort_range, 'Effort Estimate', effort_color),
        (cmp_c,        'Compatible Libs', C_GREEN_800),
        (int_c,        'Interop-OK',      C_AMBER_800),
        (blk_c,        'Blocking Libs',   C_RED_800),
    ]
    # Give the effort card extra width so "~8–13 days" renders at the same
    # large font size as the single-number cards beside it.
    story.append(metric_cards(card_data, ST, col_weights=[1.6, 0.8, 0.8, 0.8]))
    story.append(SP(3))

    exec_text = parse_exec(body)
    if exec_text:
        story.append(exec_box(exec_text, ST))

    # ════════════════════════════════════════════════════════════════
    # PAGE 3 — DEPENDENCY AUDIT
    # ════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(section_header('1', 'Dependency Audit', ST))
    story.append(SP(4))

    dep_groups = parse_dep_groups(body)

    for label, kind, headers, rows in dep_groups:
        # Detect the 3-equal-package-name grid used by the Compatible section.
        # That table has three columns all labelled "Package" — it must NOT be
        # treated as Package | Version | Notes (Version col is only 12% wide).
        is_pkg_grid = (
            len(headers) == 3
            and all(h.strip().lower() == 'package' for h in headers)
        )

        if is_pkg_grid:
            # Render as three equal-width package columns.
            # Use td_pattern (7pt Courier) so long scoped names fit on fewer lines.
            pkg_cw   = [CW / 3] * 3
            rendered = []
            for row in rows:
                rendered.append([
                    Paragraph(md2rl((row + ['', '', ''])[i]), ST['td_pattern'])
                    for i in range(3)
                ])
            col_headers = ['Package', 'Package', 'Package']
        else:
            # Standard: Package | Version | Notes
            pkg_cw   = [CW * 0.38, CW * 0.12, CW * 0.50]
            rendered = []
            for row in rows:
                pkg   = row[0] if len(row) > 0 else ''
                ver   = row[1] if len(row) > 1 else ''
                # Skip the Status column (index 2) — conveyed by group bar colour
                notes = row[3] if len(row) > 3 else (row[2] if len(row) > 2 else '')
                rendered.append([
                    Paragraph(md2rl(pkg),   ST['td_pkg']),
                    Paragraph(md2rl(ver),   ST['td']),
                    Paragraph(md2rl(notes), ST['td']),
                ])
            col_headers = ['Package', 'Version', 'Notes']

        block = KeepTogether([
            group_bar(label, kind),
            data_table(col_headers, rendered, pkg_cw, ST),
        ])
        story.append(block)
        story.append(SP(3))

    # ════════════════════════════════════════════════════════════════
    # PAGE 4 — JS/TS SOURCE FINDINGS
    # ════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(section_header('2', 'JS / TS Source Findings', ST))
    story.append(SP(4))

    # Findings column layout: File | Lines | Pattern | Tag | Owner | Priority
    # The Lines column is optional — iOS/Android tables omit it in the markdown.
    # We detect this from the parsed headers and insert an empty placeholder so
    # the pattern content always lands in the wide Pattern column, not Lines.
    # File=20%, Ln=7%, Pattern=28%, Tag=12%, Owner=18%, Priority=15%
    # Owner and Priority get more room so values like "In-house / Vendor" and "BLOCKING" don't squeeze.
    findings_cw = [CW * 0.20, CW * 0.07, CW * 0.28, CW * 0.12, CW * 0.18, CW * 0.15]

    def _render_findings_rows(rows, headers, ST):
        has_lines = any('line' in h.lower() for h in headers)
        rendered = []
        for row in rows:
            if has_lines:
                file_c = row[0] if len(row) > 0 else ''
                line_c = row[1] if len(row) > 1 else ''
                pat_c  = row[2] if len(row) > 2 else ''
                tag_c  = row[3] if len(row) > 3 else ''
                own_c  = row[4] if len(row) > 4 else 'In-house'
                pri_c  = row[5] if len(row) > 5 else own_c
            else:
                # No Lines column — shift pattern/tag/owner/priority left by one.
                file_c = row[0] if len(row) > 0 else ''
                line_c = ''
                pat_c  = row[1] if len(row) > 1 else ''
                tag_c  = row[2] if len(row) > 2 else ''
                own_c  = row[3] if len(row) > 3 else 'In-house'
                pri_c  = row[4] if len(row) > 4 else own_c
            # If owner cell contains a severity label, it was the last column.
            if own_c.lower() in ('blocking', 'interop-ok', 'interop'):
                pri_c, own_c = own_c, 'In-house'
            rendered.append([
                Paragraph(md2rl(file_c), ST['td_code']),
                Paragraph(md2rl(line_c), ST['td']),
                Paragraph(md2rl(pat_c),  ST['td_pattern']),
                tag_cell(tag_c, ST),
                Paragraph(md2rl(own_c),  ST['td_bold'] if 'in-house' in own_c.lower() else ST['td']),
                priority_cell(pri_c, ST),
            ])
        return rendered

    for heading, kind, headers, rows in parse_findings(body, 'JS/TS Source Findings'):
        rendered = _render_findings_rows(rows, headers, ST)
        if heading:
            story.append(group_bar(heading, kind))
        story.append(data_table(
            ['File', 'Ln', 'Pattern', 'Tag', 'Owner', 'Priority'],
            rendered, findings_cw, ST,
        ))
        story.append(SP(3))

    story.append(SP(2))
    story.append(section_header('3', 'iOS Native Findings', ST))
    story.append(SP(4))

    for _, kind, headers, rows in parse_findings(body, 'iOS Native Findings'):
        rendered = _render_findings_rows(rows, headers, ST)
        story.append(data_table(
            ['File', 'Ln', 'Pattern', 'Tag', 'Owner', 'Priority'],
            rendered, findings_cw, ST,
        ))
        story.append(SP(3))

    # ════════════════════════════════════════════════════════════════
    # PAGE 5 — ANDROID + ACTION PLAN
    # ════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(section_header('4', 'Android Native Findings', ST))
    story.append(SP(4))

    for _, kind, headers, rows in parse_findings(body, 'Android Native Findings'):
        rendered = _render_findings_rows(rows, headers, ST)
        story.append(data_table(
            ['File', 'Ln', 'Pattern', 'Tag', 'Owner', 'Priority'],
            rendered, findings_cw, ST,
        ))
        story.append(SP(3))

    story.append(SP(3))
    story.append(section_header('5', 'Prioritized Action Plan', ST))
    story.append(SP(4))

    phases = parse_action_plan(body)
    for pi, (title, steps) in enumerate(phases):
        # For each phase, keep the bar together with its first step card so
        # the heading never appears orphaned at the bottom of a page.
        # This works for any dynamic content because step_card uses
        # splitByRow=False, making each card atomic for KeepTogether.
        anchor = [phase_bar(title, pi, ST), SP(2)]
        if steps:
            anchor += [step_card(1, steps[0][0], steps[0][1], ST), SP(1.5)]
        story.append(KeepTogether(anchor))
        for si, (stitle, sdesc) in enumerate(steps[1:], start=2):
            story.append(step_card(si, stitle, sdesc, ST))
            story.append(SP(1.5))
        story.append(SP(3))

    # ════════════════════════════════════════════════════════════════
    # PAGE 6 — EFFORT ESTIMATE
    # ════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(section_header('6', 'Effort Estimate', ST))
    story.append(SP(4))

    # Effort banner: time range + label on left, description on right
    col_hex = '%02X%02X%02X' % (int(effort_color.red * 255),
                                 int(effort_color.green * 255),
                                 int(effort_color.blue * 255))
    # Measure the effort range text to pick font size that fits without wrapping
    from reportlab.pdfbase.pdfmetrics import stringWidth
    range_font_size = 28
    # Allow generous inner width (left_w minus padding)
    left_w = 180
    inner_w = left_w - 30  # account for left+right padding
    text_w = stringWidth(effort_range, 'Helvetica-Bold', range_font_size)
    while text_w > inner_w and range_font_size > 16:
        range_font_size -= 1
        text_w = stringWidth(effort_range, 'Helvetica-Bold', range_font_size)

    range_p = Paragraph(
        f'<font color="#{col_hex}"><b>{effort_range}</b></font>',
        S('_er', fontName='Helvetica-Bold', fontSize=range_font_size,
          leading=range_font_size + 4),
    )
    label_p = Paragraph(
        f'<font color="#{col_hex}"><b>{effort_label.upper()} EFFORT</b></font>',
        S('_el', fontName='Helvetica-Bold', fontSize=8,
          textColor=effort_color, leading=10, letterSpacing=1.0),
    )
    left_col = Table([[range_p], [label_p]], colWidths=[left_w - 10])
    left_col.setStyle(TableStyle([
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    desc_p = Paragraph(
        f'Estimated <b>{effort_range}</b> of engineering work to complete the migration.<br/><br/>'
        f'Re-run the audit after each sprint to track progress and reassess the effort estimate.',
        ST['effort_desc'],
    )
    banner = Table([[left_col, desc_p]], colWidths=[left_w, CW - left_w])
    banner.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 0.5, C_GRAY_200),
        ('BACKGROUND',   (0, 0), (-1, -1), C_GRAY_50),
        ('LEFTPADDING',  (0, 0), (0, -1),  20),
        ('LEFTPADDING',  (1, 0), (1, -1),  18),
        ('RIGHTPADDING', (0, 0), (-1, -1), 18),
        ('TOPPADDING',   (0, 0), (-1, -1), 16),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 16),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBEFORE',   (1, 0), (1, -1),  0.5, C_GRAY_200),
    ]))
    story.append(banner)
    story.append(SP(4))

    # Optional effort breakdown table (if present in the markdown)
    effort_headers, effort_rows = parse_effort_table(body)
    if effort_headers and effort_rows:
        eff_cw = [CW * 0.54, CW * 0.14, CW * 0.16, CW * 0.16]
        rendered_eff = []
        for row in effort_rows:
            is_total = any('total' in c.lower() for c in row)
            sty      = ST['td_bold'] if is_total else ST['td']
            sty_r    = S('_mr', fontName=sty.fontName, fontSize=sty.fontSize,
                         textColor=sty.textColor, leading=sty.leading,
                         alignment=TA_RIGHT)
            r = [Paragraph(md2rl(row[0] if row else ''), sty)]
            for cell in (row[1:4] if len(row) >= 4 else row[1:]):
                r.append(Paragraph(md2rl(cell), sty_r))
            while len(r) < 4:
                r.append(Paragraph('', ST['td']))
            rendered_eff.append(r)
        story.append(data_table(effort_headers[:4], rendered_eff, eff_cw, ST))
        story.append(SP(4))

    # Scan coverage cards
    story.append(HRFlowable(width=CW, thickness=0.5, color=C_GRAY_200))
    story.append(SP(3))
    story.append(Paragraph('SCAN COVERAGE', ST['toc_label']))
    story.append(SP(2))

    scan_items = [(js_f, 'JS / TS Files'), (ios_f, 'iOS Files'),
                  (and_f, 'Android Files'), (deps_n, 'Dependencies')]
    scan_cells = []
    for num, lbl in scan_items:
        cell = Table([
            [Paragraph(num, ST['scan_num'])],
            [Paragraph(lbl.upper(), ST['scan_lbl'])],
        ], colWidths=[CW / 4 - 6])
        cell.setStyle(TableStyle([
            ('BOX',          (0, 0), (-1, -1), 0.5, C_GRAY_200),
            ('BACKGROUND',   (0, 0), (-1, -1), C_GRAY_50),
            ('TOPPADDING',   (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 12),
            ('LEFTPADDING',  (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        scan_cells.append(cell)
    scan_row = Table([scan_cells], colWidths=[CW / 4] * 4)
    scan_row.setStyle(TableStyle([
        ('LEFTPADDING',  (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    story.append(scan_row)
    story.append(SP(4))

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    print(f'✅  PDF written to {out_path}')


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='Generate PDF audit report from Markdown.')
    ap.add_argument('--input',  required=True, help='Path to MIGRATION_AUDIT_*.md')
    ap.add_argument('--output', required=True, help='Output PDF path')
    args = ap.parse_args()

    md_path  = Path(args.input)
    out_path = Path(args.output)

    if not md_path.exists():
        print(f'ERROR: input file not found: {md_path}', file=sys.stderr)
        sys.exit(1)

    md_text = md_path.read_text(encoding='utf-8')
    meta, body = parse_md(md_text)
    build_pdf(meta, body, out_path)


if __name__ == '__main__':
    main()
