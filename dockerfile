FROM alpine

# System deps (Python + Postgres + build tools jeśli będą potrzebne)
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-flask \
    postgresql17 \
    postgresql17-client \
    py3-greenlet \
    gcc \
    musl-dev \
    python3-dev

# Virtualenv for Python packages we need via pip
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Python deps for WebSocket (Socket.IO over Eventlet)
# We install via pip to get recent versions.
RUN pip3 install --no-cache-dir \
    flask-socketio \
    python-socketio \
    eventlet \
    psycopg2-binary

# Postgres runtime dirs/permissions
RUN mkdir /run/postgresql && chown postgres:postgres /run/postgresql/

# App & DB artifacts
COPY docker/setup.sh /
COPY docker/database.sql /srv/
RUN chmod +x /setup.sh
RUN mkdir -p /srv/web
COPY web/ /srv/web

# Initialize PG cluster
USER postgres
RUN mkdir -p /var/lib/postgresql/data && \
    chmod 700 /var/lib/postgresql/data && \
    initdb -D /var/lib/postgresql/data

USER root
ENTRYPOINT ["/setup.sh"]
