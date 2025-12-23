import sqlite3
from datetime import datetime

conn = sqlite3.connect("articles.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    title TEXT,
    summary TEXT,
    created_at TEXT
)
""")

conn.commit()

def article_exists(url):
    cursor.execute("SELECT 1 FROM articles WHERE url=?", (url,))
    return cursor.fetchone() is not None

def save_article(url, title, summary):
    cursor.execute(
        "INSERT OR IGNORE INTO articles (url, title, summary, created_at) VALUES (?, ?, ?, ?)",
        (url, title, summary, datetime.utcnow().isoformat())
    )
    conn.commit()
