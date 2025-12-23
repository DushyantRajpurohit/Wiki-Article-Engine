from config import WIKIPEDIA_RSS
from rss_reader import fetch_article_urls
from extractor import extract_article
from summarizer import summarize
from storage import article_exists, save_article

def run():
    urls = fetch_article_urls(WIKIPEDIA_RSS)

    for url in urls:
        if article_exists(url):
            continue

        title, text = extract_article(url)
        if not text:
            continue

        summary = summarize(text)
        save_article(url, title, summary)

        print(f"Saved summary for: {url}")

if __name__ == "__main__":
    run()