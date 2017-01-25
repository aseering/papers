import os
from bs4 import BeautifulSoup
try:
    import psycopg2
except ImportError:
    import psycopg2cffi as psycopg2
    
conn = psycopg2.connect(os.environ.get("DSN", ""))
cur = conn.cursor()

def process_next_articles():
    cur.execute("BEGIN");
    cur.execute("LOCK TABLE sites");
    cur.execute("SELECT site FROM sites WHERE processed = false limit 1")
    site, = cur.fetchone()
    cur.execute("UPDATE sites SET processed = true WHERE site = %s", (site,))
    cur.execute("COMMIT")

    print "PROCESSING", site
    
    occasional_commit = 0
    cur.execute("SELECT id FROM articles WHERE title IS NULL AND synopsis IS NULL AND site = %s", (site,))
    ids = list(cur.fetchall())
    for (id_,) in ids:
        process(id_)

        occasional_commit += 1
        if occasional_commit >= 100:
            occasional_commit = 0
            conn.commit()

    conn.commit()

def process(id_):
    cur.execute("SELECT f_path, fulltext FROM articles WHERE id = %s", (id_,))
    url, article = cur.fetchone()

    print "***", url
    
    html = BeautifulSoup(article, "lxml")
    title = html.title.getText() if html.title is not None else ""
    synopsis = ""
    for p in html.find_all('p'):
        text = p.getText()
        if len(text) > 100:
            synopsis = text
            break

    cur.execute("UPDATE articles SET title = %s, synopsis = %s WHERE id = %s",
                (title, synopsis, id_))

process_next_articles()
