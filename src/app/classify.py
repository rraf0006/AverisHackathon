"""Step 1 — Triage. Keyword rules first (free, instant, explainable); if the
rules aren't confident, ask the LLM. The body is trusted over the subject,
because subjects are often stale ("RE: RE: ...") or misleading.
"""
from __future__ import annotations

import re

from . import llm

CATEGORIES = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]

CATEGORY_HELP = {
    "BL_COMPARISON": "Asks to check / confirm / compare a draft Bill of Lading against the Shipping Instruction, or asks for the draft BL so it can be checked.",
    "SI_REQUEST": "Sends or requests a new Shipping Instruction (SI) — no BL check requested.",
    "INVOICE_QUERY": "Invoices, billing, GR, local charges, THC, freight, D&D / detention / demurrage, cancel invoice.",
    "GENERAL": "Operational updates, reports, reminders, automated notifications, HR / office news.",
    "SPAM": "Phishing, prizes, scams, marketing, fake account alerts.",
}

# (category, regex, weight). Body hits count fully, subject hits count 0.4×.
RULES: list[tuple[str, str, float]] = [
    # BL comparison
    ("BL_COMPARISON", r"draft\s*(b/?l|bill of lading)", 1.0),
    ("BL_COMPARISON", r"\b(check|verify|compare|confirm)\b[^.]{0,60}\b(b/?l|bill of lading)\b", 2.0),
    ("BL_COMPARISON", r"\b(b/?l|bill of lading)\b[^.]{0,40}\b(against|matches|vs\.?)\b[^.]{0,20}\b(si|shipping instruction)\b", 2.5),
    ("BL_COMPARISON", r"\b(si|shipping instruction)\b[^.]{0,20}\band\b[^.]{0,20}\b(draft|b/?l|bill of lading)\b", 1.5),
    ("BL_COMPARISON", r"to confirm docs|request bl draft|amend bl|discrepanc", 1.0),
    ("BL_COMPARISON", r"send (us |me )?(the )?draft\s*(b/?l|bill of lading)[^.]{0,60}\b(check|checking|review|confirm)", 2.0),
    ("BL_COMPARISON", r"\b(review|look over|go through|cross.?check)\b[^.]{0,40}\b(b/?l|bill of lading)\b", 2.0),
    ("BL_COMPARISON", r"(lines? up|consistent|agrees?|match(es)?) with (our |the )?(si|shipping instruction)", 2.0),
    ("BL_COMPARISON", r"(核对|检查|对比)[^。]{0,20}提单|提单[^。]{0,20}(核对|一致)", 2.5),
    ("BL_COMPARISON", r"(确认|审核|比较)[^。]{0,24}(提单|提单草稿)|提单[^。]{0,24}(相符|差异|不一致)", 2.5),
    ("BL_COMPARISON", r"提单[^。]{0,24}(装运指示|托运指示)|(?:装运指示|托运指示)[^。]{0,24}提单", 2.0),
    # Malay / Indonesian: "semak draf BL", "periksa draft BL"
    ("BL_COMPARISON", r"(semak|periksa|bandingkan|sahkan|teliti)[^.]{0,50}(b/?l|bill of lading|bil muatan|konosemen)", 2.0),
    ("BL_COMPARISON", r"(b/?l|bil muatan|konosemen)[^.]{0,50}(sepadan|selaras|sama|berbanding|percanggahan|perbezaan)[^.]{0,30}(si|arahan penghantaran)", 2.5),
    ("BL_COMPARISON", r"(si|arahan penghantaran)[^.]{0,30}(dengan|dan|berbanding)[^.]{0,30}(b/?l|bil muatan|konosemen)", 2.0),
    # SI request
    ("SI_REQUEST", r"(please find|attached|herewith)[^.]{0,20}shipping instruction for", 2.5),
    ("SI_REQUEST", r"\b(cust si|request si|si needed|send (the |us )?si|provide (the )?si)\b", 1.5),
    ("SI_REQUEST", r"^\s*(re_ |re: |fw: )*si\s*-\s", 1.0),
    ("SI_REQUEST", r"\bpol:\s|\bpod:\s", 0.5),
    ("SI_REQUEST", r"(here (is|are)|sending|attached)[^.]{0,20}(the |our )?shipping instructions?\b(?![^.]{0,30}(draft|b/?l|bill of lading))", 2.0),
    # "here is the SI, send the draft BL when ready" = an SI, not a check request
    ("SI_REQUEST", r"revert with (the )?draft\s*(b/?l|bill of lading)( once| when)", 2.0),
    # Invoice
    ("INVOICE_QUERY", r"\binvoice\b", 1.5),
    ("INVOICE_QUERY", r"\bbilling\b|\bgr\b is still missing|missing gr|post the gr", 1.5),
    ("INVOICE_QUERY", r"d\s*&\s*d|detention|demurrage|local charge|\bthc\b|freight charge|debit note|credit note|reverse the pgi", 2.0),
    ("INVOICE_QUERY", r"\binvois\b|\bfaktur\b|\btagihan\b|发票", 1.5),
    ("INVOICE_QUERY", r"\b(charged|overcharg\w*|refund|payment|corrected bill)\b|\bbill\b(?! of lading)", 1.5),
    # General
    ("GENERAL", r"automated notification|no action required|rpa bot", 3.5),
    ("GENERAL", r"berthing report|update summary|loading completed|outstanding bl|pending bl", 2.0),
    ("GENERAL", r"reminder|happy (and prosperous )?new year|office (resumes|closed)|holiday|time off|welcome", 2.0),
    # Spam
    ("SPAM", r"congratulations|you have won|claim (your|the)|gift card|lottery|monthly draw", 3.0),
    ("SPAM", r"bitcoin|crypto|guaranteed \d+%|investment opportunity|business proposal|usd [\d.]+ million", 3.0),
    ("SPAM", r"verify (your )?account|mailbox (has )?exceeded|storage (limit|is full)|avoid (suspension|deactivation)|bank details", 3.0),
    ("SPAM", r"unpaid customs fee|parcel will be returned|limited time offer|\d+% off|buy now|one weird trick", 3.0),
    ("SPAM", r"https?://(?!www\.(aprilasia|paperone)\.com)", 1.0),
]

SPAM_SENDER = re.compile(r"@(.*(verify|prize|winner|secure-mailbox|crypto|claims?)[^@]*)$", re.I)
BANNER = re.compile(r"^WARNING: This email originated outside.*$", re.I | re.M)


def _main_body(body: str) -> str:
    """Drop the external-sender banner and anything below a quoted reply."""
    body = BANNER.sub("", body)
    body = re.split(r"\n_{5,}\s*\n|\nFrom:\s.*\nSent:", body)[0]
    return body


def rule_scores(email: dict) -> dict[str, float]:
    body = _main_body(email.get("body", "")).lower()
    subject = email.get("subject", "").lower()
    scores = {c: 0.0 for c in CATEGORIES}
    for cat, pat, w in RULES:
        if re.search(pat, body, re.M):
            scores[cat] += w
        if re.search(pat, subject):
            scores[cat] += 0.4 * w
    if SPAM_SENDER.search(email.get("from", "")):
        scores["SPAM"] += 2.0
    # An email carrying an SI + another document is almost always a check request
    atts = [a.lower() for a in email.get("attachments", [])]
    if len(atts) >= 2:
        scores["BL_COMPARISON"] += 1.0
    return scores


def classify(email: dict, use_llm: bool = True) -> dict:
    scores = rule_scores(email)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    (best, s1), (_, s2) = ranked[0], ranked[1]
    confident = s1 >= 2.0 and (s1 - s2) >= 1.0
    result = {"category": best, "decided_by": "rule", "confidence": round(min(1.0, (s1 - s2) / 3 + 0.4), 2),
              "scores": {k: round(v, 2) for k, v in scores.items()}, "reason": None}
    if confident:
        result["reason"] = f"Keyword rules matched {best} (score {s1:.1f} vs {s2:.1f})."
        return result
    if use_llm and llm.available():
        out = llm.classify_email(email, CATEGORY_HELP)
        if out and out.get("category") in CATEGORIES:
            result.update(category=out["category"], decided_by="llm",
                          confidence=float(out.get("confidence", 0.7)),
                          reason=out.get("reason") or "Classified by the AI model.")
            return result
    if s1 == 0:
        result.update(category="GENERAL", confidence=0.2)
    result["decided_by"] = "rule_low_confidence"
    result["reason"] = "Rules were not confident and no AI model was available — please double-check."
    return result
