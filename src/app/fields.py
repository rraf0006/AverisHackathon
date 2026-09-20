"""The 7 compared fields: which labels mean which field, and how to normalise
values so formatting differences never count as a mismatch.

Label matching is the fast, free path. Anything it can't map is left for the
LLM extractor (llm.py) — so an unseen label on finals day still gets read.
"""
from __future__ import annotations

import math
import re
import unicodedata

FIELDS = ["shipper", "consignee", "notify_party", "port_of_loading",
          "port_of_discharge", "container_count", "gross_weight_kg"]

FIELD_LABELS = {
    "shipper": "Shipper", "consignee": "Consignee", "notify_party": "Notify party",
    "port_of_loading": "Port of loading", "port_of_discharge": "Port of discharge",
    "container_count": "Container count", "gross_weight_kg": "Gross weight (kg)",
}

# Ordered: first match wins. "Notify Party/Intermediate Consignee" must hit
# notify before consignee; "Shipper (Principal or Seller)" must hit shipper.
FIELD_PATTERNS: list[tuple[str, str]] = [
    ("notify_party", r"notify|通知人|通知方|pihak (yang )?dimaklum|pihak pemberitahuan|pihak untuk dihubungi"),
    ("consignee", r"consignee|to the order of|收货人|收件人|提货人|penerima|penerima (kiriman|barang)"),
    ("shipper", r"shipper|exporter|发货人|托运人|出口商|pengirim|pengeksport|pihak penghantar|penghantar barang"),
    ("port_of_loading", r"port of loading|load(ing)? port|\bpol\b|port of shipment|装货港|起运港|始发港|pelabuhan (muat|pemuatan|asal)"),
    ("port_of_discharge", r"port of discharge|discharge port|\bpod\b|port of destination|卸货港|目的港|到达港|pelabuhan (bongkar|pemunggahan|destinasi)"),
    ("container_count", r"no\.? of containers|container count|total containers|number of containers|containers? qty|箱数|集装箱数量|货柜数量|jumlah (kontainer|kontena)|bilangan kontena|kuantiti kontena"),
    ("gross_weight_kg", r"gross\s*w|毛重|总毛重|berat kasar|berat kotor|jumlah berat kasar"),
]

# Labels we recognise but deliberately don't compare.
OTHER_LABEL_PATTERN = (
    r"^(b/?l (no|number)|bl no|bill of lading no|booking|oc no|hs code|freight|vessel|ocean vessel|"
    r"voy|voyage|export carrier|commodity|description|kinds of packages|net weight|incoterms|"
    r"invoice|payment terms|country of origin|certificate|issuing authority|buyer|seller|order no|"
    r"container no|carton)"
)


def _clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip().lower()


def label_to_field(label: str) -> str | None:
    low = _clean_label(label)
    if re.search(r"net\s*w|container no\b", low):
        return None
    if re.search(r"description|kinds of packages", low):
        return None
    for fname, pat in FIELD_PATTERNS:
        if re.search(pat, low):
            return fname
    return None


def is_label(text: str) -> bool:
    low = _clean_label(text)
    if not low or len(low) > 70:
        return False
    return label_to_field(low) is not None or re.search(OTHER_LABEL_PATTERN, low) is not None


NUMERIC_FIELDS = ("container_count", "gross_weight_kg")


def fields_from_pairs(pairs: list[tuple[str, str]]) -> dict[str, dict]:
    """Returns {field: {"label", "value"}}. First occurrence wins, except for
    numeric fields, where a "TOTAL …" label beats a table column header and
    the value must actually start with a number."""
    out: dict[str, dict] = {}
    for label, value in pairs:
        f = label_to_field(label)
        if not f or value is None or not str(value).strip():
            continue
        value = str(value).strip()
        if f in NUMERIC_FIELDS:
            first = value.splitlines()[0].strip()
            if not re.match(r"^[\d.,]+", first) and not is_placeholder(first):
                continue
            is_total = "total" in label.lower()
            if f in out:
                if is_total and not out[f].get("total"):
                    out[f] = {"label": label.strip(), "value": value, "total": True}
                elif not out[f].get("total") and normalise(f, out[f]["value"]) != normalise(f, value):
                    out[f]["conflict"] = True
                continue
            out[f] = {"label": label.strip(), "value": value, "total": is_total}
        elif f in out:
            if normalise(f, out[f]["value"]) != normalise(f, value):
                out[f]["conflict"] = True
        else:
            out[f] = {"label": label.strip(), "value": value}
    for v in out.values():
        v.pop("total", None)
    return out


# ------------------------------------------------------------ normalisation

PLACEHOLDER_RE = re.compile(r"^\s*(\?{2,}|_{2,}.*|tba|tbc|tbd|n/?a|-+|nil|pending|to be advised)\s*$", re.I)


def is_placeholder(value: str | None) -> bool:
    if value is None or not str(value).strip():
        return True
    v = str(value).strip()
    first = v.splitlines()[0]
    return bool(PLACEHOLDER_RE.match(first)) or bool(re.search(r"_{3,}|\?{3,}", first))


_SUFFIXES = [
    (r"\bCOMPANY\b", "CO"), (r"\bLIMITED\b", "LTD"), (r"\bCORPORATION\b", "CORP"),
    (r"\bINCORPORATED\b", "INC"), (r"\bPRIVATE\b", "PTE"), (r"\bSENDIRIAN BERHAD\b", "SDN BHD"),
]


def _fold(value: str) -> str:
    """Compatibility-normalise text and remove accents without deleting scripts.

    The old A-Z-only cleanup made every Chinese or Arabic company name become an
    empty string, so two unrelated parties could compare equal.
    """
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch)).upper()


def _alnum_words(value: str) -> str:
    return re.sub(r"\s+", " ", "".join(ch if ch.isalnum() else " " for ch in _fold(value))).strip()


def party_name(value: str) -> str:
    """The party's name is its first line; the rest is address."""
    lines = value.strip().splitlines()
    if not lines:
        return ""
    first = lines[0]
    first = re.split(r"\s+\|\s+", first)[0]
    return first.strip()


def norm_party(value: str) -> str:
    name = _fold(party_name(value))
    name = name.replace("&", " AND ")
    for pat, rep in _SUFFIXES:
        name = re.sub(pat, rep, name)
    name = name.replace(".", "")                  # L.L.C. → LLC, PTE. → PTE
    name = name.replace("/", "")                  # A/S → AS (Danish), M/S → MS
    return _alnum_words(name)


_PORT_ALIASES = {"HO CHI MINH": "HOCHIMINH", "HO CHI MINH CITY": "HOCHIMINH", "HOCHIMINH CITY": "HOCHIMINH",
                 "SAIGON": "HOCHIMINH", "NHAVA SHEVA": "NHAVASHEVA", "JAWAHARLAL NEHRU": "NHAVASHEVA",
                 "PORT KELANG": "PORT KLANG",
                 # official name vs the name everyone actually writes
                 "JNPT": "NHAVASHEVA", "JAWAHARLAL NEHRU PORT": "NHAVASHEVA",
                 # romanisation variants of the same port
                 "PUSAN": "BUSAN", "KEELUNG": "JILONG", "DALIAN": "DALIEN"}


def norm_port(value: str) -> str:
    lines = value.strip().splitlines()
    if not lines:
        return ""
    v = _fold(lines[0])
    v = re.sub(r"\([A-Z]{5}\)", "", v)           # UN/LOCODE like (MYPKG)
    v = re.sub(r"\(.*?\)", "", v)                 # terminal names like (WESTPORT)
    city = v.split(",")[0]
    city = _alnum_words(city)
    return _PORT_ALIASES.get(city, city).replace(" ", "")


_COUNTRY_ALIASES = {
    "US": "USA", "UNITED STATES": "USA", "UNITED STATES OF AMERICA": "USA",
    "UK": "UNITED KINGDOM", "UAE": "UNITED ARAB EMIRATES",
    "KOREA": "SOUTH KOREA", "REPUBLIC OF KOREA": "SOUTH KOREA",
}


def same_port(a: str, b: str) -> bool:
    """Compare ports while using country/UNLOCODE evidence when both sides have it.

    A missing country remains compatible with a named country, preserving common
    forms such as ``BUSAN`` vs ``BUSAN, SOUTH KOREA``. Conflicting explicit
    countries or location codes are never discarded.
    """
    if norm_port(a) != norm_port(b):
        return False

    def details(value: str) -> tuple[str | None, str | None]:
        lines = value.strip().splitlines()
        line = _fold(lines[0]) if lines else ""
        codes = re.findall(r"\(([A-Z]{5})\)", line)
        pieces = [p.strip() for p in line.split(",")]
        country = _alnum_words(re.sub(r"\([A-Z]{5}\)", "", pieces[1])) if len(pieces) > 1 else ""
        country = _COUNTRY_ALIASES.get(country, country) or None
        return (codes[-1] if codes else None), country

    a_code, a_country = details(a)
    b_code, b_country = details(b)
    if a_code and b_code and a_code != b_code:
        return False
    if a_country and b_country and a_country != b_country:
        return False
    return True


def parse_container_count(value: str) -> int | None:
    v = unicodedata.normalize("NFKC", str(value)).upper()
    if re.search(r"\d+\s*[-–—]\s*\d+", v):
        return None
    parts = re.findall(r"(\d+)\s*[X×*]\s*\d{2}", v)      # 3 x 40'HC, 2X20GP
    if parts:
        result = sum(int(p) for p in parts)
    else:
        reverse = re.findall(r"\d{2}\s*(?:'\s*)?(?:GP|HC|HQ|FCL)?\s*[X×*]\s*(\d+)", v)
        if reverse:
            result = sum(int(p) for p in reverse)
        else:
            m = re.search(r"(?:\((\d+)\)|(\d+))\s+CONTAINERS?\b", v)
            if not m:
                m = re.fullmatch(r"\s*(\d+)\s*", v)
            if not m:
                return None
            result = int(next(g for g in m.groups() if g is not None))
    return result if 1 <= result <= 10_000 else None


LB_TO_KG = 0.45359237


def parse_weight_kg(value) -> float | None:
    if isinstance(value, (int, float)):
        num, unit = float(value), "KG"
    else:
        v = unicodedata.normalize("NFKC", str(value)).upper()
        m = re.search(r"([-+]?\d(?:[\d.,\s\u00a0\u202f]*\d)?)\s*"
                      r"(KGS?|KILO(?:GRAMS?)?|MT|MTS|TONNES?|TONS?|LBS?|POUNDS?)?", v)
        if not m:
            return None
        raw = re.sub(r"[\s\u00a0\u202f]", "", m.group(1))
        if "," in raw and "." in raw:
            decimal = "," if raw.rfind(",") > raw.rfind(".") else "."
            thousands = "." if decimal == "," else ","
            raw = raw.replace(thousands, "").replace(decimal, ".")
        elif "," in raw:
            raw = raw.replace(",", "") if re.fullmatch(r"[-+]?\d{1,3}(?:,\d{3})+", raw) else raw.replace(",", ".")
        try:
            num, unit = float(raw), (m.group(2) or "KG")
        except ValueError:
            return None
    if unit.startswith(("MT", "TON")):
        num *= 1000
    elif unit.startswith(("LB", "POUND")):
        num *= LB_TO_KG
    return num if math.isfinite(num) and 0 < num <= 1_000_000_000 else None


def normalise(fname: str, value: str):
    if fname in ("shipper", "consignee", "notify_party"):
        return norm_party(value)
    if fname in ("port_of_loading", "port_of_discharge"):
        return norm_port(value)
    if fname == "container_count":
        return parse_container_count(value)
    if fname == "gross_weight_kg":
        return parse_weight_kg(value)
    return value


def display_value(fname: str, value: str) -> str:
    if fname in ("shipper", "consignee", "notify_party"):
        return party_name(value)
    return value.strip().splitlines()[0]
