#!/bin/sh
#
# Uninstalls Watchtower.

. ./watchtower.conf
. ../../libs/docker.sh

docker_container_uninstall "${WATCHTOWER_CONTAINER_NAME}"
