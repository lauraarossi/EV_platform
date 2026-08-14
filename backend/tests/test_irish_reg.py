"""Decoding Irish registration plates."""
import pytest

from app.services.irish_reg import decode


@pytest.mark.parametrize(
    "reg,year,half,county",
    [
        ("251-D-12345", 2025, 1, "Dublin"),
        ("252-D-12345", 2025, 2, "Dublin"),
        ("132-C-4567", 2013, 2, "Cork"),
        ("241-KY-1", 2024, 1, "Kerry"),
        ("201-G-99999", 2020, 1, "Galway"),
    ],
)
def test_modern_plates(reg, year, half, county):
    r = decode(reg)
    assert r.valid
    assert (r.year, r.half, r.county) == (year, half, county)


@pytest.mark.parametrize(
    "reg,year,county",
    [
        ("05-KY-1234", 2005, "Kerry"),
        ("12-D-98765", 2012, "Dublin"),
        ("99-WW-1234", 1999, "Wicklow"),
    ],
)
def test_pre_2013_plates_have_no_half_year(reg, year, county):
    """The half-year digit only arrived in 2013, when buyers shunned '13'."""
    r = decode(reg)
    assert r.valid
    assert r.year == year
    assert r.county == county
    assert r.half is None


@pytest.mark.parametrize("reg", ["251 D 12345", "251d12345", "  251-d-12345  ", "251D12345"])
def test_accepts_loose_formatting(reg):
    r = decode(reg)
    assert r.valid and r.year == 2025 and r.county == "Dublin"


def test_two_letter_county_codes():
    assert decode("231-WH-1234").county == "Westmeath"
    assert decode("221-MO-1").county == "Mayo"


def test_unknown_county_code_is_flagged_not_guessed():
    r = decode("251-ZZ-1234")
    assert not r.valid
    assert any("ZZ" in n for n in r.notes)


@pytest.mark.parametrize("reg", ["", "hello", "AB12CDE", "1-2-3"])
def test_rejects_nonsense(reg):
    r = decode(reg)
    assert not r.valid
    assert r.year is None


def test_never_claims_to_know_make_or_model():
    """The national database isn't public, so these must stay empty."""
    r = decode("251-D-12345")
    assert r.make is None
    assert r.model is None
    assert any("make and model" in n.lower() for n in r.notes)


def test_pre_2000_years_resolve_to_the_1900s():
    assert decode("97-D-1234").year == 1997
