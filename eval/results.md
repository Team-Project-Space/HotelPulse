# HotelPulse tagger eval

Mode: **live (gemini / gemini-3.1-flash-lite)**
Reviews: **8** (from `eval/labeled_reviews.jsonl`)

## Summary

| Metric | Value |
|---|---|
| Macro F1 (topics present in gold) | 1.0 |
| Micro precision | 1.0 |
| Micro recall | 1.0 |
| Micro F1 | 1.0 |
| Sentiment accuracy (matched topics) | 1.0 (n=8) |

## Per-topic

| Topic | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| cleanliness | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| staff | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| food | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| wifi | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| ac | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| noise | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| location | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |
| value | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |

## Notes

- Offline mode uses a keyword mock tagger — numbers are a harness sanity check, not live-model accuracy.
- Run `py eval/run_eval.py --live` to measure the real model and paste those numbers into README.md.
- Report honestly; do not tune the labeled set to flatter the model.
