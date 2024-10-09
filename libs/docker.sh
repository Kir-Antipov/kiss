#################################################
# Checks if a Docker container with the specified
# name exists.
# Arguments:
#   $1. The name of the container to check.
# Returns:
#   0 if a container with the given name exists;
#   otherwise, a non-zero status.
#################################################
docker_container_exists() {
  command -v docker > /dev/null 2>& 1 &&
  docker ps -a --format '{{ .Names }}' | grep -Fxq "${1}"
}

#################################################
# Checks if a Docker container name is available.
# Arguments:
#   $1. The name of the container to check.
# Outputs:
#   Writes an error message to stderr
#   if the container name is already in use.
# Returns:
#   0 if the container name is available;
#   1 if the container name is already in use.
#################################################
docker_container_name_is_available() {
  if docker_container_exists "${1}"; then
    echo "${0}: container with the name '${1}' already exists" >& 2
    return 1
  fi
}

#################################################
# Uninstalls a Docker container by name.
# Arguments:
#   $1. The name of the container to uninstall.
# Returns:
#   0 if the container no longer exists;
#   otherwise, a non-zero status.
#################################################
docker_container_uninstall() {
  if ! docker_container_exists "${1}"; then
    return 0
  fi

  docker stop "${1}"
  docker rm -f "${1}"
}

#################################################
# Attempts to start a Docker container by name.
# Arguments:
#   $1. The name of the container to start.
# Returns:
#   0 if the container does not exist or
#   is successfully started;
#   otherwise, a non-zero status.
#################################################
docker_container_try_start() {
  if ! docker_container_exists "${1}"; then
    return 0
  fi

  docker start "${1}"
}

#################################################
# Attempts to stop a Docker container by name.
# Arguments:
#   $1. The name of the container to stop.
# Returns:
#   0 if the container does not exist or
#   is successfully stopped;
#   otherwise, a non-zero status.
#################################################
docker_container_try_stop() {
  if ! docker_container_exists "${1}"; then
    return 0
  fi

  docker stop "${1}"
}
