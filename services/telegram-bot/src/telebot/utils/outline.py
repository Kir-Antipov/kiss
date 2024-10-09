import json
import re
from dataclasses import dataclass, field, fields
from datetime import datetime
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from utils.net import create_ssl_context

def _snake_to_camel(name: str) -> str:
  if not name:
    return name
  name = name.lower()
  name_camel = "".join(x.capitalize() for x in name.split("_"))
  return name[0] + name_camel[1:]

def _dict_to_class(dict: dict[str] | None, cls):
  if not dict:
    return None
  metadata = {f.metadata.get("name", _snake_to_camel(f.name)): f.name for f in fields(cls)}
  kwargs = {metadata[key]: value for key, value in dict.items()}
  return cls(**kwargs)


@dataclass
class DataLimit:
  bytes: int = -1

@dataclass
class AccessKey:
  id: str = None
  name: str = None
  password: str = None
  port: int = 0
  method: str = None
  access_url: str = None
  data_limit: DataLimit | None = None

@dataclass
class ServerInfo:
  id: str = field(default=None, metadata={"name": "serverId"})
  name: str = field(default=None)
  version: str = field(default=None)
  hostname: str = field(default=None, metadata={"name": "hostnameForAccessKeys"})
  port: int = field(default=0, metadata={"name": "portForNewAccessKeys"})
  created: datetime = field(default=None, metadata={"name": "createdTimestampMs"})
  telemetry_enabled: bool = field(default=None, metadata={"name": "metricsEnabled"})
  data_limit: DataLimit | None = field(default=None, metadata={"name": "accessKeyDataLimit"})

  def __post_init__(self):
    if self.created is not None and not isinstance(self.created, datetime):
      self.created = datetime.fromtimestamp(float(self.created) / 1000)


class OutlineAPIClient:
  def __init__(self, base_url: str, fingerprint: str | bytes = None) -> None:
    self.base_url = base_url.rstrip("/")
    self.http_client = AsyncHTTPClient(defaults=dict(allow_nonstandard_methods=True))
    self.headers = {"Content-Type": "application/json"}
    self.ssl_context = create_ssl_context(fingerprint=fingerprint)

  @staticmethod
  def from_url(url: str, fingerprint: str | bytes = None, prefer_localhost=True) -> "OutlineAPIClient":
    public_api_url = url.strip()
    if not prefer_localhost:
      return OutlineAPIClient(public_api_url, fingerprint=fingerprint)

    parsed_url = urlparse(public_api_url)
    local_netloc = "localhost".join(parsed_url.netloc.rsplit(parsed_url.hostname, 1))
    local_api_url = parsed_url._replace(netloc=local_netloc).geturl()
    local_client = OutlineAPIClient(local_api_url, fingerprint=fingerprint)
    if local_client.is_available():
      return local_client

    return OutlineAPIClient(public_api_url, fingerprint=fingerprint)

  @staticmethod
  def from_access_config(path: str, prefer_localhost=True) -> "OutlineAPIClient":
    with open(path) as file:
      config = file.read()

    url_match = re.search(r"^apiUrl:(.+)$", config, re.MULTILINE)
    fingerprint_match = re.search(r"^certSha256:([A-Fa-f0-9]{64})$", config, re.MULTILINE)

    url = url_match and url_match[1]
    fingerprint = fingerprint_match and fingerprint_match[1]
    if not url:
      raise ValueError(f"'{path}' does not contain a valid 'apiUrl' entry")

    return OutlineAPIClient.from_url(url, fingerprint, prefer_localhost)

  @staticmethod
  def _parse(obj: dict):
    if "bytes" in obj:
      return _dict_to_class(obj, DataLimit)
    elif "metricsEnabled" in obj:
      return _dict_to_class(obj, ServerInfo)
    elif "accessUrl" in obj:
      return _dict_to_class(obj, AccessKey)
    return obj

  async def _request(self, path: str, method: str = "GET", payload=None):
    url = f"{self.base_url}{path}"
    body = json.dumps(payload).encode("utf-8") if payload else None
    request = HTTPRequest(url, method, self.headers, body, ssl_options=self.ssl_context)
    response = await self.http_client.fetch(request)
    if response.code not in (200, 201):
      return None
    return json.loads(response.body, object_hook=OutlineAPIClient._parse)

  def is_available(self) -> bool:
    req = Request(f"{self.base_url}/metrics/enabled", headers=self.headers)
    try:
      with urlopen(req, context=self.ssl_context, timeout=5) as response:
        return response.code == 200
    except:
      return False

  async def is_telemetry_enabled(self) -> bool:
    server: ServerInfo = await self._request("/metrics/enabled")
    return server.telemetry_enabled

  async def get_transfer_metrics(self) -> dict[str, int]:
    return (await self._request("/metrics/transfer"))["bytesTransferredByUserId"]

  async def get_server_info(self) -> ServerInfo:
    return await self._request("/server")

  async def patch_server_info(self, server: ServerInfo | None) -> None:
    if server is None:
      return
    if server.name is not None:
      await self._request("/name", "PUT", {"name": server.name})
    if server.hostname is not None:
      await self._request("/server/hostname-for-access-keys", "PUT", {"hostname": server.hostname})
    if server.port and server.port > 0:
      await self._request("/server/port-for-new-access-keys", "PUT", {"port": server.port})
    if server.telemetry_enabled is not None:
      await self._request("/metrics/enabled", "PUT", {"metricsEnabled": server.telemetry_enabled})
    if server.data_limit and server.data_limit.bytes < 0:
      await self._request("/server/access-key-data-limit", "DELETE")
    elif server.data_limit and server.data_limit.bytes >= 0:
      await self._request("/server/access-key-data-limit", "PUT", {"limit": {"bytes": server.data_limit.bytes}})

  async def get_access_keys(self) -> list[AccessKey]:
    return (await self._request("/access-keys"))["accessKeys"]

  async def get_access_key(self, id: str) -> AccessKey | None:
    try:
      return await self._request(f"/access-keys/{id}")
    except HTTPError as e:
      if e.code != 404: raise
      return None

  async def delete_access_key(self, id: str) -> bool:
    try:
      await self._request(f"/access-keys/{id}", "DELETE")
      return True
    except HTTPError as e:
      if e.code != 404: raise
      return False

  async def patch_access_key(self, key: AccessKey) -> bool:
    try:
      if key.name is not None:
        await self._request(f"/access-keys/{key.id}/name", "PUT", {"name": key.name})
      if key.data_limit and key.data_limit.bytes < 0:
        await self._request(f"/access-keys/{key.id}/data-limit", "DELETE")
      elif key.data_limit and key.data_limit.bytes >= 0:
        await self._request(f"/access-keys/{key.id}/data-limit", "PUT", {"limit": {"bytes": key.data_limit.bytes}})
      return True
    except HTTPError as e:
      if e.code != 404: raise
      return False

  async def create_access_key(self, key: AccessKey = None) -> AccessKey:
    key = key or AccessKey()
    data = {
      "name": key.name,
      "method": key.method,
      "password": key.password,
      "port": key.port if key.port and key.port > 0 else None,
      "limit": {"bytes": key.data_limit.bytes} if key.data_limit and key.data_limit.bytes >= 0 else None,
    }
    data = {k: v for k, v in data.items() if v is not None}
    if key.id:
      return await self._request(f"/access-keys/{key.id}", "PUT", data)
    else:
      return await self._request("/access-keys", "POST", data)
