"""
Wikipedia summaries, measured.

    python -m wikieval models      # which Gemini models your key can use
    python -m wikieval sample      # draw the article sample (data/articles.jsonl)
    python -m wikieval summarize   # summarise every article with every model in config.SUMMARIZERS
    python -m wikieval judge       # judge every summary sentence against its article
    python -m wikieval perturb     # plant known errors and judge those too
    python -m wikieval recheck     # redo the quote check on stored verdicts (no API calls)
    python -m wikieval review      # you label a blind sample of sentences
    python -m wikieval report      # results/report.md

Every stage skips work already done, so any stage can be rerun or resumed.
"""

import random
import re
import sys

from . import config, llm
from .judge import is_flagged, judge
from .perturb import KINDS, perturb
from .report import write_report
from .store import append_jsonl, read_jsonl, write_jsonl
from .summarize import summarize
from .text import quote_in_article, split_sentences
from .wikipedia import sample_articles


def articles_by_id():
    articles = read_jsonl(config.ARTICLES)
    if not articles:
        sys.exit("No articles yet. Run: python -m wikieval sample")
    return {a["pageid"]: a for a in articles}


def cmd_models():
    for name in llm.list_models():
        print(name)


def cmd_sample():
    if config.ARTICLES.exists():
        sys.exit(f"{config.ARTICLES} already exists. Delete it first to draw a new sample.")
    write_jsonl(config.ARTICLES, sample_articles(config.N_ARTICLES, config.MIN_WORDS, config.MAX_WORDS))


def cmd_summarize():
    done = {(s["pageid"], s["model"]) for s in read_jsonl(config.SUMMARIES)}
    exhausted = set()
    for article in articles_by_id().values():
        for model in config.SUMMARIZERS:
            if (article["pageid"], model) in done or model in exhausted:
                continue
            try:
                summary = summarize(article, model)
            except llm.DailyQuota as e:
                # One model running out shouldn't stop the others
                print(e)
                exhausted.add(model)
                continue
            except llm.Blocked as e:
                append_jsonl(config.SUMMARIES, {
                    "pageid": article["pageid"], "title": article["title"], "model": model,
                    "blocked": str(e), "summary": "", "sentences": [],
                })
                print(f"{model}: {article['title']}: BLOCKED ({e})")
                continue
            append_jsonl(config.SUMMARIES, {
                "pageid": article["pageid"], "title": article["title"], "model": model,
                "summary": summary, "sentences": split_sentences(summary),
            })
            print(f"{model}: {article['title']}")


def cmd_judge():
    articles = articles_by_id()
    done = {(j["pageid"], j["model"], j["judge"]) for j in read_jsonl(config.JUDGEMENTS)}
    for s in read_jsonl(config.SUMMARIES):
        if s.get("blocked") or (s["pageid"], s["model"], config.JUDGE) in done:
            continue
        try:
            verdicts = judge(articles[s["pageid"]], s["sentences"])
        except llm.Blocked as e:
            append_jsonl(config.JUDGEMENTS, {
                "pageid": s["pageid"], "title": s["title"], "model": s["model"],
                "judge": config.JUDGE, "blocked": str(e), "verdicts": [],
            })
            print(f"{s['model']}: {s['title']}: judge BLOCKED ({e})")
            continue
        append_jsonl(config.JUDGEMENTS, {
            "pageid": s["pageid"], "title": s["title"], "model": s["model"],
            "judge": config.JUDGE, "verdicts": verdicts,
        })
        print(f"{s['model']}: {s['title']}: {sum(map(is_flagged, verdicts))}/{len(verdicts)} flagged")


def cmd_perturb():
    """Plant errors in the first summarizer's summaries only: one model is enough to test the judge."""
    articles = articles_by_id()
    done = {(p["pageid"], p["kind"], p["judge"]) for p in read_jsonl(config.PERTURBED)}
    summaries = [s for s in read_jsonl(config.SUMMARIES) if s["model"] == config.SUMMARIZERS[0] and not s.get("blocked")]
    for s in sorted(summaries, key=lambda s: s["pageid"]):
        article = articles[s["pageid"]]
        for kind in KINDS:
            # Seeded per article and kind, so adding a kind or resuming changes nothing else
            rng = random.Random(f"{config.SEED}:{s['pageid']}:{kind}")
            planted = perturb(s["sentences"], article["text"], kind, rng)
            if planted is None or (s["pageid"], kind, config.JUDGE) in done:
                continue
            index, changed = planted
            sentences = s["sentences"][:index] + [changed] + s["sentences"][index + 1 :]
            try:
                verdicts = judge(article, sentences)
            except llm.Blocked as e:
                print(f"{kind}: {s['title']}: judge BLOCKED ({e})")
                continue
            append_jsonl(config.PERTURBED, {
                "pageid": s["pageid"], "title": s["title"], "model": s["model"], "judge": config.JUDGE,
                "kind": kind, "index": index, "original": s["sentences"][index], "changed": changed,
                "verdicts": verdicts,
            })
            print(f"{kind}: {s['title']}: {'caught' if is_flagged(verdicts[index]) else 'MISSED'}")


def cmd_recheck():
    """Rerun the code-side quote check on stored verdicts, after a change to the matcher."""
    articles = articles_by_id()
    for path in (config.JUDGEMENTS, config.PERTURBED):
        records = read_jsonl(path)
        for record in records:
            for v in record["verdicts"]:
                v["quote_found"] = quote_in_article(v["quote"], articles[record["pageid"]]["text"])
        write_jsonl(path, records)


def relevant_passages(sentence, article_text, n=2):
    """The article paragraphs sharing the most words with the sentence, to help a human check it."""
    words = set(re.findall(r"[a-z0-9]{4,}", sentence.lower()))
    paragraphs = [p for p in article_text.split("\n") if not p.startswith("=")]
    return sorted(paragraphs, key=lambda p: -len(words & set(re.findall(r"[a-z0-9]{4,}", p.lower()))))[:n]


def review_queue():
    """
    Everything the judge flagged, an equal-sized random sample of what it passed,
    and every planted entity swap it missed (to check whether the swap is still true).
    Shuffled, and shown without the judge's verdict, so the human label is blind.
    """
    rng = random.Random(config.SEED)
    flagged, passed = [], []
    for j in read_jsonl(config.JUDGEMENTS):
        for i, v in enumerate(j["verdicts"]):
            item = {"source": "summary", "pageid": j["pageid"], "model": j["model"], "index": i,
                    "sentence": v["sentence"], "judge_flagged": is_flagged(v)}
            (flagged if item["judge_flagged"] else passed).append(item)
    queue = flagged + rng.sample(passed, min(len(passed), max(len(flagged), 20)))
    for p in read_jsonl(config.PERTURBED):
        if p["kind"] == "entity" and not is_flagged(p["verdicts"][p["index"]]):
            queue.append({"source": "entity_swap_missed", "pageid": p["pageid"], "model": p["model"],
                          "index": p["index"], "sentence": p["changed"], "judge_flagged": False})
    rng.shuffle(queue)
    return queue


def cmd_review():
    articles = articles_by_id()
    labelled = {(l["source"], l["pageid"], l["model"], l["index"], l["sentence"]) for l in read_jsonl(config.HUMAN_LABELS)}
    queue = [q for q in review_queue() if (q["source"], q["pageid"], q["model"], q["index"], q["sentence"]) not in labelled]
    print(f"{len(queue)} sentences to label. For each: is EVERYTHING in it stated by the article?")
    print("  y = yes, faithful   n = no, unfaithful   s = skip   q = quit (progress is saved)\n")
    for k, item in enumerate(queue, 1):
        article = articles[item["pageid"]]
        print("=" * 80)
        print(f"[{k}/{len(queue)}] {article['title']}  ({article['url']})\n")
        print(f"SENTENCE: {item['sentence']}\n")
        for passage in relevant_passages(item["sentence"], article["text"]):
            print(f"  > {passage[:700]}\n")
        answer = ""
        while answer not in ("y", "n", "s", "q"):
            answer = input("Faithful? [y/n/s/q] ").strip().lower()
        if answer == "q":
            break
        if answer == "s":
            continue
        append_jsonl(config.HUMAN_LABELS, {**item, "human_faithful": answer == "y"})


def cmd_report():
    print(write_report())


COMMANDS = {"models": cmd_models, "sample": cmd_sample, "summarize": cmd_summarize, "judge": cmd_judge,
            "perturb": cmd_perturb, "recheck": cmd_recheck, "review": cmd_review, "report": cmd_report}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]]()
