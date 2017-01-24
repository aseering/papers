try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    import psycopg2cffi as psycopg2
    from psycopg2cffi.extras import DictCursor

from flask import Flask, request, render_template
app = Flask(__name__)

RESULTS_PER_PAGE = 10

# If we get more than RESULTS_PER_PAGE results,
# scan up to this times as many more results forwards before giving up.
# Then rank and return the results.
RESULTS_OVERSCAN = 10

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

def do_query(qry, offset):
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("""
        SELECT url,
               title,
               fulltext,
               ts_headline('english', fulltext, plainto_tsquery(%s)) AS excerpt,
               ts_rank_cd(fulltext_tsvector, plainto_tsquery(%s)) AS rank
        FROM (
              SELECT url,
                     title,
                     fulltext,
                     fulltext_tsvector
              FROM articles
              WHERE fulltext_tsvector @@ plainto_tsquery('english', %s)
              LIMIT %s) a
        ORDER BY rank DESC LIMIT %s OFFSET %s;
        """, (qry, qry, qry, RESULTS_PER_PAGE*RESULTS_OVERSCAN, RESULTS_PER_PAGE, offset))
    return list(cur.fetchall())

@app.route('/', methods=["GET", "POST"])
def search():
    results = []
    if request.args and "search" in request.args:
        page = int(request.args.get("page", "0"))
        results = do_query(request.args["search"], page * RESULTS_PER_PAGE)

    print results
    
    return render_template("search_template.html",
                           results = results,
                           search = request.args.get("search", ""))
