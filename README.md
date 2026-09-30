# HotelPulse

HotelPulse tells small hotel owners what guests are unhappy about, how they compare with nearby hotels, and what to fix first.

## Setup (short)

```powershell
py -m pip install -r requirements.txt
py -m pip install -e . --no-deps --no-build-isolation
copy .env.example .env
# Fill in SERPAPI_API_KEY and GEMINI_API_KEY (or GROQ_API_KEY)
py -m streamlit run src/hotelpulse/app/streamlit_app.py
```

### Free LLM (no credit card)

Tagging uses **Google Gemini** by default (`GEMINI_API_KEY`, model `gemini-3.1-flash-lite`) or **Groq** as fallback (`GROQ_API_KEY`). Set `LLM_PROVIDER=gemini|groq` only if you have both keys and want to force one. Paid Anthropic is not used.

- Gemini key: https://aistudio.google.com/apikey
- Groq key: https://console.groq.com/keys

### Tests

```powershell
py -m pytest
```

### Live eval (uses free LLM tokens)

```powershell
py eval/run_eval.py --live
```

