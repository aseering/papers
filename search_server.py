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

# How many results to display per page, when responding to a search?
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
    """
    Create a prepared statement for the SQL query that we're going to
    run for every search executed against this site.

    This method MUST be called before we handle ANY search requests!
    """
    cur = conn.cursor()

    # Two bits of magic SQL cleverness in this query:
    #
    # - Self-JOIN on 'article':
    #   PostgreSQL's TOAST storage for large fields means that we don't
    #   need to read the field when we scan the table initially.
    #   But PostgreSQL doesn't support late materialization, so it will
    #   go ahead and read the field for all rows that it scans (at the
    #   cost of a disk seek per row) if we ask for the field at all,
    #   even though we're going to throw most of those rows away.  The
    #   JOIN makes that 2 seeks per row, but only for the small number
    #   of rows that we're actually going to display.
    #
    # - Inner LIMIT on the number of matched docs
    #   If we wanted to display the best search results, we would fetch
    #   all matching documents, rank them, sort them, and pick the top K
    #   best ones.  (PostgreSQL is hopefully clever enough to turn a
    #   "sort + limit K" into a priority queue of size K, but that's an
    #   implementation detail.)  But say someone searches for the word
    #   "the", or something else very common.  (And pretend that "the"
    #   isn't a stop word, just a normal-but-exceedingly-common word.)
    #   We'll get a zillion results, and they'll all be low-quality.
    #   So, rather than spending all of the time to read and rank them,
    #   the inner loop forces us to give up ranking before we waste
    #   too much time doing so.  We then take our initial results and
    #   proceed to sort, rank, dedupe, etc them from there.
    #
    # Also -- we don't really need to prepare this query; it takes
    # much longer to run than it does to plan.
    # But I think the code structure is a little cleaner if we
    # do prepare it.
    
    cur.execute("""\
        PREPARE article_search AS
        SELECT grouped_matches.id AS id,
               articles.site AS site,
               REPLACE(articles.url, 'index.html', '') AS url,
               articles.title AS title,
               ts_headline('english', articles.fulltext_no_html, plainto_tsquery($1), 'MinWords=30,MaxWords=50') AS excerpt,
               grouped_matches.count AS count
        FROM (
            SELECT FIRST(id) AS id,
                   FIRST(rank) AS rank,
                   COUNT(*) AS count
            FROM (
                SELECT id,
                       site,
                       title,
                       ts_rank_cd(fulltext_tsvector, plainto_tsquery($1)) AS rank
                FROM articles
                WHERE fulltext_tsvector @@ plainto_tsquery($1)
                LIMIT %s
            ) AS ranked_ordered_matches
            GROUP BY site, title
            ORDER BY rank DESC LIMIT %s OFFSET $2
        ) AS grouped_matches
        INNER JOIN articles ON grouped_matches.id = articles.id
        ORDER BY grouped_matches.rank DESC, grouped_matches.id DESC;
        """, (RESULTS_OVERSCAN, RESULTS_PER_PAGE))

# Pre-plan giant query at application start-up
prepare_query()    


# TODO:  There is allegedly a built-in Jinja2 filter 'default'
# that does exactly this.  But I couldn't get it to work?...
@app.template_filter('default_value')
def default_value_filter(s, default):
    """
    Jinja2 template filter:
    Return the filtered object unmodified,
    or 'default' if the filtered object is
    undefined/None or otherwise falsey.
    """
    if not s:
        return default
    return s
    

@app.route('/css/<path:path>')
def send_css(path):
    """
    Flask route to serve flat CSS files from the 'css/' directory
    """
    return send_from_directory('css', path)


def do_query(qry, offset):
    """
    Execute the specified query against our document index.
    Return a representation of all matching documents.

    :param str qry:     A space-separated list of words to search for
    :param int offset:  For pagination, how many records in the resultset to skip over.
                        Should be a multiple of RESULTS_PER_PAGE.

    :return: A list of records that match the specified search.
             Records contain something like the following fields:
             - id (int)    -- opaque unique internal page identifier
             - site (str)  -- hostname that page came from
             - url (str)   -- full URL to original document
             - excerpt (str; safe HTML) -- context from the article; query terms in bold
             - count (int) -- if > 1, then `count` other matching articles had the same title and site
    :rtype: list[dict]
    """
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("EXECUTE article_search(%s, %s);",
                (qry, offset))

    # aseering -- cast the resultset to a list because
    # I was seeing a weird issue where it didn't evaluate
    # in Jinja2 as either being falsey or of having length 0
    # when it was empty.  Switching to a list fixed this.
    return list(cur.fetchall())


@app.route('/', methods=["GET"])
def search():
    """
    Perform a search.  Or, just display the prompt to perform a search.
    Takes some URL query parameters:

    :param str search: Space-separated list of terms to search for.  If omitted, no search is performed.
    :param int page: Page of results to display.  Each page displays `RESULTS_PER_PAGE` results.
    :return: Search page, or Search Results page, as an HTTP response.
    """
    results = []
    page = 1

    if request.args and "search" in request.args:
        # Make 'page' 1-indexed, for human readability.
        # But the actual offset that SQL wants is 0-indexed.  So, translate as needed.
        page = int(request.args.get("page", "1"))
        results = do_query(request.args["search"], (page - 1) * RESULTS_PER_PAGE)
    
    return render_template("search_template.html",
                           results = results,
                           search = request.args.get("search", ""),
                           next_page = page + 1)
