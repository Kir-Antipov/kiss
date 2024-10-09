#################################################
# Unpacks provided files from a backup file.
# Arguments:
#   $1. The name of the backup to extract from.
#   ... A list of files to extract.
# Returns:
#   0 if all specified files are extracted;
#   otherwise, a non-zero status.
#################################################
unbak() {
  local tarball_filename="${1}"
  shift || return

  while [ $# -gt 0 ]; do
    local target_dirname="$(dirname "${1}")"
    mkdir -p "${target_dirname}" &&
    tar -xzf "${tarball_filename}" -C "${target_dirname}" "${1##*/}" || return
    shift
  done
}
