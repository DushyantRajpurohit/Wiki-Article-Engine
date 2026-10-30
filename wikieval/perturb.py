"""
Plant one known error in a summary, so the judge can be tested against ground truth.

Four kinds:
- negation: "was" becomes "was not"
- number:   a year or count changes to a value that appears nowhere in the article
- entity:   a name is swapped for a different name from the same article
- addition: an invented claim is added, the classic LLM failure: nothing in the article
            contradicts it, the article just doesn't say it

Each returns None when the sentence offers nothing to change, and the caller tries
another sentence. An entity swap can occasionally produce a sentence that is still
true; the human review catches those, and the README reports how many.
"""

import re

KINDS = ("negation", "number", "entity", "addition")

VERB = re.compile(r"\b(is|was|are|were|has|had|can|could|will|would)\b")
# Not decades or ordinals: "1980s" would become "1985s", which gives the error away
NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(?![\w]|[.,]\d)")
# Two or more capitalised words in a row ("Royal Navy", "Bedford Vehicles")
NAME = re.compile(r"\b[A-Z][a-z]+(?:\s+(?:of|de|von|the)?\s*[A-Z][a-z]+)+\b")


def negate(sentence, article_text, rng):
    matches = list(VERB.finditer(sentence))
    if not matches:
        return None
    m = rng.choice(matches)
    return sentence[: m.end()] + " not" + sentence[m.end() :]


def change_number(sentence, article_text, rng):
    matches = list(NUMBER.finditer(sentence))
    rng.shuffle(matches)
    for m in matches:
        value = int(m.group().replace(",", ""))
        if 1000 <= value <= 2100:
            candidates = [value + d for d in (-9, -7, -5, -3, 3, 5, 7, 9)]  # a different year
        elif value >= 2:
            candidates = [value * 2, value * 3, round(value / 2), value + 4]
        else:
            continue
        rng.shuffle(candidates)
        for new in candidates:
            new_text = f"{new:,}" if "," in m.group() else str(new)
            # The planted value must not appear in the article, or it might genuinely be supported
            if new != value and not re.search(rf"(?<![\d,]){re.escape(new_text)}(?![\d,])", article_text):
                return sentence[: m.start()] + new_text + sentence[m.end() :]
    return None


def swap_entity(sentence, article_text, rng):
    in_sentence = list(NAME.finditer(sentence))
    if not in_sentence:
        return None
    present = {m.group() for m in in_sentence}
    others = sorted({n for n in NAME.findall(article_text) if n not in present
                     and not any(n in p or p in n for p in present)})
    if not others:
        return None
    m = rng.choice(in_sentence)
    return sentence[: m.start()] + rng.choice(others) + sentence[m.end() :]


ADDITIONS = (", according to a {year} government report",
             ", a decision that was widely criticised in {year}",
             ", and this was the subject of a documentary released in {year}")


def add_claim(sentence, article_text, rng):
    """Add a plausible, checkable claim, using a year the article never mentions."""
    if not sentence.endswith("."):
        return None
    years = [y for y in range(1975, 2021) if str(y) not in article_text]
    if not years:
        return None
    addition = rng.choice(ADDITIONS).format(year=rng.choice(years))
    return sentence[:-1] + addition + "."


PERTURBERS = {"negation": negate, "number": change_number, "entity": swap_entity, "addition": add_claim}


def perturb(sentences, article_text, kind, rng):
    """
    Return (index, new sentence) for one changed sentence, or None if no sentence works.
    The first sentence is skipped: it usually restates the title, which makes errors trivial.
    """
    order = list(range(1, len(sentences))) or [0]
    rng.shuffle(order)
    for i in order:
        changed = PERTURBERS[kind](sentences[i], article_text, rng)
        if changed and changed != sentences[i]:
            return i, changed
    return None
