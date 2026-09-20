"""The agentic pipeline: Triage → Read documents → Extract fields → Verify →
(Escalate). Our code controls the order; the AI is called only where it adds
something (unclear emails, unknown labels, scanned PDFs). Every step writes
to `trace`, which the dashboard shows so a reviewer can see *why*.
"""
from __future__ import annotations

import re
import time
from typing import Callable

from . import llm
from .classify import classify
from .fields import (FIELD_LABELS, FIELDS, display_value, fields_from_pairs,
                     is_placeholder, normalise, same_port)
from .parsing import ParsedDoc, parse_attachment

WRONG_TYPES = {"COMMERCIAL_INVOICE", "PACKING_LIST", "CERTIFICATE_OF_ORIGIN"}
DOC_TYPE_NAMES = {"COMMERCIAL_INVOICE": "a Commercial Invoice", "PACKING_LIST": "a Packing List",
                  "CERTIFICATE_OF_ORIGIN": "a Certificate of Origin", "OTHER": "not a Bill of Lading"}

# Statuses shown in the app. For the organisers' scorer, WAITING_FOR_BL and
# NOT_CHECKED map to "OK" (see to_submission).
STATUSES = ["OK", "MISMATCH", "NEEDS_REVIEW", "WAITING_FOR_BL", "NOT_CHECKED"]


class Trace:
    def __init__(self):
        self.steps: list[dict] = []

    def add(self, step: str, status: str, detail: str, t0: float):
        self.steps.append({"step": step, "status": status, "detail": detail,
                           "ms": int((time.time() - t0) * 1000)})


def _read_doc(path: str, data: bytes, trace: Trace, use_llm: bool) -> tuple[ParsedDoc, dict, dict]:
    """Returns (parsed doc, fields {field: {value,label,quote,source}}, extra info)."""
    t0 = time.time()
    doc = parse_attachment(path, data)
    info = {"ai_read": False}
    fields: dict[str, dict] = {}
    if doc.ok:
        for f, v in fields_from_pairs(doc.pairs).items():
            if v.get("conflict"):
                fields[f] = {"value": None, "label": v["label"],
                             "quote": f"Conflicting values found for {v['label']}", "source": "rules"}
            else:
                fields[f] = {"value": v["value"], "label": v["label"],
                             "quote": f"{v['label']}: {v['value'].splitlines()[0]}", "source": "rules"}
        trace.add("Read document", "ok", f"{path.split('/')[-1]}: looks like {doc.doc_type}, found {len(fields)}/7 fields by label", t0)
    elif doc.error == "no_text_layer" and use_llm and llm.can_read_pdf():
        out = llm.extract_fields(None, pdf_bytes=data, hint="(scanned — read it visually)")
        if isinstance(out, dict) and out.get("readable", True) and isinstance(out.get("fields", {}), dict):
            doc.doc_type = out.get("doc_type") or doc.doc_type
            info["ai_read"] = True
            for f in FIELDS:
                fv = (out.get("fields") or {}).get(f) or {}
                if not isinstance(fv, dict):
                    continue
                if fv.get("value") not in (None, ""):
                    fields[f] = {"value": str(fv["value"]), "label": "(read from scan by AI)",
                                 "quote": fv.get("quote"), "source": "ai-vision"}
            trace.add("Read document", "warn", f"{path.split('/')[-1]}: scanned image — AI read it visually ({len(fields)}/7 fields); a person should confirm", t0)
        else:
            trace.add("Read document", "fail", f"{path.split('/')[-1]}: scanned image, AI could not read it", t0)
    else:
        why = {"empty": "the file is empty (0 bytes)", "corrupt": "the file is damaged and won't open",
               "no_text_layer": "it's a scanned image with no text (no AI vision model configured)",
               "unsupported": "unsupported file type"}.get(doc.error, doc.error)
        trace.add("Read document", "fail", f"{path.split('/')[-1]}: {why}", t0)
    return doc, fields, info


def _fill_with_llm(doc: ParsedDoc, fields: dict, trace: Trace, role: str):
    missing = [f for f in FIELDS if f not in fields]
    if not missing or not doc.ok or not llm.available():
        return
    t0 = time.time()
    out = llm.extract_fields(doc.text, hint=f"(expected: {role})")
    if not isinstance(out, dict) or not isinstance(out.get("fields"), dict):
        trace.add("Extract fields (AI)", "warn", f"AI extraction failed for {role}: {llm.last_error or 'no answer'}", t0)
        return
    got = []
    for f in missing:
        fv = (out.get("fields") or {}).get(f) or {}
        if not isinstance(fv, dict):
            continue
        if fv.get("value") not in (None, ""):
            fields[f] = {"value": str(fv["value"]), "label": "(matched by AI)", "quote": fv.get("quote"), "source": "ai"}
            got.append(FIELD_LABELS[f])
    trace.add("Extract fields (AI)", "ok", f"{role}: AI found {', '.join(got) or 'nothing new'} for labels the rules didn't recognise", t0)


# Weights can arrive in different units, and converting pounds to kilograms does
# not land on a round number, so exact equality would report a defect on two
# documents that say the same thing. The smallest genuine weight defect in the
# organisers' data is 0.233% (500 kg on 214,270), and no matching pair differs
# numerically at all — so 0.01% absorbs conversion rounding with a 20x margin
# below anything real.
WEIGHT_TOLERANCE = 1e-4


def _same_value(field: str, a, b) -> bool:
    if field == "gross_weight_kg" and isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b or abs(a - b) <= WEIGHT_TOLERANCE * max(abs(a), abs(b))
    return a == b


def compare_fields(si: dict, bl: dict) -> list[dict]:
    rows = []
    for f in FIELDS:
        s, b = si.get(f), bl.get(f)
        s_val, b_val = (s or {}).get("value"), (b or {}).get("value")
        row = {"field": f, "label": FIELD_LABELS[f],
               "si": display_value(f, s_val) if s_val else None,
               "bl": display_value(f, b_val) if b_val else None,
               "si_quote": (s or {}).get("quote"), "bl_quote": (b or {}).get("quote"),
               "si_source": (s or {}).get("source"), "bl_source": (b or {}).get("source"),
               "match": None, "note": None}
        if is_placeholder(s_val) or is_placeholder(b_val):
            which = "SI" if is_placeholder(s_val) else "BL"
            row["note"] = f"{which} value is missing or a placeholder"
        else:
            if f in ("port_of_loading", "port_of_discharge"):
                ns, nb = s_val, b_val
            else:
                ns, nb = normalise(f, s_val), normalise(f, b_val)
            if ns is None or nb is None:
                row["note"] = "Could not read the value"
            else:
                row["match"] = same_port(ns, nb) if f in ("port_of_loading", "port_of_discharge") else _same_value(f, ns, nb)
                if row["match"] and display_value(f, s_val).upper() != display_value(f, b_val).upper():
                    row["note"] = "Same value, different formatting"
        rows.append(row)
    return rows


def process_email(email: dict, read_bytes: Callable[[str], bytes], use_llm: bool = True,
                  second_opinion: bool = False) -> dict:
    trace = Trace()
    res = {"email_id": email["email_id"], "from": email.get("from"), "subject": email.get("subject"),
           "body": email.get("body", ""), "attachments": email.get("attachments", []),
           "status": "NOT_CHECKED", "review_reason": None, "review_detail": None, "ai_used": [],
           "defect_fields": [], "has_defect": False, "comparison": [], "documents": [],
           "error": None}
    try:
        _run(email, read_bytes, use_llm, trace, res, second_opinion)
    except Exception as exc:  # never let one email kill the batch
        res["status"], res["review_reason"] = "NEEDS_REVIEW", "processing_error"
        res["review_detail"] = f"Processing failed ({type(exc).__name__}: {exc}). Retry or check by hand."
        res["error"] = f"{type(exc).__name__}: {exc}"
        trace.add("Error", "fail", res["review_detail"], time.time())
    res["trace"] = trace.steps
    res["llm_model"] = llm.model_name() if llm.available() else None
    return res


def _run(email, read_bytes, use_llm, trace, res, second_opinion=False):
    # ① Triage
    t0 = time.time()
    c = classify(email, use_llm=use_llm)
    res.update(category=c["category"], decided_by=c["decided_by"], class_confidence=c["confidence"],
               class_reason=c["reason"], class_scores=c["scores"])
    trace.add("Triage", "ok" if c["decided_by"] != "rule_low_confidence" else "warn",
              f"{c['category']} — {c['reason']}", t0)
    if c["decided_by"] == "llm":
        res["ai_used"].append("sorted this email (the keyword rules weren't confident)")
    if c["category"] != "BL_COMPARISON":
        return

    # ② Documents present?
    atts = email.get("attachments", [])
    if not atts:
        t0 = time.time()
        if re.search(r"attach|enclosed|compare the si|find (the )?si", email.get("body", ""), re.I) and \
                not re.search(r"(send|share|provide) (us |me )?the draft b/?l", email.get("body", ""), re.I):
            _escalate(res, "missing_attachment", "The email says documents are attached, but none arrived.")
            trace.add("Check attachments", "fail", "Email mentions attachments but there are none", t0)
        else:
            res["status"] = "WAITING_FOR_BL"
            trace.add("Check attachments", "ok", "Request for the draft BL — nothing to compare yet", t0)
        return

    docs = []
    for p in atts:
        doc, fields, info = _read_doc(p, read_bytes(p), trace, use_llm)
        docs.append((doc, fields, info))
        res["documents"].append({**doc.to_dict(), "ai_read": info["ai_read"],
                                 "fields": {k: v["value"] for k, v in fields.items()}})

    # ③ Which one is the SI, which is the BL?
    sis = [d for d in docs if d[0].doc_type == "SI"]
    bls = [d for d in docs if d[0].doc_type == "BL"]
    si = sis[0] if len(sis) == 1 else None
    bl = bls[0] if len(bls) == 1 else None
    unread = [d for d in docs if not d[0].ok and not d[2]["ai_read"]]
    wrong = [d for d in docs if d[0].doc_type in WRONG_TYPES]
    t0 = time.time()
    if unread:
        names = ", ".join(d[0].path.split("/")[-1] for d in unread)
        _escalate(res, "unreadable", f"Could not read {names}: {unread[0][0].error.replace('_', ' ')}.")
        trace.add("Escalate", "fail", res["review_detail"], t0)
        return
    if len(sis) > 1 or len(bls) > 1:
        _escalate(res, "wrong_doc_type", "Multiple Shipping Instructions or draft Bills of Lading arrived; a person must choose the correct version.")
        trace.add("Escalate", "fail", res["review_detail"], t0)
        return
    if wrong and bl is None:
        d = wrong[0][0]
        _escalate(res, "wrong_doc_type", f"{d.path.split('/')[-1]} is {DOC_TYPE_NAMES.get(d.doc_type, d.doc_type)}, not a draft Bill of Lading.")
        trace.add("Escalate", "fail", res["review_detail"], t0)
        return
    if si is None or bl is None:
        if len(docs) == 1:
            _escalate(res, "missing_attachment", "Only one document arrived — the draft BL (or the SI) is missing.")
        else:
            _escalate(res, "wrong_doc_type", "Couldn't tell which attachment is the SI and which is the draft BL.")
        trace.add("Escalate", "fail", res["review_detail"], t0)
        return

    # ④ Fill gaps with the AI (labels the rules didn't recognise)
    if use_llm:
        _fill_with_llm(si[0], si[1], trace, "Shipping Instruction")
        _fill_with_llm(bl[0], bl[1], trace, "draft Bill of Lading")

    for d in docs:
        if d[2]["ai_read"]:
            res["ai_used"].append(f"read {d[0].path.split('/')[-1]} visually — it is a scan with no text")
    n_ai_fields = sum(1 for side in (si[1], bl[1]) for v in side.values() if v.get("source") == "ai")
    if n_ai_fields:
        res["ai_used"].append(f"filled {n_ai_fields} field(s) the rules' label list didn't recognise")

    # ⑤ Verify — deterministic comparison
    t0 = time.time()
    rows = compare_fields(si[1], bl[1])
    res["comparison"] = rows
    mism = [r["field"] for r in rows if r["match"] is False]
    blanks = [r for r in rows if r["match"] is None]
    res["defect_fields"] = mism
    trace.add("Verify", "ok", f"{7 - len(blanks)}/7 fields compared, {len(mism)} mismatch(es)"
              + (f": {', '.join(FIELD_LABELS[m] for m in mism)}" if mism else ""), t0)

    # ⑥ Decide
    ai_scan = si[2]["ai_read"] or bl[2]["ai_read"]
    if blanks:
        what = "; ".join(f"{r['label']} ({r['note']})" for r in blanks)
        _escalate(res, "missing_value", f"Can't confirm every field: {what}.")
        trace.add("Escalate", "warn", res["review_detail"], time.time())
    elif ai_scan:
        _escalate(res, "unreadable", "One document is a scanned image. The AI read it, but a person should confirm before we rely on it.")
        trace.add("Escalate", "warn", res["review_detail"], time.time())
    elif mism:
        res.update(status="MISMATCH", has_defect=True)
        # A second pair of eyes on the cases we would actually send back to a customer.
        # Advisory only: it is recorded and shown, and it never edits status/category/
        # comparison, so the submitted answer is identical whether or not it runs.
        if second_opinion and use_llm and llm.available():
            t0 = time.time()
            op = llm.second_opinion(si[0].text or "", bl[0].text or "", [r for r in rows if r["match"] is False])
            if op:
                res["second_opinion"] = op
                res["ai_used"].append("double-checked the mismatch as a second reviewer")
                trace.add("Second opinion (AI)", "ok" if op["agrees"] else "warn",
                          ("AI agrees these fields really don't match" if op["agrees"]
                           else "AI disagrees with the rules — worth a human look") + f": {op['note']}", t0)
    else:
        res["status"] = "OK"


def _escalate(res: dict, reason: str, detail: str):
    res.update(status="NEEDS_REVIEW", review_reason=reason, review_detail=detail,
               has_defect=False)


def to_submission(res: dict) -> dict:
    """The organisers' scorer format."""
    status = res.get("status")
    if res.get("category") != "BL_COMPARISON" or status in ("WAITING_FOR_BL", "NOT_CHECKED"):
        status = "OK"
    needs = status == "NEEDS_REVIEW"
    mism = status == "MISMATCH"
    reason = res.get("review_reason") if needs else None
    if reason == "processing_error":
        reason = "unreadable"
    return {"category": res.get("category", "GENERAL"), "status": status, "review_reason": reason,
            "has_defect": mism, "defect_fields": list(res.get("defect_fields", [])) if mism else [],
            "decided_by": "llm" if res.get("decided_by") == "llm" else "rule"}
