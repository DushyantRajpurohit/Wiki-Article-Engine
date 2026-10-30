from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"

ARTICLES = DATA / "articles.jsonl"
SUMMARIES = DATA / "summaries.jsonl"
JUDGEMENTS = DATA / "judgements.jsonl"
PERTURBED = DATA / "perturbed.jsonl"
HUMAN_LABELS = DATA / "human_labels.jsonl"
# Every LLM response, keyed by its exact request, so reruns cost nothing
LLM_CACHE = DATA / "llm_cache.sqlite"

# Models compared as summarizers, and the one that judges them all.
# Check what your key can use with: python -m wikieval models
# The judge is a different model from either summarizer, so no model grades its own work.
# Free-tier limits decide this: gemini-3.5-flash allows 20 requests a day, too few to judge with.
SUMMARIZERS = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
JUDGE = "gemini-3.1-flash-lite"

# Gemini free tier allows roughly 10-15 requests a minute; stay under it
REQUESTS_PER_MINUTE = 8

SUMMARY_WORDS = 120

# Article sample: long enough to need summarizing, short enough to stay cheap
N_ARTICLES = 30
MIN_WORDS = 1500
MAX_WORDS = 8000

# Seeds which sentence gets which planted error, so the perturbed set is reproducible
SEED = 7

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "wiki-summary-eval/0.1 (https://github.com/DushyantRajpurohit/Wiki-Article-Engine)"
