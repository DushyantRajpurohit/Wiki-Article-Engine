"""
Sentence-level faithfulness judge.

The judge sees the article and the numbered summary sentences, and for each one
returns a verdict plus a verbatim quote as evidence. The quote is then checked
against the article in code, so a "supported" verdict backed by an invented
quote is caught rather than trusted.
"""

from typing import Literal

from pydantic import BaseModel

from . import config, llm
from .text import quote_in_article

SYSTEM = """You check summaries against their source article, one sentence at a time.
Be strict: a sentence is supported only if the article states everything in it,
including every name, number and date. Background knowledge does not count."""

PROMPT = """ARTICLE: {title}

{text}

SUMMARY SENTENCES:
{sentences}

For each summary sentence, in order, give:
- verdict: "supported" if the article states everything in the sentence;
  "contradicted" if the article states something incompatible with it;
  "not_found" if the article does not state it (even if it may be true).
- quote: the article passage that decides the verdict, copied exactly, word for word.
  For "not_found", quote the closest relevant passage, or "" if there is none.
- reason: one short sentence."""


class SentenceVerdict(BaseModel):
    sentence: int
    verdict: Literal["supported", "contradicted", "not_found"]
    quote: str
    reason: str


class Judgement(BaseModel):
    verdicts: list[SentenceVerdict]


def judge(article, sentences, model=config.JUDGE):
    """Return one verdict per sentence, each with `quote_found` set by an exact-text check."""
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, 1))
    prompt = PROMPT.format(title=article["title"], text=article["text"], sentences=numbered)
    result = llm.generate(model, prompt, system=SYSTEM, schema=Judgement)

    by_number = {v["sentence"]: v for v in result["verdicts"]}
    verdicts = []
    for i, sentence in enumerate(sentences, 1):
        v = by_number.get(i)
        if v is None:
            # The judge skipped this sentence; record that rather than guess
            verdicts.append({"sentence": sentence, "verdict": "missing", "quote": "", "reason": "",
                             "quote_found": False})
            continue
        verdicts.append({
            "sentence": sentence,
            "verdict": v["verdict"],
            "quote": v["quote"],
            "reason": v["reason"],
            "quote_found": quote_in_article(v["quote"], article["text"]),
        })
    return verdicts


def is_flagged(verdict):
    """A sentence counts as unfaithful if the judge says so, or claims support it can't quote."""
    if verdict["verdict"] in ("contradicted", "not_found", "missing"):
        return True
    return not verdict["quote_found"]
