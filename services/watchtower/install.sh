#!/bin/sh
#
# Installs Watchtower.

. ./watchtower.conf
. ../../libs/docker.sh

docker_container_name_is_available "${WATCHTOWER_CONTAINER_NAME}" &&
docker run -d \
  --name "${WATCHTOWER_CONTAINER_NAME}" --log-driver local --restart always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower --label-enable --tlsverify --rolling-restart --cleanup \
  --stop-timeout "${WATCHTOWER_TIMEOUT}s" --interval "${WATCHTOWER_POLL_INTERVAL}"
