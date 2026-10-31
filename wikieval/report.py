"""Turn the pipeline's records into results/report.md and results/metrics.json."""

import json
import math
from collections import defaultdict

from . import config
from .judge import is_flagged
from .store import read_jsonl


def wilson(successes, n, z=1.96):
    """95% Wilson score interval for a proportion, as percentages. Honest at small n, unlike +/- 1.96 SE."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (100 * (centre - half), 100 * (centre + half))


def pct(successes, n):
    if n == 0:
        return "n/a"
    low, high = wilson(successes, n)
    return f"{100 * successes / n:.1f}% ({low:.0f}–{high:.0f})"


def summarizer_table(judgements):
    rows = defaultdict(lambda: defaultdict(int))
    for j in judgements:
        r = rows[j["model"]]
        r["summaries"] += 1
        for v in j["verdicts"]:
            r["sentences"] += 1
            r["flagged"] += is_flagged(v)
            r["contradicted"] += v["verdict"] == "contradicted"
            r["not_found"] += v["verdict"] == "not_found"
            r["unquotable"] += v["verdict"] == "supported" and not v["quote_found"]
            r["missing"] += v["verdict"] == "missing"
    return rows


def judge_test_table(perturbed, judgements):
    """Per kind of planted error: how often the judge flagged the changed sentence."""
    original = {(j["pageid"], j["model"]): j["verdicts"] for j in judgements}
    rows = defaultdict(lambda: defaultdict(int))
    for p in perturbed:
        r = rows[p["kind"]]
        r["n"] += 1
        r["caught"] += is_flagged(p["verdicts"][p["index"]])
        # Untouched sentences should get the same flag as in the original judgement
        before = original.get((p["pageid"], p["model"]))
        if before and len(before) == len(p["verdicts"]):
            for i, (a, b) in enumerate(zip(before, p["verdicts"])):
                if i != p["index"]:
                    r["untouched"] += 1
                    r["stable"] += is_flagged(a) == is_flagged(b)
    return rows


def human_table(labels):
    """Judge vs human on the blind review sample."""
    flagged = [l for l in labels if l["source"] == "summary" and l["judge_flagged"]]
    passed = [l for l in labels if l["source"] == "summary" and not l["judge_flagged"]]
    swaps = [l for l in labels if l["source"] == "entity_swap_missed"]
    return {
        # Of the sentences the judge flagged, how many did the human also find unfaithful
        "flag_precision": (sum(not l["human_faithful"] for l in flagged), len(flagged)),
        # Of the sentences the judge passed, how many did the human find unfaithful
        "miss_rate": (sum(not l["human_faithful"] for l in passed), len(passed)),
        # Planted swaps the judge missed that the human says are, by chance, still true
        "swaps_still_true": (sum(l["human_faithful"] for l in swaps), len(swaps)),
    }


def write_report():
    all_judgements = [j for j in read_jsonl(config.JUDGEMENTS) if j["judge"] == config.JUDGE]
    judgements = [j for j in all_judgements if not j.get("blocked")]
    summaries = read_jsonl(config.SUMMARIES)
    perturbed = [p for p in read_jsonl(config.PERTURBED) if p["judge"] == config.JUDGE]
    labels = read_jsonl(config.HUMAN_LABELS)
    articles = read_jsonl(config.ARTICLES)

    lines = [f"# Results", "",
             f"{len(articles)} Wikipedia articles · judge: `{config.JUDGE}` · 95% Wilson intervals in brackets", ""]

    lines += ["## How faithful are the summaries?", "",
              "| Summarizer | Summaries | Sentences | Flagged | Contradicted | Not in article | Supported, but quote not found |",
              "|---|---|---|---|---|---|---|"]
    s_rows = summarizer_table(judgements)
    for model, r in s_rows.items():
        n = r["sentences"]
        lines.append(f"| `{model}` | {r['summaries']} | {n} | {pct(r['flagged'], n)} | {pct(r['contradicted'], n)} "
                     f"| {pct(r['not_found'], n)} | {pct(r['unquotable'], n)} |")

    lines += ["", "## Does the judge catch planted errors?", "",
              "| Planted error | Cases | Caught | Untouched sentences judged the same as before |",
              "|---|---|---|---|"]
    t_rows = judge_test_table(perturbed, judgements)
    for kind, r in t_rows.items():
        lines.append(f"| {kind} | {r['n']} | {pct(r['caught'], r['n'])} | {pct(r['stable'], r['untouched'])} |")

    blocked = [f"{s['title']} (`{s['model']}`, summarizing)" for s in summaries if s.get("blocked")]
    blocked += [f"{j['title']} (`{j['model']}`, judging)" for j in all_judgements if j.get("blocked")]
    lines += ["", "## Refused by the safety filter", "",
              f"{len(blocked)} requests were refused and are left out of the tables above"
              + (": " + "; ".join(blocked) + "." if blocked else ".")]

    h = human_table(labels)
    lines += ["", "## Does the judge agree with a human?", ""]
    if labels:
        lines += [
            "| Check | Result |", "|---|---|",
            f"| Judge's flags the human agrees with (precision) | {pct(*h['flag_precision'])} of {h['flag_precision'][1]} |",
            f"| Sentences the judge passed that the human found unfaithful (misses) | {pct(*h['miss_rate'])} of {h['miss_rate'][1]} |",
            f"| Missed entity swaps that are, by chance, still true | {h['swaps_still_true'][0]} of {h['swaps_still_true'][1]} |",
        ]
    else:
        lines.append("Not reviewed yet: run `python -m wikieval review`.")

    report = "\n".join(lines) + "\n"
    config.RESULTS.mkdir(exist_ok=True)
    (config.RESULTS / "report.md").write_text(report, encoding="utf-8")
    (config.RESULTS / "metrics.json").write_text(json.dumps({
        "judge": config.JUDGE,
        "summarizers": s_rows, "planted_errors": t_rows, "human": h, "blocked": blocked,
    }, indent=2), encoding="utf-8")
    return report
