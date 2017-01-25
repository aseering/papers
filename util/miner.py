import bs4
import datetime
import os
import psycopg2cffi as psycopg2
import sys

def load_all(start_path):
        occasional_commit = 0

        conn = psycopg2.connect("")
        cur = conn.cursor()

        cur.execute("PREPARE insert_article AS INSERT INTO articles (f_path, f_path_raw, site, mtime, fulltext, raw_document) VALUES ($1, $2, $3, $4, $5, $6)")

        occasonal_commit = 0
        
        for root, dirs, files in os.walk(("./" + start_path) if start_path else "."):        
                if "/" not in root:
                        continue  # Root dir doesn't belong to any one paper

                files_to_insert = []
                
                for f in files:
                        f_path = os.path.join(root, f)
                        f_path_utf8 = bs4.UnicodeDammit.detwingle(f_path).decode("utf8", errors="replace")
                        site = root.split("/")[1]
                        with open(f_path) as fd:
                                first_chunk = fd.read(4096)
                                if '\0' in first_chunk:
                                        continue  # is binary

                                print "***", f_path
                                
                                f_data = first_chunk + fd.read()
                                cleaned_f_data = bs4.UnicodeDammit.detwingle(f_data).decode("utf8", errors="replace")
                                
                                file_stat = os.fstat(fd.fileno())
                                mtime = file_stat.st_mtime
                                mtime = datetime.datetime.utcfromtimestamp(mtime)
                                cur.execute("EXECUTE insert_article(%s, %s, %s, %s, %s, %s)",
                                            (f_path_utf8, psycopg2.Binary(f_path), site, mtime, cleaned_f_data, psycopg2.Binary(f_data)))


                #cur.executemany("INSERT INTO articles (f_path, f_path_raw, site, mtime, fulltext, raw_document) VALUES (%s, %s, %s, %s, %s, %s)",
                #                files_to_insert)

                conn.commit()


if len(sys.argv) > 1:
        start_path = sys.argv[1]
else:
        start_path = None

load_all(start_path)

