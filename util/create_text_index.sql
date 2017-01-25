update articles set fulltext_tsvector = to_tsvector('english', fulltext_no_html);
create index articles_fulltext_idx on articles using gin (fulltext_tsvector);
