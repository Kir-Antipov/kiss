#################################################
# Removes the oldest files in a directory
# exceeding a specified limit.
# Arguments:
#   $1. The directory to clean up.
#   $2=1. The number of files to keep.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
rml() {
  local file=""
  local files="$(\ls -1rAt "${1}")"
  local file_count=$(printf "%s" "${files}" | grep -c ".")
  local rm_count=$((${file_count} - ${2:-1}))

  while IFS= read -r file; do
    [ ${rm_count} -gt 0 ] || return 0

    [ -f "${1}/${file}" ] &&
    rm "${1}/${file}" ||
    return

    rm_count=$((${rm_count} - 1))
  done <<EOF
${files}
EOF
}

#################################################
# Creates a lightweight "copy" of a file.
# Arguments:
#   $1. The source file to copy or link.
#   $2. The target location.
# Returns:
#   0 if the operation succeeds;
#   otherwise, a non-zero status.
#################################################
cptmp() {
  case "${1}" in
    *.sqlite3) sqlite3 "${1}" ".backup '${2}'" ;;
    *) ln -s "$(realpath "${1}")" "${2}" ;;
  esac
}

#################################################
# Creates a tarball from the specified files.
# Arguments:
#   $1. The name of the tarball to create.
#   ... The files to include in the tarball.
# Returns:
#   0 if the tarball is created successfully;
#   otherwise, a non-zero status.
#################################################
mktar() {
  local current_directory="${PWD}"
  local tarball_filename="${1}"
  local tarball_directory="${1}~tmp+$$"
  shift || return

  mkdir -p "${tarball_directory}" &&

  while [ $# -gt 0 ]; do
    cptmp "${1}" "${tarball_directory}/${1##*/}" &&
    shift
  done &&

  cd "${tarball_directory}" &&
  tar -czhf "../${tarball_filename##*/}" *
  local exit_code=$?

  cd "${current_directory}" &&
  rm -rf -- "${tarball_directory}"
  return $exit_code
}

#################################################
# Creates a backup of the specified files.
# Arguments:
#   $1. The target location.
#   ... The files to include in the backup.
# Options:
#   -n  Set a custom name for the backup file.
#   -s  Set a name for the latest backup symlink.
#   -l  Set the max number of backups to keep.
#   -t  Set the target location.
#   -T  Treat the target as a normal file.
# Returns:
#   0 if the backup is created successfully;
#   otherwise, a non-zero status.
#################################################
mkbak() {
  __error_mkbak() {
    echo "mkbak: ${1}" >& 2
    return 1
  }

  local target_directory=""
  local target_name=""
  local symlink_name=""
  local no_target_directory=""
  local limit=31

  while [ $# -gt 0 ]; do
    case "${1}" in
      -n|--name) target_name="${2}"; shift ;;
      -s|--symlink) symlink_name="${2}"; shift ;;
      -l|--limit) limit=$((${2} + 1)); shift ;;
      -t|--target-directory) target_directory="${2}"; shift ;;
      -T|--no-target-directory) no_target_directory=true ;;
      --) shift; break ;;
      -*) __error_mkbak "invalid option: '${1}'" || return ;;
      *) [ -z "${target_directory}" ] && target_directory="${1}" || break ;;
    esac
    shift 2> /dev/null || __error_mkbak "missing operand" || return
  done
  [ -n "${target_directory}" ] || __error_mkbak "missing path operand" || return

  if [ -n "${no_target_directory}" ]; then
    mktar "${target_directory}" "${@}"
  else
    target_name="${target_directory}/$(date -u +"${target_name:-"%Y-%m-%d_%H%M%S.bak"}")"
    symlink_name="${target_directory}/${symlink_name:-"latest.bak"}"

    mktar "${target_name}" "${@}" &&
    ln -f "${target_name}" "${symlink_name}" &&
    rml "${target_directory}" "${limit}"
  fi
}
