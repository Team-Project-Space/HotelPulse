"""Run the real tagger over eval/labeled_reviews.jsonl and report accuracy.

Offline mode (default): uses a deterministic rule-based mock tagger so the
script runs without an LLM key. With --live it calls the real free tagger
(Gemini Flash preferred, Groq Llama fallback).

Usage:
    py eval/run_eval.py              # offline mock
    py eval/run_eval.py --live      # real free LLM (Gemini or Groq)
    py eval/run_eval.py --live --limit 10

Writes eval/results.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hotelpulse.models import Review, Sentiment, Topic, TopicMention  # noqa: E402

EVAL_DIR = Path(__file__).parent
LABELED = EVAL_DIR / "labeled_reviews.jsonl"
RESULTS = EVAL_DIR / "results.md"


def load_labeled(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or not line.startswith("{"):
            continue
        rows.append(json.loads(line))
    return rows


def row_to_review(row: dict) -> Review:
    return Review(
        review_id=row["review_id"],
        hotel_id="eval:hotel",
        source="google_maps",
        rating=None,
        text=row["text"],
        review_date=None,
    )


# ---------------------------------------------------------------------------
# Offline mock tagger — keyword heuristics, NOT the production tagger.
# Used only so run_eval.py can execute without an API key.
# ---------------------------------------------------------------------------

_KEYWORDS: dict[Topic, list[str]] = {
    Topic.cleanliness: ["clean", "spotless", "mould", "mold", "moss", "dirty", "smell", "gandi", "safai", "sheet"],
    Topic.staff: ["staff", "reception", "front desk", "housekeeping", "manager", "waiter", "helpful", "rude", "polite", "host"],
    Topic.food: ["food", "breakfast", "buffet", "dinner", "lunch", "restaurant", "khana", "omelette", "menu", "cook"],
    Topic.wifi: ["wifi", "wi-fi", "internet", "video call", "network"],
    Topic.ac: ["ac", "air con", "air-condition", "cooling", "cool", "garam", "geyser"],
    Topic.noise: ["noise", "noisy", "shor", "loud", "truck", "construction", "bar downstairs", "quiet"],
    Topic.location: ["location", "walking distance", "station", "beach", "lake", "centre", "center", "ferry", "bus stand", "doori"],
    Topic.value: ["value", "price", "rate", "overpriced", "worth", "money", "budget", "cheap", "expensive", "hisaab"],
}


def mock_tag(text: str, review_id: str) -> list[TopicMention]:
    lowered = text.lower()
    out: list[TopicMention] = []
    for topic, words in _KEYWORDS.items():
        if not any(w in lowered for w in words):
            continue
        # crude sentiment: negative cues beat positive
        neg = any(
            w in lowered
            for w in (
                "slow", "rude", "broken", "dead", "not ", "no ", "poor", "average",
                "overpriced", "noise", "noisy", "dirty", "mould", "mold", "smell",
                "forgot", "refused", "extra", "killed", "died", "grinding", "gandi",
                "nahi", "kam nahi", "problem", "missed", "confused", "no discount",
            )
        )
        pos = any(
            w in lowered
            for w in (
                "clean", "great", "perfect", "helpful", "friendly", "spotless",
                "good", "recommended", "polite", "worked", "right", "nice",
                "best", "fine", "theek", "helpful", "safai",
            )
        )
        if neg and pos:
            sentiment = Sentiment.mixed
            severity = 2
        elif neg:
            sentiment = Sentiment.negative
            severity = 3 if any(w in lowered for w in ("broken", "dead", "rude", "not working", "nahi kar")) else 2
        else:
            sentiment = Sentiment.positive
            severity = 1
        # quote: first sentence-ish chunk containing a keyword
        quote = _first_sentence_with(text, words) or text[:80]
        out.append(
            TopicMention(
                review_id=review_id,
                topic=topic,
                sentiment=sentiment,
                severity=severity,
                quote=quote,
                quote_en=quote,
            )
        )
    return out


def _first_sentence_with(text: str, words: list[str]) -> str | None:
    parts = re.split(r"(?<=[.!?])\s+", text)
    for part in parts:
        low = part.lower()
        if any(w in low for w in words):
            return part.strip()[:200]
    return None


def live_tag(text: str, review_id: str) -> list[TopicMention]:
    from hotelpulse.analysis.tagger import tag_reviews

    review = Review(
        review_id=review_id,
        hotel_id="eval:hotel",
        source="google_maps",
        text=text,
    )
    return tag_reviews([review], persist=False)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def evaluate(gold_rows: list[dict], pred_fn) -> dict:
    """Topic-level precision/recall/F1 + sentiment accuracy on matched topics."""
    topics = list(Topic)
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    sent_correct = 0
    sent_total = 0
    gold_topic_set: set[tuple[str, Topic]] = set()
    pred_topic_set: set[tuple[str, Topic]] = set()
    gold_sent: dict[tuple[str, Topic], str] = {}
    pred_sent: dict[tuple[str, Topic], str] = {}

    for row in gold_rows:
        rid = row["review_id"]
        text = row["text"]
        gold = {(Topic(m["topic"]), Sentiment(m["sentiment"])) for m in row.get("mentions", [])}
        gold_topics = {t for t, _ in gold}
        for t in gold_topics:
            gold_topic_set.add((rid, t))
            gold_sent[(rid, t)] = next(s for tt, s in gold if tt == t)

        preds = pred_fn(text, rid)
        pred_topics = {m.topic for m in preds}
        for t in pred_topics:
            pred_topic_set.add((rid, t))
            pred_sent[(rid, t)] = next(m.sentiment for m in preds if m.topic == t).value

        for t in topics:
            g = t in gold_topics
            p = t in pred_topics
            if g and p:
                tp[t] += 1
            elif p and not g:
                fp[t] += 1
            elif g and not p:
                fn[t] += 1

    for key in gold_topic_set & pred_topic_set:
        sent_total += 1
        if gold_sent[key] == pred_sent[key]:
            sent_correct += 1

    per_topic = {}
    f1s = []
    for t in topics:
        precision = tp[t] / (tp[t] + fp[t]) if (tp[t] + fp[t]) else 0.0
        recall = tp[t] / (tp[t] + fn[t]) if (tp[t] + fn[t]) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        per_topic[t.value] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "tp": tp[t],
            "fp": fp[t],
            "fn": fn[t],
        }
        if (tp[t] + fn[t]) > 0:  # only average topics that appear in gold
            f1s.append(f1)

    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
    micro_p = sum(tp.values()) / max(1, sum(tp.values()) + sum(fp.values()))
    micro_r = sum(tp.values()) / max(1, sum(tp.values()) + sum(fn.values()))
    micro_f1 = (
        2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) else 0.0
    )
    sent_acc = sent_correct / sent_total if sent_total else 0.0

    return {
        "n_reviews": len(gold_rows),
        "per_topic": per_topic,
        "macro_f1": round(macro_f1, 3),
        "micro_precision": round(micro_p, 3),
        "micro_recall": round(micro_r, 3),
        "micro_f1": round(micro_f1, 3),
        "sentiment_accuracy": round(sent_acc, 3),
        "sentiment_n": sent_total,
    }


def write_results_md(stats: dict, mode: str) -> None:
    lines = [
        "# HotelPulse tagger eval",
        "",
        f"Mode: **{mode}**",
        f"Reviews: **{stats['n_reviews']}** (from `eval/labeled_reviews.jsonl`)",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Macro F1 (topics present in gold) | {stats['macro_f1']} |",
        f"| Micro precision | {stats['micro_precision']} |",
        f"| Micro recall | {stats['micro_recall']} |",
        f"| Micro F1 | {stats['micro_f1']} |",
        f"| Sentiment accuracy (matched topics) | {stats['sentiment_accuracy']} (n={stats['sentiment_n']}) |",
        "",
        "## Per-topic",
        "",
        "| Topic | Precision | Recall | F1 | TP | FP | FN |",
        "|---|---|---|---|---|---|---|",
    ]
    for topic, row in stats["per_topic"].items():
        lines.append(
            f"| {topic} | {row['precision']} | {row['recall']} | {row['f1']} "
            f"| {row['tp']} | {row['fp']} | {row['fn']} |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- Offline mode uses a keyword mock tagger — numbers are a harness sanity check, not live-model accuracy.",
        "- Run `py eval/run_eval.py --live` to measure the real model and paste those numbers into README.md.",
        "- Report honestly; do not tune the labeled set to flatter the model.",
        "",
    ]
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {RESULTS}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the real free LLM tagger (Gemini preferred, Groq fallback)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate first N reviews")
    args = parser.parse_args()

    rows = load_labeled(LABELED)
    if args.limit:
        rows = rows[: args.limit]

    if args.live:
        from hotelpulse.analysis.llm_client import LLMClientError, resolve_provider
        from hotelpulse.config import get_settings

        try:
            provider = resolve_provider()
        except LLMClientError as exc:
            print(str(exc))
            return 1
        settings = get_settings()
        model = settings.tag_model
        stats = evaluate(rows, live_tag)
        mode = f"live ({provider} / {model})"
    else:
        stats = evaluate(rows, mock_tag)
        mode = "offline mock (keyword tagger)"

    write_results_md(stats, mode)
    print(json.dumps({k: stats[k] for k in stats if k != "per_topic"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
