import re
import urllib.parse

def expand_url(url: str, scheme: str = None, domain: str = None) -> str:
  if "*" in url and not domain:
    raise ValueError("could not expand URL: missing domain name")

  domain_url = domain and urllib.parse.urlparse(domain)
  domain_netloc = domain_url and (domain_url.netloc or domain_url.path)
  default_scheme = scheme or (domain_url and domain_url.scheme) or "https"
  url = url.replace("*", domain_netloc or "")
  url = url if "://" in url else f"{default_scheme}://{url}"
  return url

def extract_url(text: str) -> str | None:
  match = re.search(r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.[a-z]{2,6}", text or "")
  url = match and match[0] and urllib.parse.urlparse(match[0])
  url = url and url._replace(
    scheme=url.scheme or "https", netloc=url.netloc or url.path,
    path=url.path if url.path and url.netloc else ""
  )
  url = url and url._replace(path=url.path or ("/" if "/" not in url.netloc else ""))
  return url and url.geturl()

def append_url_parameter(url: str, param_key, param_value=None) -> str:
  url_parts = urllib.parse.urlparse(url)
  query_params = urllib.parse.parse_qs(url_parts.query)
  query_params[param_key] = param_value if param_value is not None else ""
  new_query_string = urllib.parse.urlencode(query_params, doseq=True)
  return urllib.parse.urlunparse((
    url_parts.scheme,
    url_parts.netloc,
    url_parts.path,
    url_parts.params,
    new_query_string,
    url_parts.fragment,
  ))
