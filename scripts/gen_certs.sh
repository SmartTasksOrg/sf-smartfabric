#!/usr/bin/env bash
# Generate a self-contained demo PKI for an mTLS fabric:
#   - a fabric CA
#   - a server cert (the node presents this)
#   - one or more client certs (peers present these; the node requires one)
#
# This is a DEMO CA for local mTLS testing. In production, issue certs from your
# own PKI / SPIFFE / cloud CA — the protocol only cares that both ends present a
# cert chaining to a CA the fabric trusts.
#
#   scripts/gen_certs.sh [out_dir] [client_name...]
#
set -euo pipefail
OUT="${1:-certs}"; shift || true
CLIENTS=("$@"); [ ${#CLIENTS[@]} -eq 0 ] && CLIENTS=("client-a")
mkdir -p "$OUT"; cd "$OUT"

echo "== fabric CA =="
openssl genrsa -out ca.key 4096 2>/dev/null
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 \
  -subj "/O=SmartFabric/CN=SmartFabric Demo CA" -out ca.crt 2>/dev/null

echo "== server (node) cert =="
openssl genrsa -out server.key 2048 2>/dev/null
openssl req -new -key server.key -subj "/O=SmartFabric/CN=smartfabric-node" -out server.csr 2>/dev/null
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -days 825 -sha256 -out server.crt 2>/dev/null
rm -f server.csr

for name in "${CLIENTS[@]}"; do
  echo "== client cert: $name =="
  openssl genrsa -out "$name.key" 2048 2>/dev/null
  openssl req -new -key "$name.key" -subj "/O=SmartFabric/CN=$name" -out "$name.csr" 2>/dev/null
  openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -days 825 -sha256 -out "$name.crt" 2>/dev/null
  rm -f "$name.csr"
done

echo ""
echo "wrote to $(pwd):"
ls -1 *.crt *.key
echo ""
echo "start an mTLS node:"
echo "  sf-smartfabric serve --tls-cert $OUT/server.crt --tls-key $OUT/server.key --tls-ca $OUT/ca.crt"
