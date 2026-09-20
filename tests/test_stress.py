"""Stress tests: emails and documents deliberately unlike the organisers' data.

Run:  python3 -m pytest tests/test_stress.py -q

The 520 sample emails are all decided by rules, so they prove the rules fit *that*
inbox — not that the system survives a real one. Everything here is hand-written
to break it: reply chains, autoreplies, retractions, languages the rules were
never given, and the same value written two legitimate ways.

Two properties matter more than any individual case:

1. When the rules are out of their depth they must say so (`rule_low_confidence`)
   rather than answer confidently. That is what routes an email to the AI, or to
   a person. A rule that is confidently wrong is the only genuinely bad outcome.
2. The same real-world value written differently must not be reported as a
   mismatch. A false alarm sent to a customer costs more than a missed check,
   because it destroys trust in every other check the system makes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from app import llm  # noqa: E402
from app.classify import classify  # noqa: E402
from app.fields import norm_party, norm_port, parse_container_count, parse_weight_kg  # noqa: E402
from app.pipeline import process_email  # noqa: E402


def _email(subject, body, attachments=()):
    return {"email_id": "s1", "from": "customer@example.com", "subject": subject,
            "body": body, "attachments": list(attachments)}


# ─────────────────────── 1. the rules must know their limits ───────────────────
# Every one of these is a real inbox shape the keyword rules were never built for.
# The assertion is deliberately NOT "the rules get it right" — it is "the rules do
# not get it confidently wrong", which is the property that keeps a human in the
# loop. If someone tunes the rules to be more decisive, these fail first.

AMBIGUOUS = [
    ("reply chain, invoice quoted underneath",
     "RE: RE: FW: shipment",
     "Please check the attached draft against the SI.\n\n-----Original Message-----\n"
     "Subject: INVOICE 5250070084\nKindly settle the invoice by Friday."),
    ("marketing spam wearing shipping vocabulary",
     "Reduce your demurrage and detention costs by 80%",
     "Dear Shipper, our AI platform optimises your bill of lading workflow and "
     "shipping instruction processing. Book a demo today!"),
    ("out-of-office autoreply that quotes the subject",
     "Automatic reply: TO CONFIRM DOCS _ 5RSG-00133",
     "I am out of the office until 5 January with limited access to email. "
     "For urgent draft BL matters please contact the documentation desk."),
    ("customer retracts the request",
     "Re: draft BL check",
     "Please ignore my previous email, the draft BL was already approved "
     "yesterday. No action needed."),
    ("Spanish — a real lane in this dataset (Callao, Valparaiso)",
     "Revisión de borrador de BL",
     "Buenos días, adjunto la instrucción de embarque y el borrador del "
     "conocimiento de embarque. Favor verificar que coincidan."),
    ("Vietnamese — also a real lane (Ho Chi Minh, Haiphong)",
     "Kiểm tra vận đơn nháp",
     "Chào anh/chị, đính kèm SI và vận đơn nháp. Vui lòng kiểm tra giúp."),
    ("terse operator shorthand, no keywords at all",
     "5RSG-00133",
     "attached. pls confirm asap"),
]


@pytest.mark.parametrize("label,subject,body", AMBIGUOUS, ids=[c[0] for c in AMBIGUOUS])
def test_rules_hand_off_instead_of_guessing(monkeypatch, label, subject, body):
    monkeypatch.setattr(llm, "available", lambda: False)
    r = classify(_email(subject, body), use_llm=False)
    assert r["decided_by"] == "rule_low_confidence", (
        f"rules answered {r['category']!r} confidently on a case they were never "
        f"built for ({label}) — this would reach a customer with no human check")


def test_ai_answers_the_cases_the_rules_pass_up(monkeypatch):
    """The handoff has to actually land somewhere: when a key is set, the
    unclear email is decided by the model and labelled as such."""
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "classify_email",
                        lambda *a, **k: {"category": "SPAM", "confidence": 0.93,
                                         "reason": "marketing blast, not an operational request"})
    r = classify(_email("Reduce your demurrage costs by 80%",
                        "Our AI platform optimises your bill of lading workflow."), use_llm=True)
    assert r["category"] == "SPAM"
    assert r["decided_by"] == "llm"
    assert "marketing" in r["reason"]


def test_clear_emails_never_waste_an_ai_call(monkeypatch):
    """The flip side: obvious emails must stay on the rules. If this breaks, every
    email starts costing money and latency."""
    def explode(*a, **k):
        raise AssertionError("the AI was called for an unambiguous email")
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "classify_email", explode)
    r = classify(_email("TO CONFIRM DOCS _ 5RSG-00133 _ CALLAO_PERU",
                        "Attached please find the SI and the draft BL. "
                        "Kindly check the draft BL against the SI and confirm."), use_llm=True)
    assert r["decided_by"] == "rule" and r["category"] == "BL_COMPARISON"


# ─────────────── 2. the same value written two legitimate ways ─────────────────
# Each of these was found failing by stress-testing and then fixed. They are
# regression locks: none of these shapes appear in the organisers' data, so
# nothing here can be satisfied by memorising it.

@pytest.mark.parametrize("a,b", [
    ("A.P. MOLLER MAERSK A/S", "AP MOLLER MAERSK AS"),     # Danish suffix with a slash
    ("BALL & DOGGETT", "BALL AND DOGGETT"),
    ("PT. SAMUDERA INDONESIA TBK", "PT SAMUDERA INDONESIA TBK"),
    ("NIPPON PAPER CO.,LTD.", "NIPPON PAPER CO LTD"),
])
def test_same_company_written_differently(a, b):
    assert norm_party(a) == norm_party(b)


def test_a_different_company_is_still_different():
    # the guard against over-normalising: these are two real, separate entities
    assert norm_party("ACME PAPER SDN BHD") != norm_party("ACME PAPER (M) SDN BHD")


@pytest.mark.parametrize("a,b", [
    ("NHAVA SHEVA, INDIA", "JNPT (NHAVA SHEVA), INDIA"),   # official name vs common name
    ("BUSAN, SOUTH KOREA", "PUSAN, KOREA"),                # romanisation
    ("HO CHI MINH CITY", "HOCHIMINH CITY, VIETNAM"),
    ("PORT KLANG (WESTPORT)", "PORT KELANG, MALAYSIA"),
])
def test_same_port_written_differently(a, b):
    assert norm_port(a) == norm_port(b)


def test_nearby_ports_are_not_confused():
    assert norm_port("NEW YORK, US") != norm_port("NEWARK, US")


@pytest.mark.parametrize("text,kg", [
    ("55 200 KG", 55200),          # space as a thousands separator (European)
    ("55,200 KG", 55200),
    ("55.2 MT", 55200),
    ("121,000 LBS", 54884.7),      # pounds, on US export paperwork
    ("128,544.00 KGS", 128544),
])
def test_weight_units_and_separators(text, kg):
    got = parse_weight_kg(text)
    assert got is not None and abs(got - kg) < 1.0, f"{text!r} read as {got}"


def test_a_space_separator_is_not_read_as_a_tiny_weight():
    """The specific 1000x bug: '55 200 KG' once parsed as 55 kg, which would
    report a mismatch against an identical weight written '55,200 KG'."""
    assert parse_weight_kg("55 200 KG") == parse_weight_kg("55,200 KG")


# ─────────────── 3. unknown wording must escalate, never be guessed ────────────

SI_UNKNOWN_LABELS = """SHIPPING INSTRUCTION
Shpr: ACME PAPER SDN BHD
Cnee: GLOBAL BOOKS LLC
Notify Address: GLOBAL BOOKS LLC
Place of Receipt: SHAH ALAM
POL: PORT KLANG, MALAYSIA
POD: JEBEL ALI, UAE
Total Pkgs: THREE (3) CONTAINERS
Gross Wt.: 55.2 MT
"""

BL_PLAIN = """BILL OF LADING (DRAFT)
Shipper: ACME PAPER SDN BHD
Consignee: GLOBAL BOOKS LLC
Notify Party: GLOBAL BOOKS LLC
Port of Loading: PORT KLANG, MALAYSIA
Port of Discharge: JEBEL ALI, UAE
No. of Containers: 3
Gross Weight: 55,200 KG
"""


def test_labels_the_rules_do_not_know_go_to_a_person(monkeypatch):
    """`Shpr`/`Cnee` are common abbreviations the rules have never been taught.
    The system must not silently compare nothing and call it a match."""
    monkeypatch.setattr(llm, "available", lambda: False)
    files = {"si.txt": SI_UNKNOWN_LABELS.encode(), "bl.txt": BL_PLAIN.encode()}
    r = process_email(_email("Please check the draft BL against the SI",
                             "Attached SI and draft BL.", files), files.__getitem__, use_llm=False)
    assert r["status"] == "NEEDS_REVIEW"
    assert r["review_reason"] == "missing_value"
    assert r["status"] != "OK", "an unreadable field was treated as agreement"


def test_the_ai_fills_the_labels_the_rules_missed(monkeypatch):
    """And with a key set, those same labels are recovered rather than escalated —
    this is the one place the AI changes an outcome on the happy path."""
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "can_read_pdf", lambda: False)

    def fake_extract(text, pdf_bytes=None, hint=""):
        if "Shpr" not in (text or ""):
            return None
        return {"fields": {"shipper": {"value": "ACME PAPER SDN BHD"},
                           "consignee": {"value": "GLOBAL BOOKS LLC"},
                           "notify_party": {"value": "GLOBAL BOOKS LLC"},
                           "port_of_loading": {"value": "PORT KLANG, MALAYSIA"},
                           "port_of_discharge": {"value": "JEBEL ALI, UAE"},
                           "container_count": {"value": "3"},
                           "gross_weight_kg": {"value": "55.2 MT"}}}

    monkeypatch.setattr(llm, "extract_fields", fake_extract)
    files = {"si.txt": SI_UNKNOWN_LABELS.encode(), "bl.txt": BL_PLAIN.encode()}
    r = process_email(_email("Please check the draft BL against the SI",
                             "Attached SI and draft BL.", files), files.__getitem__, use_llm=True)
    assert r["status"] == "OK", r.get("comparison")
    assert any("field" in u for u in r["ai_used"])


# ─────────────── 4. end-to-end traps that would be false alarms ────────────────

def test_the_same_weight_in_different_units_is_not_a_mismatch(monkeypatch):
    """SI in tonnes, draft BL in pounds — the same shipment. Reporting this as a
    defect would send a customer a correction for a document that is correct."""
    monkeypatch.setattr(llm, "available", lambda: False)
    si = BL_PLAIN.replace("BILL OF LADING (DRAFT)", "SHIPPING INSTRUCTION") \
                 .replace("Gross Weight: 55,200 KG", "Gross Weight: 55.2 MT")
    bl = BL_PLAIN.replace("Gross Weight: 55,200 KG", "Gross Weight: 121,695 LBS")
    files = {"si.txt": si.encode(), "bl.txt": bl.encode()}
    r = process_email(_email("check draft BL", "Attached SI and draft BL.", files),
                      files.__getitem__, use_llm=False)
    assert r["status"] == "OK", f"false alarm on equivalent weights: {r.get('comparison')}"


def test_a_real_weight_difference_is_still_caught(monkeypatch):
    """The other half of the same coin — the unit handling must not swallow a
    genuine discrepancy."""
    monkeypatch.setattr(llm, "available", lambda: False)
    si = BL_PLAIN.replace("BILL OF LADING (DRAFT)", "SHIPPING INSTRUCTION")
    bl = BL_PLAIN.replace("Gross Weight: 55,200 KG", "Gross Weight: 65,200 KG")
    files = {"si.txt": si.encode(), "bl.txt": bl.encode()}
    r = process_email(_email("check draft BL", "Attached SI and draft BL.", files),
                      files.__getitem__, use_llm=False)
    assert r["status"] == "MISMATCH"
    assert r["defect_fields"] == ["gross_weight_kg"]


def test_two_shipping_instructions_and_no_bl_goes_to_a_person(monkeypatch):
    """A customer attaches the SI twice instead of the draft BL. There is nothing
    to compare, and pretending otherwise would be worse than saying so."""
    monkeypatch.setattr(llm, "available", lambda: False)
    si = BL_PLAIN.replace("BILL OF LADING (DRAFT)", "SHIPPING INSTRUCTION")
    files = {"si1.txt": si.encode(), "si2.txt": si.encode()}
    r = process_email(_email("check draft BL", "Attached SI and draft BL.", files),
                      files.__getitem__, use_llm=False)
    assert r["status"] == "NEEDS_REVIEW"


def test_container_counts_written_in_words_are_not_invented(monkeypatch):
    """'THREE (3) CONTAINERS' is not parsed today. The requirement is only that
    it is left blank and escalated rather than guessed at."""
    assert parse_container_count("THREE (3) CONTAINERS") in (None, 3)
    assert parse_container_count("2 x 40'HC + 1 x 20'GP") == 3
    assert parse_container_count("2X40'HC") == 2
