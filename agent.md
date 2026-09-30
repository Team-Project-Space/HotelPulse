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
- [`pyproject.toml`](./pyproject.toml): Dependencies declared. **Fixed:** added `[tool.hatch.build.targets.wheel] packages = ["src/hotelpulse"]` (without it the editable install ships nothing — src-layout + hatchling), `[tool.pytest.ini_options] pythonpath = ["src"]`, and `pytest` under `[project.optional-dependencies] dev`.
- [`requirements.txt`](./requirements.txt): **New.** Pinned from the verified working install.
- [`.env.example`](./.env.example): **New.** All keys/settings from PRD §15, plus the credit guard-rail vars.
- [`Makefile`](./Makefile): **New.** `install`, `install-dev`, `run`, `test`, `eval`, `db-init`, `fmt-check`, `clean`. Uses `py` per Gotcha 3.
- [`data/.gitkeep`](./data/.gitkeep), [`tests/fixtures/.gitkeep`](./tests/fixtures/.gitkeep): **New.**
- [`README.md`](./README.md): Pitch paragraph only. PRD §18 still owes setup, architecture, accuracy, caching, limitations, disclosures.
- [`.vscode/settings.json`](./.vscode/settings.json): **Fixed.** Pointed at the non-existent Python 3.13; now Python 3.12.4 with pytest enabled.
- Environment verified: `py -m streamlit run src/hotelpulse/app/streamlit_app.py` returns HTTP 200 on `/_stcore/health`. `import hotelpulse` works with no `sys.path` hack.

### B. Frontend UI Implementation — **MOCK DATA ONLY**
The UI is styled to match all three design mockups and runs, but **nothing is wired to a backend yet.** Every number on screen is a hardcoded literal. This is a visual prototype, not a functioning feature. Do not read §2.B as "Phase 4 done".
1. **Design System & Components:** [`src/hotelpulse/app/components.py`](./src/hotelpulse/app/components.py) — 8 `render_*` functions, pure presentational, takes plain values.
2. **Streamlit App Flow:** [`src/hotelpulse/app/streamlit_app.py`](./src/hotelpulse/app/streamlit_app.py)
   - **Default Entrance State (`view_mode = "landing"`):** Matches `image.png`. Hotel name + City inputs, full-width `Analyze my hotel →` CTA.
   - **Transition to Dashboard:** Clicking the CTA flips `view_mode` to `dashboard`. It does **not** fetch anything.
   - **Switching Back:** `← Search Another Hotel` returns to landing.
   - **Sidebar Switcher:** Manual landing/dashboard toggle for design evaluation.
   - **Evidence Modal Dialogs:** `@st.dialog` reading from the `MOCK_EVIDENCE` dict.
   - **SerpApi Credit Monitor:** `st.metric("14 / 250")` — a string literal, not a real count.
3. **Hardcoded values that must be replaced in Phase 4** (do not delete the components, just feed them real data):
   - `MOCK_EVIDENCE` dict (~line 45) — 3 topics x quotes.
   - Dashboard header `address="Hampankatta, Mangalore"`, `updated_date`, `review_count=1248` (~line 233).
   - `render_metrics_bar(4.2, 72, 16, 1248)` (~line 243).
   - `issues_data` 3 fix cards (~line 261), `strengths_data` (~line 317), `topics_grid_data` 8 topics (~line 347), `comparison_rows` + `next_actions` (~line 363).
   - Sidebar sliders/checkboxes at ~line 163 are not wired to anything.

### C. Critical Fixes Made & Gotchas to Know
1. **HTML Rendering in Streamlit:**
   - In Markdown, lines indented with 4 or more spaces are converted into code blocks (`<pre><code>`).
   - All HTML in `components.py` has had multiline whitespace stripped, and `streamlit_app.py` uses `st.html()` (not `st.markdown`) to render pure HTML without code-block formatting.
2. **Module Import Path (`sys.path`):**
   - Streamlit scripts run with `__file__` directory as root. We added automatic `sys.path.insert(0, src_dir)` at the top of `streamlit_app.py` so `hotelpulse` imports cleanly from any directory.
3. **Windows Application Control (WDAC Error 4551):**
   - On this machine, running `.venv\Scripts\python.exe` is blocked by Windows security policy.
   - **Always run commands using the system `py` command** (e.g. `py -m streamlit run ...`, `py -m pytest ...`), which points to `C:\Users\Asus\AppData\Local\Programs\Python\Python312\python.exe` (**Python 3.12.4** — the only interpreter installed; there is no Python 3.13 on this box).
   - Dependencies are installed into that system interpreter (`py -m pip install -e .`). It already hosts torch/transformers/scikit-learn; the HotelPulse additions are streamlit, serpapi, anthropic and pytest. Verified working.
4. **`pip install` is slow here, not broken.** The wheels are large (`streamlit` 10.1 MB, `pydeck` 11.4 MB) and download at roughly 30–40 kB/s, so a fresh `pip install` can exceed 10 minutes. It is not hung. For long installs, run them backgrounded with output redirected to a log and poll the log rather than raising the tool timeout.
5. **Editable install needs `hatchling` preinstalled** if you pass `--no-build-isolation`. It is now pinned in `requirements.txt`.
6. **SerpApi reality check — PRD §6.1 contains three factual errors.** Verified against SerpApi docs 2026-09-30. PRD §21.7 says to adapt the code and note it in the README, so these are deliberate deviations, not bugs:
   | PRD says | Actually |
   |---|---|
   | `sort_by=newest` | **`sort_by=newestFirst`** (others: `qualityScore`, `ratingHigh`, `ratingLow`) |
   | implies 10–20 reviews/page | **First page returns 8.** `num` is *rejected* on page 1 when no `next_page_token`/`topic_id`/`query` is set. So `MAX_REVIEWS_OWN=100` costs ~13 credits. |
   | count credits from the cache table | Search responses contain **no** `credits`/`credits_left` field. Use `client.account()` (free, does not consume quota) → `this_month_usage`, `total_searches_left`. Counting `api_cache` rows is still the cheapest local proxy. |

   Other confirmed details:
   - Engines: `google_maps`, `google_maps_reviews`, `tripadvisor`, `tripadvisor_reviews`.
   - `google_maps` needs `type=search` + `q`; optional `ll=@<lat>,<lng>,<zoom>z` (only with `type=search`). `start` steps by 20, max 100.
   - Place data lives at **`local_results[]`**, but Google sometimes returns **`place_results[]`** instead. **Handle both.** Fields: `title`, `data_id` (use for reviews), `place_id`, `gps_coordinates.{latitude,longitude}`, `rating`, `reviews`, `address`.
   - `google_maps_reviews` takes `data_id` or `place_id`. Pagination is `serpapi_pagination.next_page_token` (also a `next` URL). The `start` offset is discontinued for this engine.
   - Maps review fields: `reviews[].snippet` (text; `extracted_snippet.original` is fuller), `.user.name`, `.rating`, `.iso_date` (parse this, **not** the human `date` string), `.review_id` (dedupe key).
   - Tripadvisor search returns **`places[]`** (not `local_results`): `title`, `place_id` (Tripadvisor numeric id), `place_type`. Use `ssrc=h` to restrict to hotels.
   - Tripadvisor reviews: `reviews[].snippet` (text), `.author.display_name`, `.rating`, `.date` (already `YYYY-MM-DD`), `.review_id`. `limit` max 20. `sort_by=most_recent`. `reviews[].response` is the *hotel's* reply — filter it out or it contaminates the text.
   - Python client: `serpapi.Client(api_key=...)`, `client.search({...})` returns a `SerpResults` (a `UserDict` subclass, so `results["reviews"]` and `.get(...)` both work).
   - **Free plan is 250/month *and* 50/hour.** You will hit the hourly cap long before the monthly one when bursting. Do not set `no_cache=true` — SerpApi's own 1-hour cache is free and does not count against quota.
   - Credit math at the chosen conservative caps (`MAX_REVIEWS_OWN=30`, `MAX_REVIEWS_COMPETITOR=10`): ~4 credits own + ~2 per competitor × 4 = **~12 credits per full run, so ~20 runs/month.**

---

## 3. How to Run and Test the App

From the project root (see Gotcha 3 — always `py`, never `.venv`):
```powershell
py -m streamlit run src/hotelpulse/app/streamlit_app.py
```
App will be accessible at: `http://localhost:8501`.

Tests (offline, no API keys needed):
```powershell
py -m pytest
```

Or via `make` if it is installed (`make run`, `make test`, `make db-init`, `make eval`).

Health check without a browser: `py -m streamlit run ... --server.headless true --server.port 8511`, then `Invoke-WebRequest http://localhost:8511/_stcore/health` should return `ok`.

---

## 4. Next Steps & Instructions for the Next Agent

The UI is ready. Next is implementing the backend according to Section 16 of [`PRD.md`](./PRD.md).

**Progress against PRD §16:** Phase 1 box 1 (skeleton) is now done. Boxes 2–6 remain, then everything else. Commit at the end of each numbered group.

### **Phase 1: Database & SerpApi Caching (Next Priority)**
1. **Models & config** (do this first, everything depends on it):
   - `src/hotelpulse/models.py` — copy PRD §9 verbatim, plus whatever view models the UI needs (`Issue` already exists there; add `TopicScore`, `CompetitorRow`, `AnalysisResult`).
   - `src/hotelpulse/config.py` — `load_dotenv()`, `DB_PATH`, `MAX_REVIEWS_OWN=30`, `MAX_REVIEWS_COMPETITOR=10`, `TAG_MODEL`, `WRITE_MODEL`, `SERP_MONTHLY_BUDGET=250`.
2. **Database Layer:**
   - Create `src/hotelpulse/db/schema.sql` (schema is defined in Section 10 of `PRD.md`):
      - `api_cache`: SHA256 keyed cache of all raw SerpApi responses.
      - `hotels`: Hotel metadata (`hotel_id`, `name`, `address`, `lat`, `lng`, `rating`, `review_count`, `is_own`).
      - `reviews`: Individual review records (`review_id`, `hotel_id`, `source`, `rating`, `text`, `review_date`, `reviewer`, `language`).
      - `mentions`: Topic sentiment mentions (`topic`, `sentiment`, `severity`, `quote`, `quote_en`, `prompt_version`).
      - `tagged_reviews`: Tracking reviews already processed to prevent re-calling LLM.
   - Create `src/hotelpulse/db/connection.py` (`get_conn()`, `init_db()`). Turn on `PRAGMA foreign_keys=ON` and `row_factory=sqlite3.Row`.
   - Create `src/hotelpulse/db/repo.py` (CRUD helpers for cache, hotels, reviews, and mentions).
   - **Add `api_calls_this_month()`** — counts `api_cache` rows by `fetched_at` month. PRD §6.1 wants a real sidebar number and this is the cheapest local source of truth.
3. **SerpApi Client Layer:**
   - Create `src/hotelpulse/serp/client.py`:
     - Implement `cached_search(engine, params, refresh=False)` wrapper.
     - Cache key = `sha256(engine + json.dumps(params, sort_keys=True))`.
     - If cached in `api_cache` and not `refresh=True`, return cached response.
     - Track monthly API call count against the 250 credit budget.
     - Wrap `serpapi.HTTPError` / `serpapi.TimeoutError` into a `SerpApiError` carrying a plain-language message. **No stack traces reach the UI** (PRD §13).
   - Create `src/hotelpulse/serp/maps.py` for finding hotel and nearby competitors (`engine=google_maps`, `type=search`). **Read both `local_results` and `place_results`** — see Gotcha 6.
   - Create `src/hotelpulse/serp/reviews_maps.py` for paginated Google Maps reviews (`engine=google_maps_reviews`, `data_id`, `sort_by=newestFirst`, loop `next_page_token`).
   - Create `src/hotelpulse/serp/normalize.py` to convert raw SerpApi JSON into Pydantic models. Field map is in Gotcha 6.
4. **Tests:**
   - Do **one real fetch first** (2–3 credits: 1 `google_maps` + 1–2 `google_maps_reviews`), save the raw JSON to `tests/fixtures/maps_search.json` and `maps_reviews.json`. Hand-written fixtures will not match the real shape.
   - `tests/conftest.py` — temp SQLite fixture + a fake `serpapi.Client` that **raises** if it is ever constructed, so a stray network call fails loudly.
   - Write `tests/test_normalize.py` and `tests/test_cache.py`.
   - **Rule:** Never call live APIs in tests. All tests must pass completely offline.
5. **Manual check (§16 box 6):** run one real hotel fetch, then re-run it and prove 0 API calls were made.

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
