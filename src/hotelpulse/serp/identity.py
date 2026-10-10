"""Cross-source hotel identity matching (Google Maps <-> Tripadvisor).

When a Tripadvisor search returns several similarly-named listings, we must not
silently attach the wrong hotel's reviews. This module keeps that decision
conservative:

* Token-overlap name similarity, 0.55 confidence threshold.
* A guard against matching different numeric hotel suffixes — `OYO 123` and
  `OYO 456` must never match, brands rely on that number.
* Ambiguous ties are rejected rather than guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hotelpulse.models import HotelCandidate

CONFIDENCE_THRESHOLD = 0.55

# Brand-number tokens: "OYO 123", "Treebo 456", "FabHotel 789".
_BRAND_NUMBER = re.compile(
    r"\b(oyo|treebo|fabhotel|fabexpress|hotel)\s*(\d{1,6})\b", re.IGNORECASE
)

_STOPWORDS = {
    "hotel", "the", "a", "an", "in", "by", "of", "and", "&",
    "residency", "inn", "lodge", "palace", "resort", "stay",
}


def _tokens(name: str) -> list[str]:
    lowered = name.lower()
    return [t for t in re.findall(r"[a-z0-9]+", lowered) if t not in _STOPWORDS or t.isdigit()]


def _brand_numbers(name: str) -> dict[str, str]:
    """Map brand -> number for every '<brand> <digits>' token in the name."""
    return {m.group(1).lower(): m.group(2) for m in _BRAND_NUMBER.finditer(name)}


def name_similarity(a: str, b: str) -> float:
    """Token overlap between two names, 0.0 to 1.0."""
    ta = set(_tokens(a))
    tb = set(_tokens(b))
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    return len(intersection) / max(len(ta), len(tb))


def _suffix_conflict(a: str, b: str) -> bool:
    """True when two names carry the same brand prefix but *different* numbers.

    'OYO 123 Bangalore' vs 'OYO 456 Bangalore' -> conflicting. A name with no
    brand number is never in conflict by this rule alone.
    """
    na = _brand_numbers(a)
    nb = _brand_numbers(b)
    for brand, num in na.items():
        other = nb.get(brand)
        if other is not None and other != num:
            return True
    return False


@dataclass(frozen=True)
class MatchResult:
    candidate: HotelCandidate | None
    confidence: float
    reason: str


def match_tripadvisor_listing(
    own_name: str,
    candidates: list[HotelCandidate],
    *,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> MatchResult:
    """Pick the one Tripadvisor listing that is confidently the same hotel.

    Returns a MatchResult with candidate=None when:
      * there are no candidates;
      * no candidate clears the confidence threshold;
      * two or more candidates tie at the top (ambiguous).
    """
    if not candidates:
        return MatchResult(None, 0.0, "no tripadvisor candidates")

    scored: list[tuple[float, HotelCandidate]] = []
    for cand in candidates:
        if _suffix_conflict(own_name, cand.name):
            continue
        sim = name_similarity(own_name, cand.name)
        if sim >= threshold:
            scored.append((sim, cand))

    if not scored:
        return MatchResult(None, 0.0, "no candidate above threshold")

    scored.sort(key=lambda t: t[0], reverse=True)
    best_score, best = scored[0]
    if len(scored) > 1:
        second_score = scored[1][0]
        if best_score == second_score:
            return MatchResult(
                None,
                best_score,
                "ambiguous tie between two equally-named listings",
            )
    return MatchResult(best, best_score, "matched")
