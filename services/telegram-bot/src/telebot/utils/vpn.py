import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from inspect import isawaitable
from random import Random
from typing import Any, Callable
from utils.db import DB, UserLike, User as DBUser
from utils.outline import OutlineAPIClient, AccessKey as OutlineAccessKey, ServerInfo as OutlineServerInfo, DataLimit
from utils.units import DataSpan
from utils.url import append_url_parameter

@dataclass
class AccessKey:
  id: str | None
  outline_id: str
  owner: DBUser | None
  name: str
  password: str
  port: int
  method: str
  access_url: str
  data_usage: DataSpan
  data_limit: DataSpan | None
  expires_at: datetime | None

  @property
  def is_expired(self) -> bool:
    if self.expires_at is None:
      return False
    return self.expires_at <= datetime.now(timezone.utc)

@dataclass
class ServerInfo:
  id: str
  name: str
  version: str
  hostname: str
  port: int
  created: datetime
  telemetry_enabled: bool
  data_limit: DataSpan | None
  access_keys: list[AccessKey]

  @property
  def data_usage(self) -> DataSpan:
    return DataSpan(sum(x.data_usage for x in self.access_keys))

AccessUrlProvider = Callable[[AccessKey], str]

AccessKeyCallback = Callable[[AccessKey], Any]


def _get_prefixed_access_url(
    outline_key: OutlineAccessKey,
    prefix_map: dict[int, list[str]]) -> str:
  access_url = outline_key.access_url
  prefixes = prefix_map.get(outline_key.port, [])
  if len(prefixes) > 1:
    prefix = Random(access_url).choice(prefixes)
  else:
    prefix = prefixes[0] if prefixes else ""

  if prefix:
    return append_url_parameter(access_url, "prefix", prefix)
  else:
    return access_url

def _create_prefix_map(map_entries) -> dict[int, list[str]]:
  return {
    port: [prefixes] if isinstance(prefixes, str) else list(prefixes)
      for ports, prefixes in map_entries
      for port in ((ports,) if isinstance(ports, int) else ports)
  }

# Loosely based on: https://www.reddit.com/r/outlinevpn/wiki/index/prefixing/
DEFAULT_PREFIX_MAP = _create_prefix_map([
  # SSH
  # [ssh, netconf-ssh, netconf-ch-ssh, snmpssh-trap]
  # [ssh]
  ([22, 830, 4334, 5162], "SSH-2.0\r\n"),

  # DNS-over-TCP
  # [dns]
  # [DNS-over-TCP request]
  (53, "\u0005\u00DC\u005F\u00E0\u0001\u0020"),

  # HTTP
  # [http]
  # [POST request, PUT request]
  (80, ["POST ", "PUT "]),

  # TLS
  # [https, smtps, nntps, ldaps, ftps-data, ftps, imaps, pop3s, Apple APN, Play Store, turns]
  # [TLS ClientHello, TLS Application Data]
  (
    [443, 463, 563, 636, 989, 990, 993, 995, 5223, 5228, 5349],
    ["\u0016\u0003\u0001\u0000\u00a8\u0001\u0001", "\u0013\u0003\u0003\u003F"]
  ),
])


class VPNManager:
  def __init__(
      self, db: DB, outline: OutlineAPIClient, *,
      prefix_map: dict[int, list[str]] = None,
      access_url_provider: AccessUrlProvider = None,
      on_access_key_created: AccessKeyCallback = None,
      on_access_key_deleted: AccessKeyCallback = None) -> None:
    self.db = db
    self.outline = outline
    self.prefix_map = DEFAULT_PREFIX_MAP if prefix_map is None else prefix_map
    self.resolve_access_url = access_url_provider or (lambda x: x.access_url)
    self.on_access_key_created = on_access_key_created
    self.on_access_key_deleted = on_access_key_deleted

  def is_available(self) -> bool:
    return self.outline.is_available()

  async def get_server_info(self) -> ServerInfo:
    server_info, access_keys = await asyncio.gather(
      self.outline.get_server_info(),
      self.get_access_keys(allow_expired=True),
    )

    byte_limit = server_info.data_limit.bytes if server_info.data_limit else -1
    data_limit = DataSpan(byte_limit) if byte_limit >= 0 else None
    return ServerInfo(**{
      **asdict(server_info),
      "data_limit": data_limit,
      "access_keys": access_keys,
    })

  async def patch_server_info(
      self, *, name: str = None, hostname: str = None, port: int = None,
      telemetry_enabled: bool = None, data_limit: int = None) -> None:
    await self.outline.patch_server_info(OutlineServerInfo(
      name=name,
      hostname=hostname,
      port=port,
      telemetry_enabled=telemetry_enabled,
      data_limit=DataLimit(int(data_limit)) if data_limit is not None else None,
    ))

  async def create_access_key(
      self, user: UserLike, *, name: str = None, password: str = None,
      port: int = None, method: str = None, data_limit: int = None,
      expires_at: datetime = None) -> AccessKey:
    owner = self.db.users.get(user)
    if not owner:
      raise ValueError(f"invalid user: '{user}'")

    outline_key = await self.outline.create_access_key(OutlineAccessKey(
      name=name, port=port,
      method=method, password=password,
      data_limit=DataLimit(int(data_limit)) if data_limit is not None else None,
    ))
    if not outline_key:
      raise ValueError(f"got an invalid response from the Outline Server")

    db_key = self.db.access_keys.create(
      user=owner,
      outline_id=outline_key.id,
      expires_at=expires_at,
    )
    if not outline_key:
      raise ValueError(f"could not create a new access key entry")

    access_key = await self.get_access_key(db_key.user_id, db_key.id, allow_expired=True)
    if not access_key:
      raise ValueError("could not find the access key")

    callback_result = self.on_access_key_created and self.on_access_key_created(access_key)
    if isawaitable(callback_result):
      await callback_result

    return access_key

  async def get_access_key(self, user: UserLike, id: str, allow_expired=False) -> AccessKey | None:
    access_keys = await self.get_access_keys(user, id, allow_expired)
    return access_keys[0] if access_keys else None

  async def get_access_keys(self, user: UserLike = None, id: str = None, allow_expired=False) -> list[AccessKey]:
    if id:
      db_key = self.db.access_keys.get(user, id)
      db_keys = [db_key] if db_key else []
    elif user:
      db_keys = self.db.access_keys.get_all_by_user(user)
    elif allow_expired is ...:
      db_keys = self.db.access_keys.get_all_expired()
    else:
      db_keys = self.db.access_keys.get_all()

    if not (user or id or allow_expired is ...):
      outline_keys = await self.outline.get_access_keys()
    elif db_keys and len(db_keys) > 1:
      outline_keys = await self.outline.get_access_keys()
      outline_keys = [x for x in outline_keys if any(x.id == y.outline_id for y in db_keys)]
    elif db_keys:
      outline_key = await self.outline.get_access_key(db_keys[0].outline_id)
      outline_keys = [outline_key] if outline_key else []
    else:
      outline_keys = []

    if outline_keys:
      transfer_metrics = await self.outline.get_transfer_metrics()
    else:
      transfer_metrics: dict[str, int] = {}

    owners = self.db.users.get_all(list(set(x.user_id for x in db_keys)))
    access_keys: list[AccessKey] = []

    for outline_key in outline_keys:
      db_key = next((x for x in db_keys if x.outline_id == outline_key.id), None)
      owner = db_key and next((x for x in owners if x.id == db_key.user_id), None)
      data_usage = DataSpan(transfer_metrics.get(outline_key.id, 0))
      byte_limit = outline_key.data_limit.bytes if outline_key.data_limit else -1
      data_limit = DataSpan(byte_limit) if byte_limit >= 0 else None
      tmp_key = AccessKey(**{
        **asdict(outline_key), "id": db_key and db_key.id,
        "outline_id": outline_key.id, "owner": owner,
        "data_usage": data_usage, "data_limit": data_limit,
        "expires_at": db_key and db_key.expires_at,
        "access_url": _get_prefixed_access_url(outline_key, self.prefix_map),
      })
      access_url = self.resolve_access_url(tmp_key)
      access_key = AccessKey(**{**asdict(tmp_key), "owner": owner, "access_url": access_url})
      if not allow_expired and access_key.is_expired:
        await self._delete_access_key(access_key)
      else:
        access_keys.append(access_key)

    return access_keys

  async def patch_access_key(
      self, user: UserLike, id: str, *,
      name: str = None, data_limit: int = None) -> bool:
    patched = await self.patch_access_keys(user, id, name=name, data_limit=data_limit)
    return patched > 0

  async def patch_access_keys(
      self, user: UserLike = None, id: str = None, *, name: str = None,
      data_limit: int = None, expires_at: datetime | None = ...) -> int:
    access_keys = await self.get_access_keys(user, id, allow_expired=True)
    count = 0
    for access_key in access_keys:
      success = await self._patch_access_key(
        access_key, name=name, data_limit=data_limit, expires_at=expires_at
      )
      count += 1 if success else 0
    return count

  async def _patch_access_key(
      self, access_key: AccessKey, *, name: str = None,
      data_limit: int = None, expires_at: datetime | None = ...) -> bool:
    outline_success = await self.outline.patch_access_key(OutlineAccessKey(
      id=access_key.outline_id, name=name,
      data_limit=DataLimit(int(data_limit)) if data_limit is not None else None,
    ))
    db_success = self.db.access_keys.update(
      user=access_key.owner, id=access_key.id, expires_at=expires_at
    )
    return outline_success or db_success

  async def delete_access_key(self, user: UserLike, id: str) -> AccessKey | None:
    access_keys = await self.delete_access_keys(user, id)
    return access_keys[0] if access_keys else None

  async def delete_access_keys(self, user: UserLike = None, id: str = None) -> list[AccessKey]:
    access_keys = await self.get_access_keys(user, id, allow_expired=True)
    for access_key in access_keys:
      await self._delete_access_key(access_key)
    return access_keys

  async def delete_expired_access_keys(self) -> list[AccessKey]:
    access_keys = await self.get_access_keys(allow_expired=...)
    for access_key in access_keys:
      await self._delete_access_key(access_key)
    return access_keys

  async def _delete_access_key(self, access_key: AccessKey) -> None:
    if access_key.outline_id is not None:
      await self.outline.delete_access_key(access_key.outline_id)

    if access_key.id is not None and access_key.owner is not None:
      self.db.access_keys.delete(access_key.owner.id, access_key.id)

    callback_result = self.on_access_key_deleted and self.on_access_key_deleted(access_key)
    if isawaitable(callback_result):
      await callback_result

  async def get_raw_access_url(self, user: UserLike, id: str) -> str | None:
    db_key = self.db.access_keys.get(user, id)
    if not db_key:
      return None

    if db_key.is_expired:
      await self.delete_access_key(db_key.user_id, db_key.id)
      return None

    outline_key = await self.outline.get_access_key(db_key.outline_id)
    return outline_key and _get_prefixed_access_url(outline_key, self.prefix_map)
