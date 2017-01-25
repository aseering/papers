analyze articles;

create unique index articles_id on articles (id);

update articles set url = regexp_replace(f_path, '\./\./(.*)', 'http://\1');

alter table articles
      alter column site set data type varchar(64),
      alter column f_path set not null,
      alter column f_path_raw set not null,
      alter column site set not null,
      alter column mtime set not null,
      alter column fulltext set not null,
      alter column raw_document set not null,
      alter column url set not null;

create index articles_fulltext on articles using gin(to_tsvector('english', fulltext));
--create index articles_title on articles using gin(to_tsvector('english', title));
--create index articles_synopsis on articles using gin(to_tsvector('english', synopsis));

vacuum full;
