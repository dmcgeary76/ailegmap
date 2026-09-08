"""Text-density scorer: pure functions plus the rescore round-trip."""
import base64
import io
import zipfile
from datetime import datetime

from app.sync import text_scorer as tsc
from app.sync.text_scorer import extract_text, score_text, combine, MIME_HTML, MIME_PDF, MIME_DOCX, MIME_RTF


CYBERBULLYING = """
AN ACT relating to digital citizenship and media literacy instruction in public schools.
SECTION 1. Definitions. As used in this chapter:
(1) "Artificial intelligence" means a machine-based system that makes predictions.
(2) "Cyberbullying" means bullying through electronic means.
SECTION 2. Each district shall provide instruction on digital citizenship, including
online safety, evaluating sources, and responsible social media use. """ + ("Districts shall report annually on instruction provided under this section. " * 60)

REAL_AI_BILL = """
AN ACT relating to the use of artificial intelligence in public school classrooms.
SECTION 1. ARTIFICIAL INTELLIGENCE IN INSTRUCTION
(a) A teacher may use an artificial intelligence system to support instruction only under the
direction of the teacher. (b) A district may not use artificial intelligence as the primary basis
for a grade or a disciplinary decision. (c) Parents may opt a student out of student-facing AI tools.
SECTION 2. The State Board shall issue guidance on generative AI by July 1. """ + ("The board shall review this guidance annually. " * 40)

TITLE_ONLY = ("SECTION 1. The commission shall study educational materials used in sentencing. " * 40)


def test_definitions_only_is_thin():
    s = score_text(CYBERBULLYING)
    assert s["ai_mentions"] == 1
    assert s["definition_only"] is True
    assert s["ai_in_heading"] is False
    assert s["thin"] and not s["dense"]


def test_real_bill_is_dense_with_heading():
    s = score_text(REAL_AI_BILL)
    assert s["ai_mentions"] >= 4
    assert s["ai_in_heading"] is True     # "SECTION 1. ARTIFICIAL INTELLIGENCE IN INSTRUCTION"
    assert s["definition_only"] is False
    assert s["dense"] and not s["thin"]
    assert s["ai_density"] > 0


def test_overlapping_terms_count_once():
    s = score_text("The generative AI tool. The AI tool.")
    assert s["ai_mentions"] == 2          # "generative ai" and "ai", not 3


def test_combine_rules():
    dense = score_text(REAL_AI_BILL)
    thin = score_text(CYBERBULLYING)
    none = score_text(TITLE_ONLY)
    assert combine("HIGH", "", none) == ("LOW", "title_only")
    assert combine("HIGH", "", dense) == ("HIGH", "")
    assert combine("MEDIUM", "review", dense) == ("MEDIUM", "dense")
    assert combine("MEDIUM", "review", thin) == ("LOW", "thin_mention")
    assert combine("MEDIUM", "review", {"words": 900, "ai_mentions": 2, "ai_in_heading": False,
                                        "ai_density": 2.2, "definition_only": False, "dense": False, "thin": False}) == ("MEDIUM", "review")
    # never override the title-only gates, and unreadable text changes nothing
    assert combine("LOW", "noise", dense) == ("LOW", "noise")
    assert combine("LOW", "higher_ed", dense) == ("LOW", "higher_ed")
    assert combine("MEDIUM", "review", {"words": None, "readable": False}) == ("MEDIUM", "text_unreadable")
    assert combine("HIGH", "", None) == ("HIGH", "")
    # a stub document (few words, no hits) does not demote a HIGH
    assert combine("HIGH", "", score_text("Short placeholder text.")) == ("HIGH", "")


def test_extract_html_pdf_docx_and_unreadable():
    html_doc = b"<html><head><style>p{}</style></head><body><h1>Artificial Intelligence Act</h1><p>Section 1. AI in schools.</p></body></html>"
    t = extract_text(html_doc, MIME_HTML)
    assert "Artificial Intelligence Act" in t and "p{}" not in t and "<" not in t

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", '<w:document><w:body><w:p><w:r><w:t>Generative AI guidance</w:t></w:r></w:p></w:body></w:document>')
    assert "Generative AI guidance" in extract_text(buf.getvalue(), MIME_DOCX)

    from pypdf import PdfWriter
    w = PdfWriter(); w.add_blank_page(width=200, height=200)
    pdf = io.BytesIO(); w.write(pdf)
    assert extract_text(pdf.getvalue(), MIME_PDF) == ""     # readable, just empty
    assert extract_text(b"{\\rtf1 hello}", MIME_RTF) is None  # unsupported -> None
    assert extract_text(b"", MIME_HTML) is None


def test_rescore_keeps_text_derived_classification(db):
    """A MEDIUM demoted to thin_mention by --score-text must stay demoted when
    --rescore re-runs the title scorer (it re-folds the stored columns)."""
    from app.models.legislation import Bill
    from app.sync.legiscan_sync import rescore
    b = Bill(state_code="TX", legiscan_bill_id=7, bill_number="SB2787",
             bill_title="Relating to digital citizenship and media literacy instruction in public schools",
             match_confidence="MEDIUM", flag_reason="review", decision="PENDING",
             text_scored_at=datetime(2026, 9, 8), text_words=1200, ai_mentions=1,
             ai_in_heading=False, ai_density=0.8, definition_only=True)
    db.add(b); db.commit()
    rescore(db, "TX")
    db.refresh(b)
    assert (b.match_confidence, b.flag_reason) == ("LOW", "thin_mention")


def test_text_scorer_driver_with_fake_api(db, monkeypatch):
    """End to end against a stubbed LegiScan: getBill -> texts[], getBillText -> base64 HTML."""
    from app.models.legislation import Bill
    from app.sync.legiscan_sync import LegiScanSync
    from app.sync.text_scorer import TextScorer
    hi = Bill(state_code="HI", legiscan_bill_id=1, bill_number="HB1887",
              bill_title="Relating To Artificial Intelligence Literacy Education.",
              match_confidence="HIGH", flag_reason="", decision="PENDING")
    tx = Bill(state_code="TX", legiscan_bill_id=2, bill_number="HB641",
              bill_title="Relating to digital citizenship instruction in public schools.",
              match_confidence="MEDIUM", flag_reason="review", decision="PENDING")
    db.add_all([hi, tx]); db.commit()

    docs = {1: REAL_AI_BILL, 2: CYBERBULLYING}
    def fake_get(**params):
        if params["op"] == "getBill":
            bid = params["id"]
            return {"bill": {"texts": [{"doc_id": 100 + bid, "date": "2026-01-01", "text_hash": f"h{bid}", "mime_id": 1}]}}
        if params["op"] == "getBillText":
            bid = params["id"] - 100
            body = "<html><body><pre>" + docs[bid].replace("\n", "<br>") + "</pre></body></html>"
            return {"text": {"doc_id": params["id"], "mime_id": 1, "text_hash": f"h{bid}",
                             "doc": base64.b64encode(body.encode()).decode()}}
    sync = LegiScanSync(db=db, api_key="x", fetch_status=False, sleep=0)
    monkeypatch.setattr(sync, "_get", fake_get)

    stats = TextScorer(db, sync).run("all")
    assert stats["candidates"] == 2 and stats["fetched"] == 2 and stats["errors"] == 0
    db.refresh(hi); db.refresh(tx)
    assert hi.match_confidence == "HIGH" and hi.ai_in_heading and hi.text_hash == "h1"
    assert (tx.match_confidence, tx.flag_reason) == ("LOW", "thin_mention")
    assert tx.text_words > 100 and tx.definition_only

    # second run: hashes unchanged -> no getBillText calls
    stats2 = TextScorer(db, sync).run("all")
    assert stats2["skipped_same_hash"] == 2 and stats2["fetched"] == 0
