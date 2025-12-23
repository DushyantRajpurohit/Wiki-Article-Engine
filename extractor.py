import trafilatura

def extract_article(url):
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None, None

    result = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        with_metadata=True
    )

    if not result:
        return None, None

    return "Wikipedia Article", result