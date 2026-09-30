import sys
from pathlib import Path

# Ensure src directory is in sys.path for local module resolution
src_dir = str(Path(__file__).resolve().parent.parent.parent)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import streamlit as st  # pyrefly: ignore [missing-import] # type: ignore
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

# Page configuration
st.set_page_config(
    page_title="HotelPulse - Know what your guests really think",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inject custom CSS design system
st.html(CUSTOM_CSS)

# Session state initialization - default to landing search screen
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "landing"

if "hotel_name" not in st.session_state:
    st.session_state.hotel_name = "Hotel Paradise"

if "city" not in st.session_state:
    st.session_state.city = "Mangalore"


# Mock evidence database matching design.md
MOCK_EVIDENCE = {
    "Cleanliness": [
        {
            "quote": "Rooms were not clean, especially the bathroom.",
            "source": "Google",
            "date": "12 Sep 2026",
            "reviewer": "Rahul Verma",
            "sentiment": "negative",
            "severity": 3,
        },
        {
            "quote": "Bedsheets had stains and bathroom had water stagnation.",
            "source": "Google",
            "date": "04 Sep 2026",
            "reviewer": "Pooja Nair",
            "sentiment": "negative",
            "severity": 3,
        },
        {
            "quote": "Housekeeping did not clean the room until we called twice.",
            "source": "Tripadvisor",
            "date": "22 Aug 2026",
            "reviewer": "Vikram Sen",
            "sentiment": "negative",
            "severity": 2,
        },
    ],
    "Wi-Fi": [
        {
            "quote": "WiFi is very slow and keeps disconnecting.",
            "source": "Tripadvisor",
            "date": "8 Sep 2026",
            "reviewer": "Anand K.",
            "sentiment": "negative",
            "severity": 3,
        },
        {
            "quote": "Zero WiFi range on the 3rd floor rooms.",
            "source": "Google",
            "date": "29 Aug 2026",
            "reviewer": "Kavita S.",
            "sentiment": "negative",
            "severity": 2,
        },
    ],
    "Breakfast": [
        {
            "quote": "Breakfast was good but there were not many choices.",
            "source": "Google",
            "date": "6 Sep 2026",
            "reviewer": "Manish Rao",
            "sentiment": "mixed",
            "severity": 2,
        },
        {
            "quote": "Same idli sambar breakfast every morning with no fruits.",
            "source": "Google",
            "date": "18 Aug 2026",
            "reviewer": "Deepak G.",
            "sentiment": "negative",
            "severity": 2,
        },
    ],
}


# Evidence Dialog (Modal)
@st.dialog("Guest Review Evidence")
def show_evidence_modal(topic_name):
    quotes = MOCK_EVIDENCE.get(topic_name, [])
    st.markdown(f"### Verbatim Quotes: **{topic_name}**")
    st.caption("Verbatim substrings extracted directly from guest reviews.")

    if not quotes:
        st.info("No negative quotes recorded for this topic.")
        return

    for item in quotes:
        sev_stars = "⭐" * item["severity"]
        sev_color = "#dc2626" if item["sentiment"] == "negative" else "#d97706"
        st.html(
            f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:1rem; margin-bottom:0.75rem;">
                <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#64748b; margin-bottom:0.35rem;">
                    <span><b>{item['reviewer']}</b> ({item['source']})</span>
                    <span>{item['date']} · <span style="color:{sev_color}; font-weight:700;">{item['sentiment'].upper()}</span> ({sev_stars})</span>
                </div>
                <div style="font-size:0.925rem; font-style:italic; color:#1e293b; background:#f8fafc; padding:0.65rem 0.85rem; border-left:3px solid {sev_color}; border-radius:4px;">
                    "{item['quote']}"
                </div>
            </div>
            """
        )


# Sidebar controls for configuration & debugging
with st.sidebar:
    st.markdown("### ⚙️ Demo Controls")
    selected_view = st.radio(
        "Current Screen",
        options=["Landing / Search View", "Dashboard View"],
        index=0 if st.session_state.view_mode == "landing" else 1,
    )
    if selected_view == "Landing / Search View" and st.session_state.view_mode != "landing":
        st.session_state.view_mode = "landing"
        st.rerun()
    elif selected_view == "Dashboard View" and st.session_state.view_mode != "dashboard":
        st.session_state.view_mode = "dashboard"
        st.rerun()

    st.divider()
    st.markdown("### 📊 SerpApi Credit Status")
    st.metric(label="Searches Used This Month", value="14 / 250")
    st.progress(14 / 250)
    st.caption("Cached responses in SQLite: 100% hits")

    st.divider()
    st.markdown("### 🎯 Data Scope")
    st.slider("Max Own Reviews", min_value=20, max_value=200, value=100, step=10)
    st.slider("Max Competitor Reviews", min_value=10, max_value=80, value=40, step=5)
    st.checkbox("Google Maps", value=True)
    st.checkbox("Tripadvisor", value=True)


# ==========================================
# RENDER: Landing / Search View (image.png)
# ==========================================
if st.session_state.view_mode == "landing":
    st.html(
        render_top_navbar(
            hotel_name=st.session_state.hotel_name,
            city=st.session_state.city,
        )
    )
    st.html(render_landing_hero())

    # Centered search card container matching image.png
    col_l, col_center, col_r = st.columns([1, 1.4, 1])
    with col_center:
        with st.container(border=True):
            st.markdown('<label style="font-size:0.875rem; font-weight:600; color:#334155; margin-bottom:0.25rem; display:block;">Hotel name</label>', unsafe_allow_html=True)
            hotel_input = st.text_input(
                "Hotel name",
                value=st.session_state.hotel_name,
                label_visibility="collapsed",
                placeholder="Hotel Paradise",
            )

            st.markdown('<label style="font-size:0.875rem; font-weight:600; color:#334155; margin-top:0.85rem; margin-bottom:0.25rem; display:block;">City</label>', unsafe_allow_html=True)
            city_input = st.text_input(
                "City",
                value=st.session_state.city,
                label_visibility="collapsed",
                placeholder="Mangalore",
            )

            st.html("<div style='height: 1.25rem;'></div>")

            if st.button("Analyze my hotel →", type="primary", use_container_width=True):
                st.session_state.hotel_name = hotel_input or "Hotel Paradise"
                st.session_state.city = city_input or "Mangalore"
                st.session_state.view_mode = "dashboard"
                st.rerun()

            st.html('<div class="hp-subtext">We analyze available guest reviews from Google and Tripadvisor.</div>')


# ==========================================
# RENDER: Dashboard View (image-1.png & image-2.png)
# ==========================================
else:
    # Top navbar
    st.html(
        render_top_navbar(
            hotel_name=st.session_state.hotel_name,
            city=st.session_state.city,
        )
    )

    # Top action bar with "Change Hotel" button
    col_nav_l, col_nav_r = st.columns([4, 1])
    with col_nav_r:
        if st.button("← Search Another Hotel", type="secondary", use_container_width=True):
            st.session_state.view_mode = "landing"
            st.rerun()

    # Dashboard Header
    st.html(
        render_dashboard_header(
            hotel_name=st.session_state.hotel_name,
            address="Hampankatta, Mangalore",
            updated_date="28 Sep 2026",
            review_count=1248,
        )
    )

    # 4 Key Metrics Bar
    st.html(
        render_metrics_bar(
            overall_rating=4.2,
            positive_pct=72,
            needs_attention_pct=16,
            reviews_analyzed=1248,
        )
    )

    # ------------------------------------------
    # Section: 🔴 What should I fix?
    # ------------------------------------------
    st.html(
        """
        <div class="hp-section-header">🔴 What should I fix?</div>
        <div class="hp-section-sub">The three issues guests mention most often.</div>
        """
    )

    issues_data = [
        {
            "priority_level": "HIGH PRIORITY",
            "topic_name": "Cleanliness",
            "pct_reviews": 32,
            "neg_mentions": 68,
            "sample_quote": "Rooms were not clean, especially the bathroom.",
            "source": "Google",
            "date": "12 Sep 2026",
        },
        {
            "priority_level": "HIGH PRIORITY",
            "topic_name": "Wi-Fi",
            "pct_reviews": 28,
            "neg_mentions": 54,
            "sample_quote": "WiFi is very slow and keeps disconnecting.",
            "source": "Tripadvisor",
            "date": "8 Sep 2026",
        },
        {
            "priority_level": "MEDIUM",
            "topic_name": "Breakfast",
            "pct_reviews": 24,
            "neg_mentions": 39,
            "sample_quote": "Breakfast was good but there were not many choices.",
            "source": "Google",
            "date": "6 Sep 2026",
        },
    ]

    st.html(render_fix_cards_html(issues_data))

    # Interactive evidence triggers for the 3 fix cards
    col_ev1, col_ev2, col_ev3 = st.columns(3)
    with col_ev1:
        if st.button("View Cleanliness Evidence →", key="ev_clean", use_container_width=True):
            show_evidence_modal("Cleanliness")
    with col_ev2:
        if st.button("View Wi-Fi Evidence →", key="ev_wifi", use_container_width=True):
            show_evidence_modal("Wi-Fi")
    with col_ev3:
        if st.button("View Breakfast Evidence →", key="ev_bfast", use_container_width=True):
            show_evidence_modal("Breakfast")

    st.html("<div style='height: 1.5rem;'></div>")

    # ------------------------------------------
    # Section: 🟢 What guests like
    # ------------------------------------------
    st.html(
        """
        <div class="hp-section-header">🟢 What guests like</div>
        <div class="hp-section-sub">Keep doing these things.</div>
        """
    )

    strengths_data = [
        {
            "topic_name": "Staff",
            "positive_pct": 82,
            "quote": "Very friendly and helpful staff.",
        },
        {
            "topic_name": "Location",
            "positive_pct": 78,
            "quote": "Good location near the city center.",
        },
        {
            "topic_name": "Value for money",
            "positive_pct": 71,
            "quote": "Worth the price.",
        },
    ]

    st.html(render_strength_cards_html(strengths_data))

    # ------------------------------------------
    # Section: What guests talk about (8 Topics)
    # ------------------------------------------
    st.html(
        """
        <div class="hp-section-header" style="margin-top: 1rem;">What guests talk about</div>
        <div class="hp-section-sub">Topics mentioned in your reviews.</div>
        """
    )

    topics_grid_data = [
        {"name": "Cleanliness", "score_pct": 48},
        {"name": "Wi-Fi", "score_pct": 40},
        {"name": "Food", "score_pct": 55},
        {"name": "AC", "score_pct": 62},
        {"name": "Noise", "score_pct": 68},
        {"name": "Value", "score_pct": 71},
        {"name": "Location", "score_pct": 78},
        {"name": "Staff", "score_pct": 82},
    ]

    st.html(render_topics_mini_grid(topics_grid_data))

    # ------------------------------------------
    # Section: Bottom 2-Column (Competitors & Actions)
    # ------------------------------------------
    comparison_rows = [
        {"topic": "Cleanliness", "you_pct": 48, "nearby_pct": 72, "gap": -24},
        {"topic": "Wi-Fi", "you_pct": 40, "nearby_pct": 67, "gap": -27},
        {"topic": "Staff", "you_pct": 82, "nearby_pct": 78, "gap": 4},
        {"topic": "Location", "you_pct": 78, "nearby_pct": 79, "gap": 1},
    ]

    next_actions = [
        {
            "title": "Check housekeeping",
            "desc": "Focus on bathrooms and bedsheets.",
        },
        {
            "title": "Check Wi-Fi in rooms",
            "desc": "Guests report slow and unstable internet.",
        },
        {
            "title": "Review breakfast choices",
            "desc": "Guests want more variety.",
        },
    ]

    alert_message = "Cleanliness and Wi-Fi are your biggest gaps compared with nearby hotels."

    st.html(
        render_comparison_table_and_actions(
            comparison_rows=comparison_rows,
            alert_text=alert_message,
            actions=next_actions,
        )
    )
