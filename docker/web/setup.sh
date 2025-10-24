#!/bin/sh
# Run during container start.

tls=/srv/tls

openssl ecparam -name prime256v1 -genkey -noout -out $tls.key
openssl req -new -key $tls.key -out $tls.csr -subj "/C=PL/O=Politechnika Wroclawska/CN=TLS Cert"
openssl x509 -req -in $tls.csr -out $tls.pem -key $tls.key

cd /srv && nginx
cd /srv && python3 -m web &

tail -f /dev/null
