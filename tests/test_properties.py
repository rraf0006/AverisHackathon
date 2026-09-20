"""Generated-input properties for parsers and normalisers."""
import math
import sys
from pathlib import Path

from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.fields import norm_party, norm_port, parse_container_count, parse_weight_kg  # noqa: E402
from app.parsing import parse_attachment  # noqa: E402


TEXT = st.text(max_size=250)


@settings(max_examples=150, deadline=None)
@given(TEXT)
def test_party_normalisation_is_idempotent(value):
    assert norm_party(norm_party(value)) == norm_party(value)


@settings(max_examples=150, deadline=None)
@given(TEXT)
def test_port_normalisation_is_idempotent(value):
    assert norm_port(norm_port(value)) == norm_port(value)


@settings(max_examples=200, deadline=None)
@given(TEXT)
def test_weight_parser_never_raises_and_only_returns_positive_finite_values(value):
    result = parse_weight_kg(value)
    assert result is None or (math.isfinite(result) and result > 0)


@settings(max_examples=200, deadline=None)
@given(TEXT)
def test_container_parser_never_raises_and_only_returns_safe_positive_counts(value):
    result = parse_container_count(value)
    assert result is None or 1 <= result <= 10_000


@settings(max_examples=150, deadline=None)
@given(TEXT)
def test_arbitrary_utf8_text_attachment_never_crashes(value):
    doc = parse_attachment("anything.txt", value.encode("utf-8"))
    assert doc.error in (None, "empty", "no_text_layer")


@settings(max_examples=100, deadline=None)
@given(st.binary(max_size=512))
def test_arbitrary_pdf_bytes_are_reported_instead_of_raising(value):
    doc = parse_attachment("anything.pdf", value)
    assert doc.ok or doc.error in {"empty", "corrupt", "no_text_layer"}


@settings(max_examples=150, deadline=None)
@given(st.integers(min_value=1, max_value=10_000))
def test_plain_container_counts_round_trip(value):
    assert parse_container_count(str(value)) == value


@settings(max_examples=150, deadline=None)
@given(st.integers(min_value=1, max_value=999_999_999))
def test_integer_kg_weights_round_trip(value):
    assert parse_weight_kg(f"{value} KG") == value
