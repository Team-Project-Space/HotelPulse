-- HotelPulse schema (PRD section 10).
-- Applied by hotelpulse.db.connection.init_db(); every statement is idempotent.

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

-- `tagged_reviews` marks reviews already processed (including reviews with zero
-- mentions) so they are not re-sent to the LLM. Primary key includes
-- prompt_version so bumping PROMPT_VERSION re-tags everything.
CREATE TABLE IF NOT EXISTS tagged_reviews (
  review_id   TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  PRIMARY KEY (review_id, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_reviews_hotel ON reviews(hotel_id);
CREATE INDEX IF NOT EXISTS idx_mentions_review ON mentions(review_id);

-- Added by the implementation. `api_cache` holds one row per unique query and
-- is overwritten on refresh, so it cannot be used to measure credit spend. This
-- append-only ledger records every outbound API call and is the source of truth
-- for the sidebar credit meter and the monthly budget guard.
CREATE TABLE IF NOT EXISTS api_calls (
  call_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  engine      TEXT NOT NULL,
  cache_key   TEXT NOT NULL,
  params_json TEXT NOT NULL,
  search_id   TEXT,
  called_at   TEXT NOT NULL
);

-- Added by the implementation. `mentions` is queried almost entirely by
-- (hotel, topic) via a join on reviews, and `api_cache` is scanned by month
-- for the sidebar credit counter.
CREATE INDEX IF NOT EXISTS idx_mentions_topic ON mentions(topic);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(review_date);
CREATE INDEX IF NOT EXISTS idx_api_cache_fetched ON api_cache(fetched_at);
CREATE INDEX IF NOT EXISTS idx_api_calls_called ON api_calls(called_at);
CREATE INDEX IF NOT EXISTS idx_hotels_own ON hotels(is_own);
