import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from telegram import Message, MessageOrigin
from telegram.ext import ApplicationBuilder, Defaults, MessageHandler, filters
from utils.db import DB, Tag, TagLike
from utils.format import FormatMap
from utils.l10n import L10nTable, load_l10n_table
from utils.mail import Mail, request_url
from utils.net import create_http_server
from utils.outline import OutlineAPIClient
from utils.tg import prepare_handler
from utils.units import DataSpan, TimeSpan
from utils.vpn import AccessKey, VPNManager

_TOKEN_PLACEHOLDER = "<TOKEN>"

class _HasTagFilter(filters.MessageFilter):
  def __init__(self, db: DB, tag: TagLike) -> None:
    super().__init__()
    self.db = db
    self.tag = tag

  def filter(self, message: Message) -> bool:
    user = message.from_user
    return bool(user and self.db.user_tags.exists(user.id, self.tag))


class Telebot:
  def __init__(
      self, db: DB, outline: OutlineAPIClient = None,
      mail: Mail = None, language: str | L10nTable = None) -> None:
    self.db = db
    self.mail = mail
    self.l10n = load_l10n_table(language)

    self.telegram_app = self.__build_telegram_app(db)
    self.http_server = self.__build_http_server()
    self.vpn = self.__build_vpn_manager(db, outline)

    self._cache = self.telegram_app.bot_data

  def run(
      self, token: str, *, api_url="", api_address="", api_port=80,
      webhook_url="", webhook_address="", webhook_port=8080) -> None:
    if not token:
      raise ValueError(f"could not start the bot: the token is missing")

    self.http_server.url = api_url or ""
    self.http_server.listen(address=api_address, port=api_port)

    bot = self.telegram_app.bot
    bot_settings = [bot._token, bot._base_url, bot._base_file_url]
    [bot._token, bot._base_url, bot._base_file_url] = (
      x.replace(_TOKEN_PLACEHOLDER, token) for x in bot_settings
    )
    asyncio.run_coroutine_threadsafe(self.cleanup(), asyncio.get_event_loop())

    if webhook_url:
      self.telegram_app.run_webhook(
        listen=webhook_address, port=webhook_port,
        webhook_url=webhook_url, secret_token=str(uuid.uuid4()),
      )
    else:
      self.telegram_app.run_polling()

    self.http_server.stop()
    self.http_server.url = ""
    [bot._token, bot._base_url, bot._base_file_url] = bot_settings


  async def cleanup(self) -> str:
    self.vpn and await self.vpn.delete_expired_access_keys()
    return self.l10n["CLEANUP_SUCCESS"]

  def register(self, user_id: int, user_username: str) -> str:
    self.db.users.create(user_id, user_username)
    return self.help()

  def help(self) -> str:
    return self.l10n["HELP"]

  def help_admin(self) -> str:
    return self.l10n["HELP_ADMIN"]

  def add_tag_self(self, user_id: int, tag: TagLike, token: str) -> str:
    params = FormatMap({"user": user_id, "tag": tag})
    if token != self.telegram_app.bot.token:
      return self.l10n["INVALID_TOKEN"]

    created = self.db.user_tags.create(user_id, tag)
    if created:
      return self.l10n["USER_SELF_TAG_ADD_SUCCESS"].format_map(params)
    else:
      return self.l10n["USER_SELF_TAG_ADD_FAILURE"].format_map(params)

  def add_tag(self, user: str, tag: TagLike) -> str:
    user_tag = self.db.user_tags.create(user, tag)
    params = FormatMap({"user": user, "tag": tag})
    if user_tag:
      return self.l10n["USER_TAG_ADD_SUCCESS"].format_map(params)
    else:
      return self.l10n["USER_TAG_ADD_FAILURE"].format_map(params)

  def remove_tag(self, user: str, tag: TagLike) -> str:
    deleted = self.db.user_tags.delete(user, tag)
    params = FormatMap({"user": user, "tag": tag})
    if deleted:
      return self.l10n["USER_TAG_REMOVE_SUCCESS"].format_map(params)
    else:
      return self.l10n["USER_TAG_REMOVE_FAILURE"].format_map(params)

  def set_nickname(self, user: str, nickname: str) -> str:
    updated = self.db.users.update(user, nickname=nickname)
    params = FormatMap({"user": user, "nickname": nickname})
    if updated:
      return self.l10n["USER_NICKNAME_SET_SUCCESS"].format_map(params)
    else:
      return self.l10n["USER_NICKNAME_SET_FAILURE"].format_map(params)

  def print_telegram_user(self, message: Message) -> str:
    user = message and message.from_user
    origin = message and message.forward_origin
    if origin is not None:
      user = origin.sender_user if origin.type == MessageOrigin.USER else None
    if user:
      return self.l10n["TELEGRAM_USER_INFO"].format_map(FormatMap(user))
    else:
      return self.l10n["TELEGRAM_USER_INFO_MISSING"]

  def print_user(self, user: str) -> str:
    db_user = self.db.users.get(user)
    if not db_user:
      return self.l10n["INVALID_USER"].format_map(FormatMap({"user": user}))

    db_user.is_admin = self.db.user_tags.exists(db_user, Tag.ADMIN)
    db_user.is_banned = self.db.user_tags.exists(db_user, Tag.BANNED)
    return self.l10n["USER_INFO"].format_map(FormatMap(db_user))

  def print_users(self) -> str:
    users = [x for x in self.db.users.get_all() if x.id > 0]
    op_users = self.db.user_tags.get_all_by_tag(Tag.ADMIN)
    banned_users = self.db.user_tags.get_all_by_tag(Tag.BANNED)
    for user in users:
      user.is_admin = any(x.user_id == user.id for x in op_users)
      user.is_banned = any(x.user_id == user.id for x in banned_users)
    return self.l10n["ALL_USERS_INFO"].format_map(FormatMap({"users": users}))

  async def get_mirror(self, address: str, force: bool = False):
    if not self.mail:
      yield self.l10n["FEATURE_DISABLED"]
      return

    cached_url, cache_date = self._cache.get(address, ("", datetime.min))
    url = cached_url
    new_url = ""
    if force or datetime.now() - cache_date >= timedelta(hours=6):
      yield self.l10n["MIRROR_FETCH_IN_PROGRESS"]
      new_url = await request_url(self.mail, address, timeout=120)

    if new_url:
      self._cache[address] = (new_url, datetime.now())
      url = new_url

    if url:
      yield self.l10n["MIRROR_FETCH_SUCCESS"].format_map(FormatMap({"url": url}))
    else:
      yield self.l10n["MIRROR_FETCH_FAILURE"]

  async def print_server_info(self) -> str:
    if not self.vpn:
      return self.l10n["FEATURE_DISABLED"]

    server_info = await self.vpn.get_server_info()
    return self.l10n["SERVER_INFO"].format_map(FormatMap(server_info))

  async def edit_server_info(self, name: str = None, port: int = None, data_limit: DataSpan = None) -> str:
    if not self.vpn:
      return self.l10n["FEATURE_DISABLED"]

    await self.vpn.patch_server_info(
      name=name or None,
      port=port,
      data_limit=data_limit,
      telemetry_enabled=False,
    )
    return self.l10n["SERVER_INFO_UPDATE_SUCCESS"]

  async def print_access_keys(self, user_id: int) -> str:
    if not self.vpn:
      return self.l10n["FEATURE_DISABLED"]

    access_keys = await self.vpn.get_access_keys(user=user_id)
    return self.l10n["ACCESS_INFO"].format_map(FormatMap({"access_keys": access_keys}))

  async def add_access_key(self, user: str, name: str = None, port: int = None, data_limit: DataSpan = None, time_limit: TimeSpan = None) -> str:
    if not self.vpn:
      return self.l10n["FEATURE_DISABLED"]

    owner = self.db.users.get(user)
    expires_at = None
    if time_limit and time_limit.total_seconds() >= 0:
      expires_at = datetime.now() + time_limit

    if not owner:
      return self.l10n["INVALID_USER"].format_map(FormatMap({"user": user}))

    access_key = await self.vpn.create_access_key(
      user=owner,
      port=port,
      name=name or owner.nickname,
      data_limit=data_limit,
      expires_at=expires_at,
    )
    if access_key:
      return self.l10n["ACCESS_KEYS_ADD_SUCCESS"].format_map(FormatMap({"access_keys": [access_key]}))
    else:
      return self.l10n["ACCESS_KEYS_ADD_FAILURE"]

  async def edit_access_keys(self, user: str, id: str = None, name: str = None, data_limit: DataSpan = None, time_limit: TimeSpan = None) -> str:
    if not self.vpn:
      return self.l10n["FEATURE_DISABLED"]

    owner = self.db.users.get(user)
    expires_at = ...
    if time_limit and time_limit.total_seconds() >= 0:
      expires_at = datetime.now() + time_limit
    elif time_limit and time_limit.total_seconds() < 0:
      expires_at = None

    if not owner:
      return self.l10n["INVALID_USER"].format_map(FormatMap({"user": user}))

    count = await self.vpn.patch_access_keys(
      user=owner,
      id=id,
      name=name,
      data_limit=data_limit,
      expires_at=expires_at,
    )
    if count:
      return self.l10n["ACCESS_KEYS_EDIT_SUCCESS"].format_map(FormatMap({"count": count}))
    else:
      return self.l10n["ACCESS_KEYS_EDIT_FAILURE"]

  async def remove_access_keys(self, user: str, id: str = None) -> str:
    if not self.vpn:
      return self.l10n["FEATURE_DISABLED"]

    owner = self.db.users.get(user)
    if not owner:
      return self.l10n["INVALID_USER"].format_map(FormatMap({"user": user}))

    access_keys = await self.vpn.delete_access_keys(owner, id)
    if access_keys:
      return self.l10n["ACCESS_KEYS_REMOVE_SUCCESS"].format_map(FormatMap({"access_keys": access_keys}))
    else:
      return self.l10n["ACCESS_KEYS_REMOVE_FAILURE"]

  async def on_access_key_created(self, access_key: AccessKey) -> None:
    try:
      await self._on_access_key_created(access_key)
    except:
      pass

  async def _on_access_key_created(self, access_key: AccessKey) -> None:
    if not (access_key.owner and access_key.owner.id > 0):
      return None
    user = access_key.owner.id
    notification = self.l10n["ACCESS_KEYS_ADD_NOTIFICATION"].format_map(FormatMap({"access_keys": [access_key]}))
    await self.telegram_app.bot.send_message(user, notification, disable_web_page_preview=True)

  async def on_access_key_deleted(self, access_key: AccessKey) -> None:
    try:
      await self._on_access_key_deleted(access_key)
    except:
      pass

  async def _on_access_key_deleted(self, access_key: AccessKey) -> None:
    if not (access_key.owner and access_key.owner.id > 0):
      return None

    user = access_key.owner.id
    notification = self.l10n["ACCESS_KEYS_REMOVE_NOTIFICATION"].format_map(FormatMap({"access_keys": [access_key]}))
    await self.telegram_app.bot.send_message(user, notification)

  async def get_raw_access_url(self, user: str, id: str) -> str | None:
    if not (self.vpn and id):
      return None

    return await self.vpn.get_raw_access_url(user or -1, id)

  def get_access_url(self, access_key: AccessKey) -> str:
    if not (self.http_server.url and access_key.id):
      return access_key.access_url

    base_url = self.http_server.url.split("://", maxsplit=1)[-1].rstrip("/")
    if access_key.owner and access_key.owner.id > 0:
      access_url = f"ssconf://{base_url}/{access_key.owner.nickname}/{access_key.id}"
    else:
      access_url = f"ssconf://{base_url}/{access_key.id}"
    return access_url


  def __build_http_server(self):
    async def http_handler(path: str, _: str) -> str | None:
      *_, user, id = ["", "", *(x for x in path.split("/") if x)]
      return await self.get_raw_access_url(user, id)

    http_server = create_http_server(http_handler)
    http_server.url = ""
    return http_server

  def __build_vpn_manager(self, db: DB, outline: OutlineAPIClient | None):
    if not (db and outline):
      return None

    return VPNManager(
      db,
      outline,
      access_url_provider=self.get_access_url,
      on_access_key_created=self.on_access_key_created,
      on_access_key_deleted=self.on_access_key_deleted,
    )

  def __build_telegram_app(self, db: DB):
    defaults = Defaults(parse_mode="HTML", tzinfo=timezone.utc)
    app = ApplicationBuilder().token(_TOKEN_PLACEHOLDER).defaults(defaults).build()

    is_allowed = ~_HasTagFilter(db, Tag.BANNED)
    is_admin = _HasTagFilter(db, Tag.ADMIN)
    def h(pattern, callback, filter=None):
      pattern = filters.Regex(pattern) if isinstance(pattern, str) else pattern
      filter = is_allowed & filter if filter is not None else is_allowed
      filter = pattern & filter
      app.add_handler(MessageHandler(filter, prepare_handler(callback)))

    # General Commands
    h(r"^/start$", self.register)
    h(r"^/help$", self.help_admin, is_admin)
    h(r"^/help$", self.help)
    h(r"^/me$", self.print_telegram_user)
    h(filters.FORWARDED, self.print_telegram_user)

    # VPN Management
    vpn_id = r"\s+@?(?P<user>[\w-]+)(?::(?P<id>[\w-]+))?"
    vpn_params = (
      r"(?:\s+with\s+(?P<data_limit>[-+]?(?:\d*\.\d+|\d+)\s*\S*))?"
      r"(?:\s+for\s+(?P<time_limit>[-+]?(?:\d*\.\d+|\d+)\s*\S*))?"
      r"(?:\s+at\s*(?P<port>\d{1,5}))?"
      r"(?:\s+as\s*(?P<name>.*))?$"
    )
    h(r"^/vpn$", self.print_access_keys)
    h(r"^/vpn(?:\s*|_)server$", self.print_server_info, is_admin)
    h(r"^/vpn(?:\s*|_)server" + vpn_params, self.edit_server_info, is_admin)
    h(r"^/vpn(?:\s*|_)add" + vpn_id + vpn_params, self.add_access_key, is_admin)
    h(r"^/vpn(?:\s*|_)edit" + vpn_id + vpn_params, self.edit_access_keys, is_admin)
    h(r"^/vpn(?:\s*|_)remove" + vpn_id, self.remove_access_keys, is_admin)

    # User Management
    h(r"^/user\s+@?(?P<user>[\w-]+)$", self.print_user, is_admin)
    h(r"^/users$", self.print_users, is_admin)
    h(r"^/nickname\s+@?(?P<user>[\w-]+)\s+@?(?P<nickname>[\w-]+)$", self.set_nickname, is_admin)

    # Admin & Moderation
    h(r"^/ascend\s+(?P<token>\S+)$", dict(_=self.add_tag_self, tag=Tag.ADMIN))
    h(r"^/op\s+@?(?P<user>[\w-]+)$", dict(_=self.add_tag, tag=Tag.ADMIN), is_admin)
    h(r"^/deop\s+@?(?P<user>[\w-]+)$", dict(_=self.remove_tag, tag=Tag.ADMIN), is_admin)
    h(r"^/ban\s+@?(?P<user>[\w-]+)$", dict(_=self.add_tag, tag=Tag.BANNED), is_admin)
    h(r"^/pardon\s+@?(?P<user>[\w-]+)$", dict(_=self.remove_tag, tag=Tag.BANNED), is_admin)

    # Maintenance
    h(r"^/cleanup$", self.cleanup, is_admin)

    # Help
    h(is_admin, self.help_admin)
    h(filters.ALL, self.help)

    return app
