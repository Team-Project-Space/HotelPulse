"""UI components and CSS design system for HotelPulse matching design.md specifications."""

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

/* Global resets & typography */
html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #0f172a;
    background-color: #f8fafc;
}

/* Remove default Streamlit top padding and margins */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1200px !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

/* Top Navbar */
.hp-navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 0 1.5rem 0;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 2rem;
}

.hp-logo {
    font-size: 1.5rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #0f172a;
    display: flex;
    align-items: center;
    gap: 2px;
}

.hp-logo span {
    color: #2563eb;
}

.hp-nav-right {
    display: flex;
    align-items: center;
    gap: 1rem;
    font-size: 0.875rem;
    color: #64748b;
}

.hp-hotel-crumb {
    font-weight: 500;
    color: #475569;
}

.hp-change-btn {
    color: #2563eb;
    text-decoration: none;
    font-weight: 600;
    cursor: pointer;
}

.hp-change-btn:hover {
    text-decoration: underline;
}

.hp-badge-pill {
    background-color: #f1f5f9;
    border: 1px solid #e2e8f0;
    color: #64748b;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
}

/* Landing / Search Screen */
.hp-landing-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    margin-top: 2.5rem;
    text-align: center;
}

.hp-pill-tag {
    display: inline-block;
    background-color: #eff6ff;
    color: #2563eb;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 0.35rem 0.85rem;
    border-radius: 9999px;
    margin-bottom: 1.25rem;
    text-transform: uppercase;
}

.hp-hero-title {
    font-size: 2.75rem;
    font-weight: 800;
    line-height: 1.15;
    letter-spacing: -0.03em;
    color: #0f172a;
    margin-bottom: 0.75rem;
}

.hp-hero-subtitle {
    font-size: 1.125rem;
    color: #64748b;
    max-width: 580px;
    margin-bottom: 2.5rem;
}

.hp-search-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.05), 0 8px 10px -6px rgba(15, 23, 42, 0.03);
    padding: 2.25rem;
    width: 100%;
    max-width: 500px;
    text-align: left;
}

.hp-input-label {
    font-size: 0.875rem;
    font-weight: 600;
    color: #334155;
    margin-bottom: 0.35rem;
    display: block;
}

.hp-subtext {
    font-size: 0.8125rem;
    color: #94a3b8;
    text-align: center;
    margin-top: 1rem;
}

/* Dashboard Header */
.hp-dash-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 1.75rem;
}

.hp-tag-blue {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #2563eb;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}

.hp-hotel-title {
    font-size: 2.25rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #0f172a;
    line-height: 1.1;
    margin: 0;
}

.hp-hotel-sub {
    font-size: 1rem;
    color: #64748b;
    margin-top: 0.25rem;
}

.hp-header-meta {
    font-size: 0.875rem;
    color: #94a3b8;
    font-weight: 500;
}

/* 4 Key Metrics Card Row */
.hp-metrics-container {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1.25rem 2rem;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.5rem;
    margin-bottom: 2.25rem;
    box-shadow: 0 2px 8px -2px rgba(15, 23, 42, 0.04);
}

.hp-metric-item {
    border-right: 1px solid #f1f5f9;
    padding-right: 1rem;
}

.hp-metric-item:last-child {
    border-right: none;
    padding-right: 0;
}

.hp-metric-label {
    font-size: 0.8125rem;
    color: #64748b;
    font-weight: 500;
    margin-bottom: 0.35rem;
}

.hp-metric-val {
    font-size: 1.875rem;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 0.2rem;
}

.hp-metric-sub {
    font-size: 0.75rem;
    color: #94a3b8;
    font-weight: 500;
}

/* Section Header */
.hp-section-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #0f172a;
    margin-bottom: 0.2rem;
}

.hp-section-sub {
    font-size: 0.875rem;
    color: #64748b;
    margin-bottom: 1.25rem;
}

/* Fix First Cards */
.hp-cards-grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
    margin-bottom: 2.5rem;
}

.hp-fix-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-top: 3.5px solid #ef4444;
    border-radius: 12px;
    padding: 1.25rem 1.35rem;
    box-shadow: 0 4px 12px -2px rgba(15, 23, 42, 0.04);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.hp-fix-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 18px -4px rgba(15, 23, 42, 0.08);
}

.hp-fix-card.medium-priority {
    border-top-color: #f59e0b;
}

.hp-fix-card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.85rem;
}

.hp-num-circle {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background-color: #fee2e2;
    color: #dc2626;
    font-weight: 700;
    font-size: 0.8125rem;
    display: flex;
    align-items: center;
    justify-content: center;
}

.hp-num-circle.medium {
    background-color: #fef3c7;
    color: #d97706;
}

.hp-priority-pill {
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 0.2rem 0.55rem;
    border-radius: 6px;
    background-color: #fee2e2;
    color: #dc2626;
    text-transform: uppercase;
}

.hp-priority-pill.medium {
    background-color: #fef3c7;
    color: #d97706;
}

.hp-card-title {
    font-size: 1.1875rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.2rem;
}

.hp-card-stat {
    font-size: 0.8125rem;
    color: #64748b;
    margin-bottom: 0.85rem;
}

.hp-quote-box {
    font-size: 0.875rem;
    color: #334155;
    font-style: italic;
    background-color: #f8fafc;
    border-left: 2px solid #cbd5e1;
    padding: 0.65rem 0.85rem;
    border-radius: 0 6px 6px 0;
    margin-bottom: 0.75rem;
    line-height: 1.45;
}

.hp-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 0.5rem;
}

.hp-evidence-link {
    color: #2563eb;
    font-weight: 600;
    font-size: 0.8125rem;
    cursor: pointer;
    text-decoration: none;
}

.hp-evidence-link:hover {
    text-decoration: underline;
}

/* What guests like (Strengths) */
.hp-strength-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #16a34a;
    border-radius: 12px;
    padding: 1.25rem 1.35rem;
    box-shadow: 0 4px 12px -2px rgba(15, 23, 42, 0.04);
}

.hp-strength-title {
    font-size: 1.0625rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.15rem;
}

.hp-strength-positive {
    font-size: 0.875rem;
    font-weight: 700;
    color: #16a34a;
    margin-bottom: 0.65rem;
}

.hp-strength-quote {
    font-size: 0.875rem;
    color: #475569;
    font-style: italic;
    line-height: 1.4;
}

/* What guests talk about (8 Topics) */
.hp-topics-grid-8 {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 0.85rem;
    margin-bottom: 2.5rem;
}

.hp-topic-mini-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 0.85rem 0.65rem 0.75rem 0.65rem;
    text-align: center;
    box-shadow: 0 2px 6px -1px rgba(15, 23, 42, 0.03);
    position: relative;
    overflow: hidden;
}

.hp-topic-name {
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 600;
    margin-bottom: 0.4rem;
}

.hp-topic-pct {
    font-size: 1.35rem;
    font-weight: 800;
    margin-bottom: 0.5rem;
}

.hp-indicator-bar {
    height: 3px;
    width: 60%;
    margin: 0 auto;
    border-radius: 9999px;
}

/* Bottom 2-Column Section */
.hp-bottom-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.hp-bottom-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1.5rem;
    box-shadow: 0 4px 12px -2px rgba(15, 23, 42, 0.04);
}

.hp-box-title {
    font-size: 1.2rem;
    font-weight: 800;
    color: #0f172a;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.2rem;
}

.hp-box-sub {
    font-size: 0.8125rem;
    color: #64748b;
    margin-bottom: 1.25rem;
}

/* Comparison Table */
.hp-comp-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1.25rem;
}

.hp-comp-table th {
    text-align: left;
    font-size: 0.75rem;
    font-weight: 600;
    color: #94a3b8;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #f1f5f9;
}

.hp-comp-table td {
    padding: 0.85rem 0;
    font-size: 0.875rem;
    border-bottom: 1px solid #f8fafc;
}

.hp-comp-topic {
    font-weight: 600;
    color: #334155;
}

.hp-alert-banner {
    background-color: #fefce8;
    border: 1px solid #fef08a;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-size: 0.8125rem;
    color: #854d0e;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* 3 Actions List */
.hp-action-item {
    display: flex;
    align-items: flex-start;
    gap: 0.85rem;
    padding: 0.85rem 0;
    border-bottom: 1px solid #f8fafc;
}

.hp-action-item:last-child {
    border-bottom: none;
}

.hp-action-num {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background-color: #eff6ff;
    color: #2563eb;
    font-size: 0.75rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
}

.hp-action-heading {
    font-size: 0.9375rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.15rem;
}

.hp-action-desc {
    font-size: 0.8125rem;
    color: #64748b;
}

/* Evidence Dialog Content */
.hp-evidence-item {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 0.85rem;
}

.hp-evidence-header {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #64748b;
    margin-bottom: 0.4rem;
}

.hp-evidence-quote {
    font-size: 0.875rem;
    color: #1e293b;
    font-style: italic;
    line-height: 1.45;
}

/* Primary Button Styling Override for Streamlit */
div.stButton > button[kind="primary"] {
    background-color: #2563eb !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 0.65rem 1.5rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2) !important;
}

div.stButton > button[kind="primary"]:hover {
    background-color: #1d4ed8 !important;
    box-shadow: 0 6px 10px -1px rgba(37, 99, 235, 0.3) !important;
    transform: translateY(-1px) !important;
}

div.stButton > button[kind="secondary"] {
    background-color: #ffffff !important;
    color: #2563eb !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.8125rem !important;
}

div.stButton > button[kind="secondary"]:hover {
    border-color: #2563eb !important;
    background-color: #f8fafc !important;
}

/* Hide Streamlit default hamburger & footer */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""

def render_top_navbar(hotel_name=None, city=None, analyzed_reviews=None, on_change_callback=None):
    """Renders the top navbar matching image.png & image-1.png."""
    if hotel_name and city:
        right_html = f"""<div class="hp-nav-right">
<span class="hp-hotel-crumb">{hotel_name} · {city}</span>
<span class="hp-badge-pill">Expires in 2 days</span>
</div>"""
    else:
        right_html = """<div class="hp-nav-right">
<span class="hp-badge-pill">Demo Session</span>
</div>"""

    return f"""<div class="hp-navbar">
<div class="hp-logo">Hotel<span>Pulse</span></div>
{right_html}
</div>"""

def render_landing_hero():
    """Renders the hero headline and subtitle for the landing screen."""
    return """<div class="hp-landing-container">
<div class="hp-pill-tag">SIMPLE HOTEL INSIGHTS</div>
<div class="hp-hero-title">Know what your guests really think.</div>
<div class="hp-hero-subtitle">See what to fix, what guests love, and how you compare with nearby hotels.</div>
</div>"""

def render_dashboard_header(hotel_name, address, updated_date, review_count):
    """Renders dashboard header with metadata."""
    return f"""<div class="hp-dash-header">
<div>
<div class="hp-tag-blue">YOUR HOTEL</div>
<h1 class="hp-hotel-title">{hotel_name}</h1>
<div class="hp-hotel-sub">{address}</div>
</div>
<div class="hp-header-meta">
Updated {updated_date} · {review_count:,} reviews analyzed
</div>
</div>"""

def render_metrics_bar(overall_rating, positive_pct, needs_attention_pct, reviews_analyzed):
    """Renders the 4 metrics container."""
    return f"""<div class="hp-metrics-container">
<div class="hp-metric-item">
<div class="hp-metric-label">Overall rating</div>
<div class="hp-metric-val" style="color: #0f172a;">
<span style="color: #f59e0b; font-size: 1.5rem; vertical-align: middle;">★</span> {overall_rating:.1f}
</div>
<div class="hp-metric-sub">Guest rating</div>
</div>
<div class="hp-metric-item">
<div class="hp-metric-label">Positive</div>
<div class="hp-metric-val" style="color: #16a34a;">{positive_pct}%</div>
<div class="hp-metric-sub">Guests are happy</div>
</div>
<div class="hp-metric-item">
<div class="hp-metric-label">Needs attention</div>
<div class="hp-metric-val" style="color: #dc2626;">{needs_attention_pct}%</div>
<div class="hp-metric-sub">Negative reviews</div>
</div>
<div class="hp-metric-item">
<div class="hp-metric-label">Reviews analyzed</div>
<div class="hp-metric-val" style="color: #0f172a;">{reviews_analyzed:,}</div>
<div class="hp-metric-sub">Google + Tripadvisor</div>
</div>
</div>"""

def render_fix_cards_html(issues):
    """Renders the 3 'What should I fix?' cards."""
    cards_html = []
    for idx, issue in enumerate(issues, start=1):
        is_medium = issue.get("priority_level", "HIGH PRIORITY") == "MEDIUM"
        card_class = "hp-fix-card medium-priority" if is_medium else "hp-fix-card"
        circle_class = "hp-num-circle medium" if is_medium else "hp-num-circle"
        pill_class = "hp-priority-pill medium" if is_medium else "hp-priority-pill"

        cards_html.append(f"""<div class="{card_class}">
<div>
<div class="hp-fix-card-top">
<div class="{circle_class}">{idx}</div>
<div class="{pill_class}">{issue['priority_level']}</div>
</div>
<div class="hp-card-title">{issue['topic_name']}</div>
<div class="hp-card-stat">{issue['pct_reviews']}% of reviews · {issue['neg_mentions']} negative mentions</div>
<div class="hp-quote-box">"{issue['sample_quote']}"</div>
</div>
<div class="hp-card-footer">
<span>{issue['source']} · {issue['date']}</span>
</div>
</div>""")

    return f"""<div class="hp-cards-grid-3">{''.join(cards_html)}</div>"""

def render_strength_cards_html(strengths):
    """Renders the 3 'What guests like' cards."""
    cards_html = []
    for item in strengths:
        cards_html.append(f"""<div class="hp-strength-card">
<div class="hp-strength-title">{item['topic_name']}</div>
<div class="hp-strength-positive">{item['positive_pct']}% positive</div>
<div class="hp-strength-quote">"{item['quote']}"</div>
</div>""")

    return f"""<div class="hp-cards-grid-3">{''.join(cards_html)}</div>"""

def render_topics_mini_grid(topics_data):
    """Renders the 8 micro topic cards with indicator underlines."""
    cards_html = []
    for item in topics_data:
        pct = item['score_pct']
        if pct < 50:
            color = "#ef4444"
        elif pct < 65:
            color = "#f59e0b"
        else:
            color = "#16a34a"

        cards_html.append(f"""<div class="hp-topic-mini-card">
<div class="hp-topic-name">{item['name']}</div>
<div class="hp-topic-pct" style="color: {color};">{pct}%</div>
<div class="hp-indicator-bar" style="background-color: {color};"></div>
</div>""")

    return f"""<div class="hp-topics-grid-8">{''.join(cards_html)}</div>"""

def render_comparison_table_and_actions(comparison_rows, alert_text, actions):
    """Renders the bottom 2-column layout (Comparison Table + 3 Actions)."""
    table_rows_html = []
    for row in comparison_rows:
        gap = row['gap']
        gap_sign = f"+{gap}" if gap > 0 else f"{gap}"
        gap_color = "#16a34a" if gap > 0 else "#dc2626"
        you_color = "#16a34a" if row['you_pct'] >= 70 else ("#f59e0b" if row['you_pct'] >= 50 else "#dc2626")

        table_rows_html.append(f"""<tr>
<td class="hp-comp-topic">{row['topic']}</td>
<td style="color: {you_color}; font-weight: 700;">{row['you_pct']}%</td>
<td style="color: #475569; font-weight: 500;">{row['nearby_pct']}%</td>
<td style="color: {gap_color}; font-weight: 700;">{gap_sign}</td>
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

    return f"""<div class="hp-bottom-grid">
<div class="hp-bottom-card">
<div class="hp-box-title">🏨 How do you compare?</div>
<div class="hp-box-sub">Your hotel vs nearby hotels.</div>
<table class="hp-comp-table">
<thead>
<tr>
<th style="width: 35%;">Topic</th>
<th style="width: 20%;">You</th>
<th style="width: 25%;">Nearby</th>
<th style="width: 20%;">Gap</th>
</tr>
</thead>
<tbody>
{''.join(table_rows_html)}
</tbody>
</table>
<div class="hp-alert-banner">
<span>⚠️</span>
<span>{alert_text}</span>
</div>
</div>

<div class="hp-bottom-card">
<div class="hp-box-title">💡 Your next 3 actions</div>
<div class="hp-box-sub">Simple things you can act on.</div>
<div>
{''.join(actions_html)}
</div>
</div>
</div>"""
