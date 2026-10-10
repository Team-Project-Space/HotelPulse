"""HotelPulse Streamlit dashboard — real pipeline, redesigned premium SaaS UI.

The pipeline, scoring, caching and evidence logic are unchanged; this file
only changes what is rendered and how. Session-state keys and widget keys are
kept identical so history and tests continue to work.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Ensure src directory is in sys.path for local module resolution
src_dir = str(Path(__file__).resolve().parent.parent.parent)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import streamlit as st  # pyrefly: ignore [missing-import] # type: ignore

from hotelpulse.analysis.ranking import (
    format_gap,
    priority_label,
    topic_label,
    valid_score,
)
from hotelpulse.app.components import (
    CUSTOM_CSS,
    render_comparison_table_and_actions,
    render_dashboard_header,
    render_fix_cards_html,
    render_landing_hero,
    render_metrics_bar,
    render_source_status,
    render_strength_cards_html,
    render_topics_mini_grid,
    render_top_navbar,
)
from hotelpulse.models import Review, Source
from hotelpulse.services.pipeline import (
    PipelineError,
    PipelineResult,
    analyze_hotel,
    build_evidence_map,
)

# Page configuration
st.set_page_config(
    page_title="HotelPulse · Guest Review Intelligence",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.html(CUSTOM_CSS)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "view_mode": "landing",
    "hotel_name": "OYO",
    "city": "Bangalore",
    "analysis": None,
    "evidence": {},
    "error": None,
    "ran_once": False,
    "warnings_seen": [],
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _score_pct(score: float | None) -> int | None:
    """Map a 1–5 topic score onto the UI's 0–100 indicator. None passes through."""
    if score is None:
        return None
    return int(round(score / 5.0 * 100))


def _run_analysis(hotel_name: str, city: str) -> None:
    """Run the pipeline, catch every failure, and route to the dashboard."""
    try:
        result = analyze_hotel(hotel_name, city, refresh=False)
    except PipelineError as exc:
        st.session_state.error = str(exc)
        st.session_state.analysis = None
        st.session_state.evidence = {}
        st.session_state.view_mode = "dashboard"
        return
    except Exception as exc:  # noqa: BLE001 — surface any pipeline failure in UI
        st.session_state.error = f"Analysis failed: {exc}"
        st.session_state.analysis = None
        st.session_state.evidence = {}
        st.session_state.view_mode = "dashboard"
        return

    st.session_state.analysis = result
    st.session_state.evidence = build_evidence_map(result)
    st.session_state.error = None
    st.session_state.ran_once = True
    st.session_state.hotel_name = result.hotel_name
    st.session_state.city = city
    st.session_state.view_mode = "dashboard"


# ---------------------------------------------------------------------------
# Sidebar wiring (unchanged contract)
# ---------------------------------------------------------------------------
_LANDING_OPTION = "Landing / Search View"
_DASHBOARD_OPTION = "Dashboard View"


def _view_option(view_mode: str) -> str:
    return _LANDING_OPTION if view_mode == "landing" else _DASHBOARD_OPTION


def _on_view_change() -> None:
    """Sidebar radio -> view_mode.

    Runs only when the user actually changes the radio, so a programmatic
    view change made by buttons is never undone.
    """
    st.session_state.view_mode = (
        "landing" if st.session_state.sidebar_view_radio == _LANDING_OPTION else "dashboard"
    )


def _sync_widget_text(key: str, value: str) -> None:
    """Push a canonical value into a text input exactly once.

    A widget key wins over `value=` from the second render onward, so without
    this the landing inputs never show the hotel/city the analysis used.
    """
    marker = f"{key}__synced"
    if st.session_state.get(marker) == value:
        return
    st.session_state[key] = value
    st.session_state[marker] = value


# ---------------------------------------------------------------------------
# Evidence modal
# ---------------------------------------------------------------------------
@st.dialog("Guest Review Evidence")
def show_evidence_modal(topic_name: str) -> None:
    quotes = st.session_state.evidence.get(topic_name, [])
    st.markdown(f"### Verbatim quotes: **{topic_name}**")
    st.caption("Verbatim substrings extracted directly from guest reviews.")

    if not quotes:
        st.info("No quotes recorded for this topic.")
        return

    for item in quotes:
        sev_stars = "★" * int(item.get("severity", 1))
        sev_color = "#dc2626" if item.get("sentiment") == "negative" else "#d97706"
        st.html(
            f"""
            <div style="background:var(--hp-surface); border:1px solid var(--hp-border); border-radius:12px; padding:1rem; margin-bottom:0.75rem;">
                <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:var(--hp-text-3); margin-bottom:0.35rem;">
                    <span><b>{item.get('reviewer', 'Guest')}</b> · {item.get('source', 'review')}</span>
                    <span>{item.get('date', '—')} · <span style="color:{sev_color}; font-weight:700;">{item.get('sentiment', '').upper()}</span> ({sev_stars})</span>
                </div>
                <div style="font-size:0.925rem; font-style:italic; color:var(--hp-text); background:var(--hp-surface-2); padding:0.65rem 0.85rem; border-left:3px solid {sev_color}; border-radius:0 8px 8px 0;">
                    "{item.get('quote', '')}"
                </div>
                <div style="font-size:0.75rem; color:var(--hp-text-4); margin-top:0.4rem;">Verified verbatim against the raw review text</div>
            </div>
            """
        )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _credit_block() -> None:
    result: PipelineResult | None = st.session_state.analysis
    st.markdown("### 📊 SerpApi Credit Status")
    if result is not None:
        used = result.budget.calls_this_month
        budget = max(1, result.budget.monthly_budget)
        st.metric(label="Searches Used This Month", value=f"{used} / {budget}")
        st.progress(min(1.0, used / budget))
        st.caption(
            f"Cached responses: {result.budget.cache_hits} · "
            f"LLM tagged this run: {result.tagged_this_run}"
        )
    else:
        st.metric(label="Searches Used This Month", value="—")
        st.caption("Run an analysis to see live credit usage.")


with st.sidebar:
    st.markdown("### ⚙️ Demo Controls")
    st.session_state.sidebar_view_radio = _view_option(st.session_state.view_mode)
    st.radio(
        "Current Screen",
        options=[_LANDING_OPTION, _DASHBOARD_OPTION],
        key="sidebar_view_radio",
        on_change=_on_view_change,
    )

    st.divider()
    _credit_block()

    st.divider()
    st.markdown("### 🎯 Demo")
    if st.button("Load demo: OYO · Bangalore", use_container_width=True):
        with st.spinner("Analyzing OYO Bangalore (cached SerpApi + Gemini tags)…"):
            _run_analysis("OYO", "Bangalore")
        st.rerun()


# ---------------------------------------------------------------------------
# Landing / Search View
# ---------------------------------------------------------------------------
if st.session_state.view_mode == "landing":
    st.html(
        render_top_navbar(
            hotel_name=st.session_state.hotel_name,
            city=st.session_state.city,
        )
    )
    st.html(render_landing_hero())

    col_l, col_center, col_r = st.columns([1, 1.4, 1])
    with col_center:
        with st.container(border=True):
            _sync_widget_text("hotel_name_input", st.session_state.hotel_name)
            st.markdown(
                '<label style="font-size:0.875rem; font-weight:600; color:var(--hp-text-2); margin-bottom:0.25rem; display:block;">Hotel name</label>',
                unsafe_allow_html=True,
            )
            hotel_input = st.text_input(
                "Hotel name",
                value=st.session_state.hotel_name,
                label_visibility="collapsed",
                placeholder="e.g. Hotel O by OYO Manyata Stay Inn",
                key="hotel_name_input",
            )

            _sync_widget_text("city_input", st.session_state.city)
            st.markdown(
                '<label style="font-size:0.875rem; font-weight:600; color:var(--hp-text-2); margin-top:0.85rem; margin-bottom:0.25rem; display:block;">City</label>',
                unsafe_allow_html=True,
            )
            city_input = st.text_input(
                "City",
                value=st.session_state.city,
                label_visibility="collapsed",
                placeholder="e.g. Bangalore",
                key="city_input",
            )

            st.html("<div style='height: 1rem;'></div>")

            if st.button("Analyze my hotel", type="primary", use_container_width=True):
                hotel_name = (hotel_input or "").strip() or "OYO"
                city = (city_input or "").strip() or "Bangalore"
                with st.spinner("Searching Google Maps · fetching available reviews · tagging topics with Gemini…"):
                    _run_analysis(hotel_name, city)
                st.rerun()

            st.html(
                '<div class="hp-subtext">Searches Google Maps for your hotel, collects available guest reviews, then tags topics and sentiment with free LLM analysis.</div>'
            )
            if st.session_state.error:
                st.error(st.session_state.error)


# ---------------------------------------------------------------------------
# Dashboard View
# ---------------------------------------------------------------------------
else:
    st.html(
        render_top_navbar(
            hotel_name=st.session_state.hotel_name,
            city=st.session_state.city,
        )
    )

    col_nav_l, col_nav_r = st.columns([4, 1])
    with col_nav_r:
        if st.button("← Search Another Hotel", type="secondary", use_container_width=True):
            st.session_state.view_mode = "landing"
            st.rerun()

    result: PipelineResult | None = st.session_state.analysis

    if result is None:
        st.info(
            "No analysis yet. Go back to search and click **Analyze my hotel**, "
            "or use **Load demo: OYO · Bangalore** in the sidebar."
        )
        if st.session_state.error:
            st.error(st.session_state.error)
        st.stop()

    analysis = result.analysis
    hotel = analysis.hotel
    overall = analysis.overall
    comparison = result.comparison

    st.session_state.evidence = build_evidence_map(result)

    updated = "—"
    if analysis.data_updated_at:
        try:
            updated = date.fromisoformat(analysis.data_updated_at[:10]).strftime("%d %b %Y")
        except ValueError:
            updated = analysis.data_updated_at[:10]

    st.html(
        render_dashboard_header(
            hotel_name=hotel.name,
            address=hotel.address or result.city,
            updated_date=updated,
            review_count=analysis.reviews_analyzed,
        )
    )

    # --- Honest source-status chips ----------------------------------------
    maps_reviews = [r for r in analysis.reviews if r.source == Source.google_maps.value]
    ta_reviews = [r for r in analysis.reviews if r.source == Source.tripadvisor.value]
    ta_note = None
    for w in result.warnings:
        if "Tripadvisor" in w or "TripAdvisor" in w:
            ta_note = w.replace("Tripadvisor: ", "").replace("TripAdvisor: ", "")
            break
    st.html(
        render_source_status(
            maps_available=len(maps_reviews) > 0,
            tripadvisor_available=len(ta_reviews) > 0,
            tripadvisor_note=ta_note,
            no_reviews=len(analysis.reviews) == 0,
        )
    )

    # --- KPI cards ----------------------------------------------------------
    pos_pct = overall.positive_pct if overall.positive_pct is not None else None
    attn_pct = overall.negative_pct if overall.negative_pct is not None else None
    coverage = ("Google Maps + TripAdvisor" if (maps_reviews and ta_reviews)
                else "Google Maps only" if maps_reviews
                else "TripAdvisor only" if ta_reviews
                else "No sources")

    st.html(
        render_metrics_bar(
            overall_rating=overall.average_rating,
            positive_pct=pos_pct,
            needs_attention_pct=attn_pct,
            reviews_analyzed=analysis.reviews_analyzed,
            coverage_label=coverage,
        )
    )

    # --- Fix First ----------------------------------------------------------
    st.html(
        """
        <div class="hp-section-header"><span class="hp-section-icon red">①</span>What should I fix?</div>
        <div class="hp-section-sub">The three issues guests mention most, backed by verbatim review evidence.</div>
        """
    )

    issues_data = []
    for idx, issue in enumerate(analysis.fix_first, start=1):
        label = topic_label(issue.topic)
        pct = (
            int(round(100.0 * issue.mention_count / analysis.reviews_analyzed))
            if analysis.reviews_analyzed
            else 0
        )
        sample = issue.quotes[0] if issue.quotes else None
        review = None
        if sample:
            review = next(
                (r for r in analysis.reviews if r.review_id == sample.review_id),
                None,
            )
        issues_data.append(
            {
                "priority_level": priority_label(issue.topic_score),
                "topic_name": label,
                "pct_reviews": pct,
                "neg_mentions": issue.negative_count,
                "sample_quote": sample.quote if sample else "No verbatim quote yet.",
                "source": (
                    review.source.replace("_", " ") if review else "review"
                ),
                "date": (
                    review.review_date.strftime("%d %b %Y")
                    if review and review.review_date
                    else "—"
                ),
            }
        )

    while len(issues_data) < 3:
        issues_data.append(
            {
                "priority_level": "MEDIUM",
                "topic_name": "Not enough data",
                "pct_reviews": 0,
                "neg_mentions": 0,
                "sample_quote": "Analyze more reviews to surface additional issues.",
                "source": "—",
                "date": "—",
            }
        )

    st.html(render_fix_cards_html(issues_data[:3]))

    col_ev1, col_ev2, col_ev3 = st.columns(3)
    ev_labels = [item["topic_name"] for item in issues_data[:3]]
    for col, label in zip((col_ev1, col_ev2, col_ev3), ev_labels):
        with col:
            if label != "Not enough data" and st.button(
                f"View {label} Evidence →", key=f"ev_{label}", use_container_width=True
            ):
                show_evidence_modal(label)

    st.html("<div style='height: 1.25rem;'></div>")

    # --- What guests like ----------------------------------------------------
    st.html(
        """
        <div class="hp-section-header"><span class="hp-section-icon teal">✓</span>What guests like</div>
        <div class="hp-section-sub">Keep doing these things.</div>
        """
    )

    strengths_data = []
    for s in analysis.strengths:
        quote = s.quotes[0].quote if s.quotes else "Guests mention this topic often."
        strengths_data.append(
            {
                "topic_name": topic_label(s.topic),
                "positive_pct": int(round(s.positive_pct)),
                "quote": quote,
            }
        )
    if not strengths_data:
        strengths_data = [
            {
                "topic_name": "Not enough data",
                "positive_pct": 0,
                "quote": "Need more positive mentions to surface strengths.",
            }
        ]
        while len(strengths_data) < 3:
            strengths_data.append(dict(strengths_data[0]))

    st.html(render_strength_cards_html(strengths_data[:3]))

    # --- Topic grid ------------------------------------------------------------
    st.html(
        """
        <div class="hp-section-header"><span class="hp-section-icon navy">▦</span>What guests talk about</div>
        <div class="hp-section-sub">Topic scores (1–5 scale shown as % fill). “Not enough data” means fewer than 3 tagged mentions — it is not a zero score.</div>
        """
    )

    topics_grid_data = [
        {
            "name": topic_label(ts.topic),
            "score_pct": _score_pct(ts.score),
        }
        for ts in analysis.topic_scores
        if ts.mention_count > 0
    ]
    if not topics_grid_data:
        topics_grid_data = [{"name": "No topics yet", "score_pct": None}]
    st.html(render_topics_mini_grid(topics_grid_data))

    # --- Comparison + actions ----------------------------------------------------
    st.html(
        """
        <div class="hp-section-header"><span class="hp-section-icon blue">⇄</span>How do you compare?</div>
        <div class="hp-section-sub">Valid topic scores vs nearby hotels. Gap = your score − nearby average, on the raw 1–5 scale (never a percentage).</div>
        """
    )

    comparison_rows = []
    eligible = [
        r for r in comparison.rows
        if valid_score(r.own_score) and valid_score(r.competitor_avg)
    ]
    for row in eligible:
        gap_text = format_gap(row.own_score - row.competitor_avg)
        comparison_rows.append(
            {
                "topic": topic_label(row.topic),
                "you_pct": int(round(row.own_score / 5 * 100)),
                "nearby_pct": int(round(row.competitor_avg / 5 * 100)),
                "gap": gap_text,
            }
        )

    if not comparison_rows:
        comparison_rows = [
            {
                "topic": "Not enough comparison data yet.",
                "you_pct": None,
                "nearby_pct": None,
                "gap": None,
            }
        ]

    action_templates = {
        topic_label(i.topic): (
            f"Check {topic_label(i.topic).lower()}",
            f"Guests flag this often ({i.negative_count} negative mentions).",
        )
        for i in analysis.fix_first
    }
    next_actions = []
    for issue in analysis.fix_first[:3]:
        title, desc = action_templates.get(
            topic_label(issue.topic),
            (f"Review {topic_label(issue.topic).lower()}", "Guests mention this topic."),
        )
        next_actions.append({"title": title, "desc": desc})
    if not next_actions:
        next_actions = [
            {
                "title": "Keep collecting reviews",
                "desc": "More data will unlock fix-first priorities.",
            }
        ]
        while len(next_actions) < 3:
            next_actions.append(dict(next_actions[0]))

    alert_message = comparison.alert_text or "Not enough comparison data yet."
    if not comparison.competitors:
        alert_message = (
            "No nearby competitor reviews cached yet — " + alert_message
        )

    st.html(
        render_comparison_table_and_actions(
            comparison_rows=comparison_rows,
            alert_text=alert_message,
            actions=next_actions[:3],
        )
    )
