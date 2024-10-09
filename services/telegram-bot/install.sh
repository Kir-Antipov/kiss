#!/bin/sh
#
# Installs Telegram Bot.

. ./telegram-bot.conf
. ../outline-server/outline-server.conf
. ../../libs/docker.sh

docker_container_name_is_available "${TB_CONTAINER_NAME}" &&
mkdir -p "${TB_DIR}" && chmod ug+rwx,g+s,o-rwx "${TB_DIR}" &&
docker buildx build --network=host --no-cache -t telebot:latest . &&
docker run -d \
  --name "${TB_CONTAINER_NAME}" --log-driver local --restart always \
  --label "com.centurylinklabs.watchtower.enable=true" \
  -e TB_HOSTNAME="${DOMAIN_NAME}" \
  -p "${TB_API_PORT}:80" \
  -p "${TB_WEBHOOK_PORT}:8080" \
  -v "${TB_DIR}/:/data/" \
  -v "$(dirname "${SHADOWBOX_ACCESS_CONFIG}")/:$(dirname "${SHADOWBOX_ACCESS_CONFIG}")/" \
  telebot:latest \
    --api-url "tunnel.*" --webhook-url "bot.*" \
    -a "${SHADOWBOX_ACCESS_CONFIG}" --outline-ignore-localhost
