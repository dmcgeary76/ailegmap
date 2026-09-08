"""Text-density scorer: does the bill's *text* actually talk about AI?

The title scorer (``score_bill``) only sees titles. A bill clears the LegiScan
full-text query by mentioning an AI term once, anywhere -- so a cyberbullying
bill that defines "artificial intelligence" in a definitions list looks the
same as a bill that is about AI. This module fetches the latest text document
for a bill, counts AI-term hits, notes whether any hit sits in a heading and
whether every hit is inside a definition, and folds that into the final
confidence via ``combine``.

Pure functions (unit-tested, no network):
    extract_text(data, mime_id)  -> str | None
    score_text(text)             -> dict
    combine(title_conf, title_flag, text_score) -> (confidence, flag_reason)

``TextScorer`` does the API work and writes the columns on ``bills``:
text_doc_id, text_hash, text_mime, text_words, ai_mentions, ai_in_heading,
ai_density, definition_only, text_scored_at. The text itself is never stored.
"""
import base64
import html
import io
import re
import zipfile
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.sync.legiscan_sync import AI_TERMS, CONF_HIGH, CONF_MEDIUM, CONF_LOW

# LegiScan getBillText mime_id values
MIME_HTML, MIME_PDF, MIME_WORDPERFECT, MIME_DOC, MIME_RTF, MIME_DOCX = 1, 2, 3, 4, 5, 6
READABLE = {MIME_HTML, MIME_PDF, MIME_DOCX}
MAX_TEXT_BYTES = 2_000_000

# Thresholds -- first cut from docs/TEXT_DENSITY_SCORER.md; tune after the
# first --score-text run prints the distribution.
DENSE_MENTIONS = 3        # this many hits AND DENSE_DENSITY (or >= 2 with one in a heading) = about AI
DENSE_DENSITY = 1.0       # hits per 1,000 words; keeps an 80k-word bond bill with 11 hits out
THIN_MENTIONS = 2         # at most this many hits, and either all inside definitions ...
THIN_DENSITY = 0.5        # ... or this sparse = a passing mention
MIN_WORDS_FOR_TITLE_ONLY = 200   # don't call a HIGH "title_only" on a stub document
DEFINITION_WINDOW = 200   # chars around a hit to look for "means" / "as used in"

def _phrase_pattern(term: str) -> "re.Pattern":
    """Match a vocabulary term in extracted text. Between the words of a phrase
    allow any whitespace (PDF line wraps), hyphens, and stray line numbers
    ("artificial\n 12 intelligence" is how Iowa's PDFs come out of pypdf),
    or nothing at all ("artificialintelligence"). Terms of three letters or
    fewer need a boundary on both sides; longer ones need none."""
    parts = [re.escape(w) for w in term.split()]
    gap = r"(?:[\s\-]*(?:\d{1,3}\s+)?)"
    body = gap.join(parts)
    if len(term) <= 3:
        return re.compile(r"(?<!\w)" + body + r"(?!\w)", re.I)
    # Longer terms get NO word boundaries: Missouri's PDFs come out of pypdf
    # with the spaces dropped ("Theinclusion ofartificial intelligence"), and
    # "artificial intelligence" is unambiguous however it is glued.
    return re.compile(body, re.I)


_AI_PATTERNS = [_phrase_pattern(t) for t in AI_TERMS]
_DEFINITION_CUES = re.compile(
    r"\b(means|shall mean|is defined as|as used in|as defined in|definitions?|the term)\b", re.I)
_HEADING_LEAD = re.compile(r"^\s*(sec(tion)?\.?\s*\d|§|article\s+[\divx]+|part\s+[\divx]+|chapter\s+\d|\d+(\.\d+)*\s*[.)-])", re.I)
_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_text(data: bytes, mime_id: int) -> Optional[str]:
    """Plain text from a LegiScan document, or None when the format is unreadable."""
    if not data:
        return None
    data = data[:MAX_TEXT_BYTES]
    if mime_id == MIME_HTML:
        s = data.decode("utf-8", errors="replace")
        s = _SCRIPT.sub(" ", s)
        s = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>|</li>|</tr>", "\n", s, flags=re.I)
        s = _TAG.sub(" ", s)
        return _tidy(html.unescape(s))
    if mime_id == MIME_PDF:
        try:
            from pypdf import PdfReader
        except ImportError:  # pragma: no cover
            return None
        try:
            reader = PdfReader(io.BytesIO(data))
            return _tidy("\n".join((p.extract_text() or "") for p in reader.pages))
        except Exception:
            return None
    if mime_id == MIME_DOCX:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        except (zipfile.BadZipFile, KeyError):
            return None
        xml = re.sub(r"</w:p>", "\n", xml)
        return _tidy(html.unescape(_TAG.sub(" ", xml)))
    return None  # WordPerfect, .doc, RTF: skip


_LIGATURES = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
              "\u00ad": "", "\u2010": "-", "\u2011": "-", "\u2019": "'", "\u201c": '"', "\u201d": '"'}


def _tidy(s: str) -> str:
    """Normalise extracted text so the vocabulary can match it.

    PDF text arrives with typographic ligatures ("arti\ufb01cial" -- the fi
    ligature -- is not "artificial" to a regex), soft hyphens, and words
    hyphenated across line ends ("intelli-\ngence"). Fix all three."""
    for a, b in _LIGATURES.items():
        s = s.replace(a, b)
    s = s.replace("\xa0", " ")
    s = re.sub(r"(\w)-\s*\n\s*(?=[a-z])", r"\1", s)   # end-of-line syllable hyphenation
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _is_heading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 140:
        return False
    words = line.split()
    if len(words) > 16:
        return False
    if _HEADING_LEAD.match(line):
        return True
    letters = [c for c in line if c.isalpha()]
    if len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        return True   # "ARTIFICIAL INTELLIGENCE IN SCHOOLS"
    # No "short line without a period" rule: PDF extraction wraps every line,
    # so that heuristic called one hit in three a heading on the first run.
    return False


def score_text(text: str) -> Dict:
    """Count AI-term hits and characterise where they sit.

    Returns: words, ai_mentions, ai_in_heading, ai_density (per 1,000 words),
    definition_only (every hit within DEFINITION_WINDOW chars of a definition
    cue), plus ``dense`` / ``thin`` booleans derived with the module thresholds.
    """
    text = text or ""
    words = len(text.split())
    hits: List[Tuple[int, int]] = []
    for pat in _AI_PATTERNS:
        for m in pat.finditer(text):
            hits.append((m.start(), m.end()))
    # de-duplicate overlapping hits ("generative ai" also matches "ai")
    hits.sort()
    merged: List[Tuple[int, int]] = []
    for s, e in hits:
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    n = len(merged)

    in_heading = False
    for s, e in merged:
        line_start = text.rfind("\n", 0, s) + 1
        line_end = text.find("\n", e)
        line = text[line_start: line_end if line_end != -1 else len(text)]
        if _is_heading(line):
            in_heading = True
            break

    definition_only = n > 0 and all(
        _DEFINITION_CUES.search(text[max(0, s - DEFINITION_WINDOW): e + DEFINITION_WINDOW])
        for s, e in merged
    )
    density = round(n * 1000.0 / words, 2) if words else 0.0
    return {
        "words": words,
        "ai_mentions": n,
        "ai_in_heading": in_heading,
        "ai_density": density,
        "definition_only": definition_only,
        "dense": (in_heading and n >= 2) or (n >= DENSE_MENTIONS and density >= DENSE_DENSITY),
        "thin": n <= THIN_MENTIONS and (definition_only or density < THIN_DENSITY),
    }


def combine(title_confidence: str, title_flag: str, ts: Optional[Dict]) -> Tuple[str, str]:
    """Fold a text score into the title classification.

    Title-only noise / higher-ed gates are never overridden. Otherwise:
      HIGH   + no AI in a real document           -> LOW   'title_only'
      MEDIUM + no AI in a real document           -> LOW   'no_mention'
      MEDIUM + dense (heading, or >= 3 hits at >= 1/1k words) -> MEDIUM 'dense' (review first)
      MEDIUM + thin (<= 2 hits, definitions or < 0.5/1k)      -> LOW 'thin_mention'
      MEDIUM otherwise                            -> MEDIUM 'review'
      anything with no readable text             -> unchanged, flag 'text_unreadable'
                                                   only where the flag was 'review'
    """
    if title_flag in ("noise", "higher_ed"):
        return title_confidence, title_flag
    if ts is None:
        return title_confidence, title_flag
    if not ts.get("readable", True) or ts.get("words") is None:
        return title_confidence, ("text_unreadable" if title_flag == "review" else title_flag)
    if title_confidence == CONF_HIGH:
        if ts["ai_mentions"] == 0 and ts["words"] >= MIN_WORDS_FOR_TITLE_ONLY:
            return CONF_LOW, "title_only"
        return CONF_HIGH, title_flag
    if title_confidence == CONF_MEDIUM:
        if ts["ai_mentions"] == 0 and ts["words"] >= MIN_WORDS_FOR_TITLE_ONLY:
            return CONF_LOW, "no_mention"
        if ts["dense"]:
            return CONF_MEDIUM, "dense"
        if ts["thin"]:
            return CONF_LOW, "thin_mention"
        return CONF_MEDIUM, "review"
    return title_confidence, title_flag


def text_score_from_bill(bill) -> Optional[Dict]:
    """Rebuild the score dict from stored columns (for --rescore, no network)."""
    if bill.text_scored_at is None:
        return None
    if bill.text_words is None:   # scored, but the document was unreadable
        return {"words": None, "readable": False}
    n = bill.ai_mentions or 0
    density = bill.ai_density or 0.0
    return {
        "words": bill.text_words, "ai_mentions": n, "ai_in_heading": bool(bill.ai_in_heading),
        "ai_density": density, "definition_only": bool(bill.definition_only),
        "dense": (bool(bill.ai_in_heading) and n >= 2) or (n >= DENSE_MENTIONS and density >= DENSE_DENSITY),
        "thin": n <= THIN_MENTIONS and (bool(bill.definition_only) or density < THIN_DENSITY),
        "readable": True,
    }


# ---------------------------------------------------------------------------
# API driver
# ---------------------------------------------------------------------------

class TextScorer:
    """Fetch, extract, score and store. One getBill + one getBillText per bill,
    skipped when the stored text_hash still matches the newest document."""

    def __init__(self, db, sync, force: bool = False):
        self.db = db
        self.sync = sync            # a LegiScanSync: reuses _get(), sleep, stats
        self.force = force
        self.stats = {"candidates": 0, "fetched": 0, "skipped_same_hash": 0, "unreadable": 0,
                      "no_text": 0, "reclassified": 0, "errors": 0}

    def candidates(self, scope: str):
        """HIGH and MEDIUM by title, anything a reviewer INCLUDED (so a rescued
        LOW gets a text score too), and anything already text-scored (so a bill
        demoted to LOW is re-checked if its text changes). Never-scored LOW-by-
        title bills are not worth the quota."""
        from app.models.legislation import Bill
        from sqlalchemy import or_
        q = self.db.query(Bill).filter(or_(Bill.match_confidence.in_((CONF_HIGH, CONF_MEDIUM)),
                                           Bill.decision == "INCLUDED",
                                           Bill.text_scored_at.isnot(None)))
        q = q.filter(Bill.superseded_by.is_(None))   # the carried-over copy has the same text
        if scope != "all":
            q = q.filter(Bill.state_code == scope)
        return q.order_by(Bill.state_code, Bill.bill_number).all()

    def newest_text(self, legiscan_bill_id: int) -> Optional[Dict]:
        data = self.sync._get(op="getBill", id=legiscan_bill_id)
        self.sync.stats["getbill_calls"] += 1
        if not data:
            return None
        texts = (data.get("bill") or {}).get("texts") or []
        if not texts:
            return None
        return max(texts, key=lambda t: (t.get("date") or "", t.get("doc_id") or 0))

    def fetch_document(self, doc_id: int) -> Optional[Dict]:
        data = self.sync._get(op="getBillText", id=doc_id)
        if not data:
            return None
        return data.get("text") or None

    def score_bill(self, bill) -> bool:
        """Returns True when the bill's classification changed."""
        import time
        from app.sync.legiscan_sync import score_bill, flag_for
        newest = self.newest_text(bill.legiscan_bill_id)
        time.sleep(self.sync.sleep)
        if not newest:
            self.stats["no_text"] += 1
            return False
        doc_id = newest.get("doc_id")
        doc_hash = newest.get("text_hash")
        if not self.force and bill.text_scored_at and doc_hash and bill.text_hash == doc_hash:
            self.stats["skipped_same_hash"] += 1
            return False
        doc = self.fetch_document(doc_id)
        time.sleep(self.sync.sleep)
        self.stats["fetched"] += 1
        bill.text_doc_id = doc_id
        bill.text_hash = doc_hash or (doc or {}).get("text_hash")
        bill.text_scored_at = datetime.utcnow()
        mime_id = int((doc or {}).get("mime_id") or 0)
        bill.text_mime = mime_id
        text = None
        if doc and doc.get("doc"):
            try:
                text = extract_text(base64.b64decode(doc["doc"]), mime_id)
            except Exception:
                text = None
        if text is None:
            self.stats["unreadable"] += 1
            bill.text_words = None
            bill.ai_mentions = bill.ai_density = None
            bill.ai_in_heading = bill.definition_only = None
            ts = {"words": None, "readable": False}
        else:
            ts = score_text(text)
            bill.text_words = ts["words"]
            bill.ai_mentions = ts["ai_mentions"]
            bill.ai_in_heading = ts["ai_in_heading"]
            bill.ai_density = ts["ai_density"]
            bill.definition_only = ts["definition_only"]
        title = score_bill({"title": bill.bill_title or "", "relevance": bill.relevance_score or 0})
        conf, flag = combine(title["confidence"], flag_for(title), ts)
        changed = (conf, flag) != (bill.match_confidence, bill.flag_reason)
        bill.match_confidence, bill.flag_reason = conf, flag
        return changed

    def run(self, scope: str = "all") -> Dict:
        bills = self.candidates(scope)
        self.stats["candidates"] = len(bills)
        print(f"\n📄 Text scoring {len(bills)} bill(s) ({scope})")
        for i, b in enumerate(bills, 1):
            try:
                before = (b.match_confidence, b.flag_reason)
                if self.score_bill(b):
                    self.stats["reclassified"] += 1
                    print(f"  {b.state_code} {b.bill_number:10} {before[0]}/{before[1] or '-'} -> "
                          f"{b.match_confidence}/{b.flag_reason or '-'}  hits={b.ai_mentions} "
                          f"words={b.text_words}  {(b.bill_title or '')[:60]}")
                if i % 25 == 0:
                    self.db.commit()
                    print(f"  … {i}/{len(bills)}")
            except Exception as e:
                self.stats["errors"] += 1
                print(f"  ❌ {b.state_code} {b.bill_number}: {e}")
                self.db.rollback()
        self.db.commit()
        return self.stats


def distribution(db, scope: str = "all") -> str:
    """A compact table of stored text scores by title confidence, for tuning."""
    from app.models.legislation import Bill
    from collections import Counter
    q = db.query(Bill).filter(Bill.text_scored_at.isnot(None))
    if scope != "all":
        q = q.filter(Bill.state_code == scope)
    rows = q.all()
    lines = [f"{len(rows)} bill(s) text-scored"]
    by = Counter((b.match_confidence, b.flag_reason or "-") for b in rows)
    for (c, f), n in sorted(by.items()):
        lines.append(f"  {c:<7} {f:<16} {n}")
    buckets = Counter()
    for b in rows:
        if b.text_words is None:
            buckets["unreadable"] += 1
        elif (b.ai_mentions or 0) == 0:
            buckets["0 hits"] += 1
        elif b.ai_mentions <= 2:
            buckets["1-2 hits" + (" (definitions)" if b.definition_only else "")] += 1
        elif b.ai_mentions <= 9:
            buckets["3-9 hits"] += 1
        else:
            buckets["10+ hits"] += 1
    lines.append("  hits: " + ", ".join(f"{k}={v}" for k, v in sorted(buckets.items())))
    return "\n".join(lines)


def dump_text(db, sync, state: str, bill_number: str, chars: int = 3000) -> str:
    """Diagnostic: list a bill's text documents and print the start of the
    extracted text of the newest one, with the hit positions."""
    from app.models.legislation import Bill
    b = (db.query(Bill).filter(Bill.state_code == state.upper(), Bill.bill_number == bill_number)
         .order_by(Bill.legiscan_bill_id.desc()).first())
    if not b:
        return f"no bill {state} {bill_number}"
    data = sync._get(op="getBill", id=b.legiscan_bill_id) or {}
    texts = (data.get("bill") or {}).get("texts") or []
    out = [f"{b.state_code} {b.bill_number} (legiscan {b.legiscan_bill_id}) -- {len(texts)} text document(s):"]
    for t in texts:
        out.append(f"  doc {t.get('doc_id')}  {t.get('date')}  {t.get('type')}  mime={t.get('mime_id')}  size={t.get('text_size')}")
    if not texts:
        return "\n".join(out)
    newest = max(texts, key=lambda t: (t.get("date") or "", t.get("doc_id") or 0))
    doc = (sync._get(op="getBillText", id=newest["doc_id"]) or {}).get("text") or {}
    raw = base64.b64decode(doc.get("doc") or "")
    text = extract_text(raw, int(doc.get("mime_id") or 0))
    if text is None:
        out.append(f"  newest doc {newest.get('doc_id')}: UNREADABLE (mime {doc.get('mime_id')}, {len(raw)} bytes)")
        return "\n".join(out)
    sc = score_text(text)
    out.append(f"  newest doc {newest.get('doc_id')}: {sc}")
    for pat in _AI_PATTERNS:
        for m in list(pat.finditer(text))[:3]:
            out.append(f"    hit @{m.start()}: …{text[max(0, m.start()-40):m.end()+40]!r}…")
    out.append("---- extracted text (first %d chars) ----" % chars)
    out.append(text[:chars])
    return "\n".join(out)
