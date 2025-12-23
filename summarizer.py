from openai import OpenAI
from config import SUMMARY_WORDS

client = OpenAI()

def summarize(text):
    prompt = f"""
    Summarize the following Wikipedia article in {SUMMARY_WORDS} words.
    Keep the summary neutral, factual, and concise.

    {text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        timeout=20
    )

    return response.choices[0].message.content.strip()