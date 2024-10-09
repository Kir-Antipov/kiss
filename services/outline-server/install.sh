#!/bin/sh
#
# Installs Outline Server.

. ./outline-server.conf
. ../../libs/net.sh
. ../../libs/docker.sh
. ../../libs/random.sh

generate_certificate() {
  openssl req -x509 -nodes \
    -days 36500 -newkey rsa:4096 -subj "/CN=${1}" \
    -out "${2}" -keyout "${3}" > /dev/null
}

get_certificate_fingerprint() {
  openssl x509 -in "${1}" -noout -sha256 -fingerprint |
  sed -e "s/.*=//" -e "s/://g"
}

format_access_config() {
  echo "certSha256:${2}"
  echo "apiUrl:${1}"
}

format_server_config() {
  jq -n '$ARGS.positional
    | {
        name: .[0],
        hostname: .[1],
        portForNewAccessKeys: (try (.[2] | tonumber) catch "")
      }
    | del(.. | select(. == ""))' --args "${1}" "${2}" "${3}"
}

configure_container() {
  local container_name="${SHADOWBOX_CONTAINER_NAME}"
  local data_dir="${SHADOWBOX_DIR}"
  local state_dir="${data_dir}/persisted-state"
  local access_config="${SHADOWBOX_ACCESS_CONFIG}"
  local server_config="${state_dir}/shadowbox_server_config.json"
  local server_name="${SHADOWBOX_SERVER_NAME}"
  local public_hostname="${SHADOWBOX_HOSTNAME:-"$(get_ip)"}"
  local api_secret="$(rands "$(randi 16 32)")"
  local api_port="${SHADOWBOX_API_PORT:-"$(randi 49152 65535)"}"
  local keys_port="${SHADOWBOX_KEYS_PORT}"
  local public_api_url="https://${public_hostname}:${api_port}/${api_secret}"
  local local_api_url="https://localhost:${api_port}/${api_secret}"
  local metrics_url="${SHADOWBOX_METRICS_URL}"
  local certificate="${state_dir}/shadowbox-selfsigned.crt"
  local private_key="${state_dir}/shadowbox-selfsigned.key"
  local fingerprint=""

  [ -n "${public_hostname}" ] &&
  docker_container_name_is_available "${container_name}" &&

  mkdir -p "${data_dir}" && chmod u+s,ug+rwx,o-rwx "${data_dir}" &&
  mkdir -p "${state_dir}" && chmod ug+rwx,g+s,o-rwx "${state_dir}" &&

  generate_certificate "${public_hostname}" "${certificate}" "${private_key}" &&
  fingerprint="$(get_certificate_fingerprint "${certificate}")" &&

  format_access_config "${public_api_url}" "${fingerprint}" > "${access_config}" &&
  format_server_config "${server_name}" "${public_hostname}" "${keys_port}" > "${server_config}" &&

  docker run -d \
    --name "${container_name}" --restart always --log-driver local \
    --net host --label "com.centurylinklabs.watchtower.enable=true" \
    -v "${state_dir}:${state_dir}" \
    -e SB_STATE_DIR="${state_dir}" \
    -e SB_API_PORT="${api_port}" \
    -e SB_API_PREFIX="${api_secret}" \
    -e SB_CERTIFICATE_FILE="${certificate}" \
    -e SB_PRIVATE_KEY_FILE="${private_key}" \
    -e SB_METRICS_URL="${metrics_url}" \
    quay.io/outline/shadowbox:stable &&

  while ! curl -fsk "${local_api_url}/access-keys" > /dev/null; do sleep 1; done
}

main() {
  local current_umask="$(umask)"
  umask 0007

  configure_container
  local exit_code=$?

  umask "${current_umask}"
  return $exit_code
}

main "${@}"
