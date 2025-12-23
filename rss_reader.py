import feedparser

def fetch_article_urls(feed_url, limit=5):
    feed = feedparser.parse(feed_url)
    urls = []

    for entry in feed.entries[:limit]:
        urls.append(entry.link)

    return urls