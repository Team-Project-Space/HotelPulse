# HotelPulse — Agent Context & Handoff Guide

> **Audience:** Next AI Agent working on HotelPulse.  
> Read this document first before writing code or running commands.

---

## 1. Project Overview & Goals

- **Project Name:** HotelPulse
- **Purpose:** A review intelligence and action-recommendation dashboard for independent hotel owners/managers (10–50 rooms, tier-2/3 Indian cities).
- **Core Value:**
  - Pulls reviews via SerpApi (Google Maps + Tripadvisor) without wasting credits.
  - LLM extracts 8 topic sentiments (Cleanliness, Staff, Food, WiFi, AC, Noise, Location, Value) across English, Hinglish, and regional languages.
  - Automatically ranks top 3 "Fix First" issues with verbatim review quotes as evidence.
  - Compares topic scores against 3–5 nearby competitors (distinguishing "Common in area" vs "Unique to you").
- **Track & Deadline:** SerpApi Hackathon (Commerce & Market Intelligence track). Target: **October 5, 2026**.
- **Key References:**
  - Full product specifications: [`PRD.md`](./PRD.md)
  - UI design reference images: [`playwright/playwright/design.md`](./playwright/playwright/design.md)
    - [`image.png`](./playwright/playwright/image.png) — Landing / Search View
    - [`image-1.png`](./playwright/playwright/image-1.png) — Dashboard Overview & "What should I fix?"
    - [`image-2.png`](./playwright/playwright/image-2.png) — Strengths, 8 Topic Micro-cards, Competitor Comparison, and 3 Next Actions

---

## 2. What Has Been Completed So Far

### A. Project Scaffolding
- [`pyproject.toml`](./pyproject.toml): Configured with required dependencies (`streamlit`, `plotly`, `pydantic`, `python-dotenv`, `tenacity`, `serpapi`, `anthropic`).
- [`README.md`](./README.md): Basic overview initialized.
- [`.vscode/settings.json`](./.vscode/settings.json): Configured Python interpreter to system Python 3.13 and added `./src` to `python.analysis.extraPaths`.

### B. Complete Frontend UI Implementation
The entire UI has been built and styled to match the design mockups:
1. **Design System & Components:** [`src/hotelpulse/app/components.py`](./src/hotelpulse/app/components.py)
   - Custom CSS injected for Plus Jakarta Sans / Inter typography, card shadows, pill badges, and layout grids.
   - `render_top_navbar`: HotelPulse brand logo, hotel crumb, and session badge.
   - `render_landing_hero`: Clean headline and subtitle for the landing screen.
   - `render_dashboard_header`: Hotel title, address, updated timestamp, and reviews analyzed count.
   - `render_metrics_bar`: 4-column metrics bar (`Overall rating ★ 4.2`, `Positive 72%`, `Needs attention 16%`, `Reviews analyzed 1,248`).
   - `render_fix_cards_html`: Top 3 "Fix First" cards with colored priority banners (`HIGH PRIORITY` / `MEDIUM`), negative mention counters, verbatim quotes, sources, and dates.
   - `render_strength_cards_html`: Top 3 positive strength cards with green left-accent borders.
   - `render_topics_mini_grid`: 8 horizontal topic micro-cards with color-coded bottom indicator bars (red, amber, green).
   - `render_comparison_table_and_actions`: Side-by-side bottom grid with:
     - Competitor comparison table (`Topic`, `You`, `Nearby`, `Gap`) and amber warning banner.
     - Top 3 actionable recommendations with blue circular number badges.
2. **Streamlit App Entrypoint:** [`src/hotelpulse/app/streamlit_app.py`](./src/hotelpulse/app/streamlit_app.py)
   - Dual-mode navigation:
     - **Landing / Search View** matching `image.png` (centered card with Hotel name, City input, and `Analyze my hotel →` CTA).
     - **Dashboard View** matching `image-1.png` and `image-2.png`.
   - Interactive evidence dialog (`@st.dialog`) displaying real verbatim review quotes with reviewer names, dates, sources, and sentiment stars when clicking `View Evidence →`.
   - Sidebar controls for SerpApi credit tracker (`14 / 250`), review caps, and source filters.

### C. Critical Fixes Made & Gotchas to Know
1. **HTML Rendering in Streamlit:**
   - In Markdown, lines indented with 4 or more spaces are converted into code blocks (`<pre><code>`).
   - All HTML in `components.py` has had multiline whitespace stripped, and `streamlit_app.py` uses `st.html()` (not `st.markdown`) to render pure HTML without code-block formatting.
2. **Module Import Path (`sys.path`):**
   - Streamlit scripts run with `__file__` directory as root. We added automatic `sys.path.insert(0, src_dir)` at the top of `streamlit_app.py` so `hotelpulse` imports cleanly from any directory.
3. **Windows Application Control (WDAC Error 4551):**
   - On this machine, running `.venv\Scripts\python.exe` is blocked by Windows security policy.
   - **Always run commands using the system `py` command** (e.g. `py -m streamlit run ...`, `py -m pytest ...`), which points to `C:\Users\USER\AppData\Local\Programs\Python\Python313\python.exe`.

---

## 3. How to Run and Test the App

From the project root:
```powershell
py -m streamlit run src/hotelpulse/app/streamlit_app.py
```
App will be accessible at: `http://localhost:8501`.

---

## 4. Next Steps & Instructions for the Next Agent

The UI is ready. Next is implementing the backend according to Section 16 of [`PRD.md`](./PRD.md).

### **Phase 1: Database & SerpApi Caching (Next Priority)**
1. **Database Layer:**
   - Create `src/hotelpulse/db/schema.sql` (schema is defined in Section 10 of `PRD.md`):
     - `api_cache`: SHA256 keyed cache of all raw SerpApi responses.
     - `hotels`: Hotel metadata (`hotel_id`, `name`, `address`, `lat`, `lng`, `rating`, `review_count`, `is_own`).
     - `reviews`: Individual review records (`review_id`, `hotel_id`, `source`, `rating`, `text`, `review_date`, `reviewer`, `language`).
     - `mentions`: Topic sentiment mentions (`topic`, `sentiment`, `severity`, `quote`, `quote_en`, `prompt_version`).
     - `tagged_reviews`: Tracking reviews already processed to prevent re-calling LLM.
   - Create `src/hotelpulse/db/connection.py` (`get_conn()`, `init_db()`).
   - Create `src/hotelpulse/db/repo.py` (CRUD helpers for cache, hotels, reviews, and mentions).
2. **SerpApi Client Layer:**
   - Create `src/hotelpulse/serp/client.py`:
     - Implement `cached_search(engine, params)` wrapper.
     - Cache key = `sha256(engine + sorted_params_json)`.
     - If cached in `api_cache` and not `refresh=True`, return cached response.
     - Track monthly API call count against the 250 credit budget.
   - Create `src/hotelpulse/serp/maps.py` for finding hotel and nearby competitors (`engine=google_maps`).
   - Create `src/hotelpulse/serp/reviews_maps.py` for paginated Google Maps reviews (`engine=google_maps_reviews`, `data_id`).
   - Create `src/hotelpulse/serp/normalize.py` to convert raw SerpApi JSON into Pydantic models.
3. **Tests:**
   - Store mock SerpApi JSON fixtures in `tests/fixtures/` (`maps_search.json`, `maps_reviews.json`).
   - Write `tests/test_normalize.py` and `tests/test_cache.py`.
   - **Rule:** Never call live APIs in tests. All tests must pass completely offline.

### **Phase 2: LLM Tagging Engine**
- `src/hotelpulse/analysis/prompts.py` (System prompt with exact verbatim substring constraint).
- `src/hotelpulse/analysis/tagger.py` (Batch 10–15 reviews into Claude Haiku, validate with Pydantic, verify `assert quote in review.text`).
- `eval/labeled_reviews.jsonl` and `eval/run_eval.py` to record topic F1 and sentiment accuracy.

### **Phase 3 & 4: Scoring, Ranking & Connecting to UI**
- `src/hotelpulse/analysis/scoring.py` (Recency decay formula: $w = 0.5^{(\text{age} / 180)}$, 1–5 topic score).
- `src/hotelpulse/analysis/ranking.py` (Fix-first priority $\sum \text{severity} \times w$, top 3 strengths).
- `src/hotelpulse/services/pipeline.py` (Connect the search & analysis pipeline directly to `streamlit_app.py` so real data replaces mock data).

---

## 5. Non-Negotiable Rules
1. **Preserve UI Aesthetics:** Do not simplify or dismantle the custom CSS and card layouts in `components.py` — they must match `design.md`.
2. **Credit Budget Protection:** Hard limit of 250 SerpApi searches/month. Never call the API if a cached response exists in `api_cache`.
3. **No Live APIs in Tests:** All tests must run against JSON fixtures.
4. **Verbatim Quote Rule:** Every single quote shown in the UI must be a verified substring of the raw review text.
