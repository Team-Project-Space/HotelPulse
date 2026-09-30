"""HotelPulse Streamlit dashboard — real pipeline, not mock data."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Ensure src directory is in sys.path for local module resolution
src_dir = str(Path(__file__).resolve().parent.parent.parent)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import streamlit as st  # pyrefly: ignore [missing-import] # type: ignore

from hotelpulse.analysis.ranking import topic_label
from hotelpulse.app.components import (
    CUSTOM_CSS,
    render_top_navbar,
    render_landing_hero,
    render_dashboard_header,
    render_metrics_bar,
    render_fix_cards_html,
    render_strength_cards_html,
    render_topics_mini_grid,
    render_comparison_table_and_actions,
)
from hotelpulse.services.pipeline import (
    PipelineError,
    PipelineResult,
    analyze_hotel,
    build_evidence_map,
)

# Page configuration
st.set_page_config(
    page_title="HotelPulse - Know what your guests really think",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.html(CUSTOM_CSS)

# Session state
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "landing"
if "hotel_name" not in st.session_state:
    st.session_state.hotel_name = "OYO"
if "city" not in st.session_state:
    st.session_state.city = "Bangalore"
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "evidence" not in st.session_state:
    st.session_state.evidence = {}
if "error" not in st.session_state:
    st.session_state.error = None
if "ran_once" not in st.session_state:
    st.session_state.ran_once = False


def _score_pct(score: float | None) -> int:
    """Map 1-5 topic score onto the UI's 0-100 indicator."""
    if score is None:
        return 0
    return int(round(score / 5.0 * 100))


def _priority_label(score: float | None) -> str:
    if score is None:
        return "MEDIUM"
    return "HIGH PRIORITY" if score < 3.0 else "MEDIUM"


def _run_analysis(hotel_name: str, city: str) -> None:
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


# Evidence Dialog
@st.dialog("Guest Review Evidence")
def show_evidence_modal(topic_name: str) -> None:
    quotes = st.session_state.evidence.get(topic_name, [])
    st.markdown(f"### Verbatim Quotes: **{topic_name}**")
    st.caption("Verbatim substrings extracted directly from guest reviews.")

    if not quotes:
        st.info("No negative quotes recorded for this topic.")
        return

    for item in quotes:
        sev_stars = "⭐" * int(item.get("severity", 1))
        sev_color = "#dc2626" if item.get("sentiment") == "negative" else "#d97706"
        st.html(
            f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:1rem; margin-bottom:0.75rem;">
                <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#64748b; margin-bottom:0.35rem;">
                    <span><b>{item.get('reviewer', 'Guest')}</b> ({item.get('source', 'google maps')})</span>
                    <span>{item.get('date', '—')} · <span style="color:{sev_color}; font-weight:700;">{item.get('sentiment', '').upper()}</span> ({sev_stars})</span>
                </div>
                <div style="font-size:0.925rem; font-style:italic; color:#1e293b; background:#f8fafc; padding:0.65rem 0.85rem; border-left:3px solid {sev_color}; border-radius:4px;">
                    "{item.get('quote', '')}"
                </div>
            </div>
            """
        )


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


# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Demo Controls")
    selected_view = st.radio(
        "Current Screen",
        options=["Landing / Search View", "Dashboard View"],
        index=0 if st.session_state.view_mode == "landing" else 1,
        key="sidebar_view_radio",
    )
    if selected_view == "Landing / Search View" and st.session_state.view_mode != "landing":
        st.session_state.view_mode = "landing"
        st.rerun()
    elif selected_view == "Dashboard View" and st.session_state.view_mode != "dashboard":
        if st.session_state.analysis is None:
            st.info("Run an analysis first (or use the demo button on the landing screen).")
        st.session_state.view_mode = "dashboard"
        st.rerun()

    st.divider()
    _credit_block()

    st.divider()
    st.markdown("### 🎯 Demo")
    if st.button("Load demo: OYO · Bangalore", use_container_width=True):
        with st.spinner("Analyzing OYO Bangalore (cached SerpApi + Gemini tags)…"):
            _run_analysis("OYO", "Bangalore")
        st.rerun()


# ==========================================
# Landing / Search View
# ==========================================
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
            st.markdown(
                '<label style="font-size:0.875rem; font-weight:600; color:#334155; margin-bottom:0.25rem; display:block;">Hotel name</label>',
                unsafe_allow_html=True,
            )
            hotel_input = st.text_input(
                "Hotel name",
                value=st.session_state.hotel_name,
                label_visibility="collapsed",
                placeholder="OYO",
                key="hotel_name_input",
            )

            st.markdown(
                '<label style="font-size:0.875rem; font-weight:600; color:#334155; margin-top:0.85rem; margin-bottom:0.25rem; display:block;">City</label>',
                unsafe_allow_html=True,
            )
            city_input = st.text_input(
                "City",
                value=st.session_state.city,
                label_visibility="collapsed",
                placeholder="Bangalore",
                key="city_input",
            )

            st.html("<div style='height: 1.25rem;'></div>")

            if st.button("Analyze my hotel →", type="primary", use_container_width=True):
                hotel_name = (hotel_input or "").strip() or "OYO"
                city = (city_input or "").strip() or "Bangalore"
                with st.spinner("Searching Google Maps, fetching reviews, tagging with Gemini…"):
                    _run_analysis(hotel_name, city)
                st.rerun()

            st.html(
                '<div class="hp-subtext">We analyze available guest reviews from Google Maps (Tripadvisor in a later phase).</div>'
            )
            if st.session_state.error:
                st.error(st.session_state.error)


# ==========================================
# Dashboard View
# ==========================================
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

    # Rebuild evidence from the latest result (covers reruns)
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

    if result.warnings:
        for w in result.warnings:
            st.warning(w)

    avg_rating = overall.average_rating if overall.average_rating is not None else 0.0
    pos_pct = int(round(overall.positive_pct or 0.0))
    attn_pct = int(round(overall.negative_pct or 0.0))

    st.html(
        render_metrics_bar(
            overall_rating=avg_rating,
            positive_pct=pos_pct,
            needs_attention_pct=attn_pct,
            reviews_analyzed=analysis.reviews_analyzed,
        )
    )

    # 🔴 What should I fix?
    st.html(
        """
        <div class="hp-section-header">🔴 What should I fix?</div>
        <div class="hp-section-sub">The three issues guests mention most often.</div>
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
                "priority_level": _priority_label(issue.topic_score),
                "topic_name": label,
                "pct_reviews": pct,
                "neg_mentions": issue.negative_count,
                "sample_quote": sample.quote if sample else "No verbatim quote yet.",
                "source": (
                    review.source.replace("_", " ") if review else "google maps"
                ),
                "date": (
                    review.review_date.strftime("%d %b %Y")
                    if review and review.review_date
                    else "—"
                ),
            }
        )

    # Pad to 3 cards so the grid stays balanced when data is thin
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

    st.html("<div style='height: 1.5rem;'></div>")

    # 🟢 What guests like
    st.html(
        """
        <div class="hp-section-header">🟢 What guests like</div>
        <div class="hp-section-sub">Keep doing these things.</div>
        """
    )

    strengths_data = []
    for s in analysis.strengths:
        quote = s.quotes[0].quote if s.quotes else "Guests mention this often."
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

    # What guests talk about
    st.html(
        """
        <div class="hp-section-header" style="margin-top: 1rem;">What guests talk about</div>
        <div class="hp-section-sub">Topics mentioned in your reviews.</div>
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
        topics_grid_data = [{"name": "No topics yet", "score_pct": 0}]
    st.html(render_topics_mini_grid(topics_grid_data))

    # Comparison + actions
    st.html(
        """
        <div class="hp-section-header" style="margin-top: 1rem;">How do you compare?</div>
        <div class="hp-section-sub">Your hotel vs nearby hotels from the same search.</div>
        """
    )

    comparison_rows = []
    for row in comparison.rows:
        if row.own_score is None and row.competitor_avg is None:
            continue
        own_pct = _score_pct(row.own_score)
        nearby_pct = _score_pct(row.competitor_avg)
        gap = own_pct - nearby_pct if (row.own_score is not None and row.competitor_avg is not None) else 0
        comparison_rows.append(
            {
                "topic": topic_label(row.topic),
                "you_pct": own_pct,
                "nearby_pct": nearby_pct,
                "gap": gap,
            }
        )

    if not comparison_rows:
        comparison_rows = [
            {
                "topic": "Not enough comparison data",
                "you_pct": 0,
                "nearby_pct": 0,
                "gap": 0,
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
    for i, issue in enumerate(analysis.fix_first[:3], start=1):
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
            "No nearby competitor reviews cached yet — "
            + alert_message
        )

    st.html(
        render_comparison_table_and_actions(
            comparison_rows=comparison_rows,
            alert_text=alert_message,
            actions=next_actions[:3],
        )
    )
