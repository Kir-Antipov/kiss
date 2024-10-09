#!/bin/sh
#
# Restores Outline Server.

. ./outline-server.conf

: ${SHADOWBOX_API_URL:="$(sed -n 's|^apiUrl:https://[^:]*|https://localhost|p' "${SHADOWBOX_ACCESS_CONFIG}")"}
: ${SHADOWBOX_CONFIG:="$(tar -xOzf "${1}" shadowbox.json 2> /dev/null)"}
: ${SHADOWBOX_CONFIG:?"no backup to restore from was provided"}

req() {
  if [ -n "${3}" ]; then
    curl -fskSX "${2}" "${SHADOWBOX_API_URL}${1}" -H "Content-Type: application/json" -d "${3}"
  else
    curl -fskSX "${2:-"GET"}" "${SHADOWBOX_API_URL}${1}"
  fi
}

del_all() {
  req "${1}" \
    | jq -r --arg URL "${SHADOWBOX_API_URL}${1}" 'map("\($URL)/\(.[]?.id)") | @sh' \
    | xargs -r curl -fskSX DELETE
}

put_all() {
  echo "${2}" \
    | jq -r --arg URL "${SHADOWBOX_API_URL}${1}" 'map(.[]? | [
        "\({ name, port, limit } | del(.. | nulls))", "\($URL)/\(.id)"
      ] | @sh) | .[]' \
    | xargs -rL 1 curl -fskSX PUT -H "Content-Type: application/json" -d
}

req "/name" PUT "${SHADOWBOX_CONFIG}" &&
req "/name" PUT "${SHADOWBOX_CONFIG}" &&
req "/metrics/enabled" PUT "${SHADOWBOX_CONFIG}" &&
req "/server/port-for-new-access-keys" PUT "${SHADOWBOX_CONFIG}" &&
req "/server/access-key-data-limit" "$(echo "${SHADOWBOX_CONFIG}" | jq -r '["DELETE"][(.limit.bytes? // -1) + 1] // "PUT"')" "${SHADOWBOX_CONFIG}" &&
del_all "/access-keys" &&
put_all "/access-keys" "${SHADOWBOX_CONFIG}" > /dev/null
