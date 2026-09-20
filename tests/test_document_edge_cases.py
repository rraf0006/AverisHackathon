"""Ambiguous attachment sets, document layouts, and extreme field values."""
import io
import sys
from pathlib import Path

import openpyxl
import pytest
from pypdf import PdfWriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import llm  # noqa: E402
from app.fields import norm_party, parse_container_count, parse_weight_kg, same_port  # noqa: E402
from app.parsing import parse_attachment  # noqa: E402
from app.pipeline import process_email  # noqa: E402


SI = """SHIPPING INSTRUCTION
Shipper: ACME PAPER SDN BHD
Consignee: GLOBAL BOOKS LLC
Notify Party: GLOBAL BOOKS LLC
Port of Loading: PORT KLANG, MALAYSIA (MYPKG)
Port of Discharge: JEBEL ALI, UAE (AEJEA)
Container Count: 3
Gross Weight: 55,200 KG
"""

BL = SI.replace("SHIPPING INSTRUCTION", "BILL OF LADING (DRAFT)")


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    monkeypatch.setattr(llm, "can_read_pdf", lambda: False)


def _run(files):
    email = {"email_id": "edge", "from": "ops@example.com", "subject": "Check draft BL",
             "body": "Please check the attached draft BL against the SI.", "attachments": list(files)}
    return process_email(email, files.__getitem__, use_llm=False)


@pytest.mark.parametrize("files", [
    {"si-1.txt": SI.encode(), "si-2.txt": SI.encode(), "bl.txt": BL.encode()},
    {"si.txt": SI.encode(), "bl-1.txt": BL.encode(), "bl-2.txt": BL.encode()},
])
def test_multiple_versions_require_a_person(files):
    result = _run(files)
    assert result["status"] == "NEEDS_REVIEW"
    assert "Multiple" in result["review_detail"]


def test_unrelated_invoice_does_not_hide_a_valid_si_and_bl():
    files = {"si.txt": SI.encode(), "bl.txt": BL.encode(),
             "invoice.txt": b"COMMERCIAL INVOICE\nInvoice No: 123"}
    assert _run(files)["status"] == "OK"


def test_document_content_wins_over_a_misleading_filename():
    files = {"looks-like-bl.txt": SI.encode(), "looks-like-si.txt": BL.encode()}
    assert _run(files)["status"] == "OK"


def test_conflicting_duplicate_field_requires_review():
    conflicting = SI.replace("Gross Weight: 55,200 KG",
                             "Gross Weight: 55,200 KG\nGross Weight: 65,200 KG")
    result = _run({"si.txt": conflicting.encode(), "bl.txt": BL.encode()})
    assert result["status"] == "NEEDS_REVIEW"
    assert result["review_reason"] == "missing_value"


def test_identical_duplicate_field_is_safe():
    duplicate = SI.replace("Gross Weight: 55,200 KG",
                           "Gross Weight: 55,200 KG\nGross Weight: 55.2 MT")
    assert _run({"si.txt": duplicate.encode(), "bl.txt": BL.encode()})["status"] == "OK"


def test_password_protected_pdf_is_reported_as_unreadable():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    buf = io.BytesIO()
    writer.write(buf)
    doc = parse_attachment("draft.pdf", buf.getvalue())
    assert not doc.ok and doc.error == "corrupt"


def test_xlsx_formula_without_cached_value_does_not_get_invented():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(("SHIPPING INSTRUCTION", ""))
    ws.append(("Gross Weight", "=55000+200"))
    buf = io.BytesIO()
    wb.save(buf)
    doc = parse_attachment("si.xlsx", buf.getvalue())
    assert doc.ok and not any(label == "Gross Weight" for label, _ in doc.pairs)


def test_uppercase_file_extensions_are_supported():
    assert parse_attachment("DRAFT.TXT", BL.encode()).doc_type == "BL"


def test_corrupt_unrelated_attachment_still_forces_review():
    result = _run({"si.txt": SI.encode(), "bl.txt": BL.encode(), "other.pdf": b"not a pdf"})
    assert result["status"] == "NEEDS_REVIEW" and result["review_reason"] == "unreadable"


def test_different_non_latin_company_names_never_compare_equal():
    assert norm_party("上海纸业有限公司") != norm_party("北京纸业有限公司")
    chinese_bl = BL.replace("GLOBAL BOOKS LLC", "上海纸业有限公司", 1)
    chinese_si = SI.replace("GLOBAL BOOKS LLC", "北京纸业有限公司", 1)
    result = _run({"si.txt": chinese_si.encode(), "bl.txt": chinese_bl.encode()})
    assert result["status"] == "MISMATCH" and "consignee" in result["defect_fields"]


def test_accented_and_unaccented_company_names_match():
    assert norm_party("Société Générale") == norm_party("Societe Generale")


def test_same_city_in_different_countries_is_not_the_same_port():
    assert not same_port("Alexandria, Egypt", "Alexandria, USA")


def test_conflicting_unlocodes_are_not_discarded():
    assert not same_port("Alexandria, Egypt (EGALY)", "Alexandria, Egypt (USAXL)")


def test_missing_country_can_still_match_a_full_port_name():
    assert same_port("BUSAN", "PUSAN, SOUTH KOREA")


def test_reversed_loading_and_discharge_ports_are_both_caught():
    swapped = BL.replace("PORT KLANG, MALAYSIA (MYPKG)", "__TEMP_PORT__") \
                .replace("JEBEL ALI, UAE (AEJEA)", "PORT KLANG, MALAYSIA (MYPKG)") \
                .replace("__TEMP_PORT__", "JEBEL ALI, UAE (AEJEA)")
    result = _run({"si.txt": SI.encode(), "bl.txt": swapped.encode()})
    assert set(result["defect_fields"]) == {"port_of_loading", "port_of_discharge"}


@pytest.mark.parametrize("text,expected", [
    ("55.200,50 KG", 55200.5), ("55,200.50 KG", 55200.5),
    ("55\u202f200 KG", 55200), ("55,2 MT", 55200),
    ("0 KG", None), ("-500 KG", None), ("999999999999999999 KG", None),
])
def test_extreme_weight_formats(text, expected):
    assert parse_weight_kg(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("10 pallets in 2 containers", 2), ("2-3 containers", None),
    ("40HC x 2", 2), ("THREE (3) CONTAINERS", 3),
    ("0", None), ("-2", None), ("10001", None),
])
def test_extreme_container_formats(text, expected):
    assert parse_container_count(text) == expected


def test_attachment_read_exception_isolated_to_one_email():
    email = {"email_id": "broken", "from": "x", "subject": "Check draft BL",
             "body": "Check the attached draft BL against SI.", "attachments": ["missing.txt"]}
    result = process_email(email, lambda _: (_ for _ in ()).throw(FileNotFoundError("gone")), use_llm=False)
    assert result["status"] == "NEEDS_REVIEW" and result["review_reason"] == "processing_error"
