import random

from wikieval.judge import is_flagged
from wikieval.perturb import add_claim, change_number, negate, perturb, swap_entity
from wikieval.report import wilson
from wikieval.text import quote_in_article, split_sentences
from wikieval.wikipedia import clean_text

ARTICLE = ("The Bedford RL was a lorry built by Bedford Vehicles from 1952 until 1969. "
           "About 74,000 were made for the Royal Navy and the British Army.")


# --- sentence splitting ---

def test_splits_plain_sentences():
    assert split_sentences("It was built in 1952. It served until 1969.") == [
        "It was built in 1952.", "It served until 1969."]


def test_keeps_initials_abbreviations_and_acronyms_together():
    text = "J. R. R. Tolkien met Dr. Smith in the U.S. in 1950. They talked."
    assert split_sentences(text) == ["J. R. R. Tolkien met Dr. Smith in the U.S. in 1950.", "They talked."]


def test_splits_after_closing_quote():
    assert split_sentences('He said "no." Then he left.') == ['He said "no."', "Then he left."]


def test_numbered_name_is_not_a_sentence_end():
    assert split_sentences("He joined No. 5 Squadron. He flew.") == ["He joined No. 5 Squadron.", "He flew."]


def test_does_not_split_decimals():
    assert split_sentences("It weighs 3.5 tonnes. It is green.") == ["It weighs 3.5 tonnes.", "It is green."]


# --- quote matching ---

def test_quote_matches_despite_case_quotes_and_whitespace():
    assert quote_in_article("about 74,000   were made", ARTICLE)
    assert quote_in_article("“The Bedford RL was a lorry”", ARTICLE)


def test_invented_quote_is_rejected():
    assert not quote_in_article("about 80,000 were made", ARTICLE)


def test_ellipsis_quote_needs_every_part():
    assert quote_in_article("built by Bedford Vehicles ... for the Royal Navy", ARTICLE)
    assert not quote_in_article("built by Bedford Vehicles ... for the Royal Air Force", ARTICLE)


def test_spaced_ellipsis_separates_quote_parts():
    assert quote_in_article("built by Bedford Vehicles. . . for the Royal Navy", ARTICLE)
    assert not quote_in_article("built by Bedford Vehicles . . . for the Royal Air Force", ARTICLE)


def test_too_short_quote_is_not_evidence():
    assert not quote_in_article("Bedford", ARTICLE)
    assert not quote_in_article("", ARTICLE)


# --- planted errors ---

def test_negation_inserts_not():
    assert negate("It was built by Bedford.", ARTICLE, random.Random(0)) == "It was not built by Bedford."


def test_changed_number_never_appears_in_article():
    rng = random.Random(0)
    for _ in range(20):
        changed = change_number("Production ran from 1952 to 1969.", ARTICLE, rng)
        assert changed != "Production ran from 1952 to 1969."
        new_years = [w.strip(".") for w in changed.split() if w.strip(".").isdigit()]
        assert any(y not in ARTICLE for y in new_years)


def test_number_keeps_thousands_separator():
    changed = change_number("About 74,000 were made.", ARTICLE, random.Random(1))
    assert "," in changed and "74,000" not in changed


def test_decades_are_left_alone():
    assert change_number("It rose in the 1980s.", ARTICLE, random.Random(0)) is None


def test_added_claim_uses_a_year_the_article_never_mentions():
    changed = add_claim("It served with the Royal Navy.", ARTICLE, random.Random(0))
    assert changed.startswith("It served with the Royal Navy, ") and changed.endswith(".")
    year = next(w.strip(".,") for w in changed.split() if w.strip(".,").isdigit())
    assert year not in ARTICLE


def test_entity_swap_uses_another_name_from_the_article():
    changed = swap_entity("It served with the Royal Navy.", ARTICLE, random.Random(0))
    assert "Royal Navy" not in changed
    assert any(name in changed for name in ("Bedford Vehicles", "British Army", "Bedford RL"))


def test_perturb_returns_none_when_nothing_can_change():
    assert perturb(["Intro.", "Lovely."], ARTICLE, "number", random.Random(0)) is None


def test_perturb_skips_first_sentence():
    sentences = ["It was built in 1952.", "It was retired in 1969."]
    index, _ = perturb(sentences, ARTICLE, "negation", random.Random(0))
    assert index == 1


# --- verdicts, intervals, cleaning ---

def test_supported_without_a_real_quote_is_flagged():
    assert not is_flagged({"verdict": "supported", "quote_found": True})
    assert is_flagged({"verdict": "supported", "quote_found": False})
    assert is_flagged({"verdict": "not_found", "quote_found": True})


def test_wilson_interval_contains_estimate_and_widens_for_small_n():
    low, high = wilson(5, 10)
    assert low < 50 < high
    small = wilson(1, 2)
    large = wilson(50, 100)
    assert (small[1] - small[0]) > (large[1] - large[0])


def test_clean_text_cuts_references_and_empty_headings():
    raw = "Intro text.\n\n== History ==\nIt was built.\n\n== Variants ==\n\n== References ==\nSmith 2001."
    assert clean_text(raw) == "Intro text.\n== History ==\nIt was built."
