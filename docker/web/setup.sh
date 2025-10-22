#!/bin/sh
# Run during container start.

cd /srv && python3 -m web &

tail -f /dev/null
