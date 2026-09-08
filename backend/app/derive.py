"""Read-time derivations over the bills table.

Nothing here is stored. A state's headline bill, its legislation stage (what
the map colors by), and its review counts are computed from ``bills`` rows so
that a reviewer's decision takes effect immediately and there is exactly one
source of truth.
"""
import math
from collections import Counter
from datetime import date
from typing import Dict, Iterable, List, Optional

from app.models.legislation import Bill, LocalAction, STAGE_RANK

CONFIDENCE_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def headline_sort_key(b: Bill):
    """Best headline candidate first: a real bill before a resolution, then
    confidence, then passed, then LegiScan relevance, then most recent action."""
    return (
        0 if b.is_resolution else 1,
        CONFIDENCE_RANK.get(b.match_confidence, 0),
        1 if b.bill_stage == "passed" else 0,
        b.relevance_score or 0,
        b.last_action_date or "",
    )


def included_bills(bills: Iterable[Bill]) -> List[Bill]:
    return sorted((b for b in bills if b.effective_included), key=headline_sort_key, reverse=True)


def headline_bill(bills: Iterable[Bill]) -> Optional[Bill]:
    inc = included_bills(bills)
    return inc[0] if inc else None


def legislation_stage(bills: Iterable[Bill]) -> Optional[str]:
    """Strongest stage among included *bills*, or None when nothing is included.

    Resolutions are skipped: an adopted "urging the department to..." never
    becomes law, and the layer is labeled "Passed into law". They still show
    in the state's bill list with a resolution chip."""
    best = None
    for b in bills:
        if not b.effective_included or not b.bill_stage or b.is_resolution:
            continue
        if best is None or STAGE_RANK.get(b.bill_stage, 0) > STAGE_RANK.get(best, 0):
            best = b.bill_stage
    return best


def review_counts(bills: Iterable[Bill]) -> Dict[str, int]:
    bills = list(bills)
    by_decision = Counter(b.decision for b in bills)
    inc = [b for b in bills if b.effective_included]
    by_stage = Counter(b.bill_stage for b in inc if b.bill_stage and not b.is_resolution)
    return {
        "total": len(bills),
        "included": len(inc),
        "resolutions": sum(1 for b in inc if b.is_resolution),
        "pending": by_decision.get("PENDING", 0),
        "manually_included": by_decision.get("INCLUDED", 0),
        "manually_excluded": by_decision.get("EXCLUDED", 0),
        "held": len(bills) - len(inc),
        "by_stage": {s: by_stage.get(s, 0) for s in STAGE_RANK},
    }


# ---------------------------------------------------------------------------
# Local actions -> per-state "local signal"
# ---------------------------------------------------------------------------
# Nothing below is stored either. An action's status comes from its dates and
# lifecycle; a state's leaning comes from the direction of its *active*
# actions, weighted by how many students they touch and how recent they are.

LEANING_THRESHOLD = 0.5   # |score| below this reads as "mixed"


def action_status(a: LocalAction, today: Optional[date] = None) -> str:
    """proposed | active | expired | rescinded -- derived, never edited."""
    today = today or date.today()
    if a.lifecycle == "rescinded":
        return "rescinded"
    if a.lifecycle == "proposed":
        return "proposed"
    if a.effective_from and date.fromisoformat(a.effective_from) > today:
        return "proposed"
    if a.effective_until and date.fromisoformat(a.effective_until) < today:
        return "expired"
    return "active"


def action_weight(a: LocalAction, today: Optional[date] = None) -> float:
    """Bigger and more recent actions count for more.

    Enrollment enters on a log scale (a 900k district is ~2x a 9k district, not
    100x) and recency decays linearly from 1.0 at <=12 months old to 0.5 at
    36 months, then holds.
    """
    today = today or date.today()
    size = math.log10(max(a.enrollment or 0, 1000))
    if a.effective_from:
        months = (today - date.fromisoformat(a.effective_from)).days / 30.4
        recency = 1.0 if months <= 12 else max(0.5, 1.0 - (months - 12) / 48)
    else:
        recency = 0.75
    return size * recency


def active_actions(actions: Iterable[LocalAction], today: Optional[date] = None) -> List[LocalAction]:
    today = today or date.today()
    return [a for a in actions if action_status(a, today) == "active"]


def local_signal(actions: Iterable[LocalAction], today: Optional[date] = None) -> Dict:
    """Roll a state's local actions up to one glyph's worth of information.

    leaning: restrictive | permissive | mixed | None (no active actions).
    score:   weighted mean direction of active actions, -2..+2.
    headline: the active action a reader should see first (largest, then newest).
    """
    today = today or date.today()
    actions = list(actions)
    active = active_actions(actions, today)
    score = None
    leaning = None
    if active:
        weights = [action_weight(a, today) for a in active]
        score = round(sum(a.direction * w for a, w in zip(active, weights)) / sum(weights), 2)
        if score <= -LEANING_THRESHOLD:
            leaning = "restrictive"
        elif score >= LEANING_THRESHOLD:
            leaning = "permissive"
        else:
            leaning = "mixed"
    head = max(active, key=lambda a: (a.enrollment or 0, a.effective_from or ""), default=None)
    latest = max((a.effective_from for a in actions if a.effective_from), default=None)
    return {
        "count": len(actions),
        "active": len(active),
        "leaning": leaning,
        "score": score,
        "latest": latest,
        "headline": (
            {"jurisdiction": head.jurisdiction, "action_type": head.action_type,
             "direction": head.direction, "grade_band": head.grade_band, "summary": head.summary}
            if head else None
        ),
    }


def sort_actions(actions: Iterable[LocalAction], today: Optional[date] = None) -> List[LocalAction]:
    """Active first, then by size and recency -- the order the modal lists them in."""
    today = today or date.today()
    order = {"active": 0, "proposed": 1, "expired": 2, "rescinded": 3}
    newest_first = sorted(actions, key=lambda a: a.effective_from or "", reverse=True)
    return sorted(newest_first, key=lambda a: (order[action_status(a, today)], -(a.enrollment or 0)))
