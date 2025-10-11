#!/bin/sh
# Run during container start.

su postgres -c 'pg_ctl start -D /var/lib/postgresql/data'
cd /srv/web && flask -A main run -h 0.0.0.0 -p 80 &

tail -f /dev/null
