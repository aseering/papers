#!/bin/bash
while test ! -e stop && env DSN="host=10.10.0.1 dbname=adam user=adam" pypy get_synopsis.py ; do date; done
