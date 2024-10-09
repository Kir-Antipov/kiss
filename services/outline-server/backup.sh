#!/bin/sh
#
# Backs up Outline Server.

. ./outline-server.conf
. ../../libs/backup.sh

: ${SHADOWBOX_CONFIG:="${SHADOWBOX_DIR}/shadowbox.json"}
: ${SHADOWBOX_API_URL:="$(sed -n 's|^apiUrl:https://[^:]*|https://localhost|p' "${SHADOWBOX_ACCESS_CONFIG}")"}

curl -fskS "${SHADOWBOX_API_URL}/server" "${SHADOWBOX_API_URL}/access-keys" \
  | jq -cs '.[0] + .[1]
    | { name, metricsEnabled, port: .portForNewAccessKeys, limit: .accessKeyDataLimit, accessKeys }
    | .accessKeys |= map({ id, name, port, limit: .dataLimit })' > "${SHADOWBOX_CONFIG}" &&

mkbak ${1:+"-T"} "${1:-"${SHADOWBOX_BACKUP_DIR}"}" -- "${SHADOWBOX_CONFIG}"
EXIT_CODE=$?

rm -f -- "${SHADOWBOX_CONFIG}"
exit $EXIT_CODE
