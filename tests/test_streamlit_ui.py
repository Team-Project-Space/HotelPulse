"""UI regression tests for the Streamlit dashboard.

The bug these pin: the sidebar "Current Screen" radio used to run its
view_mode sync unconditionally on every rerun. Because a widget key beats
`index=` after the first render, the radio kept answering "Landing", so it
undid the transition the Analyze button had just made — the button looked
like it did nothing even though the pipeline had run.

Everything here is offline: `analyze_hotel` is monkeypatched, so no SerpApi
or LLM call is made (tests/conftest.py `forbid_network` would fail loudly).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from hotelpulse.models import (
    AnalysisResult,
    ApiBudget,
    ComparisonResult,
    CompetitorRow,
    Hotel,
    Issue,
    OverallStats,
    Review,
    Sentiment,
    Strength,
    Topic,
    TopicMention,
    TopicScore,
)
from hotelpulse.services import pipeline as pipeline_mod
from hotelpulse.services.pipeline import PipelineError, PipelineResult

APP_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "hotelpulse"
    / "app"
    / "streamlit_app.py"
)

LANDING = "Landing / Search View"
DASHBOARD = "Dashboard View"

DASHBOARD_SECTIONS = (
    "What should I fix",
    "What guests like",
    "What guests talk about",
    "How do you compare",
)

OWN = Hotel(
    hotel_id="google_maps:own-cid",
    source="google_maps",
    source_id="own-cid",
    name="Hotel O by OYO Manyata Stay Inn",
    address="Bengaluru, Karnataka",
    rating=4.6,
    review_count=11,
    is_own=True,
)

REVIEWS = [
    Review(
        review_id="r1",
        hotel_id=OWN.hotel_id,
        source="google_maps",
        rating=3.0,
        text="The rooms were dusty and the check-in staff were rude.",
        review_date=date(2026, 1, 10),
        reviewer="Asha",
    ),
    Review(
        review_id="r2",
        hotel_id=OWN.hotel_id,
        source="google_maps",
        rating=5.0,
        text="Great location and good value for money.",
        review_date=date(2026, 2, 2),
        reviewer="Ravi",
    ),
]


def _mention(review_id: str, topic: Topic, sentiment: Sentiment, quote: str) -> TopicMention:
    return TopicMention(
        review_id=review_id,
        topic=topic,
        sentiment=sentiment,
        severity=3 if sentiment is Sentiment.negative else 2,
        quote=quote,
    )


def build_result(city: str = "Bangalore") -> PipelineResult:
    """A small but structurally complete PipelineResult the dashboard can render."""
    analysis = AnalysisResult(
        hotel=OWN,
        reviews_analyzed=len(REVIEWS),
        overall=OverallStats(
            average_rating=4.6,
            reviews_analyzed=len(REVIEWS),
            positive_pct=72.0,
            negative_pct=16.0,
            mixed_pct=12.0,
        ),
        topic_scores=[
            TopicScore(
                topic=Topic.cleanliness,
                score=2.4,
                mention_count=6,
                negative_count=5,
                positive_count=1,
                mixed_count=0,
            ),
            TopicScore(
                topic=Topic.value,
                score=4.5,
                mention_count=5,
                negative_count=0,
                positive_count=5,
                mixed_count=0,
            ),
        ],
        fix_first=[
            Issue(
                topic=Topic.cleanliness,
                priority=7.5,
                mention_count=6,
                negative_count=5,
                topic_score=2.4,
                quotes=[
                    _mention(
                        "r1",
                        Topic.cleanliness,
                        Sentiment.negative,
                        "The rooms were dusty",
                    )
                ],
            )
        ],
        strengths=[
            Strength(
                topic=Topic.value,
                topic_score=4.5,
                mention_count=5,
                positive_pct=90.0,
                quotes=[
                    _mention(
                        "r2",
                        Topic.value,
                        Sentiment.positive,
                        "good value for money",
                    )
                ],
            )
        ],
        reviews=REVIEWS,
        data_updated_at="2026-02-02T00:00:00+00:00",
    )
    comparison = ComparisonResult(
        hotel_id=OWN.hotel_id,
        competitors=[
            Hotel(
                hotel_id="google_maps:nearby-cid",
                source="google_maps",
                source_id="nearby-cid",
                name="Nearby Stay",
                is_own=False,
            )
        ],
        rows=[
            CompetitorRow(
                topic=Topic.cleanliness,
                own_score=2.4,
                competitor_avg=3.6,
                gap=-1.2,
                own_mention_count=6,
                competitors_scoring_low=1,
                competitor_count=2,
                flag="Common in the area",
            )
        ],
        alert_text="Cleanliness is your biggest gap compared with nearby hotels.",
    )
    return PipelineResult(
        analysis=analysis,
        comparison=comparison,
        budget=ApiBudget(calls_this_month=7, monthly_budget=250, cache_hits=7),
        hotel_name=OWN.name,
        city=city,
        tagged_this_run=2,
    )


def _patch_pipeline(monkeypatch, result: PipelineResult | None = None) -> None:
    result = result or build_result()

    def fake_analyze(hotel_name: str, city: str, **kwargs) -> PipelineResult:
        return result

    monkeypatch.setattr(pipeline_mod, "analyze_hotel", fake_analyze)


def _app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=30)


def _find_button(at: AppTest, label_fragment: str):
    for button in list(at.button) + list(at.sidebar.button):
        if label_fragment in button.label:
            return button
    raise AssertionError(f"button containing {label_fragment!r} not found")


def _page_text(at: AppTest) -> str:
    parts = [str(getattr(el, "value", "")) for el in at.markdown]
    parts += [str(getattr(el, "value", "")) for el in at.get("html")]
    return "\n".join(parts)


def _assert_dashboard(at: AppTest) -> None:
    assert not at.exception, [e.message for e in at.exception]
    text = _page_text(at)
    for section in DASHBOARD_SECTIONS:
        assert section in text, f"dashboard section {section!r} missing"


def test_analyze_click_reaches_dashboard(monkeypatch) -> None:
    """The headline regression: Analyze must land on the dashboard."""
    _patch_pipeline(monkeypatch)
    at = _app()
    at.run()
    assert at.session_state["view_mode"] == "landing"

    _find_button(at, "Analyze my hotel").click().run()

    assert at.session_state["view_mode"] == "dashboard"
    assert at.session_state["analysis"] is not None
    _assert_dashboard(at)


def test_stale_sidebar_radio_does_not_revert_dashboard(monkeypatch) -> None:
    """A radio still answering 'Landing' must not undo a dashboard view."""
    _patch_pipeline(monkeypatch)
    at = _app()
    at.run()
    _find_button(at, "Analyze my hotel").click().run()
    assert at.session_state["view_mode"] == "dashboard"

    # Exactly the state the old code produced: app is on the dashboard, the
    # widget's stored value still says landing.
    at.session_state["sidebar_view_radio"] = LANDING
    at.run()

    assert at.session_state["view_mode"] == "dashboard"
    assert at.session_state["sidebar_view_radio"] == DASHBOARD
    _assert_dashboard(at)


def test_sidebar_radio_still_switches_views(monkeypatch) -> None:
    """The demo control keeps working: it is a real toggle, not decoration."""
    _patch_pipeline(monkeypatch)
    at = _app()
    at.run()

    at.radio(key="sidebar_view_radio").set_value(DASHBOARD).run()
    assert at.session_state["view_mode"] == "dashboard"

    at.radio(key="sidebar_view_radio").set_value(LANDING).run()
    assert at.session_state["view_mode"] == "landing"


def test_sidebar_radio_to_dashboard_without_results_shows_guidance(monkeypatch) -> None:
    """Switching to the dashboard with nothing analysed must explain itself."""
    _patch_pipeline(monkeypatch)
    at = _app()
    at.run()

    at.radio(key="sidebar_view_radio").set_value(DASHBOARD).run()

    assert at.session_state["view_mode"] == "dashboard"
    assert not at.exception, [e.message for e in at.exception]
    infos = " ".join(i.value for i in at.info)
    assert "No analysis yet" in infos


def test_sidebar_demo_button_reaches_dashboard(monkeypatch) -> None:
    _patch_pipeline(monkeypatch)
    at = _app()
    at.run()

    _find_button(at, "Load demo: OYO").click().run()

    assert at.session_state["view_mode"] == "dashboard"
    _assert_dashboard(at)


def test_search_another_hotel_returns_to_landing(monkeypatch) -> None:
    _patch_pipeline(monkeypatch)
    at = _app()
    at.run()
    _find_button(at, "Analyze my hotel").click().run()
    assert at.session_state["view_mode"] == "dashboard"

    _find_button(at, "Search Another Hotel").click().run()

    assert at.session_state["view_mode"] == "landing"


def test_pipeline_error_is_surfaced_on_the_dashboard(monkeypatch) -> None:
    """Failures must be visible instead of silently looking like a dead button."""

    def boom(*args, **kwargs):
        raise PipelineError("No Google Maps results for OYO, Bangalore.")

    monkeypatch.setattr(pipeline_mod, "analyze_hotel", boom)
    at = _app()
    at.run()

    _find_button(at, "Analyze my hotel").click().run()

    assert at.session_state["view_mode"] == "dashboard"
    assert at.session_state["analysis"] is None
    errors = " ".join(e.value for e in at.error)
    assert "No Google Maps results" in errors


def test_landing_input_keeps_what_the_user_typed(monkeypatch) -> None:
    """`_sync_widget_text` must not clobber in-progress typing on every rerun."""
    _patch_pipeline(monkeypatch)
    at = _app()
    at.run()

    at.text_input(key="hotel_name_input").set_value("Taj").run()
    assert at.session_state["hotel_name_input"] == "Taj"

    at.text_input(key="city_input").set_value("Mysuru").run()
    assert at.session_state["hotel_name_input"] == "Taj"
    assert at.session_state["city_input"] == "Mysuru"


def test_landing_input_updates_after_a_successful_analysis(monkeypatch) -> None:
    """After analysis the input shows the hotel the pipeline actually matched."""
    _patch_pipeline(monkeypatch, build_result())
    at = _app()
    at.run()

    _find_button(at, "Analyze my hotel").click().run()
    assert at.session_state["view_mode"] == "dashboard"

    _find_button(at, "Search Another Hotel").click().run()

    assert at.session_state["view_mode"] == "landing"
    assert at.session_state["hotel_name_input"] == OWN.name
