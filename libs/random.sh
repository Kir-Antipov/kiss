#################################################
# Converts input data to a URL- and filename-safe
# Base64-encoded string (without padding).
# Arguments:
#   None.
# Inputs:
#   Reads input data from stdin.
# Outputs:
#   Writes the Base64-encoded string to stdout.
#################################################
base64url() {
  local base64_value="$(base64 -w 0 | tr "/+" "_-")"
  printf "%s" "${base64_value%%=*}"
}

#################################################
# Generates a random integer within the specified
# range using /dev/urandom.
# Arguments:
#   $1. Minimum value of the range (inclusive).
#   $2. Maximum value of the range (exclusive).
# Outputs:
#   Writes the generated integer to stdout.
#################################################
randi() {
  od -A n -t u4 -N 4 /dev/urandom |
  awk -v min="${1:-0}" -v max="${2:-2147483647}" '{
    print int($0 / 4294967296 * (max - min)) + min
  }'
}

#################################################
# Generates a random URL- and filename-safe
# string using /dev/urandom.
# Arguments:
#   $1. The number of random bytes to encode.
#       The resulting string length will be
#       approximately 4/3 of this value.
# Outputs:
#   Writes the generated string to stdout.
#################################################
rands() {
  head -c "${1:-24}" /dev/urandom | base64url
}
