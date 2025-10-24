FROM alpine

# System deps (Python + Postgres + build tools jeśli będą potrzebne)
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-flask \
    py3-greenlet \
    nginx \
    openssl

# Virtualenv for Python packages we need via pip
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Python deps for WebSocket (Socket.IO over Eventlet)
# We install via pip to get recent versions.
RUN pip3 install --no-cache-dir \
    flask-socketio \
    python-socketio \
    psycopg2-binary

COPY docker/web/setup.sh /
COPY docker/web/nginx.conf /etc/nginx

RUN chmod +x /setup.sh
RUN mkdir -p /srv/web
COPY web/ /srv/web

USER root
ENTRYPOINT ["/setup.sh"]
