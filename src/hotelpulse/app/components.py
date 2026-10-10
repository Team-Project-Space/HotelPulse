"""UI components and CSS design system for HotelPulse.

Design system (v2 — premium SaaS light theme):

* CSS variables defined once in :root, so the whole palette is consistent and
  tweakable from one place.
* Deep navy text on light neutral surfaces, indigo primary accents, teal for
  positive values, amber warnings, red negatives — all AA-contrast against
  their backgrounds.
* Source-status components (`hp-source-*`) surface per-source availability
  honestly, never fabricating the analysed state.
* Missing data is rendered as an em-dash, never as a zero.
"""

from __future__ import annotations

CUSTOM_CSS = """
<style>
:root {
    --hp-bg:            #f6f7fb;
    --hp-surface:       #ffffff;
    --hp-surface-2:     #f8fafc;
    --hp-border:        #e4e8f0;
    --hp-border-strong: #d3d9e6;
    --hp-text:          #0b1220;
    --hp-text-2:        #334155;
    --hp-text-3:        #64748b;
    --hp-text-4:        #94a3b8;
    --hp-primary:       #4f46e5;
    --hp-primary-bg:    #eef2ff;
    --hp-primary-hover: #4338ca;
    --hp-teal:          #0d9488;
    --hp-teal-bg:       #f0fdfa;
    --hp-amber:         #b45309;
    --hp-amber-bg:      #fffbeb;
    --hp-red:           #dc2626;
    --hp-red-bg:        #fef2f2;
    --hp-navy:          #101828;
    --hp-radius:        12px;
    --hp-radius-lg:     16px;
    --hp-shadow-sm:     0 1px 2px rgba(16, 24, 40, 0.05);
    --hp-shadow:        0 4px 12px -2px rgba(16, 24, 40, 0.07);
    --hp-shadow-lg:     0 10px 30px -8px rgba(16, 24, 40, 0.12);
    --hp-font:          'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif;
}

html, body, [class*="css"] {
    font-family: var(--hp-font) !important;
    color: var(--hp-text);
    background-color: var(--hp-bg);
}

/* Streamlit shell ------------------------------------------------------- */
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 3rem !important;
    max-width: 1180px !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Scrollbars ------------------------------------------------------------ */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--hp-bg); }
::-webkit-scrollbar-thumb {
    background: var(--hp-border-strong);
    border-radius: 9999px;
}
::-webkit-scrollbar-thumb:hover { background: var(--hp-text-4); }

/* Buttons --------------------------------------------------------------- */
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.975rem !important;
    padding: 0.7rem 1.5rem !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease !important;
    box-shadow: 0 4px 10px -2px rgba(79, 70, 229, 0.35) !important;
}
div.stButton > button[kind="primary"]:hover {
    filter: brightness(1.08);
    transform: translateY(-1px);
    box-shadow: 0 6px 16px -2px rgba(79, 70, 229, 0.45) !important;
}
div.stButton > button[kind="primary"]:focus-visible {
    outline: 2px solid var(--hp-primary);
    outline-offset: 2px;
}
div.stButton > button[kind="primary"]:active { transform: translateY(0); }

div.stButton > button[kind="secondary"] {
    background: var(--hp-surface) !important;
    color: var(--hp-primary) !important;
    border: 1px solid var(--hp-border) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}
div.stButton > button[kind="secondary"]:hover {
    border-color: var(--hp-primary) !important;
    background: var(--hp-primary-bg) !important;
}

/* Inputs ---------------------------------------------------------------- */
div[data-testid="stTextInput"] input {
    background: var(--hp-surface) !important;
    border: 1px solid var(--hp-border-strong) !important;
    border-radius: 10px !important;
    font-size: 1rem !important;
    color: var(--hp-text) !important;
    padding: 0.7rem 0.9rem !important;
}
div[data-testid="stTextInput"] input::placeholder {
    color: var(--hp-text-4) !important;
    opacity: 1 !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: var(--hp-primary) !important;
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15) !important;
    outline: none;
}
div[data-testid="stTextInput"] label p {
    font-size: 0.875rem !important;
    font-weight: 600 !important;
    color: var(--hp-text-2) !important;
    margin-bottom: 0.2rem !important;
}

/* Navbar ----------------------------------------------------------------- */
.hp-navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 0 1.1rem 0;
    border-bottom: 1px solid var(--hp-border);
    margin-bottom: 1.25rem;
}

.hp-logo {
    font-size: 1.4rem;
    font-weight: 800;
    letter-spacing: -0.4px;
    color: var(--hp-navy);
    display: flex;
    align-items: center;
    gap: 0.45rem;
}

.hp-logo-mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 9px;
    background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
    color: #ffffff;
    font-size: 0.85rem;
    font-weight: 800;
}

.hp-logo-blue { color: var(--hp-primary); }

.hp-nav-right {
    display: flex;
    align-items: center;
    gap: 1rem;
    font-size: 0.85rem;
    color: var(--hp-text-3);
}

.hp-hotel-crumb {
    font-weight: 600;
    color: var(--hp-text-2);
}

.hp-badge-pill {
    background: var(--hp-surface-2);
    border: 1px solid var(--hp-border);
    color: var(--hp-text-3);
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
}

/* Landing ---------------------------------------------------------------- */
.hp-landing-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-top: 2.25rem;
    text-align: center;
}

.hp-pill-tag {
    display: inline-block;
    background: var(--hp-primary-bg);
    color: var(--hp-primary);
    border: 1px solid #e0e7ff;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    padding: 0.35rem 0.9rem;
    border-radius: 9999px;
    margin-bottom: 1.25rem;
    text-transform: uppercase;
}

.hp-hero-title {
    font-size: 2.8rem;
    font-weight: 800;
    line-height: 1.12;
    letter-spacing: -0.03em;
    color: var(--hp-navy);
    margin-bottom: 0.85rem;
    max-width: 660px;
}

.hp-hero-subtitle {
    font-size: 1.12rem;
    color: var(--hp-text-3);
    max-width: 620px;
    margin-bottom: 1.5rem;
    line-height: 1.55;
}

.hp-feature-strip {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 1rem;
    margin-top: 1.75rem;
    max-width: 860px;
}

.hp-feature-chip {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    background: var(--hp-surface);
    border: 1px solid var(--hp-border);
    border-radius: 9999px;
    padding: 0.5rem 1.1rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--hp-text-2);
    box-shadow: var(--hp-shadow-sm);
}

.hp-feature-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px; height: 26px;
    border-radius: 50%;
    font-size: 0.8rem;
    flex-shrink: 0;
}

.hp-feature-icon.indigo { background: var(--hp-primary-bg); color: var(--hp-primary); }
.hp-feature-icon.teal   { background: var(--hp-teal-bg);   color: var(--hp-teal); }
.hp-feature-icon.amber  { background: var(--hp-amber-bg);  color: var(--hp-amber); }

/* Search card (Streamlit container override) ----------------------------- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--hp-surface) !important;
    border: 1px solid var(--hp-border) !important;
    border-radius: var(--hp-radius-lg) !important;
    box-shadow: var(--hp-shadow-lg) !important;
    padding: 1.75rem 2rem !important;
}

/* Dashboard header ------------------------------------------------------- */
.hp-dash-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1rem;
    margin-bottom: 1.4rem;
    flex-wrap: wrap;
}

.hp-tag-blue {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--hp-primary);
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}

.hp-hotel-title {
    font-size: 2.1rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--hp-navy);
    line-height: 1.12;
    margin: 0;
    word-break: break-word;
}

.hp-hotel-sub {
    font-size: 0.95rem;
    color: var(--hp-text-3);
    margin-top: 0.3rem;
    word-break: break-word;
}

.hp-header-meta {
    font-size: 0.85rem;
    color: var(--hp-text-4);
    font-weight: 500;
    text-align: right;
}

/* Source status chips ----------------------------------------------------- */
.hp-source-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin: 0.5rem 0 1.4rem 0;
    align-items: center;
}

.hp-source-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    border-radius: 9999px;
    padding: 0.38rem 0.9rem;
    font-size: 0.8rem;
    font-weight: 600;
    border: 1px solid transparent;
}

.hp-source-chip.ok {
    background: var(--hp-teal-bg);
    border-color: #99f6e4;
    color: #115e59;
}

.hp-source-chip.unavail {
    background: var(--hp-surface-2);
    border-color: var(--hp-border);
    color: var(--hp-text-3);
}

.hp-source-chip.warn {
    background: var(--hp-amber-bg);
    border-color: #fde68a;
    color: var(--hp-amber);
}

.hp-source-dot {
    width: 8px; height: 8px;
    border-radius: 9999px;
    flex-shrink: 0;
}

.hp-source-chip.ok      .hp-source-dot { background: #0d9488; }
.hp-source-chip.unavail .hp-source-dot { background: #94a3b8; }
.hp-source-chip.warn    .hp-source-dot { background: #d97706; }

/* KPI cards --------------------------------------------------------------- */
.hp-metrics-container {
    background: var(--hp-surface);
    border: 1px solid var(--hp-border);
    border-radius: var(--hp-radius-lg);
    padding: 1.4rem 2rem;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.5rem;
    margin-bottom: 1.75rem;
    box-shadow: var(--hp-shadow);
}

.hp-metric-item {
    border-right: 1px solid var(--hp-border);
    padding-right: 1rem;
    min-width: 0;
}

.hp-metric-item:last-child { border-right: none; padding-right: 0; }

.hp-metric-label {
    font-size: 0.78rem;
    color: var(--hp-text-3);
    font-weight: 600;
    margin-bottom: 0.4rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.hp-metric-val {
    font-size: 1.9rem;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 0.25rem;
    color: var(--hp-navy);
}

.hp-metric-sub {
    font-size: 0.75rem;
    color: var(--hp-text-4);
    font-weight: 500;
}

/* Section headers ---------------------------------------------------------- */
.hp-section-header {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-size: 1.3rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--hp-navy);
    margin-bottom: 0.25rem;
}

.hp-section-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px; height: 30px;
    border-radius: 8px;
    font-size: 0.9rem;
    flex-shrink: 0;
}

.hp-section-icon.red  { background: var(--hp-red-bg);     color: var(--hp-red); }
.hp-section-icon.teal { background: var(--hp-teal-bg);    color: var(--hp-teal); }
.hp-section-icon.blue { background: var(--hp-primary-bg); color: var(--hp-primary); }
.hp-section-icon.navy { background: #e9edf5;              color: var(--hp-text-2); }

.hp-section-sub {
    font-size: 0.875rem;
    color: var(--hp-text-3);
    margin-bottom: 1.2rem;
}

/* Fix First cards -------------------------------------------------------- */
.hp-cards-grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.15rem;
    margin-bottom: 2.1rem;
}

.hp-fix-card {
    background: var(--hp-surface);
    border: 1px solid var(--hp-border);
    border-top: 3.5px solid var(--hp-red);
    border-radius: var(--hp-radius);
    padding: 1.1rem 1.25rem;
    box-shadow: var(--hp-shadow);
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.hp-fix-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--hp-shadow-lg);
}

.hp-fix-card.medium-priority { border-top-color: #f59e0b; }

.hp-fix-card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.hp-num-circle {
    width: 26px; height: 26px;
    border-radius: 50%;
    background: var(--hp-red-bg);
    color: var(--hp-red);
    font-weight: 700;
    font-size: 0.8125rem;
    display: flex;
    align-items: center;
    justify-content: center;
}

.hp-num-circle.medium { background: var(--hp-amber-bg); color: var(--hp-amber); }

.hp-priority-pill {
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 0.22rem 0.55rem;
    border-radius: 6px;
    background: var(--hp-red-bg);
    color: var(--hp-red);
    text-transform: uppercase;
}

.hp-priority-pill.medium { background: var(--hp-amber-bg); color: var(--hp-amber); }

.hp-card-title {
    font-size: 1.12rem;
    font-weight: 700;
    color: var(--hp-navy);
}

.hp-card-stat {
    font-size: 0.8rem;
    color: var(--hp-text-3);
}

.hp-quote-box {
    font-size: 0.875rem;
    color: var(--hp-text-2);
    font-style: italic;
    background: var(--hp-surface-2);
    border-left: 2.5px solid var(--hp-border-strong);
    padding: 0.65rem 0.85rem;
    border-radius: 0 8px 8px 0;
    line-height: 1.5;
}

.hp-card-footer {
    font-size: 0.75rem;
    color: var(--hp-text-4);
    margin-top: auto;
}

/* Strengths --------------------------------------------------------------- */
.hp-strength-card {
    background: var(--hp-surface);
    border: 1px solid var(--hp-border);
    border-left: 4px solid var(--hp-teal);
    border-radius: var(--hp-radius);
    padding: 1.1rem 1.25rem;
    box-shadow: var(--hp-shadow);
}

.hp-strength-title {
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--hp-navy);
    margin-bottom: 0.15rem;
}

.hp-strength-positive {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--hp-teal);
    margin-bottom: 0.55rem;
}

.hp-strength-quote {
    font-size: 0.875rem;
    color: var(--hp-text-2);
    font-style: italic;
    line-height: 1.5;
}

/* Topic grid --------------------------------------------------------------- */
.hp-topics-grid-8 {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 0.8rem;
    margin-bottom: 2.1rem;
}

.hp-topic-mini-card {
    background: var(--hp-surface);
    border: 1px solid var(--hp-border);
    border-radius: 10px;
    padding: 0.85rem 0.6rem 0.75rem 0.6rem;
    text-align: center;
    box-shadow: var(--hp-shadow-sm);
}

.hp-topic-name {
    font-size: 0.75rem;
    color: var(--hp-text-3);
    font-weight: 600;
    margin-bottom: 0.35rem;
}

.hp-topic-pct {
    font-size: 1.28rem;
    font-weight: 800;
}

.hp-topic-cap {
    font-size: 0.62rem;
    color: var(--hp-text-4);
    margin-top: 0.2rem;
}

.hp-indicator-bar {
    height: 4px;
    width: 70%;
    margin: 0.45rem auto 0 auto;
    border-radius: 9999px;
}

/* Bottom grid + comparison -------------------------------------------------- */
.hp-bottom-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
    margin-bottom: 2rem;
}

.hp-bottom-card {
    background: var(--hp-surface);
    border: 1px solid var(--hp-border);
    border-radius: var(--hp-radius-lg);
    padding: 1.4rem;
    box-shadow: var(--hp-shadow);
}

.hp-box-title {
    font-size: 1.12rem;
    font-weight: 800;
    color: var(--hp-navy);
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.2rem;
}

.hp-box-sub {
    font-size: 0.8rem;
    color: var(--hp-text-3);
    margin-bottom: 1.1rem;
}

.hp-comp-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1.1rem;
}

.hp-comp-table th {
    text-align: left;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--hp-text-4);
    padding-bottom: 0.65rem;
    border-bottom: 1px solid var(--hp-border);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.hp-comp-table td {
    padding: 0.8rem 0;
    font-size: 0.875rem;
    border-bottom: 1px solid var(--hp-border);
}

.hp-comp-topic { font-weight: 600; color: var(--hp-text-2); }

.hp-alert-banner {
    background: var(--hp-amber-bg);
    border: 1px solid #fde68a;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-size: 0.8125rem;
    color: var(--hp-amber);
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    line-height: 1.45;
}

.hp-alert-banner.info {
    background: var(--hp-primary-bg);
    border-color: #e0e7ff;
    color: var(--hp-primary);
}

/* Actions ------------------------------------------------------------------ */
.hp-action-item {
    display: flex;
    align-items: flex-start;
    gap: 0.8rem;
    padding: 0.8rem 0;
    border-bottom: 1px solid var(--hp-border);
}

.hp-action-item:last-child { border-bottom: none; padding-bottom: 0; }

.hp-action-num {
    width: 24px; height: 24px;
    border-radius: 50%;
    background: var(--hp-primary-bg);
    color: var(--hp-primary);
    font-size: 0.75rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
}

.hp-action-heading {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--hp-navy);
    margin-bottom: 0.15rem;
}

.hp-action-desc {
    font-size: 0.8rem;
    color: var(--hp-text-3);
}

/* Responsive ---------------------------------------------------------------- */
@media (max-width: 900px) {
    .hp-metrics-container { grid-template-columns: repeat(2, 1fr); }
    .hp-metric-item { border-right: none; padding-right: 0; }
    .hp-cards-grid-3 { grid-template-columns: 1fr; }
    .hp-topics-grid-8 { grid-template-columns: repeat(4, 1fr); }
    .hp-bottom-grid { grid-template-columns: 1fr; }
    .hp-hero-title { font-size: 2.1rem; }
}

@media (max-width: 560px) {
    .hp-metrics-container { grid-template-columns: 1fr; }
    .hp-topics-grid-8 { grid-template-columns: repeat(2, 1fr); }
    .hp-hero-title { font-size: 1.7rem; }
    .hp-hero-subtitle { font-size: 1rem; }
    .hp-hotel-title { font-size: 1.6rem; }
    .hp-nav-right { display: none; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 1.25rem 1.25rem !important; }
}
</style>
"""


# ---------------------------------------------------------------------------
# Component builders
# ---------------------------------------------------------------------------


def render_top_navbar(hotel_name: str | None = None, city: str | None = None):
    """Top navbar. The crumb only names a hotel when one has actually been set."""
    crumb = f"{hotel_name} · {city}" if (hotel_name and city) else "Guest Review Intelligence"
    return f"""<div class="hp-navbar">
<div class="hp-logo"><span class="hp-logo-mark">HP</span><span>Hotel<span class="hp-logo-blue">Pulse</span></span></div>
<div class="hp-nav-right">
<span class="hp-hotel-crumb">{crumb}</span>
<span class="hp-badge-pill">Hotel Insights</span>
</div>
</div>"""


def render_landing_hero():
    """Hero headline + subtitle + three feature chips (no metric claims)."""
    return """<div class="hp-landing-container">
<div class="hp-pill-tag">Hotel Insights</div>
<div class="hp-hero-title">Turn guest reviews into your next competitive advantage.</div>
<div class="hp-hero-subtitle">Discover what guests love, identify the issues that matter most, and understand how your hotel compares with nearby competitors.</div>
<div class="hp-feature-strip">
<div class="hp-feature-chip"><span class="hp-feature-icon indigo">◆</span>Review sentiment analysis</div>
<div class="hp-feature-chip"><span class="hp-feature-icon teal">✓</span>Evidence-backed recommendations</div>
<div class="hp-feature-chip"><span class="hp-feature-icon amber">⇄</span>Nearby hotel comparison</div>
</div>
</div>"""


def render_source_status(
    maps_available: bool,
    tripadvisor_available: bool,
    tripadvisor_note: str | None = None,
    no_reviews: bool = False,
):
    """Honest per-source availability chips.

    Renders exactly what the pipeline reports — no inferred availability and
    no claim that TripAdvisor was analysed when it was not.
    """
    if no_reviews:
        return """<div class="hp-source-row">
<div class="hp-source-chip warn"><span class="hp-source-dot"></span>No guest reviews available for this hotel yet.</div>
</div>"""

    if maps_available:
        maps_chip = """<div class="hp-source-chip ok"><span class="hp-source-dot"></span>Google Maps · available</div>"""
    else:
        maps_chip = """<div class="hp-source-chip unavail"><span class="hp-source-dot"></span>Google Maps · unavailable</div>"""

    if tripadvisor_available:
        ta_chip = """<div class="hp-source-chip ok"><span class="hp-source-dot"></span>TripAdvisor · available</div>"""
    else:
        note = tripadvisor_note or "not available"
        ta_chip = f"""<div class="hp-source-chip unavail"><span class="hp-source-dot"></span>TripAdvisor · {note}</div>"""

    return f"""<div class="hp-source-row">{maps_chip}{ta_chip}</div>"""


def render_dashboard_header(hotel_name, address, updated_date, review_count):
    """Dashboard header with real metadata (no fabricated values)."""
    count_txt = (
        f"{review_count:,} reviews analyzed" if review_count is not None else "reviews analyzed"
    )
    return f"""<div class="hp-dash-header">
<div>
<div class="hp-tag-blue">Your Hotel</div>
<h1 class="hp-hotel-title">{hotel_name}</h1>
<div class="hp-hotel-sub">{address}</div>
</div>
<div class="hp-header-meta">
Updated {updated_date} · {count_txt}
</div>
</div>"""


def _fmt(val, formatter):
    """Format a metric value, or an em-dash when it is missing."""
    if val is None:
        return "—"
    try:
        return formatter(val)
    except (TypeError, ValueError):
        return "—"


def render_metrics_bar(
    overall_rating,
    positive_pct,
    needs_attention_pct,
    reviews_analyzed,
    coverage_label=None,
):
    """The 4 KPI cards. Any missing value renders '—', never 0.

    `coverage_label` describes the review-source coverage honestly, e.g.
    "Google Maps only" or "Google Maps + Tripadvisor".
    """
    rating_text = _fmt(
        overall_rating,
        lambda v: f"""<span style="color: #f59e0b; font-size: 1.4rem; vertical-align: middle;">★</span> {v:.1f}""",
    )
    pos_text = _fmt(positive_pct, lambda v: f"{int(round(v))}%")
    neg_text = _fmt(needs_attention_pct, lambda v: f"{int(round(v))}%")
    count_text = _fmt(reviews_analyzed, lambda v: f"{int(v):,}")
    cov = coverage_label or "Review sources"

    return f"""<div class="hp-metrics-container">
<div class="hp-metric-item">
<div class="hp-metric-label">Overall rating</div>
<div class="hp-metric-val">{rating_text}</div>
<div class="hp-metric-sub">From guest reviews</div>
</div>
<div class="hp-metric-item">
<div class="hp-metric-label">Positive</div>
<div class="hp-metric-val" style="color: var(--hp-teal);">{pos_text}</div>
<div class="hp-metric-sub">Guest sentiment</div>
</div>
<div class="hp-metric-item">
<div class="hp-metric-label">Needs attention</div>
<div class="hp-metric-val" style="color: var(--hp-red);">{neg_text}</div>
<div class="hp-metric-sub">Negative sentiment</div>
</div>
<div class="hp-metric-item">
<div class="hp-metric-label">Reviews analyzed</div>
<div class="hp-metric-val">{count_text}</div>
<div class="hp-metric-sub">{cov}</div>
</div>
</div>"""


def render_fix_cards_html(issues):
    """The 3 'What should I fix?' cards."""
    cards_html = []
    for idx, issue in enumerate(issues, start=1):
        is_medium = issue.get("priority_level", "HIGH PRIORITY") == "MEDIUM"
        card_class = "hp-fix-card medium-priority" if is_medium else "hp-fix-card"
        circle_class = "hp-num-circle medium" if is_medium else "hp-num-circle"
        pill_class = "hp-priority-pill medium" if is_medium else "hp-priority-pill"

        cards_html.append(f"""<div class="{card_class}">
<div class="hp-fix-card-top">
<div class="{circle_class}">{idx}</div>
<div class="{pill_class}">{issue['priority_level']}</div>
</div>
<div class="hp-card-title">{issue['topic_name']}</div>
<div class="hp-card-stat">{issue['pct_reviews']}% of reviews · {issue['neg_mentions']} negative mentions</div>
<div class="hp-quote-box">"{issue['sample_quote']}"</div>
<div class="hp-card-footer">
<span>{issue['source']} · {issue['date']}</span>
</div>
</div>""")

    return f"""<div class="hp-cards-grid-3">{''.join(cards_html)}</div>"""


def render_strength_cards_html(strengths):
    """The 3 'What guests like' cards."""
    cards_html = []
    for item in strengths:
        cards_html.append(f"""<div class="hp-strength-card">
<div class="hp-strength-title">{item['topic_name']}</div>
<div class="hp-strength-positive">{item['positive_pct']}% positive</div>
<div class="hp-strength-quote">"{item['quote']}"</div>
</div>""")

    return f"""<div class="hp-cards-grid-3">{''.join(cards_html)}</div>"""


def render_topics_mini_grid(topics_data):
    """The 8 topic micro-cards.

    `score_pct: None` renders an em-dash ('not enough data'), never a fake 0%.
    """
    cards_html = []
    for item in topics_data:
        pct = item["score_pct"]
        if pct is None:
            color = "var(--hp-text-4)"
            display = "—"
            cap = "not enough data"
            bar_pct = 0
        else:
            if pct < 50:
                color = "var(--hp-red)"
            elif pct < 65:
                color = "var(--hp-amber)"
            else:
                color = "var(--hp-teal)"
            display = f"{int(pct)}%"
            cap = "topic score"
            bar_pct = max(4, pct)
        cards_html.append(f"""<div class="hp-topic-mini-card">
<div class="hp-topic-name">{item['name']}</div>
<div class="hp-topic-pct" style="color: {color};">{display}</div>
<div class="hp-topic-cap">{cap}</div>
<div class="hp-indicator-bar" style="background-color: {color}; width: {bar_pct}%;"></div>
</div>""")

    return f"""<div class="hp-topics-grid-8">{''.join(cards_html)}</div>"""


def render_comparison_table_and_actions(comparison_rows, alert_text, actions):
    """Bottom 2-column layout (Comparison Table + 3 Actions).

    `gap` arrives as a pre-formatted signed raw 1–5 difference string
    ("+0.4", "-1.2", "0.0") or None (missing data → em-dash row). It is never
    a percentage or percentage-point value.
    """
    def _arrow(gap_sign: str) -> str:
        if gap_sign.startswith("-"):
            return "▼"
        if gap_sign == "0.0":
            return "◆"
        return "▲"

    table_rows_html: list[str] = []
    for row in comparison_rows:
        gap_sign = row["gap"]
        if gap_sign is None:
            you_pct = row["you_pct"]
            nearby_pct = row["nearby_pct"]
            you_text = "—" if you_pct is None else f"{int(you_pct)}%"
            nearby_text = "—" if nearby_pct is None else f"{int(nearby_pct)}%"
            table_rows_html.append(f"""<tr>
<td class="hp-comp-topic">{row['topic']}</td>
<td style="color: var(--hp-text-4); font-weight: 700;">{you_text}</td>
<td style="color: var(--hp-text-4); font-weight: 500;">{nearby_text}</td>
<td style="color: var(--hp-text-4); font-weight: 700;">—</td>
</tr>""")
            continue

        arrow = _arrow(gap_sign)
        gap_color = (
            "var(--hp-red)" if gap_sign.startswith("-")
            else ("var(--hp-text-4)" if gap_sign == "0.0" else "var(--hp-teal)")
        )
        you_pct = row["you_pct"]
        if you_pct is None:
            you_color, you_text = "var(--hp-text-4)", "—"
        elif you_pct >= 70:
            you_color, you_text = "var(--hp-teal)", f"{int(you_pct)}%"
        elif you_pct >= 50:
            you_color, you_text = "var(--hp-amber)", f"{int(you_pct)}%"
        else:
            you_color, you_text = "var(--hp-red)", f"{int(you_pct)}%"
        nearby_pct = row["nearby_pct"]
        nearby_text = "—" if nearby_pct is None else f"{int(nearby_pct)}%"

        table_rows_html.append(f"""<tr>
<td class="hp-comp-topic">{row['topic']}</td>
<td style="color: {you_color}; font-weight: 700;">{you_text}</td>
<td style="color: var(--hp-text-3); font-weight: 500;">{nearby_text}</td>
<td style="color: {gap_color}; font-weight: 700;">{gap_sign} {arrow}</td>
</tr>""")

    actions_html = []
    for idx, act in enumerate(actions, start=1):
        actions_html.append(f"""<div class="hp-action-item">
<div class="hp-action-num">{idx}</div>
<div>
<div class="hp-action-heading">{act['title']}</div>
<div class="hp-action-desc">{act['desc']}</div>
</div>
</div>""")

    if not comparison_rows or all(r["gap"] is None for r in comparison_rows):
        table_html = """<div class="hp-alert-banner info">
<span>ℹ</span>
<span>Not enough comparison data yet. Your hotel and nearby competitors need scored topics in common before gaps can be shown.</span>
</div>"""
    else:
        table_html = f"""<table class="hp-comp-table">
<thead>
<tr>
<th style="width: 35%;">Topic</th>
<th style="width: 20%;">You</th>
<th style="width: 25%;">Nearby</th>
<th style="width: 20%;">Gap (1–5)</th>
</tr>
</thead>
<tbody>
{''.join(table_rows_html)}
</tbody>
</table>
<div class="hp-alert-banner">
<span>⚠️</span>
<span>{alert_text}</span>
</div>"""

    if not actions_html:
        actions_html = ["""<div class="hp-action-item">
<div class="hp-action-num">1</div>
<div>
<div class="hp-action-heading">Keep collecting reviews</div>
<div class="hp-action-desc">More guest feedback unlocks stronger recommendations.</div>
</div>
</div>"""]

    return f"""<div class="hp-bottom-grid">
<div class="hp-bottom-card">
<div class="hp-box-title">🏨 How do you compare?</div>
<div class="hp-box-sub">Your hotel vs nearby hotels, on the 1–5 topic score scale.</div>
{table_html}
</div>

<div class="hp-bottom-card">
<div class="hp-box-title">💡 Your next 3 actions</div>
<div class="hp-box-sub">Simple things you can act on.</div>
<div>
{''.join(actions_html)}
</div>
</div>
</div>"""
