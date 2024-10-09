#!/bin/sh
#
# Uninstalls Outline Server.

. ./outline-server.conf
. ../../libs/docker.sh

docker_container_uninstall "${SHADOWBOX_CONTAINER_NAME}"
rm -rf -- "${SHADOWBOX_DIR}"
rm -f  -- "${SHADOWBOX_ACCESS_CONFIG}"
