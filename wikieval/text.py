"""Sentence splitting and quote matching: the deterministic parts of the evaluation."""

import re
import unicodedata

# Words whose trailing full stop does not end a sentence
ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "st", "jr", "sr", "prof", "gen", "col", "lt", "sgt",
                 "vs", "etc", "c", "ca", "vol", "approx", "inc", "ltd", "co", "mt", "ft"}

# Group 1 is the end of the sentence, closing quotes and brackets included
SENTENCE_END = re.compile(r"([.!?][\"”')\]]*)\s+(?=[\"“(\[]?[A-Z0-9])")


def split_sentences(text):
    """
    Split a summary into sentences.

    A full stop does not end a sentence after a known abbreviation ("Dr."), a single
    capital ("J. R. R. Tolkien") or a dotted acronym ("U.S."). Summaries are short,
    plain prose, so this covers the cases that occur; tests pin each one.
    """
    text = " ".join(text.split())
    sentences, start = [], 0
    for match in SENTENCE_END.finditer(text):
        end = match.end(1)
        words = text[start:end].split()
        last_word = words[-1] if words else ""
        stem = last_word.lstrip("\"“([").rstrip(".").lower()
        if last_word.endswith(".") and (
            stem in ABBREVIATIONS
            or (stem == "no" and text[match.end() : match.end() + 1].isdigit())  # "No. 5"
            or re.fullmatch(r"[A-Za-z]", stem)
            or re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]", stem)
        ):
            continue
        sentences.append(text[start:end].strip())
        start = match.end()
    sentences.append(text[start:].strip())
    return [s for s in sentences if s]


def normalise(text):
    """Lower-case, unify quote marks and dashes, collapse whitespace: so formatting can't hide a match."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[‘’‚‛′]", "'", text)
    text = re.sub(r"[“”„‟″]", '"', text)
    text = re.sub(r"[‐‑‒–—―]", "-", text)
    return " ".join(text.split())


def quote_in_article(quote, article_text):
    """
    Is the judge's evidence really in the article?

    Judges sometimes join two nearby passages with "..." or ". . .", so each part must
    appear, and every part must be at least a few words long to count as evidence.
    """
    article = normalise(article_text)
    parts = [p.strip(" .,;:\"'") for p in re.split(r"(?:\.\s*){3,}", normalise(quote))]
    parts = [p for p in parts if p]
    return bool(parts) and all(len(p.split()) >= 3 and p in article for p in parts)
