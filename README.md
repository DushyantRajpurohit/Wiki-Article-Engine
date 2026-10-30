# Wikipedia Summaries, Measured

How often does an LLM summary say something its source doesn't? And can an LLM judge be trusted to tell?

This project summarises a fixed sample of real Wikipedia articles with Gemini, checks every summary sentence against its article, and then tests the checker itself: against errors planted on purpose, and against my own blind labels.

## Results

**Not run yet.** The tables will come from `results/report.md` once the pipeline has run.

## Method

**1. A fixed sample.** 30 random English Wikipedia articles of 1,500–8,000 words, drawn once through the MediaWiki API and saved with their revision ids in `data/articles.jsonl`. "References", "External links" and similar sections are cut off, so a book title in a citation can't be mistaken for a fact in the article.

**2. Summaries.** Every article is summarised in about 120 words by each model in `config.SUMMARIZERS`, at temperature 0, with an instruction to use only the article.

**3. A judge that has to show its evidence.** A judge model sees the article and the numbered summary sentences. For each sentence it returns `supported`, `contradicted` or `not_found`, plus a quote from the article. **The quote is then checked against the article in code.** A sentence counts as unfaithful if the judge says so, *or* if the judge says "supported" but its quote isn't actually in the article. LLM judges do invent evidence, and this catches it.

**4. Testing the judge on planted errors.** One sentence per summary is changed on purpose, three ways:

| Kind | Example | Built so that |
|---|---|---|
| negation | was built → was **not** built | blatant; a judge should never miss it |
| number | in 1952 → in **1957** | the new value appears nowhere in the article |
| entity | the Royal Navy → the **British Army** | the new name comes from the same article, which makes it hard |

The true answer is known for every planted error, so the catch rate is measured, not estimated. The test also checks that the judge's verdicts on the *untouched* sentences stay the same when one sentence changes.

**5. Testing the judge against a human.** `python -m wikieval review` shows me a shuffled mix of sentences the judge flagged and sentences it passed. I don't see the judge's verdict while labelling, so my labels are blind. That gives the judge's precision (how many flags are real) and its miss rate (how much it lets through).

All rates come with 95% Wilson intervals, because at this sample size the uncertainty matters.

## Run it

Needs Python 3.10+ and a free Gemini API key from [aistudio.google.com](https://aistudio.google.com), set as `GEMINI_API_KEY`.

```bash
pip install -r requirements.txt
python -m wikieval models       # check the model names in wikieval/config.py are available to you
python -m wikieval sample       # skip this to reuse the committed sample
python -m wikieval summarize
python -m wikieval judge
python -m wikieval perturb
python -m wikieval review       # interactive, about 20-40 minutes
python -m wikieval report
pytest
```

Every call is cached in `data/llm_cache.sqlite` and every stage skips finished work, so the free tier's daily limits only pause a run; rerunning picks up where it stopped.

## Layout

| File | Role |
|---|---|
| `wikieval/wikipedia.py` | Random sampling, full-text fetch, reference-section cleanup |
| `wikieval/llm.py` | Gemini client: cache, rate limit, retries, structured output |
| `wikieval/summarize.py` | The summary prompt |
| `wikieval/judge.py` | Sentence-level judge and the quote check |
| `wikieval/text.py` | Sentence splitting and quote matching |
| `wikieval/perturb.py` | Planted errors |
| `wikieval/report.py` | Tables, Wilson intervals |
| `wikieval/__main__.py` | The pipeline stages and the review tool |

## Data licence

Article text in `data/` is from Wikipedia, licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Each record links to its source article.

## History

This repo started as a small script that summarised Wikipedia's recent-changes feed. That feed links to edit diffs rather than articles, so it summarised the wrong thing. It was rebuilt as this evaluation.
