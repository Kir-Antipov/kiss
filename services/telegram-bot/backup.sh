#!/bin/sh
#
# Backs up Telegram Bot.

. ./telegram-bot.conf
. ../../libs/backup.sh

mkbak ${1:+"-T"} "${1:-"${TB_BACKUP_DIR}"}" -- \
  "${TB_DIR}/config.json" \
  "${TB_DIR}/db.sqlite3"
