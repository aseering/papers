#!/usr/bin/env python

try:
    import psycopg2
    from psycopg2.extras import DictCursor
    import psycopg2.extensions as psycopg2_extensions
except ImportError:
    import psycopg2cffi as psycopg2
    from psycopg2cffi.extras import DictCursor
    import psycopg2cffi.extensions as psycopg2_extensions
    
psycopg2_extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2_extensions.register_type(psycopg2.extensions.UNICODEARRAY)
    
from flask import Flask, request, render_template, send_from_directory
app = Flask(__name__)

RESULTS_PER_PAGE = 30

# If we get more than RESULTS_PER_PAGE results,
# scan up to this times as many more results forwards before giving up.
# Then rank and return the results.
RESULTS_OVERSCAN = 300

SEARCH_TEMPLATE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Newspaper Search</title>

    <link rel="stylesheet" href="https://unpkg.com/purecss@0.6.2/build/pure-min.css"></head>

<body>
    <div class="content pure-u-1">
        <h1>Newspaper Search</h1>

        <div class="searchbox pure-u-3-4">
        <form method="GET" action=".">
            <input name="search" value="{{ search }}" /><input type="submit" value="Go" />
        </form>
        </div>

        {% if not results %}
        {% if search %}
        <div class="error pure-u-1">
            <p>
                No results found.
            </p>
        </div>
        {% else %}
        <div class="info pure-u-1">
            <p>
                Please enter some search terms.
            </p>
        </div>
        {% endif %}
        {% else %}
        <div class="results pure-u-3-4">
        {% for item in results %}
            <div class="result">
                <div class="link">
                    <a href="{{ item.url }}"><{{ item.title }}</a>
                </div>
                <div class="excerpt">
                    <p>
                        {{ item.excerpt }}
                    </p>
                </div>
            </div>
        {% endfor %}
        </div>

        <div class="nextpage">
        <form method="GET" action=".">
            <input type="hidden" name="search" value="{{ search }}" /><input type="submit" value="Next" /> 
        </form>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

conn = psycopg2.connect(os.environ.get("WSGI_DBA", ""))

def prepare_query():
    cur = conn.cursor()
    cur.execute("""\
        PREPARE article_search AS

        SELECT articles1.id AS id,
               articles2.site AS site,
               REPLACE(articles2.url, 'index.html', '') AS url,
               articles2.title AS title,
               ts_headline('english', articles2.fulltext_no_html, articles1.query, 'MinWords=30,MaxWords=50') AS excerpt,
               articles1.count AS count,
               articles1.rank AS rank
        FROM (
            SELECT FIRST(id) AS id,
                   FIRST(rank) AS rank,
                   FIRST(query) AS query,
                   COUNT(*) AS count
            FROM (
                SELECT id,
                       query,
                       site,
                       title,
                       ts_rank_cd(fulltext_tsvector, query) AS rank
                FROM (
                      SELECT *
                      FROM (
                          SELECT id,
                                 site,
                                 title,
                                 fulltext_tsvector,
                                 plainto_tsquery($1) AS query
                          FROM articles ) a
                      WHERE fulltext_tsvector @@ query
                      LIMIT %s) b
                ORDER BY rank DESC
            ) c
            GROUP BY site, title
            ORDER BY rank DESC LIMIT %s OFFSET $2
        ) AS articles1,
        articles AS articles2
        WHERE articles1.id = articles2.id
        ORDER BY rank;
        """, (RESULTS_OVERSCAN, RESULTS_PER_PAGE))

# Pre-plan giant query at application start-up
prepare_query()    

@app.template_filter('default_value')
def default_value_filter(s, default):
    if not s:
        return default
    return s
    
@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

def do_query(qry, offset):
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("EXECUTE article_search(%s, %s);",
                (qry, offset))
                
    return list(cur.fetchall())

@app.route('/', methods=["GET"])
def search():
    results = []
    page = 1
    if request.args and "search" in request.args:
        # Make 'page' 1-indexed, for human readability.
        # But the actual offset that SQL wants 
        page = int(request.args.get("page", "1"))
        results = do_query(request.args["search"], (page - 1) * RESULTS_PER_PAGE)
    
    return render_template("search_template.html",
                           results = results,
                           search = request.args.get("search", ""),
                           next_page = page + 1)
