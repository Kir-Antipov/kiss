#!/bin/sh
#
# Uninstalls Telegram Bot.

. ./telegram-bot.conf
. ../../libs/docker.sh

docker_container_uninstall "${TB_CONTAINER_NAME}"
rm -rf -- "${TB_DIR}"
