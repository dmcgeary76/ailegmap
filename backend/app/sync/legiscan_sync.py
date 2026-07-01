#!/usr/bin/env python3
"""
LegiScan API sync script: Poll for K-12 AI legislation updates.

Monthly sync for all 50 states + territories:
1. Search LegiScan full-text engine for AI bills that ALSO touch K-12 education
2. Score each result for K-12-AI relevance (fuzzy mapping) and assign confidence
3. Capture real bill status (Introduced / Passed / Failed / ...) for map color-coding
4. Rank bills so the best K-12-AI match becomes the state's primary bill
5. Flag new / low-confidence bills for manual review (audit trail)

Why this version exists
------------------------
The previous version queried the bare phrase "artificial intelligence" with no
education filter and no `year` parameter. LegiScan's getSearch defaults to
`year=2` (current session only), so passed legislation from prior years was
dropped, and the unfiltered query returned any AI bill in the state (tax,
procurement, deepfakes, etc.). Whichever bill came back first was stored as the
state's primary bill -- which is why states showed bills unrelated to K-12 AI.

This version:
  * Requires BOTH an AI term AND an education term via a boolean full-text query
  * Searches ALL sessions (year=1) so passed/historical bills are included
  * Scores + ranks results, promoting the best K-12-AI match and flagging the rest
  * Reads the numeric status code to distinguish introduced / debated / passed

Usage:
    python legiscan_sync.py --preview --state CA   # Show ranked results, NO DB writes
    python legiscan_sync.py --state CA             # Sync one state
    python legiscan_sync.py --all                  # Sync all states
    python legiscan_sync.py --all --dry-run        # Test all states, no commits
    python legiscan_sync.py --review               # (see review_queue API)

Note: api.legiscan.com must be reachable from where this runs. The --preview
mode requires only the LEGISCAN_API_KEY and a network connection (no database),
so it is the quickest way to confirm the keyword search returns valid results.
"""

import requests
import json
import argparse
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import time
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# LegiScan API configuration
LEGISCAN_BASE = "https://api.legiscan.com"
PAGE_SIZE = 50  # getSearch's fixed page size (confirmed in LegiScan API docs)

# ---------------------------------------------------------------------------
# Relevance vocabulary
# ---------------------------------------------------------------------------
# An incoming bill is considered K-12-AI relevant only if it references BOTH an
# AI concept AND a K-12 education concept. LegiScan applies NLP stemming, so we
# do not need plural/variant forms in the query, but the client-side scorer below
# matches against the literal title text, so we keep a slightly broader list.

AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "generative ai",
    "large language model",
    "automated decision",
    "chatbot",
    "deepfake",
    "ai",   # word-boundary matched below, so "AI", "(AI)", "AI:" hit but "chair" does not
]

# Education vocabulary used by the title scorer. Broadened after live calibration:
# bills like "Artificial intelligence: education and workforce development" and
# "LEAD for Kids Act" were missed because bare "education" / "school" / "kids"
# were absent.
EDUCATION_TERMS = [
    "k-12",
    "k12",
    "kindergarten",
    "elementary",
    "secondary",
    "school",          # also matches "schools", "public school", "school district"
    "classroom",
    "curriculum",
    "student",
    "pupil",
    "teacher",
    "educator",
    "education",
    "instruction",
    "kids",
    # NOTE: bare "child"/"minor" deliberately excluded -- they dragged in CSAM
    # and criminal-offense bills (child pornography, deepfake crimes) that mention
    # AI but are not classroom-AI policy. Genuine school bills also carry
    # "school"/"pupil"/"student", so nothing real is lost.
]

# K-12-specific markers: presence of one of these confirms K-12 (vs higher-ed)
# context and overrides a higher-ed demotion.
K12_SPECIFIC_TERMS = [
    "k-12", "k12", "kindergarten", "elementary", "pupil",
    "secondary school", "secondary education", "public school",
    "school district", "schoolchild",
]

# Higher-ed markers: bills explicitly scoped to colleges/universities are NOT
# K-12 and are demoted unless a K-12-specific term is also present.
HIGHER_ED_TERMS = [
    "postsecondary", "post-secondary", "higher education",
    "university", "universities", "community college", "college",
]

# Title patterns that mark a bill as procedural/ceremonial/budget noise. These
# are forced to LOW confidence regardless of keyword hits.
NOISE_TITLE_TERMS = [
    "congratulating", "commending", "recognizing", "honoring", "commemorating",
    "budget act", "trailer bill", "omnibus", "maintenance of the codes",
    "supplemental appropriation", "making appropriations", "house rules",
    "state capitol", " day.", " day at", "rules of procedure",
    # criminal / CSAM bills that mention AI deepfakes but are not classroom policy
    "child pornography", "criminal offense", "prosecution and punishment",
    "child sexual",
]

# Full-text boolean query: must contain an AI concept AND an education concept,
# and NOT be a purely ceremonial resolution (those crowd out real bills).
# Phrases are quoted; LegiScan applies NLP stemming for singular/plural variants.
SEARCH_QUERY = (
    '('
    '("artificial intelligence" OR "machine learning" OR "generative AI" '
    'OR "large language model" OR "automated decision" OR chatbot) '
    'AND '
    '(school OR student OR pupil OR teacher OR educator OR classroom '
    'OR curriculum OR "K-12" OR kindergarten OR elementary '
    'OR "secondary education" OR "school district" OR "board of education")'
    ') '
    'NOT (congratulating OR commending OR recognizing OR honoring OR commemorating)'
)

# LegiScan numeric progress codes -> (label, stage for map color-coding)
#   stage values: "introduced", "debated", "passed", "failed"
STATUS_MAP: Dict[int, Tuple[str, str]] = {
    0: ("Prefiled / N/A", "introduced"),
    1: ("Introduced", "introduced"),
    2: ("Engrossed", "debated"),
    3: ("Enrolled", "debated"),
    4: ("Passed", "passed"),
    5: ("Vetoed", "failed"),
    6: ("Failed / Dead", "failed"),
}

# Confidence thresholds for ranking
CONF_HIGH = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW = "LOW"

# US states + territories (50 states + 3 territories)
STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "GU", "PR", "VI",  # Territories: Guam, Puerto Rico, Virgin Islands
]


# ===========================================================================
# Pure helper functions (no DB / no network -- unit testable)
# ===========================================================================

def map_status(raw_status) -> Tuple[str, str]:
    """Map a LegiScan numeric status code to (label, stage).

    Accepts int, numeric string, or an already-human label. Unknown values fall
    back to ("Unknown", "introduced") so the map still renders something.
    """
    if raw_status is None:
        return ("Unknown", "introduced")
    # Numeric code (int or string digit)
    try:
        code = int(raw_status)
        return STATUS_MAP.get(code, (f"Status {code}", "introduced"))
    except (TypeError, ValueError):
        pass
    # Already a string label -- normalize against known labels
    text = str(raw_status).strip().lower()
    for label, stage in STATUS_MAP.values():
        if text == label.lower():
            return (label, stage)
    if "pass" in text or "enact" in text or "signed" in text:
        return (str(raw_status), "passed")
    if "fail" in text or "dead" in text or "veto" in text:
        return (str(raw_status), "failed")
    return (str(raw_status) or "Unknown", "introduced")


def _matched_terms(text: str, vocabulary: List[str]) -> List[str]:
    """Return which vocabulary terms appear in text (case-insensitive).

    Matching requires a left word boundary but allows trailing word characters,
    giving lightweight stemming: "school" matches "schools", "student" matches
    "students" -- while "secondary education" will NOT match inside
    "POSTsecondary education" (no boundary before "secondary").
    """
    low = text.lower()
    hits = []
    for term in vocabulary:
        t = term.strip()
        # (?<!\w) = left boundary; no right boundary so plurals/derivations match.
        if re.search(r"(?<!\w)" + re.escape(t), low):
            hits.append(t)
    return hits


def score_bill(bill: Dict) -> Dict:
    """Score a LegiScan search result for K-12-AI relevance.

    Even though the query already requires AI + education terms in the bill TEXT,
    the search result only exposes the title. We use the title to estimate how
    on-topic each bill is, so the most clearly K-12-AI bill becomes the state's
    primary record and weaker matches are flagged for human review rather than
    silently promoted.

    Returns a dict with: relevance (LegiScan), title_ai_terms, title_edu_terms,
    confidence, and is_k12_ai (bool gate).
    """
    title = bill.get("title", "") or ""
    legiscan_relevance = 0
    try:
        legiscan_relevance = int(bill.get("relevance", 0) or 0)
    except (TypeError, ValueError):
        legiscan_relevance = 0

    ai_in_title = _matched_terms(title, AI_TERMS)
    edu_in_title = _matched_terms(title, EDUCATION_TERMS)
    is_noise = bool(_matched_terms(title, NOISE_TITLE_TERMS))
    is_higher_ed = bool(_matched_terms(title, HIGHER_ED_TERMS))
    is_k12_specific = bool(_matched_terms(title, K12_SPECIFIC_TERMS))

    # Gating logic, calibrated against live TX/CA results. The full-text query
    # already guarantees BOTH an AI term and an education term appear somewhere in
    # the bill TEXT. The TITLE tells us what the bill is actually *about*:
    #   * Ceremonial / budget / procedural title  -> LOW (noise, never auto-promote)
    #   * Explicitly higher-ed (no K-12 marker)    -> LOW (out of K-12 scope)
    #   * AI + education both in title             -> HIGH (clearly on-topic)
    #   * Education in title (AI guaranteed in body)-> MEDIUM (education-focused)
    #   * AI only / neither in title               -> LOW (review; e.g. AI in
    #       procurement, health, elections that mention "school" once in the body)
    if is_noise:
        confidence = CONF_LOW
    elif is_higher_ed and not is_k12_specific:
        confidence = CONF_LOW
    elif ai_in_title and edu_in_title:
        confidence = CONF_HIGH
    elif edu_in_title:
        confidence = CONF_MEDIUM
    else:
        confidence = CONF_LOW

    # is_k12_ai gate: HIGH/MEDIUM auto-qualify; LOW is kept but flagged for review.
    is_k12_ai = confidence in (CONF_HIGH, CONF_MEDIUM)

    return {
        "relevance": legiscan_relevance,
        "title_ai_terms": ai_in_title,
        "title_edu_terms": edu_in_title,
        "confidence": confidence,
        "is_k12_ai": is_k12_ai,
        "flags": {
            "noise": is_noise,
            "higher_ed": is_higher_ed and not is_k12_specific,
        },
    }


def _confidence_rank(confidence: str) -> int:
    return {CONF_HIGH: 3, CONF_MEDIUM: 2, CONF_LOW: 1}.get(confidence, 0)


def rank_bills(bills: List[Dict]) -> List[Dict]:
    """Attach scores and return bills sorted best-first.

    Sort key: (confidence, passed-stage bonus, LegiScan relevance, recency).
    The first element after ranking is the best candidate for the primary record.
    """
    enriched = []
    for bill in bills:
        score = score_bill(bill)
        label, stage = map_status(bill.get("status"))
        enriched.append({**bill, "_score": score, "_status_label": label, "_stage": stage})

    def sort_key(b):
        passed_bonus = 1 if b["_stage"] == "passed" else 0
        action_date = b.get("last_action_date") or ""
        return (
            _confidence_rank(b["_score"]["confidence"]),
            passed_bonus,
            b["_score"]["relevance"],
            action_date,
        )

    enriched.sort(key=sort_key, reverse=True)
    return enriched


# ===========================================================================
# Sync engine
# ===========================================================================

class LegiScanSync:
    """Sync K-12 AI legislation from LegiScan API."""

    def __init__(self, db=None, dry_run: bool = False, api_key: Optional[str] = None,
                 years: str = "1", fetch_status: bool = True):
        self.db = db
        self.dry_run = dry_run
        # getSearch does NOT return a bill's progress status, so we make a
        # follow-up getBill call per *relevant* bill to learn whether it passed.
        # Set False to skip (faster, but status stays "Unknown").
        self.fetch_status = fetch_status
        # `years`: LegiScan getSearch `year` param. 1=all, 2=current, 3=recent,
        # 4=prior, or a 4-digit year. Default "1" (all sessions) so passed and
        # historical bills are captured -- the previous default of 2 dropped them.
        self.years = years
        self.api_key = api_key
        if self.api_key is None:
            try:
                from app.database import settings
                self.api_key = settings.legiscan_api_key
            except Exception:
                self.api_key = os.environ.get("LEGISCAN_API_KEY")
        self.stats = {
            "searched": 0,
            "found": 0,
            "relevant": 0,
            "low_confidence": 0,
            "updated": 0,
            "flagged_review": 0,
            "errors": 0,
        }

    # ---- network ---------------------------------------------------------

    def search_bills(self, state: str) -> List[Dict]:
        """Search LegiScan for K-12 AI bills in a state (all sessions).

        getSearch returns at most PAGE_SIZE (50) results per call, even when
        `summary.count` reports far more hits in the index -- CA/NJ/HI/MD/NY/IL
        all silently lost bills past page 1 before this loop existed (up to 39
        missed for CA alone). Keep requesting subsequent pages until we've
        collected everything the index reports, or a page comes back short.
        """
        if not self.api_key:
            print(f"  ❌ LegiScan API key not set")
            print(f"     Set LEGISCAN_API_KEY in backend/.env or export LEGISCAN_API_KEY=your_key")
            self.stats["errors"] += 1
            return []

        bills: List[Dict] = []
        total_count = 0
        page = 1
        max_pages = 20  # safety cap; a single state's index shouldn't need this many

        while page <= max_pages:
            try:
                params = {
                    "key": self.api_key,
                    "op": "getSearch",
                    "state": state,
                    "query": SEARCH_QUERY,
                    "year": self.years,  # 1 = all sessions (captures passed/historical)
                    "page": page,
                }

                if page == 1:
                    print(f"  🔍 Searching {state}...", end=" ", flush=True)
                response = requests.get(LEGISCAN_BASE, params=params, timeout=20)
                response.raise_for_status()
                data = response.json()

                if data.get("status") != "OK":
                    alert = data.get("alert", {}).get("message", "")
                    print(f"❌ API error: {data.get('status')} {alert}")
                    self.stats["errors"] += 1
                    return bills  # keep whatever prior pages succeeded

                searchresult = data.get("searchresult", {})
                summary = searchresult.get("summary", {})
                total_count = summary.get("count", 0)

                page_bills = [
                    bill for key, bill in searchresult.items()
                    if key != "summary" and isinstance(bill, dict)
                ]
                if not page_bills:
                    break

                bills.extend(page_bills)

                # Stop once we have everything the index reports, or the page
                # came back short of PAGE_SIZE (LegiScan's own signal there's
                # no next page) -- whichever happens first.
                if len(bills) >= total_count or len(page_bills) < PAGE_SIZE:
                    break

                page += 1
                time.sleep(0.4)  # rate limiting between pages, same as elsewhere

            except requests.RequestException as e:
                print(f"❌ Request failed: {e}")
                self.stats["errors"] += 1
                return bills
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON response")
                self.stats["errors"] += 1
                return bills

        pages_fetched = min(page, max_pages)
        if pages_fetched > 1:
            print(f"✅ ({len(bills)} returned across {pages_fetched} pages, {total_count} total in index)")
        else:
            print(f"✅ ({len(bills)} returned, {total_count} total in index)")
        return bills

    def fetch_bill_status(self, bill_id) -> Optional[Tuple[str, str, str]]:
        """getBill lookup for authoritative status. Returns (label, stage, date)."""
        if not bill_id or not self.api_key:
            return None
        try:
            params = {"key": self.api_key, "op": "getBill", "id": bill_id}
            r = requests.get(LEGISCAN_BASE, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "OK":
                return None
            bill = data.get("bill", {})
            label, stage = map_status(bill.get("status"))
            return (label, stage, bill.get("status_date", ""))
        except (requests.RequestException, json.JSONDecodeError):
            return None

    def _enrich_status(self, bills: List[Dict]):
        """Populate real status on the given (relevant) bills via getBill."""
        if not self.fetch_status:
            return
        for b in bills:
            result = self.fetch_bill_status(b.get("bill_id"))
            if result:
                label, stage, date = result
                b["_status_label"] = label
                b["_stage"] = stage
                b["status_date"] = date
            time.sleep(0.4)  # rate limiting

    # ---- persistence -----------------------------------------------------

    def _bill_payload(self, bill: Dict) -> Dict:
        """Build the normalized bill dict we store (with relevance metadata)."""
        score = bill.get("_score") or score_bill(bill)
        label = bill.get("_status_label")
        stage = bill.get("_stage")
        if label is None or stage is None:
            label, stage = map_status(bill.get("status"))
        return {
            "bill_number": bill.get("bill_number"),
            "bill_title": bill.get("title", ""),
            "bill_status": label,
            "bill_stage": stage,  # introduced | debated | passed | failed
            "bill_url": bill.get("url", ""),
            "bill_text_url": bill.get("text_url", ""),
            "last_action": bill.get("last_action", ""),
            "last_action_date": bill.get("last_action_date", ""),
            "status_date": bill.get("status_date", ""),
            "legiscan_bill_id": bill.get("bill_id"),
            "relevance_score": score["relevance"],
            "match_confidence": score["confidence"],
            "matched_ai_terms": score["title_ai_terms"],
            "matched_edu_terms": score["title_edu_terms"],
        }

    def sync_state(self, state: str):
        """Search, rank, and persist all K-12 AI bills for a state."""
        raw_bills = self.search_bills(state)
        self.stats["searched"] += 1
        if not raw_bills:
            return []

        ranked = rank_bills(raw_bills)
        self.stats["found"] += len(ranked)

        relevant = [b for b in ranked if b["_score"]["is_k12_ai"]]
        low_conf = [b for b in ranked if not b["_score"]["is_k12_ai"]]

        # Fetch authoritative status for relevant bills only, then re-sort so
        # passed bills become the primary candidate.
        self._enrich_status(relevant)
        relevant.sort(
            key=lambda b: (
                _confidence_rank(b["_score"]["confidence"]),
                1 if b.get("_stage") == "passed" else 0,
                b["_score"]["relevance"],
                b.get("last_action_date") or "",
            ),
            reverse=True,
        )

        self.stats["relevant"] += len(relevant)
        self.stats["low_confidence"] += len(low_conf)

        if not relevant:
            print(f"     ⚠️  No high/medium-confidence K-12 AI bills "
                  f"({len(low_conf)} low-confidence flagged for review)")

        if self.db is None or self.dry_run:
            # Preview / dry-run: report relevant first, then flagged-for-review.
            for b in relevant:
                s = b["_score"]
                print(f"     [{s['confidence']:<6}] rel={s['relevance']:>3} "
                      f"{b['_status_label']:<14} {b.get('bill_number','?'):<10} "
                      f"{(b.get('title','') or '')[:70]}")
            if low_conf:
                print(f"     ----- {len(low_conf)} flagged for review (low confidence) -----")
                for b in low_conf:
                    s = b["_score"]
                    tag = "noise" if s["flags"]["noise"] else ("higher-ed" if s["flags"]["higher_ed"] else "review")
                    print(f"     [{s['confidence']:<6}] rel={s['relevance']:>3} "
                          f"{tag:<14} {b.get('bill_number','?'):<10} "
                          f"{(b.get('title','') or '')[:70]}")
            return relevant + low_conf

        self._persist(state, relevant, low_conf)
        self._upsert_review_items(state, relevant + low_conf)
        return relevant + low_conf

    def _upsert_review_items(self, state: str, bills: List[Dict]):
        """Record every discovered bill in the bill-level review queue.

        Refreshes metadata + auto-classification each run; preserves any manual
        decision/note a reviewer has set. Keyed on (state_code, legiscan_bill_id)
        so recycled bill numbers across sessions don't collide.
        """
        from app.models.legislation import BillReviewItem

        for b in bills:
            bid = b.get("bill_id")
            if not bid:
                continue
            score = b.get("_score") or score_bill(b)
            label = b.get("_status_label")
            stage = b.get("_stage")
            if label is None or stage is None:
                label, stage = map_status(b.get("status"))

            conf = score["confidence"]
            auto = "INCLUDE" if score["is_k12_ai"] else "REVIEW"
            if score["flags"]["noise"]:
                flag = "noise"
            elif score["flags"]["higher_ed"]:
                flag = "higher_ed"
            elif not score["is_k12_ai"]:
                flag = "review"
            else:
                flag = ""

            item = self.db.query(BillReviewItem).filter_by(
                state_code=state, legiscan_bill_id=bid
            ).first()

            if item is None:
                self.db.add(BillReviewItem(
                    state_code=state,
                    legiscan_bill_id=bid,
                    bill_number=b.get("bill_number"),
                    bill_title=b.get("title", ""),
                    bill_url=b.get("url", ""),
                    bill_text_url=b.get("text_url", ""),
                    bill_status=label,
                    bill_stage=stage,
                    status_date=b.get("status_date", ""),
                    last_action=b.get("last_action", ""),
                    last_action_date=b.get("last_action_date", ""),
                    relevance_score=score["relevance"],
                    match_confidence=conf,
                    auto_decision=auto,
                    flag_reason=flag,
                    matched_ai_terms=score["title_ai_terms"],
                    matched_edu_terms=score["title_edu_terms"],
                    decision="PENDING",
                ))
            else:
                # Refresh metadata + classification; KEEP manual decision/note.
                item.bill_number = b.get("bill_number")
                item.bill_title = b.get("title", "")
                item.bill_url = b.get("url", "")
                item.bill_text_url = b.get("text_url", "")
                item.bill_status = label
                item.bill_stage = stage
                item.status_date = b.get("status_date", "") or item.status_date
                item.last_action = b.get("last_action", "")
                item.last_action_date = b.get("last_action_date", "")
                item.relevance_score = score["relevance"]
                item.match_confidence = conf
                item.auto_decision = auto
                item.flag_reason = flag
                item.matched_ai_terms = score["title_ai_terms"]
                item.matched_edu_terms = score["title_edu_terms"]
                item.last_seen = datetime.utcnow()

        self.db.commit()

    def _persist(self, state: str, relevant: List[Dict], low_conf: List[Dict]):
        """Write ranked results to the DB with an audit trail."""
        from app.models.legislation import StateLegislation, LegislationUpdate
        from sqlalchemy.orm.attributes import flag_modified

        primary = relevant[0] if relevant else None
        extras = (relevant[1:] if relevant else []) + low_conf

        state_record = self.db.query(StateLegislation).filter(
            StateLegislation.state_code == state
        ).first()

        primary_payload = self._bill_payload(primary) if primary else None

        if not state_record:
            state_record = StateLegislation(
                state_code=state,
                state_name=self._get_state_name(state),
                bill_number=primary_payload["bill_number"] if primary_payload else None,
                bill_title=primary_payload["bill_title"] if primary_payload else None,
                bill_status=primary_payload["bill_status"] if primary_payload else "Absent",
                bill_url=primary_payload["bill_url"] if primary_payload else None,
                bill_legiscan_id=primary_payload["legiscan_bill_id"] if primary_payload else None,
                match_confidence=primary_payload["match_confidence"] if primary_payload else None,
                bill_stage=primary_payload["bill_stage"] if primary_payload else None,
                additional_bills=[self._bill_payload(b) for b in extras],
                guidance_exists=False,
                regulatory_stance="ABSENT",
                maturity="NASCENT",
            )
            self.db.add(state_record)
            self.db.commit()
            self.db.add(LegislationUpdate(
                state_legislation_id=state_record.id,
                field_changed="full_record",
                old_value=None,
                new_value=f"New state record. Primary: "
                          f"{primary_payload['bill_number'] if primary_payload else 'none'} "
                          f"({primary_payload['match_confidence'] if primary_payload else 'n/a'})",
                changed_by="legiscan_sync",
                change_reason="Initial state record from LegiScan API (K-12 AI filtered)",
            ))
            self.db.commit()
            self.stats["flagged_review"] += 1
            return

        # Existing record: refresh primary if we found a stronger/passed match,
        # and merge the rest into additional_bills. Dedup by legiscan_bill_id --
        # bill_number recycles across sessions (year=1), so two different HB4390s
        # are distinct bills and must both be kept.
        existing_extra = state_record.additional_bills or []
        known = {b.get("legiscan_bill_id") for b in existing_extra if b.get("legiscan_bill_id")}

        def _rank(confidence, stage):
            # Same ordering rank_bills() uses to pick a primary within one run,
            # applied here across runs so a stronger bill can replace a weaker
            # stored one instead of freezing in place forever. Legacy rows with
            # no stored confidence/stage rank at the bottom (0, 0), so the first
            # real HIGH/MEDIUM match found after this migration will promote.
            return (_confidence_rank(confidence), 1 if stage == "passed" else 0)

        changed = False
        if primary_payload:
            # NOTE: deliberately NOT gated on `primary_payload["legiscan_bill_id"]
            # not in known` here. A bill that deserves to be primary may already
            # be sitting in additional_bills from before this promotion logic
            # existed (or from a run where it wasn't yet strong enough) -- being
            # "known" must not permanently block it from ever being promoted.
            # `known` is only used below to avoid *duplicate* entries in extras.
            same_bill = (
                state_record.bill_legiscan_id is not None
                and state_record.bill_legiscan_id == primary_payload["legiscan_bill_id"]
            )
            stronger = _rank(primary_payload["match_confidence"], primary_payload["bill_stage"]) > \
                _rank(state_record.match_confidence, state_record.bill_stage)

            if same_bill:
                # Same bill re-surfacing (e.g. status advanced from Introduced to
                # Passed) -- refresh its fields in place, don't touch extras.
                if (state_record.bill_status != primary_payload["bill_status"]
                        or state_record.bill_title != primary_payload["bill_title"]):
                    old_status = state_record.bill_status
                    state_record.bill_title = primary_payload["bill_title"]
                    state_record.bill_status = primary_payload["bill_status"]
                    state_record.bill_url = primary_payload["bill_url"]
                    state_record.match_confidence = primary_payload["match_confidence"]
                    state_record.bill_stage = primary_payload["bill_stage"]
                    changed = True
                    self.db.add(LegislationUpdate(
                        state_legislation_id=state_record.id,
                        field_changed="bill_status",
                        old_value=str(old_status),
                        new_value=primary_payload["bill_status"],
                        changed_by="legiscan_sync",
                        change_reason="Status refresh on existing primary bill",
                    ))
            elif not state_record.bill_number or stronger:
                # Promote. If this bill is already sitting in additional_bills
                # (e.g. from before this promotion logic existed), pull it out
                # first so it doesn't end up listed as both primary and extra.
                if primary_payload["legiscan_bill_id"] in known:
                    existing_extra = [
                        b for b in existing_extra
                        if b.get("legiscan_bill_id") != primary_payload["legiscan_bill_id"]
                    ]

                # Demote the current primary (if any) into additional_bills so
                # it isn't lost, then adopt the new one.
                if state_record.bill_number and state_record.bill_legiscan_id and \
                        state_record.bill_legiscan_id not in known:
                    existing_extra.append({
                        "bill_number": state_record.bill_number,
                        "bill_title": state_record.bill_title,
                        "bill_status": state_record.bill_status,
                        "bill_url": state_record.bill_url,
                        "legiscan_bill_id": state_record.bill_legiscan_id,
                        "match_confidence": state_record.match_confidence,
                        "bill_stage": state_record.bill_stage,
                    })
                    known.add(state_record.bill_legiscan_id)

                old = state_record.bill_number
                state_record.bill_number = primary_payload["bill_number"]
                state_record.bill_title = primary_payload["bill_title"]
                state_record.bill_status = primary_payload["bill_status"]
                state_record.bill_url = primary_payload["bill_url"]
                state_record.bill_legiscan_id = primary_payload["legiscan_bill_id"]
                state_record.match_confidence = primary_payload["match_confidence"]
                state_record.bill_stage = primary_payload["bill_stage"]
                changed = True
                self.db.add(LegislationUpdate(
                    state_legislation_id=state_record.id,
                    field_changed="bill_number",
                    old_value=str(old),
                    new_value=primary_payload["bill_number"],
                    changed_by="legiscan_sync",
                    change_reason=f"Promoted stronger primary bill "
                                  f"({primary_payload['match_confidence']} confidence, "
                                  f"{primary_payload['bill_stage']})",
                ))
                known.add(primary_payload["legiscan_bill_id"])
            else:
                extras = [primary] + extras

        for b in extras:
            payload = self._bill_payload(b)
            bid = payload["legiscan_bill_id"]
            if bid and bid not in known:
                existing_extra.append(payload)
                known.add(bid)
                changed = True
                self.db.add(LegislationUpdate(
                    state_legislation_id=state_record.id,
                    field_changed="additional_bills",
                    old_value=None,
                    new_value=f"Added {payload['bill_number']} "
                              f"({payload['match_confidence']}, {payload['bill_status']})",
                    changed_by="legiscan_sync",
                    change_reason="Bill from LegiScan API (K-12 AI filtered)",
                ))

        if changed:
            state_record.additional_bills = existing_extra
            flag_modified(state_record, "additional_bills")
            self.db.commit()
            self.stats["updated"] += 1

    # ---- orchestration ---------------------------------------------------

    def sync_all(self):
        print("\n📡 LegiScan Sync: K-12 AI Legislation")
        print("=" * 70)
        print(f"Query: {SEARCH_QUERY}")
        print(f"Years: {self.years} (1=all sessions)   Dry run: {self.dry_run}")
        print()
        for state in STATES:
            try:
                self.sync_state(state)
                time.sleep(0.6)  # rate limiting
            except Exception as e:
                print(f"❌ Error syncing {state}: {e}")
                self.stats["errors"] += 1
                if self.db is not None:
                    # Without this, a single failed flush poisons the session --
                    # every subsequent state's commit fails too (cascading errors).
                    self.db.rollback()
        self._print_summary()

    def sync_one(self, state: str):
        print("\n📡 LegiScan Sync: Single State")
        print("=" * 70)
        print(f"State: {state}   Years: {self.years}   Dry run: {self.dry_run}")
        print(f"Query: {SEARCH_QUERY}\n")
        self.sync_state(state)
        self._print_summary()

    def _print_summary(self):
        print("\n" + "=" * 70)
        print("📊 SYNC SUMMARY")
        print("=" * 70)
        print(f"States searched:        {self.stats['searched']}")
        print(f"Bills returned:         {self.stats['found']}")
        print(f"K-12 AI relevant:       {self.stats['relevant']}")
        print(f"Low-confidence flagged: {self.stats['low_confidence']}")
        print(f"Records updated:        {self.stats['updated']}")
        print(f"New records:            {self.stats['flagged_review']}")
        print(f"Errors:                 {self.stats['errors']}")
        print("\n⚠️  DRY RUN - no changes committed" if self.dry_run else "\n✅ Sync complete")

    @staticmethod
    def _get_state_name(state: str) -> str:
        jurisdictions = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
            "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
            "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming",
            "GU": "Guam", "PR": "Puerto Rico", "VI": "Virgin Islands",
        }
        return jurisdictions.get(state, state)


def main():
    parser = argparse.ArgumentParser(description="Sync K-12 AI legislation from LegiScan API")
    parser.add_argument("--state", type=str, help="Sync single state (e.g., CA, TX, HI)")
    parser.add_argument("--all", action="store_true", help="Sync all states + territories")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without committing")
    parser.add_argument("--preview", action="store_true",
                        help="Search and print ranked results only (no DB connection needed)")
    parser.add_argument("--years", type=str, default="1",
                        help="LegiScan year scope: 1=all, 2=current, 3=recent, 4=prior, or YYYY (default 1)")
    parser.add_argument("--no-status", action="store_true",
                        help="Skip per-bill getBill status lookups (faster; status stays Unknown)")
    args = parser.parse_args()

    # Preview mode: no DB required -- quickest way to validate the keyword search.
    if args.preview:
        sync = LegiScanSync(db=None, dry_run=True, years=args.years,
                            fetch_status=not args.no_status)
        if args.state:
            sync.sync_one(args.state.upper())
        elif args.all:
            sync.sync_all()
        else:
            print("Use --preview with --state CA or --all")
        return

    from app.database import SessionLocal
    db = SessionLocal()
    try:
        sync = LegiScanSync(db, dry_run=args.dry_run, years=args.years,
                            fetch_status=not args.no_status)
        if args.state:
            sync.sync_one(args.state.upper())
        elif args.all:
            sync.sync_all()
        else:
            print("Usage:")
            print("  python legiscan_sync.py --preview --state CA  # validate search, no DB")
            print("  python legiscan_sync.py --state CA            # sync one state")
            print("  python legiscan_sync.py --all                 # sync all states")
            print("  python legiscan_sync.py --all --dry-run       # test without committing")
    finally:
        db.close()


if __name__ == "__main__":
    main()
