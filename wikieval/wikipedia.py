"""
Sample random Wikipedia articles and fetch their plain text.

The sample is saved with each article's revision id, so the exact text every
summary was judged against stays on record even after the live article changes.
"""

import re
import time

import requests

from . import config

# Everything from the first of these headings onward is lists of links and sources,
# not article prose. Left in, the judge could "find" a claim in a book title.
END_SECTIONS = ("See also", "Notes", "References", "Citations", "Sources",
                "Bibliography", "Further reading", "External links", "Footnotes")
HEADING = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$", re.MULTILINE)


def api(**params):
    params.update(action="query", format="json", formatversion=2)
    response = requests.get(config.WIKI_API, params=params, timeout=30,
                            headers={"User-Agent": config.USER_AGENT})
    response.raise_for_status()
    return response.json()


def clean_text(extract):
    """Cut the trailing reference sections and drop headings left with no text under them."""
    for match in HEADING.finditer(extract):
        if match.group(2) in END_SECTIONS:
            extract = extract[: match.start()]
            break

    lines = [line.strip() for line in extract.splitlines() if line.strip()]
    # A heading followed directly by another heading (or by nothing) has no text; drop it
    kept = [line for i, line in enumerate(lines)
            if not (HEADING.match(line) and (i + 1 == len(lines) or HEADING.match(lines[i + 1])))]
    return "\n".join(kept).strip()


def fetch_article(title):
    """Full plain text of one article. The API returns full text for one page per request."""
    page = api(titles=title, prop="extracts|info", explaintext=1)["query"]["pages"][0]
    return {
        "title": page["title"],
        "pageid": page["pageid"],
        "revid": page["lastrevid"],
        "url": "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_"),
        "text": clean_text(page["extract"]),
    }


def sample_articles(n, min_words, max_words):
    """
    Draw random articles until n fall inside the word range.

    Most random articles are stubs, so candidates are pre-filtered on page size in
    bytes before their full text is fetched.
    """
    articles, seen = [], set()
    while len(articles) < n:
        batch = api(generator="random", grnnamespace=0, grnlimit=50, prop="info")["query"]["pages"]
        for page in batch:
            if page["length"] < 15_000 or page["pageid"] in seen or page["title"].startswith("List of"):
                continue
            seen.add(page["pageid"])
            article = fetch_article(page["title"])
            words = len(article["text"].split())
            if min_words <= words <= max_words:
                article["words"] = words
                articles.append(article)
                print(f"[{len(articles)}/{n}] {article['title']} ({words} words)")
                if len(articles) == n:
                    break
            time.sleep(0.5)  # be polite to the API
    return articles
