#################################################
# Formats and prints the provided error message.
# Arguments:
#   $1. The error message to format and print.
# Outputs:
#   Writes the formatted error message to stderr.
# Returns:
#   Always returns 1.
#################################################
error() {
  echo "${0}: ${1}" >& 2
  return 1
}

#################################################
# Checks if the specified command exists.
# Arguments:
#   $1. The command to check.
# Returns:
#   0 if the specified command exists;
#   otherwise, a non-zero status.
#################################################
command_exists() {
  command -v "${1}" > /dev/null 2>& 1
}

#################################################
# Quotes and escapes each argument passed to it.
# Arguments:
#   ... The arguments to be quoted and escaped.
# Outputs:
#   Writes the quoted arguments to stdout.
#################################################
quote_args() {
  # `printf %q` is not POSIX-compliant.
  # However, GNU coreutils' printf has supported the %q format since 2015,
  # allowing us to leverage it instead of relying on the shell's built-ins.
  # Alternatively, we could loop through the arguments and manually quote them,
  # but a single call to GNU's printf is certainly faster and more robust.
  /usr/bin/printf "%q " "${@}"
}
