#!/usr/bin/env python3.10
"""
Generate submission/report.docx from the MFA Detection Platform architecture content.
Run: python3.10 submission/generate_report_docx.py
"""
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

doc = Document()

# ── Page margins ───────────────────────────────────────────────────────────
for section in doc.sections:
    section.top_margin    = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin   = Cm(2.5)
    section.right_margin  = Cm(2.5)

# ── Colour palette ─────────────────────────────────────────────────────────
BLUE_DARK  = RGBColor(0x1e, 0x3a, 0x5f)
BLUE_MID   = RGBColor(0x25, 0x63, 0xeb)
BLUE_LIGHT = RGBColor(0xdb, 0xea, 0xfe)
WHITE      = RGBColor(0xff, 0xff, 0xff)
GRAY       = RGBColor(0x6b, 0x72, 0x80)
GREEN_BG   = RGBColor(0xf0, 0xfd, 0xf4)
GREEN_BD   = RGBColor(0x16, 0xa3, 0x4a)
AMBER      = RGBColor(0xf5, 0x9e, 0x0b)
RED        = RGBColor(0xdc, 0x26, 0x26)
CODE_BG    = RGBColor(0xf1, 0xf5, 0xf9)

# ── Style helpers ──────────────────────────────────────────────────────────
def set_cell_bg(cell, hex_str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'),   'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'),  hex_str.lstrip('#'))
    tcPr.append(shd)

def set_cell_borders(cell, color='CBD5E1'):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for side in ('top','left','bottom','right'):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'),   'single')
        el.set(qn('w:sz'),    '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), color)
        tcBorders.append(el)
    tcPr.append(tcBorders)

def para_spacing(para, before=0, after=0, line=None):
    pPr = para._p.get_or_add_pPr()
    spacing = OxmlElement('w:spacing')
    spacing.set(qn('w:before'), str(before))
    spacing.set(qn('w:after'),  str(after))
    if line:
        spacing.set(qn('w:line'),     str(line))
        spacing.set(qn('w:lineRule'), 'auto')
    pPr.append(spacing)

def add_heading(doc, text, level=1, color=None):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = color or (BLUE_MID if level==1 else BLUE_DARK)
        run.font.bold = True
    para_spacing(h, before=200, after=80)
    return h

def add_body(doc, text, bold=False, italic=False, color=None, size=10):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size  = Pt(size)
    run.font.bold  = bold
    run.font.italic= italic
    if color:
        run.font.color.rgb = color
    para_spacing(p, before=40, after=40)
    return p

def add_code(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    run = p.add_run(text)
    run.font.name = 'Courier New'
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(0x1e, 0x3a, 0x5f)
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'),   'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'),  'F1F5F9')
    pPr.append(shd)
    para_spacing(p, before=40, after=40)
    return p

def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    run.font.size = Pt(10)
    p.paragraph_format.left_indent = Inches(0.3 + 0.2*level)
    para_spacing(p, before=30, after=30)
    return p

def add_numbered(doc, text, level=0):
    p = doc.add_paragraph(style='List Number')
    run = p.add_run(text)
    run.font.size = Pt(10)
    para_spacing(p, before=30, after=30)
    return p

def add_divider(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'),   'single')
    bottom.set(qn('w:sz'),    '4')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '2563EB')
    pBdr.append(bottom)
    pPr.append(pBdr)
    para_spacing(p, before=100, after=100)

def add_page_break(doc):
    doc.add_page_break()

def make_table(doc, headers, rows, col_widths=None):
    n_cols = len(headers)
    table = doc.add_table(rows=1+len(rows), cols=n_cols)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    # Header row
    hdr_row = table.rows[0]
    for i, hdr in enumerate(headers):
        cell = hdr_row.cells[i]
        set_cell_bg(cell, '1E3A5F')
        p = cell.paragraphs[0]
        run = p.add_run(hdr)
        run.font.bold  = True
        run.font.color.rgb = WHITE
        run.font.size  = Pt(9)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    # Data rows
    for ri, row in enumerate(rows):
        tr = table.rows[ri+1]
        bg = 'F8FAFC' if ri % 2 == 0 else 'FFFFFF'
        for ci, val in enumerate(row):
            cell = tr.cells[ci]
            set_cell_bg(cell, bg)
            set_cell_borders(cell)
            p = cell.paragraphs[0]
            if isinstance(val, list):
                for part, bold in val:
                    run = p.add_run(part)
                    run.font.bold  = bold
                    run.font.size  = Pt(9)
            else:
                run = p.add_run(str(val))
                run.font.size = Pt(9)
    # Column widths
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Inches(w)
    return table

def info_box(doc, lines, bg='EFF6FF', border='2563EB', label=None):
    """Simulate a coloured callout box using a single-cell table."""
    t = doc.add_table(rows=1, cols=1)
    t.style = 'Table Grid'
    cell = t.rows[0].cells[0]
    set_cell_bg(cell, bg)
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for side in ('top','left','bottom','right'):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'),   'single')
        el.set(qn('w:sz'),    '12')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), border)
        tcBorders.append(el)
    tcPr.append(tcBorders)
    for i, line in enumerate(lines):
        if i == 0:
            p = cell.paragraphs[0]
        else:
            p = cell.add_paragraph()
        if label and i == 0:
            r = p.add_run(f'{label}  ')
            r.font.bold = True
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(int(border[:2],16), int(border[2:4],16), int(border[4:],16))
        r2 = p.add_run(line)
        r2.font.size = Pt(9.5)
        p.paragraph_format.left_indent = Inches(0.15)
        para_spacing(p, before=30, after=30)
    doc.add_paragraph()
    return t

def diagram_placeholder(doc, title, description_lines, caption):
    """A styled box showing diagram description (since DOCX can't render Mermaid)."""
    doc.add_paragraph()
    t = doc.add_table(rows=1, cols=1)
    t.style = 'Table Grid'
    cell = t.rows[0].cells[0]
    set_cell_bg(cell, 'F0F7FF')
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for side in ('top','left','bottom','right'):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'),   'single')
        el.set(qn('w:sz'),    '8')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), '2563EB')
        tcBorders.append(el)
    tcPr.append(tcBorders)
    # Title
    p0 = cell.paragraphs[0]
    r = p0.add_run(f'📊  {title}')
    r.font.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = BLUE_DARK
    p0.paragraph_format.left_indent = Inches(0.15)
    para_spacing(p0, before=60, after=40)
    # Description lines
    for line in description_lines:
        p = cell.add_paragraph()
        r2 = p.add_run(line)
        r2.font.size = Pt(9)
        r2.font.name = 'Courier New'
        r2.font.color.rgb = RGBColor(0x1e, 0x3a, 0x5f)
        p.paragraph_format.left_indent = Inches(0.3)
        para_spacing(p, before=20, after=20)
    # Caption
    pc = cell.add_paragraph()
    rc = pc.add_run(caption)
    rc.font.size   = Pt(8.5)
    rc.font.italic = True
    rc.font.color.rgb = GRAY
    pc.paragraph_format.left_indent = Inches(0.15)
    para_spacing(pc, before=40, after=60)
    doc.add_paragraph()


# ══════════════════════════════════════════════════════════════════════════
# COVER PAGE
# ══════════════════════════════════════════════════════════════════════════
p_role = doc.add_paragraph()
r = p_role.add_run('LEAD / ARCHITECT ASSESSMENT — AS-BUILT REVISION')
r.font.size = Pt(9); r.font.bold = True; r.font.color.rgb = BLUE_MID
r.font.name = 'Calibri'
p_role.paragraph_format.space_before = Pt(36)

p_title = doc.add_paragraph()
r = p_title.add_run('MFA Detection Platform')
r.font.size = Pt(32); r.font.bold = True; r.font.color.rgb = BLUE_MID
r.font.name = 'Calibri'
para_spacing(p_title, before=80, after=60)

p_sub = doc.add_paragraph()
r = p_sub.add_run('AI-Enabled Made-For-Advertising Classification, Explanation & RAG Bot')
r.font.size = Pt(13); r.font.italic = True; r.font.color.rgb = GRAY
para_spacing(p_sub, before=0, after=120)

# Meta table
meta = doc.add_table(rows=4, cols=2)
meta.style = 'Table Grid'
meta_data = [
    ('Role',             'Lead / Solution Architect'),
    ('Submission Date',  'July 2026'),
    ('Stack',            'Python 3.12 · FastAPI · XGBoost · Playwright · OpenSearch · Redis · AWS Bedrock (Claude)'),
    ('Platform Status',  '✅ Baseline/POC Complete (2026-07-10)   🟡 MVP In Progress'),
]
for i, (k, v) in enumerate(meta_data):
    row = meta.rows[i]
    set_cell_bg(row.cells[0], 'EFF6FF')
    set_cell_bg(row.cells[1], 'FFFFFF')
    rk = row.cells[0].paragraphs[0].add_run(k)
    rk.font.bold = True; rk.font.size = Pt(9.5); rk.font.color.rgb = BLUE_DARK
    rv = row.cells[1].paragraphs[0].add_run(v)
    rv.font.size = Pt(9.5)
    for cell in row.cells:
        set_cell_borders(cell, '2563EB')
        cell.paragraphs[0].paragraph_format.left_indent = Inches(0.1)

meta.columns[0].width = Inches(1.6)
meta.columns[1].width = Inches(4.9)

doc.add_paragraph()
info_box(doc, [
    'Diagrams in this document show the pipeline flow as text descriptions with step-by-step stage labels.',
    'Solid labels = built and running today.  ⚠️ GAP labels = roadmap items (see Section 6).',
    'Open report.html in a browser for the full interactive Mermaid diagrams.',
], bg='FEF9C3', border='F59E0B', label='📌 Note:')

add_page_break(doc)

# ══════════════════════════════════════════════════════════════════════════
# TABLE OF CONTENTS
# ══════════════════════════════════════════════════════════════════════════
add_heading(doc, 'Table of Contents', level=1)
toc_items = [
    'Assumptions',
    '1.  System Architecture',
    '2.  Data Signals Research',
    '3.  Architecture Decision Records',
    '4.  RAG Bot Architecture',
    '5.  Risk & Guardrail Design',
    '6.  MVP vs Production Roadmap',
    '7.  Estimation — Team, Timeline & Cost',
    '8.  Cloud Service Mapping & Scale Plan',
    '9.  Working Code — Architecture Walkthrough',
]
for item in toc_items:
    add_bullet(doc, item)
add_page_break(doc)

# ══════════════════════════════════════════════════════════════════════════
# ASSUMPTIONS
# ══════════════════════════════════════════════════════════════════════════
add_heading(doc, 'Assumptions', level=1)
info_box(doc, [
    'Target users: Digital advertising operations teams — Ad Ops, Campaign Managers, and Reviewers.',
    'Primary cloud: AWS. Azure and GCP equivalents documented in Section 8.',
    'Implementation status: Baseline/POC complete 2026-07-10. This document covers MVP-to-Production.',
    'Working code is production-oriented (FastAPI + XGBoost + RAG service), not a throwaway prototype.',
    'LLM provider: AWS Bedrock (Claude Sonnet for RAG, Claude Haiku for explanations).',
    'Crawl targets are third-party ad inventory URLs; legal/robots.txt compliance per jurisdiction.',
    'Gold-label dataset: 615 URLs from internal Ad Ops review. Vendor blocklists used only for bootstrap.',
    'Traffic enrichment (paid_traffic_pct etc.) requires a Similarweb-style third-party API — one signal tier.',
    'Baseline targets: Precision ≥ 85%, Recall ≥ 70%. MVP feature expansion (16 → 60) closes the gap.',
    'Signal extraction is deterministically simulated today (SHA-256 of URL). Real Playwright crawler is Gap G2.',
], bg='EFF6FF', border='2563EB')
add_page_break(doc)


# ══════════════════════════════════════════════════════════════════════════
# SECTION 1: SYSTEM ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════
add_heading(doc, '1.  System Architecture', level=1)
add_body(doc, (
    'The MFA Detection Platform scores at URL/page-section granularity using a multi-layer evidence '
    'accumulation strategy. No single signal is sufficient — MFA operators maintain clean homepages, '
    'valid IVT profiles, and acceptable viewability scores. The platform combines crawl observations, '
    'domain metadata, supply chain signals, and campaign performance anomalies across 8 pipeline layers.'
))
add_body(doc, (
    'Every decision is bound to its evidence via a SHA-256 hash of the canonical signal snapshot JSON '
    '(evidence_hash), forming an immutable chain of custody. The LLM is intentionally not in the '
    'classification path (ADR-001) — it is used only for explanation generation and the RAG bot.'
))

add_heading(doc, '1.1  Architecture Layers', level=2)
make_table(doc,
    headers=['Layer', 'Components', 'Key Output'],
    rows=[
        ('Ingestion ✅',          'REST API (FastAPI), Batch Orchestrator (Step Functions), URL Dedup/Normaliser',  'url_id, crawl job, priority queue entry'),
        ('Signal Extraction ⚠️',  'signal-extraction-service (simulated today). Gap G2: Playwright dual-persona crawler, DOM parser, screenshots', 'Feature vector (16 features) + evidence artifacts'),
        ('Data Stores ✅',        'Postgres JSONB (signals+jobs), S3/local (artifacts), OpenSearch (vectors), Redis (cache), DynamoDB+S3 audit', 'Versioned signal snapshots, classification history'),
        ('AI / ML ✅',            'Rules Engine → XGBoost Ensemble → Confidence Calibrator → HITL Router',         'tier, mfa_score, confidence, top_signals (SHAP-ranked)'),
        ('Explanation ✅',        'Jinja2 Templates (Baseline running). Gap MVP: LLM Explanation via Bedrock Claude Haiku', 'Human-readable narrative with cited signals'),
        ('RAG Bot ✅',            'Chat Gateway → Input Sanitiser → Intent Classifier → Hybrid Retriever → Citation Validator → Grounded LLM', 'Cited answers, confidence, recommended_action'),
        ('Review UI ✅',          'React+TS Reviewer Console, Ops Dashboard, Bot Chat UI, Blocklist Export API',   'Override labels, blocklist segments, dashboard'),
        ('Observability ✅',      'CloudWatch Metrics/Logs, X-Ray Traces, Alerting SLOs, Cost Attribution',         'SLO dashboards, drift alerts, cost breakdowns'),
    ],
    col_widths=[1.4, 3.2, 2.0]
)

add_heading(doc, '1.2  End-to-End Data Flow', level=2)
diagram_placeholder(doc,
    'End-to-End Data Flow  (8 pipeline stages)',
    [
        '┌── URL DISCOVERY SOURCES ────────────────────────────────────────────┐',
        '│  Batch Inventory Feed (CSV/S3)  ·  Real-time Bid Stream (Webhook)   │',
        '│  Manual Submission (Submit URLs screen)                             │',
        '└───────────────────────────┬─────────────────────────────────────────┘',
        '                            │',
        '┌── ① INGESTION  ✅ LIVE ───▼─────────────────────────────────────────┐',
        '│  ingestion-service  →  URL Dedup/Normalise  →  url_id               │',
        '│  Kafka topic: url.discovered                                        │',
        '└───────────────────────────┬─────────────────────────────────────────┘',
        '                            │  Kafka: url.discovered',
        '┌── ② SIGNAL EXTRACTION  ⚠️ LIVE SIMULATED ───▼──────────────────────┐',
        '│  signal-extraction-service: SHA-256(URL) → 16 deterministic signals │',
        '│  ⚠️ GAP G2: crawler-service (Playwright headless Chrome, dual-persona│',
        '│      direct + referral, 60s dwell, refresh detection)               │',
        '│  Kafka topic: signals.extracted                                     │',
        '└──────────────┬──────────────────────────────┬───────────────────────┘',
        '               │ Postgres JSONB               │ S3 / Local Disk',
        '┌── ③ DATA STORES ✅ ─────────┘                │ ─────────────────────┐',
        '│  Postgres: signal_snapshots, classification_result                  │',
        '│  Elasticsearch: signals-index, policy-docs, historical, feedback    │',
        '│  Redis: domain tier cache (24h TTL)                                 │',
        '│  S3/Local: HTML, screenshots, raw artifacts                         │',
        '└───────────────────────────┬─────────────────────────────────────────┘',
        '                            │',
        '┌── ④ AI / ML LAYER  ✅ LIVE ▼────────────────────────────────────────┐',
        '│  Rules Engine  →  (rule match → short-circuit)                      │',
        '│                →  (no match)  →  XGBoost Ensemble                  │',
        '│                               →  Confidence Calibrator              │',
        '│                               →  Tier Mapping                      │',
        '│                               →  SHAP Top-5 Signal Attribution      │',
        '│  confidence < 0.85 or high-spend  →  HITL Reviewer Queue           │',
        '└──────────────┬──────────────────────────────┬───────────────────────┘',
        '               │ OK                           │ Low confidence',
        '┌── ⑤ EXPLANATION ─────────────┘             │ ──────────────────────┐',
        '│  Jinja2 Templates (Baseline ✅)             │ ⑥ HITL QUEUE  ✅     │',
        '│  LLM Bedrock Haiku (MVP ⚠️)                 │ Reviewer Console       │',
        '│  + evidence_hash binding                   │ Override + Reason Code │',
        '└──────────────┬──────────────────────────────┘ Audit Event Written   │',
        '               │                                                       │',
        '┌── ⑦ AUDIT LOG  ✅ APPEND-ONLY ▼────────────────────────────────────┐',
        '│  event_id · entity_id · action · actor_id · occurred_at             │',
        '│  evidence_hash · payload (JSONB)  — No UPDATE / DELETE permitted    │',
        '└──────────────┬──────────────────────────────────────────────────────┘',
        '               │',
        '┌── ⑧ USER-FACING UI  ✅ ──────▼────────────────────────────────────┐',
        '│  Ops Dashboard · Classification Explorer · Blocklist Export         │',
        '│  RAG Bot (POST /api/v1/chat)                                        │',
        '└────────────────────────────────────────────────────────────────────┘',
    ],
    'Figure 1.2 — End-to-end data flow. ✅ = built and verified live. ⚠️ = running simulated (Gap G2 = real crawler, MVP roadmap).'
)

add_heading(doc, '1.3  Classification Pipeline', level=2)
diagram_placeholder(doc,
    'Classification Cascade  (Rules → XGBoost → Calibrator → Tier → SHAP)',
    [
        'SignalFeatures v1.1 (16 crawl features)',
        '     │',
        '     ▼',
        '┌── Rules Engine  ✅ ──────────────────────────────────────────────┐',
        '│  Deterministic patterns (e.g. ad_ratio > 0.65 AND words < 250)  │',
        '│  Rule fires  →  classifier="rules", confidence="high"           │',
        '│  No rule     →  pass to XGBoost                                 │',
        '└──────────────┬──────────────────────────────────────────────────┘',
        '               │ no match',
        '     ▼',
        '┌── XGBoost Ensemble  ✅ ─────────────────────────────────────────┐',
        '│  predict_proba(features)  →  raw probability [0,1]              │',
        '│  Train/val split by domain (prevents leakage)                   │',
        '└──────────────┬──────────────────────────────────────────────────┘',
        '               │',
        '     ▼',
        '┌── Confidence Calibrator  ✅ ────────────────────────────────────┐',
        '│  Isotonic Regression / Platt Scaling                            │',
        '│  Maps overconfident raw probabilities → calibrated proba        │',
        '└──────────────┬──────────────────────────────────────────────────┘',
        '               │',
        '     ▼',
        '┌── Tier Mapping  ✅ ─────────────────────────────────────────────┐',
        '│  ≥ 0.80  →  MFA_High   / high                                  │',
        '│  ≥ 0.60  →  MFA_Medium / medium   → HITL Queue                 │',
        '│  ≥ 0.40  →  MFA_Low    / medium                                │',
        '│  < 0.40  →  Non_MFA    / high                                  │',
        '│  low conf→  Uncertain  / low      → HITL Queue                 │',
        '└──────────────┬──────────────────────────────────────────────────┘',
        '               │',
        '     ▼',
        '┌── SHAP Top-5 Signal Attribution  ✅ ───────────────────────────┐',
        '│  feature · value · contribution · rank (abs SHAP value)        │',
        '└──────────────┬──────────────────────────────────────────────────┘',
        '               │',
        '     ▼',
        'ClassificationOutput: tier · mfa_score · confidence · top_signals',
        '                      explanation · evidence_hash · classifier',
    ],
    'Figure 1.3 — Classification cascade. LLM is NEVER in the classification path (ADR-001).'
)

add_heading(doc, '1.4  Near-Real-Time vs Batch Processing', level=2)
make_table(doc,
    headers=['Mode', 'Path', 'SLA', 'Queue', 'Use Case'],
    rows=[
        ('Batch',            'Nightly inventory sweep, full crawl + feature extraction, Step Functions', 'Hours',   'SQS Standard',   'Daily inventory hygiene, model training data'),
        ('Near-real-time',   'New placements, shortened crawl + domain cache reuse',                    '< 2–5 min', 'SQS FIFO',       'New domain onboarding, spend-weighted escalation'),
        ('Pre-bid (Prod)',   'Redis domain risk cache lookup only — no crawl',                          '< 200ms',  'Redis only',     'DSP/SSP pre-bid integration (Production roadmap)'),
    ],
    col_widths=[1.1, 2.5, 0.8, 1.0, 1.9]
)
add_page_break(doc)


# ══════════════════════════════════════════════════════════════════════════
# SECTION 2: DATA SIGNALS
# ══════════════════════════════════════════════════════════════════════════
add_heading(doc, '2.  Data Signals Research', level=1)

add_heading(doc, '2.1  Signal Tier Framework', level=2)
make_table(doc,
    headers=['Tier', 'Signal Category', 'Key Features', 'Source', 'Gaming Risk'],
    rows=[
        ('1', 'Ad Density & Clutter',       'ad_to_content_ratio, ads_above_fold, ad_slots_count, sticky_ad_count', 'Headless crawl + DOM analysis', 'Low'),
        ('1', 'Ad Refresh Behaviour',       'refresh_events_60s, avg_refresh_interval_sec',                         '60s dwell crawl + OpenRTB',     'Medium'),
        ('1', 'Traffic Source Skew',        'paid_traffic_pct, social_traffic_pct, organic_traffic_pct',            'Verification vendor / Similarweb', 'Medium'),
        ('1', 'Referral vs Direct Delta',   'referral_direct_delta_score',                                          'Dual-persona crawl (Gap G2)',    'Low'),
        ('1', 'Content Quality',            'content_word_count, content_uniqueness_score, author_page_exists',     'NLP + LLM rubric',              'Medium'),
        ('2', 'Domain Metadata',            'domain_age_days, WHOIS privacy, registrar churn',                      'WHOIS / DNS history',           'Low'),
        ('2', 'Supply Chain',               'sellers_json_risk_tier, ads.txt reseller chain',                       'SSP sellers.json + Jounce',     'Low'),
        ('2', 'Campaign Performance',       'campaign_ctr_vs_benchmark, historical_spend_usd',                      'Campaign warehouse / DSP',      'Medium'),
        ('3', 'Reviewer Overrides',         'Historical overrides, reason codes, reviewer notes',                   'Review console / Postgres',     'Low'),
    ],
    col_widths=[0.5, 1.5, 2.3, 1.5, 0.9]
)

add_heading(doc, '2.2  Current v1.1 Feature Schema (16 Crawl Features)', level=2)
make_table(doc,
    headers=['Feature', 'Type', 'Range', 'Null When', 'MFA Direction'],
    rows=[
        ('ad_to_content_ratio',        'float', '0–1',  'Not measured',              '↑ High = MFA'),
        ('ads_above_fold',             'int',   '≥ 0',  'Not measured',              '↑ High = MFA'),
        ('ad_slots_count',             'int',   '≥ 0',  'Not measured',              '↑ High = MFA'),
        ('sticky_ad_count',            'int',   '≥ 0',  'Not measured',              '↑ High = MFA'),
        ('content_word_count',         'int',   '≥ 0',  'Not measured',              '↓ Low = MFA'),
        ('refresh_events_60s',         'int',   '≥ 0',  'Dwell not run (null ≠ 0)',  '↑ High = MFA'),
        ('avg_refresh_interval_sec',   'float', '≥ 0',  'No refresh events',         '↓ Short = MFA'),
        ('content_uniqueness_score',   'float', '0–1',  'Heuristic unavailable',     '↓ Low = MFA'),
        ('author_page_exists',         'bool',  'T/F',  'Not detected',              'false = MFA'),
        ('slideshow_pagination_depth', 'int',   '≥ 0',  'Not a slideshow',           '↑ High = MFA'),
        ('video_autoplay_count',       'int',   '≥ 0',  'Not measured',              '↑ High = MFA'),
        ('page_load_ad_latency_ms',    'float', '≥ 0',  'Not measured',              '↓ Low = ads early'),
        ('iframe_ad_count',            'int',   '≥ 0',  'Not measured',              '↑ High = MFA'),
        ('native_ad_count',            'int',   '≥ 0',  'Not measured',              '↑ High = MFA'),
        ('outbound_link_count',        'int',   '≥ 0',  'Not measured',              '↓ Low = isolated'),
        ('image_to_text_ratio',        'float', '≥ 0',  'Not measured',              '↑ Very high = MFA'),
    ],
    col_widths=[1.8, 0.6, 0.6, 1.6, 1.7]
)

add_heading(doc, '2.3  MVP Enrichment Features (Planned)', level=2)
make_table(doc,
    headers=['Feature', 'Type', 'Source', 'Notes'],
    rows=[
        ('domain_age_days',             'int',   'WHOIS / DNS history',         'Low domain age + high impressions = suspect'),
        ('paid_traffic_pct',            'float', 'Similarweb-style API',        'MFA typically > 60% paid/social'),
        ('social_traffic_pct',          'float', 'Similarweb-style API',        'Combine with referral delta'),
        ('organic_traffic_pct',         'float', 'Similarweb-style API',        'Low organic = weak editorial'),
        ('referral_direct_delta_score', 'float', 'Dual-persona crawl (Gap G2)', 'Key evasion signal'),
        ('sellers_json_risk_tier',      'str',   'SSP sellers.json + Jounce',   'Reseller node risk tier'),
        ('historical_spend_usd',        'float', 'Campaign warehouse',          'Spend-weighted HITL escalation'),
        ('campaign_ctr_vs_benchmark',   'float', 'DSP exports',                 'Anomalous CTR vs peer-set'),
        ('simhash_dup_rate',            'float', 'Simhash dedup pipeline',      'Content duplication across MFA network'),
        ('llm_content_quality_score',   'float', 'LLM rubric + NLP',            'AI-generated content quality assessment'),
    ],
    col_widths=[1.9, 0.6, 1.7, 2.5]
)

add_heading(doc, '2.4  Signals to Treat with Caution', level=2)
cautions = [
    ('Viewability alone',       'MFA sites often score HIGH viewability — they are designed to have ads in-view. Using viewability alone produces systematic false negatives.'),
    ('IVT/fraud flags alone',   'MFA traffic is frequently human and valid. IVT detects bots, not arbitrage behaviour. These signals are orthogonal, not correlated.'),
    ('Homepage-only crawling',  'MFA sites maintain clean homepages for direct navigation. Article pages under referral traffic are where MFA behaviour is expressed.'),
    ('Single-domain blocking',  'MFA operations span subdomains, reseller nodes in sellers.json, and sibling domains under the same operator.'),
]
for title, detail in cautions:
    info_box(doc, [detail], bg='FEF2F2', border='DC2626', label=f'⚠️ {title}:')
add_page_break(doc)

