"""Decode an Irish vehicle registration.

An Irish plate encodes when and where the car was first registered, so year and
county can be derived offline with no lookup at all:

    251-D-12345    ->  2025, first half,  Dublin
    132-C-4567     ->  2013, second half, Cork
    05-KY-1234     ->  2005,              Kerry

Since 2013 the year field carries a half-year digit (1 = Jan-Jun, 2 = Jul-Dec),
introduced because buyers avoided the "13" plate.

What this cannot do is tell you the make or model. That lives in the National
Vehicle and Driver File, which is not publicly accessible — commercial
resellers licence it and charge per lookup (around EUR 0.20). `LookupResult`
therefore carries only what the plate itself proves, and leaves room for a paid
provider to fill in the rest later.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

# County/city identifiers used on Irish plates.
COUNTY_CODES: dict[str, str] = {
    "C": "Cork", "CE": "Clare", "CN": "Cavan", "CW": "Carlow",
    "D": "Dublin", "DL": "Donegal", "G": "Galway", "KE": "Kildare",
    "KK": "Kilkenny", "KY": "Kerry", "L": "Limerick", "LD": "Longford",
    "LH": "Louth", "LK": "Limerick", "LM": "Leitrim", "LS": "Laois",
    "MH": "Meath", "MN": "Monaghan", "MO": "Mayo", "OY": "Offaly",
    "RN": "Roscommon", "SO": "Sligo", "T": "Tipperary", "TN": "Tipperary North",
    "TS": "Tipperary South", "W": "Waterford", "WD": "Waterford",
    "WH": "Westmeath", "WW": "Wicklow", "WX": "Wexford",
}

# 2013 onwards: three digits (year + half). Before that: two digits.
MODERN = re.compile(r"^(\d{2})([12])[\s-]*([A-Z]{1,2})[\s-]*(\d{1,6})$")
LEGACY = re.compile(r"^(\d{2})[\s-]*([A-Z]{1,2})[\s-]*(\d{1,6})$")


@dataclass
class RegLookup:
    registration: str
    valid: bool
    year: int | None = None
    half: int | None = None
    county: str | None = None
    county_code: str | None = None
    # Populated only if a licensed VRM provider is configured.
    make: str | None = None
    model: str | None = None
    notes: list[str] = field(default_factory=list)


def _expand_year(two_digits: int) -> int:
    """87 -> 1987, 05 -> 2005, using the current year as the cut-off."""
    current = datetime.date.today().year
    candidate = 2000 + two_digits
    return candidate if candidate <= current + 1 else 1900 + two_digits


def decode(registration: str) -> RegLookup:
    raw = (registration or "").strip().upper()
    cleaned = re.sub(r"[^A-Z0-9]", "", raw)

    if not cleaned:
        return RegLookup(registration=raw, valid=False, notes=["Empty registration"])

    for pattern, has_half in ((MODERN, True), (LEGACY, False)):
        m = pattern.match(cleaned)
        if not m:
            continue

        if has_half:
            yy, half, code, _ = m.groups()
            half_val = int(half)
        else:
            yy, code, _ = m.groups()
            half_val = None

        year = _expand_year(int(yy))
        county = COUNTY_CODES.get(code)

        notes: list[str] = []
        if county is None:
            notes.append(f"Unrecognised county code '{code}'")
        if has_half and year < 2013:
            notes.append("Half-year digits only came in from 2013")
        notes.append(
            "Make and model can't be derived from a plate — the national "
            "database isn't public. Pick the car below to fill those in."
        )

        return RegLookup(
            registration=raw,
            valid=county is not None,
            year=year,
            half=half_val,
            county=county,
            county_code=code,
            notes=notes,
        )

    return RegLookup(
        registration=raw,
        valid=False,
        notes=["Doesn't look like an Irish registration (e.g. 251-D-12345)"],
    )
