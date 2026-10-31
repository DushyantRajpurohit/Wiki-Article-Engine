from . import config, llm

SYSTEM = "You summarise Wikipedia articles for a general reader."

PROMPT = """Summarise the Wikipedia article below in about {words} words of plain prose.
Keep it neutral and factual. Use only information stated in the article.

Title: {title}

{text}"""


def summarize(article, model):
    prompt = PROMPT.format(words=config.SUMMARY_WORDS, title=article["title"], text=article["text"])
    return llm.generate(model, prompt, system=SYSTEM).strip()
