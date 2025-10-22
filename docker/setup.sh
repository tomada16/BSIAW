#!/bin/sh
# Run during container start.

# Start PostgreSQL
su postgres -c 'pg_ctl start -D /var/lib/postgresql/data'

# Clean & create database from dump (idempotent if your SQL handles it)
su postgres -c 'psql -f /srv/database.sql'

cd /srv && python3 -m web &

tail -f /dev/null
