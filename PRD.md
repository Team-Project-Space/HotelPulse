# HotelPulse: Product Requirements Document (PRD)

> Working name. Rename freely.
> **Audience: AI coding agent.** Read the whole file first. Build in the order given in section 16. Do not add features outside the "Must" and "Should" lists until all of them are done and tested.

---

## 1. Summary

**One-liner:** HotelPulse tells small hotel owners what guests are unhappy about, how they compare with nearby hotels, and what to fix first.

**Hackathon track:** Commerce & Market Intelligence (SerpApi hackathon).
**Deadline:** aim for **October 5, 2026** (site may say October 10; one SerpApi changelog says October 5, so use the earlier date).
**Runs:** locally (Streamlit). Demo video under 3 minutes.

## 2. Problem

- Reviews are scattered across Google Maps and Tripadvisor. Owners have no time to read them all.
- Star rating hides specifics (wifi, AC, food, cleanliness).
- Owners cannot tell whether a complaint is unique to them or common in the area.
- Owners cannot tell which problem to fix first.

## 3. Target user

Owner or manager of an independent hotel or lodge, about 10-50 rooms, including tier-2 and tier-3 Indian cities. Non-technical. UI must be: **type hotel name + city, click one button, get 3 actions.**

## 4. Goals and non-goals

### Goals
1. Fetch live reviews via SerpApi and cache them.
2. Tag every review per topic with sentiment (LLM).
3. Rank the top 3 "fix first" issues with real review quotes as evidence.
4. Compare with 3-5 owner-chosen nearby competitors, topic by topic.
5. Handle English, Hinglish and regional-language reviews.
6. Report a measured tagging accuracy on a small hand-labeled test set in the README.

### Non-goals
- No user accounts, auth, payments, or hosting.
- No revenue or occupancy claims. Never quote statistics without a real source.
- No scraping outside SerpApi.
- No mobile app.

## 5. User stories and acceptance criteria

| ID | Priority | Story | Acceptance criteria |
|---|---|---|---|
| US-1 | Must | As an owner, I enter my hotel name and city and my hotel is found. | Search returns candidate list (name, address, rating, review count). Owner picks one. |
| US-2 | Must | I see my reviews analyzed by topic. | Each review has per-topic sentiment for the 8 topics where mentioned. Stored in SQLite. |
| US-3 | Must | I see the top 3 issues to fix first. | Ranked list with score, mention count, and at least 2 verbatim quotes each (with date + source). |
| US-4 | Must | I trust the insights. | Every issue and strength card shows the exact review quotes. Quotes are verbatim substrings of the original review text. |
| US-5 | Should | I compare with nearby hotels. | Owner selects 3-5 competitors from nearby results. Gap table shows my score vs competitor average per topic. |
| US-6 | Should | I see Tripadvisor reviews too. | Second source merged into the same schema, shown with a source filter. |
| US-7 | Could | I get reply drafts for negative reviews. | Button on a negative review generates a polite, specific reply (Sonnet). |
| US-8 | Could | I see rating trend over time. | Monthly avg rating line chart. |

## 6. Feature spec

### 6.1 Review fetch (Must)
- Find hotel: SerpApi **Google Maps API** (`engine=google_maps`, `type=search`, `q="<name> <city>"`).
- Nearby competitors: same engine, query like `hotels near <lat,lng>` or `hotels in <city>`; use `ll=@lat,lng,14z`. Exclude the owner's own hotel.
- Reviews: SerpApi **Google Maps Reviews API** (`engine=google_maps_reviews`, `data_id=<data_id>`), paginate with `next_page_token`, sort `newest` by default.
- Second source (Should): **Tripadvisor Search API** to find the place, then Tripadvisor reviews endpoint.
- **Verify exact engine names and parameters in the SerpApi docs before coding.** Do not guess parameter names.
- **Credit budget: 250 searches/month.** Rules:
  - Cache every raw response in SQLite keyed by `sha256(engine + sorted params)`.
  - Never call the API if a cached response exists, unless `--refresh` / sidebar "Refresh data" is used.
  - Default caps: `MAX_REVIEWS_OWN=100`, `MAX_REVIEWS_COMPETITOR=40`.
  - Show remaining-credit estimate in the sidebar (count of API calls made this month from the cache table).

### 6.2 Normalization (Must)
All sources map to one `Review` model (section 9).

### 6.3 Topic + sentiment tagging (Must)
- Topics (fixed enum): `cleanliness`, `staff`, `food`, `wifi`, `ac`, `noise`, `location`, `value`.
- For each review the LLM returns zero or more topic mentions: `{topic, sentiment: positive|negative|mixed, severity: 1-3, quote}`.
- `quote` must be a **verbatim substring** of the review text (short, under 200 chars). Validate in code; drop or repair mentions whose quote is not a substring.
- Reviews in Hinglish or regional languages: tag normally; `quote` stays in the original language; also return `quote_en` (English translation) for display.
- Batch 10-15 reviews per LLM call. JSON-only output. Retry once on parse failure. Cache tag results per `review_id + prompt_version`.
- Model: free LLM — Google Gemini Flash preferred (`TAG_MODEL`, default `gemini-3.1-flash-lite`), Groq Llama fallback via `GROQ_API_KEY`.

### 6.4 Fix-first ranking (Must)
See section 11 for formulas. Output top 3 issues and top 3 strengths.

### 6.5 Competitor comparison (Should)
- Same pipeline per competitor (lower review cap).
- Gap table per topic: own score, competitor average, gap (own minus average), mention counts. Flag "Common in the area" if at least half of competitors also score low (below 3.0) on that topic, else "Unique to you".
- Owner chooses competitors from a multiselect; default is the 4 nearest by rating count.

### 6.6 Reply drafts (Could)
Sonnet, input: one negative review + hotel name + tagged topics. Output: 60-100 word polite reply, mentions the specific issue, no promises of compensation, same language as the review.

### 6.7 Trend (Could)
Monthly average rating chart. Google Events/News context is optional and last priority.

## 7. Architecture

```
Owner enters hotel name + city
        |
Google Maps search -> hotel data_id (+ 3-5 nearby competitors)
        |
Fetch reviews (Maps, Tripadvisor) -> cache in SQLite
        |
Normalize -> Review(rating, text, date, source, reviewer)
        |
LLM tags topics + sentiment (batches, JSON output, cached)
        |
Rank issues, compute competitor gaps
        |
Streamlit dashboard: scores, top issues, quotes, gap table
```

Layers: `serp/` (data in) -> `db/` (storage) -> `analysis/` (LLM + ranking) -> `app/` (UI). UI never calls SerpApi or the LLM directly; it calls `services/pipeline.py`.

## 8. Tech stack

- Python 3.11+
- `serpapi` (official client) for SerpApi
- Free LLM providers (no credit card): **Google Gemini** (`google-genai`, default model `gemini-3.1-flash-lite`) preferred; **Groq** (`groq`, e.g. Llama 3.3 70B) fallback. Configure via `GEMINI_API_KEY` and/or `GROQ_API_KEY` in env. Optional `LLM_PROVIDER=gemini|groq` forces one when both keys exist.
- SQLite (stdlib `sqlite3`)
- Pydantic v2 for models and LLM output validation
- Streamlit + Plotly
- pytest
- `python-dotenv`, `tenacity` (retries)

## 9. Data models (Pydantic, `hotelpulse/models.py`)

```python
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field

class Topic(str, Enum):
    cleanliness = "cleanliness"
    staff = "staff"
    food = "food"
    wifi = "wifi"
    ac = "ac"
    noise = "noise"
    location = "location"
    value = "value"

class Sentiment(str, Enum):
    positive = "positive"
    negative = "negative"
    mixed = "mixed"

class Hotel(BaseModel):
    hotel_id: str            # internal: source + ":" + source_id
    source: str              # "google_maps" | "tripadvisor"
    source_id: str           # data_id for maps
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    rating: float | None = None
    review_count: int | None = None
    is_own: bool = False

class Review(BaseModel):
    review_id: str           # sha1(source + hotel_id + reviewer + date + text[:80])
    hotel_id: str
    source: str
    rating: float | None
    text: str
    review_date: date | None
    reviewer: str | None = None
    language: str | None = None

class TopicMention(BaseModel):
    review_id: str
    topic: Topic
    sentiment: Sentiment
    severity: int = Field(ge=1, le=3)   # 1 minor, 2 clear, 3 severe
    quote: str                          # verbatim substring of review text
    quote_en: str | None = None

class Issue(BaseModel):
    topic: Topic
    priority: float
    mention_count: int
    negative_count: int
    topic_score: float
    quotes: list[TopicMention]          # top 2-5 by severity then recency
```

## 10. SQLite schema (`hotelpulse/db/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS api_cache (
  cache_key   TEXT PRIMARY KEY,
  engine      TEXT NOT NULL,
  params_json TEXT NOT NULL,
  response_json TEXT NOT NULL,
  fetched_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hotels (
  hotel_id    TEXT PRIMARY KEY,
  source      TEXT NOT NULL,
  source_id   TEXT NOT NULL,
  name        TEXT NOT NULL,
  address     TEXT,
  lat         REAL,
  lng         REAL,
  rating      REAL,
  review_count INTEGER,
  is_own      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reviews (
  review_id   TEXT PRIMARY KEY,
  hotel_id    TEXT NOT NULL REFERENCES hotels(hotel_id),
  source      TEXT NOT NULL,
  rating      REAL,
  text        TEXT NOT NULL,
  review_date TEXT,
  reviewer    TEXT,
  language    TEXT
);

CREATE TABLE IF NOT EXISTS mentions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  review_id   TEXT NOT NULL REFERENCES reviews(review_id),
  topic       TEXT NOT NULL,
  sentiment   TEXT NOT NULL,
  severity    INTEGER NOT NULL,
  quote       TEXT NOT NULL,
  quote_en    TEXT,
  prompt_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tagged_reviews (
  review_id   TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  PRIMARY KEY (review_id, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_reviews_hotel ON reviews(hotel_id);
CREATE INDEX IF NOT EXISTS idx_mentions_review ON mentions(review_id);
```

`tagged_reviews` marks reviews already processed (including reviews with zero mentions) so they are not re-sent to the LLM.

## 11. Ranking and scoring

Constants in `analysis/config.py`: `RECENCY_HALF_LIFE_DAYS = 180`, `MIN_MENTIONS = 3`.

**Recency weight:** `w = 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)`; if date missing, `w = 0.5`.

**Topic score (1-5 scale, per hotel per topic):**
```
weighted_total = sum(w for all mentions of topic)
pos = sum(w for positive) ; mix = sum(w for mixed)
topic_score = 1 + 4 * (pos + 0.5 * mix) / weighted_total
```
If fewer than `MIN_MENTIONS` mentions: score is `None`, shown as "not enough data" and excluded from ranking.

**Fix-first priority (per topic):**
```
priority = sum(severity * w for negative and mixed mentions)
```
Top 3 topics by `priority` (only topics where `topic_score < 4.0`). Tie-break: higher negative count.

**Strengths:** top 3 topics by `topic_score` with `mention_count >= MIN_MENTIONS`.

**Overall:** average star rating, positive/negative/mixed split of all mentions.

**Competitor gap:** `gap = own_topic_score - mean(competitor_topic_scores)`; negative gap = you are worse.

## 12. LLM tagging prompt (`analysis/prompts.py`)

`PROMPT_VERSION = "v1"`. Bump it whenever the prompt changes (forces re-tag).

System prompt:
```
You analyze hotel guest reviews. Reviews may be English, Hinglish (Hindi in Latin script), or regional languages.
For each review, extract mentions of these topics only: cleanliness, staff, food, wifi, ac, noise, location, value.
For each mention return: topic, sentiment (positive|negative|mixed), severity (1 minor, 2 clear, 3 severe; use 1 for positive), quote, quote_en.
Rules:
- quote MUST be copied exactly from the review text, under 200 characters. Do not edit it.
- quote_en is an English translation of quote. If quote is already English, repeat it.
- Only include a topic if the review clearly talks about it. Do not infer.
- One mention per topic per review. If mixed feelings on one topic, use "mixed".
- Return ONLY valid JSON, no prose, no markdown fences.
Output schema:
{"results":[{"review_id":"...","mentions":[{"topic":"...","sentiment":"...","severity":1,"quote":"...","quote_en":"..."}]}]}
```

User message: JSON list of `{"review_id", "text"}` (10-15 items).

Validation (`analysis/tagger.py`): parse JSON, validate with Pydantic, drop unknown topics, drop mentions where `quote not in review.text` (try whitespace-normalized match before dropping), log drop rate.

## 13. Dashboard spec (`app/streamlit_app.py`)

Sidebar: hotel name input, city input, "Find hotel" button, review cap slider, competitor multiselect, source checkboxes (Google, Tripadvisor), "Refresh data" checkbox, API-call counter.

Main page sections in order:
1. **Header:** hotel name, address, overall rating, review count analyzed, positive/negative/mixed donut (Plotly).
2. **Topic scores:** horizontal bar chart, 1-5 scale, one bar per topic (grey if not enough data).
3. **Fix these first:** 3 cards. Each: topic, priority, "mentioned in N reviews, M negative", 2-5 quotes (original + English if different), date, source. Expander "show all evidence".
4. **Your strengths:** 3 compact cards with best quotes.
5. **Competitor gaps:** table (topic, you, competitor avg, gap, Unique/Common flag) + grouped bar chart.
6. **Reply drafts (Could):** list of recent negative reviews with "Draft reply" button.
7. **Trend (Could):** monthly rating line chart.

UX rules: show a progress bar with step labels during fetch/tag; every error shows a plain-language message (no stack traces); works with cached data offline (no API key needed once cached).

## 14. Folder structure

```
hotelpulse/
├── README.md
├── PRD.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── Makefile
├── data/
│   ├── .gitkeep
│   └── hotelpulse.db              # generated, gitignored
├── eval/
│   ├── labeled_reviews.jsonl      # hand-labeled test set (30-50 reviews)
│   └── run_eval.py                # prints accuracy, saves eval/results.md
├── src/
│   └── hotelpulse/
│       ├── __init__.py
│       ├── config.py              # env loading, constants
│       ├── models.py              # Pydantic models (section 9)
│       ├── db/
│       │   ├── __init__.py
│       │   ├── schema.sql
│       │   ├── connection.py      # get_conn(), init_db()
│       │   └── repo.py            # upsert/get for hotels, reviews, mentions, cache
│       ├── serp/
│       │   ├── __init__.py
│       │   ├── client.py          # cached_search(engine, params) wrapper + call counter
│       │   ├── maps.py            # find_hotels(), find_nearby()
│       │   ├── reviews_maps.py    # fetch_maps_reviews(data_id, cap)
│       │   ├── reviews_tripadvisor.py
│       │   └── normalize.py       # raw JSON -> Hotel / Review
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── config.py          # RECENCY_HALF_LIFE_DAYS, MIN_MENTIONS, topics
│       │   ├── prompts.py
│       │   ├── tagger.py          # tag_reviews(reviews) -> mentions
│       │   ├── scoring.py         # topic_score(), overall stats
│       │   ├── ranking.py         # fix_first(), strengths()
│       │   ├── compare.py         # competitor gap table
│       │   └── replies.py         # draft_reply() (Could)
│       ├── services/
│       │   ├── __init__.py
│       │   └── pipeline.py        # analyze_hotel(), analyze_competitors()
│       └── app/
│           ├── __init__.py
│           ├── streamlit_app.py
│           └── components.py      # cards, charts
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── maps_search.json       # saved real/sample SerpApi responses
    │   ├── maps_reviews.json
    │   └── llm_tag_response.json
    ├── test_normalize.py
    ├── test_cache.py
    ├── test_tagger.py             # mocks LLM; checks quote validation
    ├── test_scoring.py
    ├── test_ranking.py
    └── test_compare.py
```

Entry point: `streamlit run src/hotelpulse/app/streamlit_app.py`.

## 15. Configuration

`.env.example`:
```
SERPAPI_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
# LLM_PROVIDER=gemini   # optional force when both keys exist
TAG_MODEL=gemini-3.1-flash-lite
WRITE_MODEL=gemini-3.1-flash-lite
DB_PATH=data/hotelpulse.db
MAX_REVIEWS_OWN=100
MAX_REVIEWS_COMPETITOR=40
```

Never commit `.env` or `data/*.db`. Add both to `.gitignore`.

`Makefile` targets: `install`, `run` (streamlit), `test`, `eval`.

## 16. Build order (agent task list)

Check each box only when its tests pass.

**Phase 1: fetch and cache**
- [ ] Project skeleton, `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`
- [ ] `db/schema.sql`, `connection.py`, `repo.py`
- [ ] `serp/client.py`: `cached_search()` with SQLite cache + call counter
- [ ] `serp/maps.py`, `serp/reviews_maps.py` with pagination and cap
- [ ] `serp/normalize.py` + `test_normalize.py`, `test_cache.py` using saved fixtures
- [ ] Manual check: one real hotel fetched and cached (keep API calls low)

**Phase 2: tagging**
- [ ] `analysis/prompts.py`, `tagger.py` with batching, JSON validation, quote-substring check, retry, per-review cache
- [ ] `test_tagger.py` with mocked LLM
- [ ] Create `eval/labeled_reviews.jsonl` (30-50 reviews, include Hinglish); `eval/run_eval.py`
- [ ] Record accuracy (topic-level F1 and sentiment accuracy) in README

**Phase 3: ranking**
- [ ] `scoring.py`, `ranking.py`, tests for formulas in section 11 with hand-computed cases

**Phase 4: dashboard**
- [ ] `services/pipeline.py`
- [ ] Streamlit sections 1-4 of section 13

**Phase 5: competitors**
- [ ] `find_nearby()`, `analyze_competitors()`, `compare.py`, test
- [ ] Dashboard section 5

**Phase 6: Should/Could (only if Phases 1-5 are done)**
- [ ] Tripadvisor source
- [ ] Reply drafts
- [ ] Trend chart

**Phase 7: ship**
- [ ] README (see section 18), setup steps tested from a clean clone
- [ ] Demo video under 3 minutes
- [ ] Submission checklist (section 19)

### Suggested day plan (deadline Oct 5, so about 6 days from Sept 29)
| Day | Work |
|---|---|
| 1 | Phase 1 |
| 2 | Phase 2 |
| 3 | Phase 3 + dashboard sections 1-4 |
| 4 | Phase 5 competitors |
| 5 | Phase 6 extras + polish, README |
| 6 | Demo video, test links in a private window, submit early |

## 17. Testing and evaluation

- `pytest` must pass without network access and without API keys (all SerpApi and LLM calls mocked or fixture-based).
- Required tests: normalization of raw SerpApi JSON, cache hit avoids API call, tagger rejects non-verbatim quotes, score/ranking math, competitor gap sign and Unique/Common flag.
- **Eval:** `eval/run_eval.py` runs the real tagger over `labeled_reviews.jsonl` and reports (a) topic detection precision/recall/F1, (b) sentiment accuracy on correctly detected topics. Paste results into README. Report honestly, do not tune numbers.

## 18. README requirements

1. What it is (pitch) and screenshot/GIF.
2. Setup: clone, `python -m venv`, `pip install -r requirements.txt`, copy `.env.example` to `.env`, add keys.
3. Run: `streamlit run src/hotelpulse/app/streamlit_app.py`
4. How SerpApi is used (list engines).
5. Architecture diagram (section 7).
6. Accuracy results from eval.
7. Credit usage and caching explanation.
8. Limitations and known risks.
9. AI-tools disclosure and prior-work disclosure.

## 19. Submission checklist

- [ ] Public GitHub repo with working setup steps
- [ ] Demo video under 3 minutes, running locally
- [ ] Project description with track: Commerce & Market Intelligence
- [ ] Participant details
- [ ] AI-tools and prior-work disclosures
- [ ] All links tested in a private window
- [ ] Submitted by **October 5**

## 20. Risks and rules

| Risk | Handling |
|---|---|
| API credit limit (250 searches/month) | Cache everything, cap reviews, show call counter, develop against fixtures |
| Unfair competitor comparison | Owner picks competitors |
| Hallucinated quotes | Verbatim-substring validation in code |
| Small review counts | `MIN_MENTIONS` threshold, show "not enough data" |
| LLM JSON errors | Pydantic validation, one retry, skip batch with logged warning |
| Revenue claims | None. No statistics without a real source |
| Scope creep | Finish Must + Should before any Could |

## 21. Rules for the AI agent

1. Follow section 16 order. Small commits per task.
2. Check SerpApi docs for exact engine and parameter names before writing fetch code. If unsure, ask the user.
3. Never hardcode API keys. Read from env.
4. Never call live APIs in tests.
5. Keep the UI simple: owner sees three actions, not a data dump.
6. Every insight shown must trace to real review text.
7. If a requirement here conflicts with SerpApi reality (field names, limits), adapt the code, note it in README, and tell the user.
