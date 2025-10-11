FROM alpine

RUN apk add python3 py3-psycopg2 py3-flask postgresql17
RUN mkdir /run/postgresql
RUN chown postgres:postgres /run/postgresql/
COPY docker/setup.sh /
RUN chmod +x /setup.sh
RUN mkdir /srv/web
COPY web/ /srv/web

USER postgres
RUN mkdir -p /var/lib/postgresql/data
RUN chmod 700 /var/lib/postgresql/data
RUN initdb -D /var/lib/postgresql/data

USER root
ENTRYPOINT ["/setup.sh"]
