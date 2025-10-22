#!/bin/sh
# Run during container start.

# Start & setup postgres.
su postgres -c 'pg_ctl start -D /var/lib/postgresql/data'
su postgres -c 'psql -f /srv/database.sql' > /dev/null

tail -f /dev/null
