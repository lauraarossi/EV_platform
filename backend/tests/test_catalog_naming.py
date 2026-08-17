"""Folding three catalogues' spellings of one car into one dropdown entry.

Every case here came out of the real data, not imagination: the picker was
showing "ZOE" beside "Zoe", and "4 E-TECH" beside "Renault 4 E-Tech Electric".
"""
import pytest

from app.services import catalog_naming as naming


# --- grouping: same car, three spellings --------------------------------------

@pytest.mark.parametrize(
    "make,model",
    [
        ("RENAULT", "RENAULT 4 E-TECH ELECTRIC"),   # EEA
        ("Renault", "4 E-Tech"),                    # evdb
        ("Renault", "Renault 4 E-Tech electric"),   # VCA, make repeated
    ],
)
def test_the_three_sources_agree_on_a_key(make, model):
    assert naming.model_key(make, model) == "4"


def test_case_alone_never_splits_a_model():
    assert naming.model_key("Renault", "ZOE") == naming.model_key("Renault", "Zoe")


def test_marketing_prefix_is_not_a_different_car():
    """VCA lists "New ZOE" alongside "Zoe"; both are the Zoe."""
    assert naming.model_key("Renault", "New ZOE") == naming.model_key("Renault", "Zoe")


def test_percent_marketing_is_not_a_different_car():
    """"MEGANE E-TECH 100% ELECTRIC" left a bare "100" no other source had."""
    assert (
        naming.model_key("Renault", "MEGANE E-TECH 100% ELECTRIC")
        == naming.model_key("Renault", "MEGANE")
    )


def test_model_year_suffixes_collapse():
    """evdb tracks "KONA MY24" and "KONA MY25" as separate models."""
    assert naming.model_key("Hyundai", "KONA MY24") == naming.model_key("Hyundai", "Kona")


def test_powertrain_variants_are_one_nameplate():
    """A Captur is a Captur whether petrol or hybrid; the fuel filter splits
    them, and the model dropdown should not."""
    assert (
        naming.model_key("Renault", "CAPTUR E-TECH HYBRID")
        == naming.model_key("Renault", "CAPTUR")
    )


def test_accents_are_folded_not_stripped():
    """Stripping would leave "citro n" and match nothing."""
    assert naming.model_key("Citroën", "ë-C3") == naming.model_key("CITROEN", "E-C3")


def test_a_name_made_only_of_noise_keeps_its_identity():
    """"Audi e-tron" and "HONDA E" reduce to nothing; were they allowed to,
    every such model would merge into a single empty key."""
    assert naming.model_key("Audi", "Audi e-tron") != ""
    assert naming.model_key("Audi", "Audi e-tron") != naming.model_key("Honda", "HONDA E")


# --- grouping: makes ----------------------------------------------------------

@pytest.mark.parametrize(
    "recorded",
    ["MG", "Mg Motors Uk"],
)
def test_corporate_names_are_the_same_manufacturer(recorded):
    assert naming.make_key(recorded) == "mg"


@pytest.mark.parametrize(
    "recorded,expected",
    [
        ("VOLKSWAGEN, VW", "volkswagen"),     # alias after a comma
        ("Volkswagen Vw", "volkswagen"),      # the same alias after a space
        ("SSANGYONG/KGM", "ssangyong"),
        ("Mitsubishi Motors Corporation", "mitsubishi"),
        ("INEOS Automotive Ltd", "ineos"),
        ("Bmw I", "bmw"),                     # BMW's electric sub-brand
        ("Leapmotor", "leapmotor"),           # "motor" inside a word survives
    ],
)
def test_make_keys(recorded, expected):
    assert naming.make_key(recorded) == expected


# --- choosing which spelling to show ------------------------------------------

def test_the_shouted_spelling_loses():
    assert naming.choose_display([("CAPTUR", "eea"), ("Captur", "vca")]) == "Captur"


def test_everything_shouted_is_title_cased():
    """Both sources capitalise the Captur, so neither can be shown as-is."""
    assert naming.choose_display([("CAPTUR", "eea"), ("CAPTUR", "vca")]) == "Captur"


def test_short_model_codes_are_not_shouting():
    """"C3" is a model code. Treating it as shouted showed the user "ë-C3"."""
    assert naming.choose_display([("C3", "eea"), ("ë-C3", "evdb")]) == "C3"


def test_two_letter_marques_keep_their_capitals():
    """The opposite of the rule above: "MG" and "DS" are acronyms. Only at two
    letters is that unambiguous — "BMW" wants capitals where "Zoe" does not."""
    assert naming.choose_display([("MG", "eea"), ("Mg", "vca")]) == "MG"
    assert naming.choose_display([("Ds", "vca"), ("DS", "eea")]) == "DS"


def test_three_letter_names_are_left_to_the_sources():
    assert naming.choose_display([("ZOE", "eea"), ("Zoe", "vca")]) == "Zoe"


def test_a_lone_letter_beside_digits_keeps_its_case():
    assert naming.choose_display([("I30", "eea"), ("i30", "vca")]) == "i30"


def test_the_base_nameplate_beats_the_powertrain_spelling():
    assert naming.choose_display(
        [("Megane E-Tech Electric", "evdb"), ("MEGANE", "eea")]
    ) == "Megane"


def test_a_bare_number_is_not_a_model_name():
    """VCA files the R5 as plain "5", which is no use in a dropdown."""
    assert naming.choose_display([("5", "vca"), ("5 E-Tech", "evdb")]) == "5 E-Tech"


def test_separated_words_beat_run_together_ones():
    """evdb writes "SantaFe"; it is a Santa Fe."""
    assert naming.choose_display([("SantaFe", "evdb"), ("Santa Fe", "vca")]) == "Santa Fe"


def test_a_letter_beside_digits_is_not_two_words():
    """The rule above must not turn "i30" into "i 30"."""
    assert naming.choose_display([("i30", "vca"), ("i 30", "eea")]) == "i30"


def test_the_accented_spelling_survives():
    """Splitting words on ASCII letters cut "Citroën" into "Citro" and "n",
    which scored it as more shouted than the flattened spelling."""
    assert naming.choose_display([("CITROEN", "eea"), ("Citroën", "evdb")]) == "Citroën"


def test_curated_sources_win_ties():
    assert naming.choose_display([("ZOE", "eea"), ("Zoe", "evdb")]) == "Zoe"


def test_acronyms_survive_title_casing():
    assert naming.smart_title("Q5 SPORTBACK 50 TFSI E") == "Q5 Sportback 50 TFSI E"


@pytest.mark.parametrize(
    "recorded,expected",
    [
        ("Bentley Motors", "Bentley"),
        ("KGM UK Motors Ltd", "KGM"),
        ("DS Automobiles", "DS"),
        ("VOLKSWAGEN, VW", "VOLKSWAGEN"),
        ("Volkswagen Vw", "Volkswagen"),
        ("Lynk & Co", "Lynk & Co"),      # "Co" is the brand here, not a suffix
        ("Ford", "Ford"),
    ],
)
def test_make_display_drops_the_paperwork(recorded, expected):
    assert naming.clean_make_display(recorded) == expected


def test_choosing_from_nothing_is_not_an_error():
    assert naming.choose_display([]) == ""
