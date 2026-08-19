"""Reconciling how three catalogues spell the same car.

The sources disagree in every way a name can disagree:

    EEA   "RENAULT"  "RENAULT 4 E-TECH ELECTRIC"   "ZOE"   "KONA, KAUAI"
    evdb  "Renault"  "4 E-Tech"                    "Zoe"   "KonaKauai"
    VCA   "Renault"  "Renault 4 E-Tech electric"   "Zoe"   "Kona Electric"

Left alone that puts four spellings of one car in the model dropdown. So each
row carries two derived keys — `make_key` and `model_key` — which strip the
name down to what identifies the car, and rows sharing a key are one model.

The keys are deliberately aggressive. "MEGANE" and "MEGANE E-TECH ELECTRIC"
collapse together, as do "CAPTUR" and "CAPTUR E-TECH HYBRID": one nameplate,
several powertrains, which the fuel filter already separates. Grouping by
nameplate is what a person expects from a Model dropdown.

Choosing which spelling to *show* is a separate problem, handled by
`choose_display`, because none of the sources is reliably the prettiest.
"""

from __future__ import annotations

import re
import unicodedata

# Marketing and powertrain words one source uses and another doesn't. Removing
# them is what lets "Audi Q4 40 E-TRON" line up with evdb's "Q4 e-tron", and
# Citroen's "E-C3" with "ë-C3" (the diaeresis normalises away to nothing).
NOISE = (
    "electric", "e-tech", "etech", "e-tron", "etron", "e-hybrid", "ehybrid",
    "bev", "ev", "hybrid", "phev", "hev", "mhev", "elektro",
    "long range", "standard range", "e",
)

# evdb and VCA are curated manufacturer data. The EEA set is bulk registration
# data typed in by 27 national authorities, largely in capitals, so it loses
# most ties on spelling — though not all, as evdb writes "SantaFe".
SOURCE_RANK = {"evdb": 0, "vca": 1, "eea": 2, "manual": 3}

# Legal and corporate words tacked onto a manufacturer name. Registration data
# records the entity that filed the paperwork — "Mitsubishi Motors Corporation",
# "Mg Motors Uk", "INEOS Automotive Ltd" — where a person just says the brand.
# Matched whole-token only, so "Leapmotor" survives intact.
MAKE_SUFFIXES = {
    "ltd", "limited", "plc", "gmbh", "ag", "sa", "nv", "bv", "inc", "llc",
    "corporation", "corp", "company", "co", "group", "holdings",
    "motors", "motor", "automotive", "automobiles", "automobile", "cars",
    "uk", "technik",
}

# Acronyms that are not shouting and must survive title-casing.
KEEP_CASE = {
    "TFSI", "TDI", "TSI", "TCE", "DCI", "HDI", "BLUEHDI", "GTI", "SUV",
    "JCW", "ALL4", "AMG", "BMW", "MHEV", "PHEV", "HEV", "AWD", "4WD",
}


def normalise(text: str | None) -> str:
    """Reduce a name to comparable letters and digits.

    Accents are folded, not stripped: evdb writes "Citroën" and "Škoda" where
    the EEA data writes "CITROEN" and "SKODA". Dropping the accented letter
    outright would leave "citro n" and never match.
    """
    s = str(text or "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _primary(name: str | None) -> str:
    """The first of several names sharing one field.

    The EEA data records market aliases together — "VOLKSWAGEN, VW",
    "SSANGYONG/KGM", "KONA, KAUAI" — and only the first is the name people use.
    """
    return re.split(r"\s*[,/]\s*", str(name or "").strip())[0].strip()


def _abbreviates(short: str, long: str) -> bool:
    """Whether `short` is `long` shortened, as "vw" is of "volkswagen"."""
    it = iter(long)
    return all(ch in it for ch in short)


def make_key(make: str | None) -> str:
    """Reduce a manufacturer name to the brand people actually say."""
    words = normalise(_primary(make)).split()
    while len(words) > 1 and words[-1] in MAKE_SUFFIXES:
        words.pop()
    # "BMW I" is BMW's electric sub-brand, not a separate manufacturer.
    if len(words) > 1 and len(words[-1]) == 1:
        words.pop()
    # "VOLKSWAGEN VW": the same alias the comma form spells "VOLKSWAGEN, VW".
    if len(words) == 2 and len(words[1]) <= 3 and _abbreviates(words[1], words[0]):
        words.pop()
    return " ".join(words)


def model_key(make: str | None, model: str | None) -> str:
    """Strip the make, model years and marketing noise from a model name.

    "RENAULT 4 E-TECH ELECTRIC" and "4 E-Tech" both reduce to "4".
    """
    raw = _primary(model) or str(model or "")
    m = normalise(raw)
    mk = normalise(make)
    if mk and m.startswith(mk + " "):
        m = m[len(mk) + 1:]
    m = re.sub(r"^(all new|new)\s+", "", m)     # VCA's "New ZOE"
    m = re.sub(r"\bmy\d{2}\b", " ", m)          # evdb's "KONA MY24"
    # "MEGANE E-TECH 100% ELECTRIC" — normalising drops the % and would
    # otherwise leave a bare "100" that no other source has.
    if "100%" in raw:
        m = re.sub(r"\b100\b", " ", m)
    for word in NOISE:
        m = re.sub(rf"\b{re.escape(normalise(word))}\b", " ", m)
    collapsed = re.sub(r"\s+", "", m)
    # A name made entirely of noise — "Audi e-tron", "HONDA E" — would reduce to
    # the empty string, and every such model would then merge into one. Fall
    # back to the full name so they stay distinct.
    return collapsed or re.sub(r"\s+", "", normalise(model))


# --- choosing the spelling to show -------------------------------------------

def is_shouty(name: str) -> bool:
    """Whether a name is in capitals for no reason.

    Tested per word, not with `isupper()` on the whole string: "C3", "MG4" and
    "A6" are model codes, and treating them as shouting would have shown the
    user "ë-C3" in place of "C3".
    """
    return any(
        len(w) >= 4 and w.isupper() and w not in KEEP_CASE
        for w in re.findall(r"[A-Za-z]+", name)
    )


def smart_title(name: str) -> str:
    return " ".join(
        w.title()
        if len(re.findall(r"[A-Za-z]", w)) >= 4 and w.isupper() and w.strip("-") not in KEEP_CASE
        else w
        for w in name.split()
    )


def clean_make_display(make: str) -> str:
    """A manufacturer name as a person would write it, without the paperwork."""
    words = _primary(make).split()
    # "Lynk & Co" is the brand, not a company suffix on "Lynk".
    if "&" not in words:
        while len(words) > 1 and normalise(words[-1]) in MAKE_SUFFIXES:
            words.pop()
    if len(words) > 1 and len(re.findall(r"[^\W\d_]", words[-1])) <= 1:
        words.pop()                              # "BMW I"
    if (
        len(words) == 2
        and len(words[1]) <= 3
        and _abbreviates(normalise(words[1]), normalise(words[0]))
    ):
        words.pop()                              # "Volkswagen VW"
    return " ".join(words) or make.strip()


def clean_display(make: str, model: str) -> str:
    """Tidy one source's spelling before it competes to be the display name."""
    m = _primary(model) or model.strip()
    mk = normalise(make)
    if normalise(m).startswith(mk + " "):        # VCA repeats the make in Model
        m = " ".join(m.split()[len(mk.split()):])
    m = re.sub(r"^(all[- ]new|new)\s+", "", m, flags=re.I).strip()
    m = re.sub(r"\s*\bMY\d{2}\b", "", m, flags=re.I).strip()
    return m or model.strip()


def _noise_words(name: str) -> int:
    noise = {normalise(w).replace(" ", "") for w in NOISE}
    return sum(1 for w in normalise(name).split() if w in noise)


def _shout_ratio(name: str) -> float:
    """How much of a name is shouted, counting only words long enough to be.

    A word of three letters or fewer is a marque or a model code — MG, DS, C3 —
    and being uppercase says nothing about it. Counting those was enough to
    make "Mg Motors Uk" look calmer than "MG".
    """
    # Unicode-aware: splitting on [A-Za-z] cut "Citroën" into "Citro" and "n",
    # which made the accented spelling score worse than the flattened one.
    letters = [c for w in re.findall(r"[^\W\d_]+", name) if len(w) >= 4 for c in w]
    if not letters:
        return 0.0
    # Rounded, so a one-letter difference doesn't outweigh the later tests.
    return round(sum(c.isupper() for c in letters) / len(letters), 1)


def _acronym_bonus(name: str) -> float:
    """Prefer capitals for a name that can only be an acronym.

    "MG" and "DS" are marques and belong in capitals, which is the opposite of
    the rule above. Deliberately limited to names whose every word is one or
    two letters: at three the two cases are indistinguishable — "BMW" wants
    capitals and "Zoe" does not — and a lone letter beside digits is the "i30"
    case, which wants its lower-case i.
    """
    words = re.findall(r"[^\W\d_]+", name)
    letters = [c for w in words for c in w]
    if len(letters) < 2 or any(len(w) > 2 for w in words):
        return 0.0
    return -round(sum(c.isupper() for c in letters) / len(letters), 1)


def _word_breaks(name: str) -> int:
    """Spaces separating two real words.

    "Santa Fe" has one and should win over evdb's "SantaFe". "i 30" has none —
    a lone letter beside digits is not two words — so "i30" is not penalised
    for closing the gap.
    """
    words = name.split()
    return sum(
        1
        for a, b in zip(words, words[1:])
        if len(re.findall(r"[A-Za-z]", a)) >= 2 and len(re.findall(r"[A-Za-z]", b)) >= 2
    )


def split_embedded_model(
    make: str, model: str, known_make_keys: set[str]
) -> tuple[str, str]:
    """Move a model name out of the make field and back where it belongs.

    Sources occasionally file a car under "Porsche Taycan" rather than
    "Porsche", which then stands in the Make dropdown as though it were a
    manufacturer. Repaired here, at ingest, rather than papered over when the
    list is drawn: the row is simply wrong, and every reader of it would
    otherwise need the same special case.

    Only splits when the shorter form is a manufacturer *in the same import*,
    and only on a word boundary — so nothing is broken up on the strength of a
    shared prefix. The words taken off the make go to the front of the model,
    since that is what they were describing.
    """
    key = make_key(make)
    parents = [k for k in known_make_keys if k != key and key.startswith(k + " ")]
    if not parents:
        return make, model

    parent = min(parents, key=len)
    words = _primary(make).split()
    kept = " ".join(words[: len(parent.split())])
    extra = " ".join(words[len(parent.split()) :])

    if extra and not normalise(model).startswith(normalise(extra)):
        model = f"{extra} {model}".strip()
    return kept or make, model


def rekey(db) -> dict[str, int]:
    """Recompute every row's grouping keys.

    These rules are heuristics over messy data and will keep being adjusted;
    when they change, the stored keys are stale until this runs. Cheaper and
    far less alarming than re-importing all three sources to fix a name.
    """
    from sqlalchemy import update

    from app.models.catalog import CatalogVehicle

    rows = db.query(CatalogVehicle).all()
    updates = [
        {"id": row.id, "make_key": mk, "model_key": mo}
        for row, mk, mo in (
            (r, make_key(r.make), model_key(r.make, r.model)) for r in rows
        )
        if (row.make_key, row.model_key) != (mk, mo)
    ]

    if updates:
        db.execute(update(CatalogVehicle), updates)
        db.commit()

    return {"rows": len(rows), "changed": len(updates)}


def choose_display(candidates: list[tuple[str, str]]) -> str:
    """Pick the best spelling from (name, source) pairs sharing a key.

    Ordered by what actually goes wrong in the data: a bare "5" is not a model
    name, "Megane" beats "Megane E-Tech Electric" as the nameplate, and
    "CAPTUR" loses to any spelling that isn't shouted.
    """
    if not candidates:
        return ""
    best = sorted(
        candidates,
        key=lambda c: (
            bool(re.fullmatch(r"\d+", c[0])),        # "5" -> prefer "5 E-Tech"
            _noise_words(c[0]),                      # prefer the base nameplate
            _shout_ratio(c[0]),                      # prefer the least shouted
            _acronym_bonus(c[0]),                    # except "MG", which is one
            -_word_breaks(c[0]),                     # "Santa Fe" over "SantaFe"
            SOURCE_RANK.get(c[1], 9),                # curated over bulk data
            len(c[0]),
            c[0],
        ),
    )[0][0]
    return smart_title(best) if is_shouty(best) else best
