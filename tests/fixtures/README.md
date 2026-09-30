# Test fixtures

Raw SerpApi responses, trimmed of anything identifying. These let the whole
suite run offline with no API key (PRD section 17).

| File | Captured from | Used by |
|---|---|---|
| `maps_search.json` | `engine=google_maps`, `type=search` | `test_normalize.py::test_maps_search_fixture_normalizes` |
| `maps_reviews.json` | `engine=google_maps_reviews`, one page | `test_normalize.py::test_maps_reviews_fixture_normalizes` |
| `llm_tag_response.json` | Free LLM tagger output (Gemini/Groq shape) | `test_tagger.py` (Phase 2) |

The two Maps tests **skip** until the files exist, so the suite passes before
the first capture. Everything else is covered by inline payloads shaped like
real responses.

## Why real responses, not hand-written ones

Hand-written fixtures encode what you *believe* the API returns. These fields
did not match the documented names on the first attempt, which is exactly the
class of bug fixtures exist to catch:

- places appear under `local_results` **or** `place_results`
- the review total is a comma string under the key `reviews` (`"1,248"`)
- `reviews[].snippet` can be empty while `extracted_snippet.original` has text
- the first reviews page returns 8 items, not 10–20

## How to capture one (costs 2–3 credits)

Set `SERPAPI_API_KEY` in `.env`, then from the project root:

```powershell
py -m pytest --collect-only -q
py -c "import json, sys; sys.path.insert(0,'src'); from hotelpulse.db.connection import init_db; init_db(); from hotelpulse.serp import maps, reviews_maps; c = maps.find_hotels('<real hotel>', '<city>', refresh=True)[0]; json.dump({...}, open('tests/fixtures/maps_search.json','w'), indent=2)"
```

Prefer capturing through the app's own code rather than the raw SDK so the
fixtures match what the pipeline actually parses. The exact helper for this
is added in Phase 1's final commit; until then capture by hand.

**Budget discipline:** capture each file exactly once. Everything downstream
replays from `api_cache`, so no further credits are spent.
