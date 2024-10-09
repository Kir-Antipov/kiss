#!/bin/sh
#
# Renews any SSL certificates that are due to expire within the next 30 days.

EXIT_CODE=0

if certbot certificates 2> /dev/null | grep -Eiq '(^|[^0-9]|[12])[0-9] day|INVALID|EXPIRED'; then
  # Check the status of the nginx service ("active" or "inactive").
  NGINX_STATUS="$(systemctl is-active nginx)"

  # If nginx is currently active, stop it to safely renew the certificates.
  [ "${NGINX_STATUS}" = "active" ] && systemctl stop nginx

  certbot renew > /dev/null 2>& 1
  EXIT_CODE=$?

  # After renewal, restart nginx if it was previously active.
  [ "${NGINX_STATUS}" = "active" ] && systemctl start nginx
fi

exit $EXIT_CODE
