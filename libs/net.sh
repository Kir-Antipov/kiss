#################################################
# Retrieves the public IP address of the machine
# by querying multiple online services.
# Arguments:
#   None.
# Outputs:
#   Writes the public IP address to stdout.
# Returns:
#   0 if a valid IP address is retrieved;
#   otherwise, a non-zero status.
#################################################
get_ip() {
  local ip=""
  local url=""
  for url in "https://ipinfo.io/ip" "https://icanhazip.com"; do
    ip="$(curl -fsS4 "${url}")"
    [ $? = 0 ] && [ -n "${ip}" ] && printf "%s" "${ip}" && return
  done
}

#################################################
# Expands a URI by adding a protocol if missing,
# and replacing wildcards with the given domain.
# Arguments:
#   $1. The URI to expand, which may contain "*"
#       as a placeholder for the domain name.
#   $2. The protocol to use if none is specified.
#       May be inferred from $3;
#       otherwise, defaults to "https".
#   $3. A reference URI to infer the domain name
#       and default protocol.
# Outputs:
#   Writes the expanded URI to stdout.
#################################################
expand_uri() {
  local uri="${1}"

  case "${uri}" in
    *"*"*)
      local domain="${3##*://}"
      if [ -z "${domain}" ]; then
        echo "${0}: cannot expand uri: missing domain name" >& 2
        return 1
      fi

      uri="$(echo "${uri}" | awk -v val="${domain}" 'gsub("\\*", val)')"
      ;;
  esac

  case "${uri}" in
    *://*) ;;
    *)
      local protocol="${2:-"${3%%${3##*://}}"}"
      protocol="${protocol:-"https"}"

      uri="${protocol%%://*}://${uri}"
      ;;
  esac

  echo "${uri}"
}
