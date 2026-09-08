#!/usr/bin/env python3
"""
LegiScan sync: discover K-12 AI bills, score them, and keep the bills table current.

1. Search LegiScan's full-text index for bills that mention an AI concept AND a
   K-12 education concept (all sessions, so passed/historical bills count).
2. Score each result for K-12-AI relevance from its title -> HIGH / MEDIUM / LOW.
   Only HIGH is shown on the map without review; MEDIUM and LOW wait in the queue.
3. Look up authoritative status via getBill (skipped when LegiScan's
   change_hash says the bill hasn't changed since we last looked).
4. Upsert every bill into the ``bills`` table. Metadata and the automatic
   classification refresh on every run; a reviewer's include/exclude decision
   is never touched. Stage transitions are logged to ``bill_status_changes``.

The map derives each state's headline bill and color from ``bills`` at read
time, so this script never decides what a state "is" -- it only keeps the
evidence fresh.

Usage:
    python -m app.sync.legiscan_sync --preview --state CA   # ranked results, no DB writes
    python -m app.sync.legiscan_sync --state CA             # sync one state
    python -m app.sync.legiscan_sync --all                  # all LegiScan-covered jurisdictions
    python -m app.sync.legiscan_sync --all --no-status      # skip getBill lookups (fast, status stays Unknown)
    python -m app.sync.legiscan_sync --all --rescore        # re-run the title scorer on stored rows, no API
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.models.legislation import JURISDICTIONS, LEGISCAN_UNSUPPORTED, AUTO_INCLUDE_CONFIDENCE  # noqa: E402

# Jurisdictions the sync searches (LegiScan rejects GU/PR/VI outright).
SEARCHABLE = [c for c in JURISDICTIONS if c not in LEGISCAN_UNSUPPORTED]

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
    "artificial-intelligence",
    "artifical intelligence",    # WV HB5205 has this typo in its enrolled title
    "artificial intelligance",
    "a.i.",
    "machine learning",
    "generative ai",
    "large language model",
    "automated decision",
    "chatbot",
    "deepfake",
    "ai",   # matched with boundaries on BOTH sides (see _matched_terms), so "AI",
            # "(AI)", "AI:" hit but "chair", "aid", "aim" do not. Until 2026-09-08
            # only the left boundary was enforced and "school aid" scored HIGH.
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
    "honor", "inaugural year",
    "budget act", "trailer bill", "omnibus", "maintenance of the codes",
    "supplemental appropriation", "making appropriations", "appropriations",
    "necessary to implement the state",   # NY budget article VII bills
    "house rules",
    "state capitol", " day.", " day at", "rules of procedure",
    # criminal / CSAM bills that mention AI deepfakes but are not classroom policy
    "child pornography", "criminal offense", "prosecution and punishment",
    "child sexual",
]

# Full-text boolean query: must contain an AI concept AND an education concept.
# Phrases are quoted; LegiScan applies NLP stemming for singular/plural variants.
#
# There is deliberately NO "NOT (congratulating OR recognizing OR ...)" clause.
# Until 2026-09-08 there was one, meant to drop ceremonial resolutions -- but it
# is a *full-text* exclusion, so any statute whose text says "recognizing" or
# "honoring" anywhere vanished. Oklahoma SB1734 (a signed K-12 AI statute) was
# one of them; the clause removed 17 of 39 Oklahoma hits. Ceremonial noise is
# handled downstream by the title scorer (NOISE_TERMS) and by is_resolution().
SEARCH_QUERY = (
    '('
    '("artificial intelligence" OR "artifical intelligence" OR "machine learning" OR "generative AI" '
    'OR "large language model" OR "automated decision" OR chatbot) '
    'AND '
    '(school OR student OR pupil OR teacher OR educator OR classroom '
    'OR curriculum OR "K-12" OR kindergarten OR elementary '
    'OR "secondary education" OR "school district" OR "board of education")'
    ')'
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



# ===========================================================================
# Pure helper functions (no DB / no network -- unit testable)
# ===========================================================================

def map_status(raw_status) -> Tuple[str, str]:
    """Map a LegiScan numeric status code to (label, stage).

    Accepts int, numeric string, or an already-human label. Unknown values map
    to ("Unknown", None): a bill whose status we never fetched must not color
    a state "Introduced" -- no stage, no color.
    """
    if raw_status is None:
        return ("Unknown", None)
    # Numeric code (int or string digit)
    try:
        code = int(raw_status)
        return STATUS_MAP.get(code, (f"Status {code}", None))
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
        # Terms of three letters or fewer ("ai") get a right boundary too, or
        # "ai" matches "aid", "aim" and "aircraft".
        pattern = r"(?<!\w)" + re.escape(t) + (r"(?!\w)" if len(t) <= 3 else "")
        if re.search(pattern, low):
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
    #   * Education in title (AI somewhere in body)-> MEDIUM (review; usually a
    #       digital-citizenship / cyberbullying / CS bill that defines AI once)
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

    # is_k12_ai gate: only AUTO_INCLUDE_CONFIDENCE goes on the map unreviewed.
    is_k12_ai = confidence in AUTO_INCLUDE_CONFIDENCE

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
    """Discover bills for a jurisdiction and upsert them into the bills table."""

    def __init__(self, db=None, api_key: Optional[str] = None, years: str = "1",
                 fetch_status: bool = True, sleep: float = 0.4, query: str = SEARCH_QUERY):
        self.db = db
        self.fetch_status = fetch_status
        self.years = years  # 1=all sessions, 2=current, 3=recent, 4=prior, or YYYY
        self.query = query  # SEARCH_QUERY unless overridden (--query) for diagnosis
        self.sleep = sleep
        self.api_key = api_key
        if self.api_key is None:
            try:
                from app.database import settings
                self.api_key = settings.legiscan_api_key
            except Exception:
                self.api_key = os.environ.get("LEGISCAN_API_KEY")
        self.stats = {
            "searched": 0, "found": 0, "relevant": 0, "low_confidence": 0,
            "new_bills": 0, "status_changes": 0, "getbill_calls": 0, "errors": 0, "carryovers_linked": 0}

    # ---- network ---------------------------------------------------------

    def _get(self, **params) -> Optional[Dict]:
        params["key"] = self.api_key
        try:
            r = requests.get(LEGISCAN_BASE, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"❌ Request failed: {e}")
            self.stats["errors"] += 1
            return None
        if data.get("status") != "OK":
            alert = data.get("alert", {}).get("message", "")
            print(f"❌ API error: {data.get('status')} {alert}")
            self.stats["errors"] += 1
            return None
        return data

    def search_bills(self, state: str) -> List[Dict]:
        """All getSearch results for a state. getSearch caps at PAGE_SIZE per call,
        so page until the index's reported count is satisfied."""
        if not self.api_key:
            print("  ❌ LEGISCAN_API_KEY not set (backend/.env)")
            self.stats["errors"] += 1
            return []

        bills: List[Dict] = []
        total_count = 0
        page = 1
        max_pages = 20
        print(f"  🔍 Searching {state}...", end=" ", flush=True)
        while page <= max_pages:
            data = self._get(op="getSearch", state=state, query=self.query,
                             year=self.years, page=page)
            if data is None:
                return bills
            sr = data.get("searchresult", {})
            total_count = sr.get("summary", {}).get("count", 0)
            page_bills = [b for k, b in sr.items() if k != "summary" and isinstance(b, dict)]
            if not page_bills:
                break
            bills.extend(page_bills)
            if len(bills) >= total_count or len(page_bills) < PAGE_SIZE:
                break
            page += 1
            time.sleep(self.sleep)
        print(f"✅ ({len(bills)} returned, {total_count} in index)")
        return bills

    def fetch_bill(self, bill_id) -> Optional[Dict]:
        """getBill: authoritative status plus description/subjects."""
        if not bill_id or not self.api_key:
            return None
        data = self._get(op="getBill", id=bill_id)
        self.stats["getbill_calls"] += 1
        if data is None:
            return None
        bill = data.get("bill", {})
        label, stage = map_status(bill.get("status"))
        return {
            "status_label": label,
            "stage": stage,
            "status_date": bill.get("status_date", ""),
            "description": bill.get("description", ""),
            "subjects": [s.get("subject_name") for s in bill.get("subjects", []) if s.get("subject_name")],
            "change_hash": bill.get("change_hash", ""),
        }

    def _enrich(self, bills: List[Dict], known_hashes: Dict[int, str]):
        """Attach getBill detail to each bill unless its change_hash is unchanged."""
        if not self.fetch_status:
            return
        for b in bills:
            bid = b.get("bill_id")
            if bid in known_hashes and b.get("change_hash") and known_hashes[bid] == b["change_hash"]:
                continue  # nothing changed since last sync -- skip the call
            detail = self.fetch_bill(bid)
            if detail:
                b["_enriched"] = True
                b["_status_label"] = detail["status_label"]
                b["_stage"] = detail["stage"]
                b["status_date"] = detail["status_date"]
                b["_description"] = detail["description"]
                b["_subjects"] = detail["subjects"]
                b["change_hash"] = detail["change_hash"] or b.get("change_hash")
            time.sleep(self.sleep)

    # ---- orchestration per state ------------------------------------------

    def sync_state(self, state: str) -> List[Dict]:
        raw = self.search_bills(state)
        self.stats["searched"] += 1
        if not raw:
            return []

        ranked = rank_bills(raw)
        self.stats["found"] += len(ranked)
        relevant = [b for b in ranked if b["_score"]["is_k12_ai"]]
        low_conf = [b for b in ranked if not b["_score"]["is_k12_ai"]]
        self.stats["relevant"] += len(relevant)
        self.stats["low_confidence"] += len(low_conf)

        known_hashes = self._known_hashes(state) if self.db is not None else {}
        self._enrich(ranked, known_hashes)

        if self.db is None:
            self._print_preview(relevant, low_conf)
            return ranked

        self._ensure_profile(state)
        self._upsert_bills(state, ranked)
        return ranked

    def _print_preview(self, relevant, low_conf):
        for b in relevant:
            s = b["_score"]
            print(f"     [{s['confidence']:<6}] rel={s['relevance']:>3} {b['_status_label']:<14} "
                  f"{b.get('bill_number','?'):<10} {(b.get('title','') or '')[:70]}")
        if low_conf:
            print(f"     ----- {len(low_conf)} held for review (low confidence) -----")
            for b in low_conf:
                s = b["_score"]
                tag = "noise" if s["flags"]["noise"] else ("higher-ed" if s["flags"]["higher_ed"] else "review")
                print(f"     [{s['confidence']:<6}] rel={s['relevance']:>3} {b['_status_label']:<14} "
                      f"{tag:<9} {b.get('bill_number','?'):<10} {(b.get('title','') or '')[:60]}")

    # ---- persistence -----------------------------------------------------

    def _known_hashes(self, state: str) -> Dict[int, str]:
        from app.models.legislation import Bill
        rows = self.db.query(Bill.legiscan_bill_id, Bill.change_hash, Bill.bill_stage) \
            .filter(Bill.state_code == state).all()
        # Only trust a hash if we also have a real stage for it (a --no-status
        # run stores hashes with stage "introduced"/Unknown, which must be refreshed).
        return {bid: h for bid, h, stage in rows if h and stage and stage != "unknown"}

    def _ensure_profile(self, state: str):
        from app.models.legislation import StateProfile
        if not self.db.query(StateProfile).filter_by(state_code=state).first():
            self.db.add(StateProfile(state_code=state, state_name=JURISDICTIONS.get(state, state)))
            self.db.commit()

    def _upsert_bills(self, state: str, bills: List[Dict]):
        """Insert new bills, refresh existing ones, log stage transitions, keep decisions."""
        from app.models.legislation import Bill, BillStatusChange

        now = datetime.utcnow()
        for b in bills:
            bid = b.get("bill_id")
            if not bid:
                continue
            score = b.get("_score") or score_bill(b)
            label, stage = b.get("_status_label"), b.get("_stage")
            if label is None or stage is None:
                label, stage = map_status(b.get("status"))
            flag = flag_for(score)

            fields = dict(
                bill_number=b.get("bill_number"),
                bill_title=b.get("title", "") or "",
                bill_url=b.get("url", ""),
                bill_text_url=b.get("text_url", ""),
                last_action=b.get("last_action", ""),
                last_action_date=_clean_date(b.get("last_action_date")),
                relevance_score=score["relevance"],
                match_confidence=score["confidence"],
                flag_reason=flag,
                matched_ai_terms=score["title_ai_terms"],
                matched_edu_terms=score["title_edu_terms"],
                last_seen=now,
            )
            if b.get("change_hash"):
                fields["change_hash"] = b["change_hash"]
            if "_description" in b:
                fields["description"] = b["_description"]
                fields["subjects"] = b["_subjects"]

            bill = self.db.query(Bill).filter_by(state_code=state, legiscan_bill_id=bid).first()
            if bill is None:
                bill = Bill(state_code=state, legiscan_bill_id=bid, decision="PENDING",
                            bill_status=label, bill_stage=stage,
                            status_date=b.get("status_date", ""), first_seen=now, **fields)
                self.db.add(bill)
                self.stats["new_bills"] += 1
                continue

            for k, v in fields.items():
                setattr(bill, k, v)
            # Only trust a status we fetched from getBill THIS run. rank_bills()
            # always sets _status_label (to "Unknown" -- getSearch has no status),
            # so testing for the key would overwrite a real status with Unknown
            # for every bill whose change_hash let us skip the getBill call.
            # That is exactly what happened to 995 bills before 2026-09-08.
            enriched = bool(b.get("_enriched"))
            if enriched:
                if bill.bill_stage != stage or bill.bill_status != label:
                    self.db.add(BillStatusChange(
                        bill=bill, old_status=bill.bill_status, new_status=label,
                        old_stage=bill.bill_stage, new_stage=stage, changed_at=now,
                    ))
                    self.stats["status_changes"] += 1
                bill.bill_status = label
                bill.bill_stage = stage
                bill.status_date = b.get("status_date", "") or bill.status_date
            # decision / decision_note / reviewed_* deliberately untouched

        self.db.commit()
        self._link_carryovers(state)

    def _link_carryovers(self, state: str):
        n = link_carryovers(self.db, state)
        if n:
            self.stats["carryovers_linked"] += n

    # ---- runs --------------------------------------------------------------

    def run(self, scope: str):
        """scope: 'all' or a jurisdiction code."""
        from app.models.legislation import SyncRun
        states = SEARCHABLE if scope == "all" else [scope]
        print("\n📡 LegiScan Sync: K-12 AI Legislation")
        print("=" * 70)
        print(f"Scope: {scope}   Years: {self.years} (1=all sessions)   "
              f"Status lookups: {'on' if self.fetch_status else 'off'}")
        print(f"Query: {self.query}\n")

        run = None
        if self.db is not None:
            run = SyncRun(scope=scope, started_at=datetime.utcnow())
            self.db.add(run)
            self.db.commit()

        for state in states:
            if state in LEGISCAN_UNSUPPORTED:
                print(f"  ⏭  {state}: not covered by LegiScan (profile is maintained by hand)")
                continue
            try:
                self.sync_state(state)
                time.sleep(self.sleep)
            except Exception as e:  # keep one bad state from poisoning the rest
                print(f"❌ Error syncing {state}: {e}")
                self.stats["errors"] += 1
                if self.db is not None:
                    self.db.rollback()

        if run is not None:
            run.finished_at = datetime.utcnow()
            run.stats = dict(self.stats)
            self.db.commit()
        self._print_summary()

    def _print_summary(self):
        print("\n" + "=" * 70)
        print("📊 SYNC SUMMARY")
        print("=" * 70)
        for k, v in self.stats.items():
            print(f"{k:<18} {v}")
        print("\n✅ Sync complete" if self.db is not None else "\n👀 Preview only -- nothing written")


def link_carryovers(db, state: str) -> int:
    """Same state, same bill number, identical title, different LegiScan id:
    that is one bill carried into the second year of a session, not two
    bills. Point every older copy at the newest (highest id) and carry a
    decision forward if only the older copy had one, so a reviewer's call
    survives the roll-over. A reused number with a different title (CA
    AB1651 in 2022 and 2026) is left alone. Returns links made/changed."""
    from app.models.legislation import Bill
    rows = db.query(Bill).filter(Bill.state_code == state).all()
    groups: Dict[tuple, List] = {}
    for b in rows:
        key = (b.bill_number or "", (b.bill_title or "").strip().lower())
        groups.setdefault(key, []).append(b)
    linked = 0
    for key, bs in groups.items():
        if len(bs) < 2 or not key[0]:
            continue
        bs.sort(key=lambda b: b.legiscan_bill_id)
        newest = bs[-1]
        for old in bs[:-1]:
            if old.superseded_by != newest.legiscan_bill_id:
                old.superseded_by = newest.legiscan_bill_id
                linked += 1
            if old.decision != "PENDING" and newest.decision == "PENDING":
                newest.decision, newest.decision_note = old.decision, old.decision_note
                newest.reviewed_by, newest.reviewed_at = old.reviewed_by, old.reviewed_at
        if newest.superseded_by:
            newest.superseded_by = None
    db.commit()
    return linked


def _clean_date(v) -> str:
    """LegiScan occasionally emits '0000-00-00'; store nothing rather than a fake date."""
    v = (v or "").strip()
    return "" if not v or v.startswith("0000") else v


def flag_for(score: Dict) -> str:
    if score["flags"]["noise"]:
        return "noise"
    if score["flags"]["higher_ed"]:
        return "higher_ed"
    if not score["is_k12_ai"]:
        return "review"
    return ""


def rescore(db, scope: str = "all") -> Dict[str, int]:
    """Re-run the title scorer over stored bills. No network. Use after changing
    the vocabulary or gates so existing rows pick up the new classification.
    Decisions are untouched; only the automatic fields change."""
    from app.models.legislation import Bill
    q = db.query(Bill)
    if scope != "all":
        q = q.filter(Bill.state_code == scope)
    changed = {"rescored": 0, "changed": 0, "unknown_stage_cleared": 0, "carryovers_linked": 0}
    for bill in q.all():
        if bill.bill_status == "Unknown" and bill.bill_stage:
            bill.bill_stage = None          # never fetched -> no color (see map_status)
            changed["unknown_stage_cleared"] += 1
        if bill.last_action_date and bill.last_action_date.startswith("0000"):
            bill.last_action_date = ""
        score = score_bill({"title": bill.bill_title or "", "relevance": bill.relevance_score or 0})
        from app.sync.text_scorer import combine, text_score_from_bill
        conf, flag = combine(score["confidence"], flag_for(score), text_score_from_bill(bill))
        new = dict(match_confidence=conf, flag_reason=flag,
                   matched_ai_terms=score["title_ai_terms"], matched_edu_terms=score["title_edu_terms"])
        if any(getattr(bill, k) != v for k, v in new.items()):
            if bill.match_confidence != new["match_confidence"]:
                print(f"  {bill.state_code} {bill.bill_number:10} {bill.match_confidence} -> {new['match_confidence']}: {(bill.bill_title or '')[:80]}")
            for k, v in new.items():
                setattr(bill, k, v)
            changed["changed"] += 1
        changed["rescored"] += 1
    db.commit()
    states = [scope] if scope != "all" else sorted({r[0] for r in db.query(Bill.state_code).distinct()})
    for st in states:
        changed["carryovers_linked"] += link_carryovers(db, st)
    return changed


def main():
    parser = argparse.ArgumentParser(description="Sync K-12 AI legislation from LegiScan")
    parser.add_argument("--state", type=str, help="Sync one jurisdiction (e.g. CA)")
    parser.add_argument("--all", action="store_true", help="Sync every LegiScan-covered jurisdiction")
    parser.add_argument("--preview", action="store_true", help="Print ranked results; no DB")
    parser.add_argument("--years", type=str, default="1",
                        help="1=all sessions, 2=current, 3=recent, 4=prior, or YYYY (default 1)")
    parser.add_argument("--no-status", action="store_true", help="Skip getBill lookups")
    parser.add_argument("--query", type=str, default=None,
                        help="Override the LegiScan search query for this run (diagnosis: e.g. --preview "
                             "--query 'SB1734' to check whether the index knows a bill at all)")
    parser.add_argument("--score-text", action="store_true",
                        help="Fetch each HIGH/MEDIUM/INCLUDED bill's latest text (getBill + getBillText), "
                             "score AI-term density, and fold it into the confidence")
    parser.add_argument("--force-text", action="store_true",
                        help="With --score-text: re-fetch even when the stored text_hash is unchanged")
    parser.add_argument("--text-report", action="store_true",
                        help="Print the distribution of stored text scores (no network)")
    parser.add_argument("--rescore", action="store_true",
                        help="Re-run the title scorer over stored bills (no API calls); combine with --state or --all")
    args = parser.parse_args()

    if not (args.state or args.all):
        parser.print_help()
        return
    scope = "all" if args.all else args.state.upper()

    if args.text_report:
        from app.database import SessionLocal, init_db
        from app.sync.text_scorer import distribution
        init_db()
        db = SessionLocal()
        try:
            print(distribution(db, scope))
        finally:
            db.close()
        return

    if args.score_text:
        from app.database import SessionLocal, init_db
        from app.sync.text_scorer import TextScorer, distribution
        init_db()
        db = SessionLocal()
        try:
            sync = LegiScanSync(db, fetch_status=False)
            stats = TextScorer(db, sync, force=args.force_text).run(scope)
            print("\n📊 TEXT SCORING SUMMARY")
            for k, v in stats.items():
                print(f"{k:<18} {v}")
            print()
            print(distribution(db, scope))
        finally:
            db.close()
        return

    if args.rescore:
        from app.database import SessionLocal, init_db
        init_db()
        db = SessionLocal()
        try:
            r = rescore(db, scope)
        finally:
            db.close()
        print(f"\nRescored {r['rescored']} bills, {r['changed']} changed classification fields, "
              f"{r['unknown_stage_cleared']} unknown stages cleared, {r['carryovers_linked']} carry-over duplicates linked")
        return

    query = args.query or SEARCH_QUERY

    if args.preview:
        LegiScanSync(db=None, years=args.years, fetch_status=not args.no_status, query=query).run(scope)
        return

    from app.database import SessionLocal, init_db
    init_db()
    db = SessionLocal()
    try:
        LegiScanSync(db, years=args.years, fetch_status=not args.no_status, query=query).run(scope)
    finally:
        db.close()


if __name__ == "__main__":
    main()
