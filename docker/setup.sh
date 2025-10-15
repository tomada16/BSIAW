#!/bin/sh
# Run during container start.

su postgres -c 'pg_ctl start -D /var/lib/postgresql/data'
# clean & create database in dump
su postgres -c 'cat /srv/database.sql | psql'
# run flask in debug mode
cd /srv/web && flask -A main run -h 0.0.0.0 -p 80 --debug &

tail -f /dev/null
