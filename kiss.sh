#!/bin/sh
#
# Manage the deployment, backup, and recovery routines for the server software.

: ${ACME_EMAIL:=""}
: ${DOMAIN_NAME:=""}
: ${LOCALHOST_NAME:="localhost"}

: ${__PWD:="${PWD}"}
: ${__0:="${0}"}
__NAME="${__0##*/}"
__NAME="${__NAME%.*}"
__VERSION="1.0.0"

. ./libs/core.sh
. ./libs/net.sh
. ./libs/random.sh

#################################################
# Resolves the absolute path.
# Arguments:
#   $1. The path to resolve.
# Outputs:
#   Writes the resolved absolute path to stdout.
#################################################
resolve_path() {
  local current_directory="${PWD}"
  cd "${__PWD}"
  realpath -m "${1}" 2> /dev/null
  cd "${current_directory}"
}

#################################################
# Installs Docker if it is not already installed.
# Arguments:
#  None
# Returns:
#   0 if Docker is successfully installed;
#   otherwise, a non-zero status.
#################################################
install_docker() {
  command_exists docker && return
  require_package curl &&
  curl -fsS https://get.docker.com/ | sh &&
  systemctl enable --now docker.service
}

#################################################
# Installs the specified package(s) using the
# appropriate package manager for the system.
# Arguments:
#   ... One or more packages to install.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
install_packages() {
  if command_exists apt-get; then
    apt-get install -y "$@"
  elif command_exists dnf; then
    dnf install -y "$@"
  elif command_exists pacman; then
    pacman -S --noconfirm "$@"
  else
    return 1
  fi
}

#################################################
# Ensures that the provided package or one of its
# substitutions is installed.
# Arguments:
#   $1. The package to check.
#   ... The alternatives to check.
# Outputs:
#   Writes the error message, if any, to stderr.
# Returns:
#   0 if the provided package is installed;
#   otherwise, a non-zero status.
#################################################
require_package() {
  local package=""

  for package in "${@}"; do
    command_exists "${package}" && return
  done

  for package in "${@}"; do
    if [ "${package}" = "docker" ]; then
      install_docker && return
    else
      install_packages "${package}" && return
    fi
  done
}

#################################################
# Expands sourced files within the given shell
# script by replacing source commands
# (i.e., "source" or ".") with the content of
# the referenced files.
# Arguments:
#   $1. The path to the shell script to process.
# Outputs:
#   Writes the script content with all sourced
#   files included inline to stdout.
#################################################
unwrap_sh_sources() {
  local current_directory="${PWD}"
  cd "$(dirname "${1}")"
  awk '{
    if (NF >= 2 && ($1 == "." || $1 == "source")) {
      gsub(/["'"'"']/, "", $2)
      while ((status = (getline line < $2)) > 0) {
        print line
      }
      if (status < 0) {
        print "# Could not automatically include the source file:"
        print
      }
      close($2)
    } else {
      print
    }
  }' "${1##*/}"
  cd "${current_directory}"
}

#################################################
# Executes the provided command on the specified
# file and replaces its contents with the output.
# Arguments:
#   $1. The command to execute on the file.
#   $2. The file to process.
#   ... Additional arguments for the command.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
process_file() {
  local tmp_filename="${2}.tmp+$$"

  cp -p --attributes-only "${2}" "${tmp_filename}"
  "${@}" > "${tmp_filename}"
  mv -f "${tmp_filename}" "${2}"
}

#################################################
# Finds and processes files within a specified
# directory that match a given pattern by
# applying a specified command to each file.
# Arguments:
#   $1. The root directory to search.
#   $2. The name pattern to match files.
#   $3. The command to execute on each file.
#   ... Additional arguments for the command.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
process_files() {
  local root_path="${1:-"."}"
  local name_pattern="${2:-"*"}"
  local command_name="${3:-":"}"
  shift 3 || return

  find "${root_path}" -type f -name "${name_pattern}" |
  while IFS= read -r file; do
    process_file "${command_name}" "${file}" "${@}" || return
  done
}

#################################################
# Generates an nginx proxy server configuration
# for the given URI, supporting HTTP and HTTPS.
# Arguments:
#   $1. The server URI.
#   $2. The backend service URI to redirect
#       requests to.
# Outputs:
#   Writes the configuration block to stdout.
#################################################
create_proxy_conf() {
  local server_name="${1##*://}"
  server_name="${server_name%%/*}"

  case "${1}" in
    http://*)
      echo 'server {'
      echo '  listen 80;'
      echo '  listen [::]:80;'
      echo '  server_name '"${server_name}"';'
      ;;

    https://*)
      echo 'server {'
      echo '  listen 80;'
      echo '  listen [::]:80;'
      echo '  server_name '"${server_name}"';'
      echo '  return 301 https://$host$request_uri;'
      echo '}'
      echo
      echo 'server {'
      echo '  listen 443 ssl;'
      echo '  listen [::]:443 ssl;'
      echo '  server_name '"${server_name}"';'
      echo
      echo '  ssl_certificate /etc/letsencrypt/live/'"${server_name}"'/fullchain.pem;'
      echo '  ssl_certificate_key /etc/letsencrypt/live/'"${server_name}"'/privkey.pem;'
      ;;

    *)
      error "unsupported protocol: '${1%%${1##*://}}'"
      return
      ;;
  esac

  echo
  echo '  location / {'
  echo '    proxy_pass '"${2}"';'
  echo '    proxy_read_timeout 200;'
  echo '    proxy_redirect '"${2}"' '"${1}"';'
  echo '    proxy_set_header Host $host;'
  echo '    proxy_set_header Connection $http_connection;'
  echo '    proxy_set_header X-NginX-Proxy true;'
  echo '    proxy_set_header X-Scheme $scheme;'
  echo '    proxy_set_header X-Real-IP $remote_addr;'
  echo '    proxy_set_header X-Forwarded-Host $http_host;'
  echo '    proxy_set_header X-Forwarded-Proto $scheme;'
  echo '    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;'
  echo '  }'
  echo '}'
}

#################################################
# Configures an nginx proxy for the given URI.
# Arguments:
#   $1. The public URI to proxy from.
#   $2. The backend URI to proxy to.
# Returns:
#   0 if the proxy is configured successfully;
#   otherwise, a non-zero status.
#################################################
configure_proxy() {
  require_package nginx || return

  local from="$(expand_uri "${1}" "https://" "${DOMAIN_NAME}")"
  local to="$(expand_uri "${2}" "http://" "${LOCALHOST_NAME}")"
  local nginx_status="$(systemctl is-active nginx)"
  local nginx_available="/etc/nginx/sites-available"
  local nginx_enabled="/etc/nginx/sites-enabled"
  local proxy_name="${from##*://}"
  proxy_name="${proxy_name%%/*}"

  [ -n "${from}" ] || error "failed to configure proxy: source URI is missing" || return
  [ -n "${to}" ] || error "failed to configure proxy: destination URI is missing" || return

  [ "${nginx_status}" = "active" ] && systemctl stop nginx

  case "${from}" in
    https://*)
      require_package certbot &&
      certbot certonly -n \
        --standalone --preferred-challenges http -d "${proxy_name}" --agree-tos \
        ${ACME_EMAIL:+"-m"} "${ACME_EMAIL:-"--register-unsafely-without-email"}"
      ;;
  esac &&

  mkdir -p "${nginx_available}" && mkdir -p "${nginx_enabled}" &&
  create_proxy_conf "${from}" "${to}" > "${nginx_available}/${proxy_name}.conf" &&
  ln -fs "${nginx_available}/${proxy_name}.conf" "${nginx_enabled}/${proxy_name}.conf"
  local exit_code=$?

  [ "${nginx_status}" = "active" ] && systemctl start nginx
  return $exit_code
}

#################################################
# Removes an nginx proxy configuration for
# the specified domain and cleans up associated
# SSL certificates, if any.
# Arguments:
#   $1. The public URI of the proxy to remove.
# Returns:
#   0 if the proxy is removed successfully;
#   otherwise, a non-zero status.
#################################################
remove_proxy() {
  local from="$(expand_uri "${1}" "https://" "${DOMAIN_NAME}")"
  local nginx_status="$(systemctl is-active nginx)"
  local nginx_available="/etc/nginx/sites-available"
  local nginx_enabled="/etc/nginx/sites-enabled"
  local proxy_name="${from##*://}"
  proxy_name="${proxy_name%%/*}"

  [ -n "${from}" ] || error "failed to disable proxy: source URI is missing" || return
  [ "${nginx_status}" = "active" ] && systemctl stop nginx

  case "${from}" in
    https://*)
      command_exists certbot &&
      certbot delete -n --cert-name "${proxy_name}" 2> /dev/null
  esac
  rm -f "${nginx_enabled}/${proxy_name}.conf" "${nginx_available}/${proxy_name}.conf"

  [ "${nginx_status}" = "active" ] && systemctl start nginx
  return 0
}

#################################################
# Retrieves a list of enabled services via
# searching service.json files within the
# ./services directory.
# Arguments:
#  None
# Outputs:
#   Writes paths of enabled services to stdout.
#################################################
get_services() {
  find ./services -type f -path './services/*/service.json' -execdir \
    jq 'if .enabled? != false then empty else null | halt_error(1) end' {} \
    ';' -print
}

#################################################
# Executes a command for the specified service,
# handling pre, post, and main command scripts
# as defined in the service.json file.
# Arguments:
#   $1. The path to the service.json file.
#   $2. The command to execute.
#   ... Additional arguments for the command.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
exec_service() {
  local current_directory="${PWD}"
  local service_directory="$(dirname "${1}")"
  local service_filename="${1##*/}"
  local command="${2}"
  shift 2 || return

  cd "${service_directory}" &&

  eval "$(jq -r '.scripts["pre'"${command}"'"]? // ":"' "${service_filename}")" &&

  case "${command}" in
    build) eval "$(jq -r '"require_package \(.devDependencies | .[]? | @sh)"' "${service_filename}")" ;;
    install) eval "$(jq -r '"require_package \(.dependencies | .[]? | @sh)"' "${service_filename}")" ;;
  esac &&

  eval "$(jq -r '.scripts["'"${command}"'"]? // ":"' "${service_filename}")" &&

  if [ "${command}" = "uninstall" ] || [ "${command}" = "install" ]; then
    # Remove reverse proxies configured by the service.
    eval "$(jq -r '"remove_proxy \(.proxies | to_entries? | .[] | [.key, .value] | @sh)"' "${service_filename}")" &&

    # Remove cronjobs specified in the service file.
    crontab -l 2> /dev/null \
      | eval "$(jq -r '
        if .jobs | length > 0 then
          "grep -vF \(.jobs | to_entries | map("-e \("\(.value) \(.key)" | @sh)") | join(" "))"
        else
          "cat -"
        end' "${service_filename}")" \
      | crontab - > /dev/null 2>& 1 &&

    # Remove files installed by the service.
    jq -r '.files | .[]? | [.[]?][0] // .' "${service_filename}" | xargs -r rm -f
  fi &&

  if [ "${command}" = "install" ]; then
    # Install files provided by the service.
    jq -r '.files
      | to_entries?
      | map([.key, .value] | flatten)
      | map((if length > 2 then ["-m", .[2], .[0], .[1]] else . end) | @sh)
      | .[]' "${service_filename}" \
      | xargs -rL 1 install -vD &&

    # Add cronjobs specified in the service file.
    {
      crontab -l 2> /dev/null
      jq -r '.jobs | to_entries? | map("\(.value) \(.key)") | .[]' "${service_filename}"
    } | crontab - > /dev/null 2>& 1 &&

    # Configure reverse proxies requested by the service.
    eval "$(jq -r '"configure_proxy \(.proxies | to_entries? | .[] | [.key, .value] | @sh)"' "${service_filename}")"
  fi &&

  eval "$(jq -r '.scripts["post'"${command}"'"]? // ":"' "${service_filename}")"

  local exit_code=$?
  cd "${current_directory}"
  return $exit_code
}

#################################################
# Executes a command for all enabled services.
# Arguments:
#   $1. The command to execute.
#   ... Additional arguments for the command.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
exec_services() {
  get_services | while IFS= read -r service; do
    exec_service "${service}" "${@}" || return
  done
}

#################################################
# Restores all enabled services from
# the specified backup file.
# Arguments:
#   $1. The backup filename.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
restore() {
  local restore_filename=""
  local input_filename="${1}"
  local input_dirname="${input_filename}~${__NAME}+$$+$(rands)"
  shift || return

  mkdir -p "${input_dirname}" &&
  tar -xzf "${input_filename}" -C "${input_dirname}" &&
  get_services | while IFS= read -r service; do
    restore_filename="${input_dirname}/$(jq -j '.name' "${service}")"
    if [ -f "${restore_filename}" ]; then
      exec_service "${service}" restore "${restore_filename}" "${@}"
    fi
  done
  local exit_code=$?

  rm -rf -- "${input_dirname}"
  return $exit_code
}

#################################################
# Creates a backup of all enabled services.
# Arguments:
#   $1. The output filename for the backup.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
backup() {
  local current_directory="${PWD}"
  local output_filename="${1}"
  local output_dirname="${output_filename}~${__NAME}+$$+$(rands)"
  shift || return

  mkdir -p "${output_dirname}" &&

  get_services | while IFS= read -r service; do
    exec_service "${service}" backup "${output_dirname}/$(jq -j '.name' "${service}")" "${@}"
  done &&

  cd "${output_dirname}" &&
  tar -czf "../${output_filename##*/}" *
  local exit_code=$?

  cd "${current_directory}" &&
  rm -rf -- "${output_dirname}"
  return $exit_code
}

#################################################
# Generates a preamble for a self-extracting
# executable archive.
# Arguments:
#   $1. The path of the main script.
#       Defaults to the name of this file.
#   $2. The byte size of the resulting preamble.
#       Will be calculated automatically.
# Outputs:
#   Writes the preamble script to stdout.
#################################################
build_preamble() {
  local exec_filename="${1:-"./${0##*/}"}"
  local byte_count=${2:-"$(build_preamble "${exec_filename}" 0 | wc -c)"}
  [ -z "${2}" ] && byte_count=$((${byte_count} + ${#byte_count} - 1))

  echo '#!/bin/sh'
  echo 'INIT_DIR=$PWD'
  echo 'TEMP_DIR=.~${0##*/}+$$'
  echo 'trap '\''cd "$INIT_DIR" && rm -rf "$TEMP_DIR"; trap - EXIT; exit'\'' EXIT INT HUP'
  echo 'mkdir -p "$TEMP_DIR" &&'
  echo 'dd bs=65536 skip='${byte_count}' iflag=skip_bytes if="$0" 2> /dev/null |'
  echo 'tar -xzC "$TEMP_DIR" && cd "$TEMP_DIR" &&'
  echo '__0="$0" __PWD="$INIT_DIR" "'"${exec_filename}"'" "$@"'
  echo 'exit'
}

#################################################
# Builds the current project into an executable.
# Arguments:
#   $1. The output filename for the executable.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
build() {
  local output_filename="${1:-"$(resolve_path "./build/${__NAME}")"}"
  local output_dirname="$(dirname "${output_filename}")/.~${__NAME}+$$+$(rands)"
  local relative_output_filename="../${output_filename##*/}"
  local current_dirname="${PWD}"
  shift || return

  rm -f "${output_filename}" &&
  mkdir -p "${output_dirname}" &&
  cp -r * "${output_dirname}" 2> /dev/null || : &&
  cd "${output_dirname}" &&
  "./${0##*/}" __build -- "${@}" &&
  { build_preamble; tar -czf - *; } > "${relative_output_filename}" &&
  chmod a+x "${relative_output_filename}"
  local exit_code=$?

  cd "${current_dirname}" &&
  rm -rf "${output_dirname}"
  return $exit_code
}

#################################################
# Builds all enabled services.
# Arguments:
#  None
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
__build() {
  process_files . "*.sh" unwrap_sh_sources &&
  exec_services build "${@}"
}

#################################################
# Executes the provided command.
# Arguments:
#   $1. The command to execute.
#   $2. The input filename.
#   $3. The output filename.
#   ... Additional arguments for the command.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
exec_command() {
  local command="${1}"
  local input_filename="${2}"
  local output_filename="${3}"
  shift 3 || return

  case "${command}" in
    __build) __build "${@}" ;;
    build) build "${output_filename}" "${@}" ;;
    backup) backup "${output_filename}" "${@}" ;;
    restore) restore "${input_filename}" "${@}" ;;
    recreate)
      exec_command install "${input_filename}" "${output_filename}" "${@}" &&
      exec_command restore "${input_filename}" "${output_filename}" "${@}"
      ;;

    *) exec_services "${command}" "${@}" ;;
  esac
}

#################################################
# Executes a command via SSH on a remote server.
# Arguments:
#   $1. The command to execute.
#   $2. The input filename.
#   $3. The output filename.
#   $4. The remote destination.
#   $5. The SSH identity file.
#   ... Additional arguments for the command.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
exec_command_ssh() {
  local command="${1}"
  local input_filename="${2}"
  local output_filename="${3}"
  local dest="${4}"
  local identity="${5}"
  shift 5 || return

  # We need to translate local paths into something that
  # we won't encounter on the server.
  local tmp_id="$$+$(rands)"
  local tmp_exec=".~${__NAME}+bin+${tmp_id}"
  local tmp_input="${input_filename:+".~${__NAME}+in+${tmp_id}"}"
  local tmp_output="${output_filename:+".~${__NAME}+out+${tmp_id}"}"

  # We place files in the $HOME directory, as it's the only location that's
  # both guaranteed to exist and where we definitely have sufficient
  # permissions to access.
  # Well, ok, it may not be the **only** option,
  # but it's certainly the easiest one to use.
  # Additionally, since we cannot guarantee that filenames won't contain
  # spaces and/or other special characters, we need to quote the dynamic parts.
  local tmp_exec_arg="~/$(quote_args "${tmp_exec}")"
  local tmp_input_arg="${tmp_input:+"~/$(quote_args "${tmp_input}")"}"
  local tmp_output_arg="${tmp_output:+"~/$(quote_args "${tmp_output}")"}"

  # I'm not a big fan of calling SSH like five times.
  # I would much prefer to do everything in one go.
  # However, we don't have a reliable mechanism for sending the output file
  # back to us without interfering with stdout or stderr.
  # Unfortunately, it doesn't seem like SSH has the ability to map additional
  # file descriptors either. So, the only reliable option at our disposal is
  # this ugly back-and-forth. It’s not optimal, but at least it works.

  # Send the input file to the server, if any.
  if [ -n "${input_filename}" ]; then
    scp -qpi "${identity}" "${input_filename}" "${dest}":~/"${tmp_input}"
  fi &&

  # Send the executable to the server.
  scp -qpi "${identity}" "$(resolve_path "${__0}")" "${dest}":~/"${tmp_exec}" &&

  # Invoke the executable.
  ssh -qi "${identity}" "${dest}" "
    ${tmp_exec_arg} '${command}' -d '${DOMAIN_NAME}' -e '${ACME_EMAIL}' \\
      ${tmp_input_arg} ${tmp_output:+"-o"} ${tmp_output_arg} -- \\
      $(quote_args "${@}")
  " &&

  # Send the output file back to us, if any.
  if [ -n "${output_filename}" ]; then
    mkdir -p "$(dirname "${output_filename}")" &&
    scp -qpi "${identity}" "${dest}":~/"${tmp_output}" "${output_filename}"
  fi
  local exit_code=$?

  # Clean up the temporary files that we created on the server.
  ssh -qi "${identity}" "${dest}" "
    rm -f ${tmp_exec_arg} ${tmp_input_arg} ${tmp_output_arg} > /dev/null 2>& 1
  "

  return $exit_code
}

#################################################
# Prints version information.
# Arguments:
#   None
# Outputs:
#   Writes version information to stdout.
#################################################
version() {
  echo "${__NAME} ${__VERSION}"
  echo
  echo "Services:"
  get_services | while IFS= read -r service; do
    jq -r '"  \(.name) \(.version // "")"' "${service}"
  done
}

#################################################
# Prints a brief help message.
# Arguments:
#   None
# Outputs:
#   Writes the help message to stdout.
#################################################
help() {
  echo "Usage: ${__0} <command> [<options>] [<file>]"
  echo "       ${__0} ssh [-i <file>] <destination> <command> [<options>] [<file>]"
  echo
  echo "Manage the deployment, backup, and recovery routines for the server software."
  echo
  echo "Examples:"
  echo "  ${__0} build -o ./build/${__NAME}"
  echo "  ${__0} install"
  echo "  ${__0} backup -o backup.tar.gz"
  echo "  ${__0} restore backup.tar.gz"
  echo "  ${__0} ssh -i ~/.ssh/id_rsa root@42.42.42.42 recreate backup.tar.gz"
  echo
  echo "Commands:"
  echo "  build [-o <build>]         Build enabled services into a single executable"
  echo "  install                    Install built services"
  echo "  uninstall                  Uninstall built services"
  echo "  backup [-o <backup>]       Backup each service via the \"backup\" command"
  echo "  restore <backup>           Restore the state of services from a backup"
  echo "  recreate <backup>          Install built services and then restore their state"
  echo "  <command>                  Execute the specified <command> for each service"
  echo
  echo "Options:"
  echo "  -h, --help                 Display this help text and exit"
  echo "  -v, --version              Display version information and exit"
  echo "  -q, --quiet                Suppress all normal output"
  echo "  -e, --email                Specify the ACME email address"
  echo "  -d, --domain               Specify the domain name of the current machine"
  echo "  -o, --output <file>        Write output to <file>"
  echo "  -i, --identity <file>      Select the <file> from which the identity is read"
}

#################################################
# Formats and prints the provided error message,
# displays the help page, and terminates the
# process.
# Arguments:
#   $1. The error message to format and print.
# Outputs:
#   Writes the formatted error message to stderr.
# Returns:
#   Never returns (exits with a status of 1).
#################################################
fatal_error() {
  error "${1}"
  help >& 2
  exit 1
}

#################################################
# The main entry point for the script.
# Arguments:
#   ... A list of the command line arguments.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
main() {
  local is_ssh=""
  local input_filename=""
  local output_filename=""
  local identity_filename=""
  local destination=""
  local command=""

  # Parse the arguments and options.
  while [ $# -gt 0 ]; do
    case "${1}" in
      -h|--help) help; exit 0 ;;
      -v|--version) version; exit 0 ;;
      -q|--quiet) exec > /dev/null ;;
      -e|--email) export ACME_EMAIL="${2}"; shift ;;
      -d|--domain) export DOMAIN_NAME="${2}"; shift ;;
      -o|--output) output_filename="$(resolve_path "${2}")"; shift ;;
      -i|--identity) identity_filename="$(resolve_path "${2}")"; shift ;;
      --) shift; break ;;
      -*) fatal_error "invalid option: '${1}'" ;;
      *)
        if [ -z "${command}" ] && [ "${1}" = "ssh" ]; then
          is_ssh=true
        elif [ -n "${is_ssh}" ] && [ -z "${destination}" ]; then
          destination="${1}"
        elif [ -z "${command}" ]; then
          command="${1}"
        elif [ -z "${input_filename}" ]; then
          input_filename="$(resolve_path "${1}")"
        else
          fatal_error "invalid argument: '${1}'"
        fi
        ;;
    esac
    shift 2> /dev/null || fatal_error "missing operand"
  done
  [ -n "${command}" ] || fatal_error "missing command"

  # Ensure that prerequisites for the script are met.
  require_package jq &&
  require_package tar ||
  return

  # Execute the specified command.
  if [ -n "${is_ssh}" ]; then
    exec_command_ssh "${command}" "${input_filename}" "${output_filename}" \
      "${destination}" "${identity_filename}" "${@}"
  else
    exec_command "${command}" "${input_filename}" "${output_filename}" "${@}"
  fi
}

main "${@}"
