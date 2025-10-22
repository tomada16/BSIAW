#!/bin/sh
# Run during container start.

# Start PostgreSQL
su postgres -c 'pg_ctl start -D /var/lib/postgresql/data'

# Clean & create database from dump (idempotent if your SQL handles it)
su postgres -c 'psql -f /srv/database.sql'

# Run the app with Socket.IO server in debug mode (code reload)
# IMPORTANT: run with the venv's Python so pip-installed deps are visible.
cd /srv/web
/opt/venv/bin/python /srv/web/main.py &

tail -f /dev/null
