#!/bin/sh
#
# Restores Telegram Bot.

. ./telegram-bot.conf
. ../../libs/docker.sh
. ../../libs/restore.sh

docker_container_try_stop "${TB_CONTAINER_NAME}" &&
unbak "${1}" \
  "${TB_DIR}/config.json" \
  "${TB_DIR}/db.sqlite3" &&
docker_container_try_start "${TB_CONTAINER_NAME}"
