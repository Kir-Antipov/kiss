import base64
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar

def _unwrap(value: int | str | Any) -> int | str:
  if isinstance(value, int):
    return value

  if hasattr(value, "id") and isinstance(value.id, int):
    return value.id

  value = str(value)
  try:
    return int(value)
  except:
    return value

def _format_date(date: datetime | None) -> str | None:
  if date is None:
    return None
  return date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _parse_date(date: str | datetime | None) -> datetime | None:
  if date is None:
    return None
  if isinstance(date, datetime):
    return date
  return datetime.fromisoformat(date).replace(tzinfo=timezone.utc)

class DB:
  def __init__(self, database: str) -> None:
    self.connection = sqlite3.connect(database, check_same_thread=False)
    self.connection.row_factory = sqlite3.Row
    self.users = self._repository(UserRepository)
    self.tags = self._repository(TagRepository)
    self.user_tags = self._repository(UserTagRepository)
    self.access_keys = self._repository(AccessKeyRepository)

  def _repository(self, cls):
    repository = cls(self)
    repository.initialize()
    return repository

  def exec(self, query: str, params: tuple = ()) -> int:
    cursor = self.connection.execute(query, params)
    cursor.connection.commit()
    return cursor.rowcount

  def get(self, query: str, params: tuple = (), cls = dict):
    cursor = self.connection.execute(query, params)
    row = cursor.fetchone()
    return cls(**row) if row is not None else None

  def get_all(self, query: str, params: tuple = (), cls = dict):
    cursor = self.connection.execute(query, params)
    rows = cursor.fetchall()
    return [cls(**row) for row in rows]

  def close(self) -> None:
    self.connection.close()


class Repository:
  def __init__(self, db: DB) -> None:
    self.db = db

  def initialize(self) -> None:
    pass


@dataclass
class User:
  id: int
  nickname: str
  joined_at: datetime

  def __post_init__(self) -> None:
    self.joined_at = _parse_date(self.joined_at)

UserLike = int | str | User

class UserRepository(Repository):
  def initialize(self) -> None:
    self.db.exec("""
      CREATE TABLE IF NOT EXISTS "users" (
        "id" INTEGER NOT NULL UNIQUE,
        "nickname" TEXT NOT NULL UNIQUE,
        "joined_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY("id")
      )
    """)
    self.db.exec("INSERT OR IGNORE INTO users (id, nickname) VALUES (-1, '_')")

  def create(self, id: int, nickname: str = None, joined_at: datetime = None) -> User:
    nickname = nickname or str(id)
    joined_at = joined_at or datetime.now(timezone.utc)
    self.db.exec(
      "INSERT OR IGNORE INTO users (id, nickname, joined_at) VALUES (?, ?, ?)",
      (id, nickname, _format_date(joined_at))
    )
    return User(id=id, nickname=nickname, joined_at=joined_at)

  def get(self, user: UserLike) -> User | None:
    user = _unwrap(user)
    column = "id" if isinstance(user, int) else "nickname"
    return self.db.get(f"SELECT * FROM users where {column} = ?", (user,), User)

  def get_all(self, ids: list[int] | None = None) -> list[User]:
    if ids is None:
      return self.db.get_all("SELECT * FROM users", (), User)

    pattern = ",".join("?" * len(ids))
    return self.db.get_all(
      f"SELECT * FROM users WHERE id IN ({pattern})",
      ids, User
    )

  def get_id(self, user: UserLike) -> int | None:
    user = _unwrap(user)
    if isinstance(user, int):
      return user

    user = self.get(user)
    return user.id if user else None

  def update(self, user: UserLike, nickname: str = None, joined_at: datetime = None) -> bool:
    current_user = self.get(user)
    if current_user is None:
      return False

    if isinstance(user, User):
      nickname = nickname or user.nickname
      joined_at = joined_at or user.joined_at

    nickname = nickname or current_user.nickname
    joined_at = joined_at or current_user.joined_at
    return self.db.exec(
      "UPDATE users SET nickname = ?, joined_at = ? WHERE id = ?",
      (nickname, _format_date(joined_at), current_user.id)
    ) > 0

  def delete(self, user: UserLike) -> bool:
    user = _unwrap(user)
    column = "id" if isinstance(user, int) else "nickname"
    return self.db.exec(f"DELETE FROM users where {column} = ?", (user,)) > 0


@dataclass
class Tag:
  ADMIN: ClassVar[str] = "ADMIN"
  BANNED: ClassVar[str] = "BANNED"

  id: int
  name: str

TagLike = int | str | Tag

class TagRepository(Repository):
  def initialize(self) -> None:
    self.db.exec("""
      CREATE TABLE IF NOT EXISTS "tags" (
        "id" INTEGER NOT NULL UNIQUE,
        "name" TEXT NOT NULL UNIQUE,
        PRIMARY KEY("id" AUTOINCREMENT)
      )
    """)
    self.db.exec(
      "INSERT OR IGNORE INTO tags (name) VALUES (?), (?)",
      (Tag.ADMIN, Tag.BANNED)
    )

  def create(self, name: str) -> Tag:
    self.db.exec("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
    return self.get(name)

  def get(self, tag: TagLike) -> Tag | None:
    tag = _unwrap(tag)
    column = "id" if isinstance(tag, int) else "name"
    return self.db.get(f"SELECT * FROM tags WHERE {column} = ?", (tag,), Tag)

  def get_id(self, tag: TagLike) -> int | None:
    tag = _unwrap(tag)
    if isinstance(tag, int):
      return tag

    tag = self.get(tag)
    return tag.id if tag else None

  def get_all(self) -> list[Tag]:
    return self.db.get_all("SELECT * FROM tags", (), Tag)

  def delete(self, tag: TagLike) -> bool:
    tag = _unwrap(tag)
    column = "id" if isinstance(tag, int) else "name"
    return self.db.exec(f"DELETE FROM tags WHERE {column} = ?", (tag,)) > 0


@dataclass
class UserTag:
  user_id: int
  tag_id: int

class UserTagRepository(Repository):
  def initialize(self) -> None:
    self.db.exec("""
      CREATE TABLE IF NOT EXISTS "user_tags" (
        "user_id" INTEGER NOT NULL,
        "tag_id" INTEGER NOT NULL,
        PRIMARY KEY("user_id","tag_id"),
        FOREIGN KEY("user_id") REFERENCES "users"("id")
          ON DELETE CASCADE ON UPDATE CASCADE,
        FOREIGN KEY("tag_id") REFERENCES "tags"("id")
          ON DELETE CASCADE ON UPDATE CASCADE
      )
    """)

  def create(self, user: UserLike, tag: TagLike) -> UserTag | None:
    uid = self.db.users.get_id(user)
    tid = self.db.tags.get_id(tag)
    if uid is None or tid is None:
      return None

    self.db.exec(
      "INSERT OR IGNORE INTO user_tags (user_id, tag_id) VALUES (?, ?)",
      (uid, tid)
    )
    return UserTag(user_id=uid, tag_id=tid)

  def get(self, user: UserLike, tag: TagLike) -> UserTag | None:
    uid = self.db.users.get_id(user)
    tid = self.db.tags.get_id(tag)
    if uid is None or tid is None:
      return None

    return self.db.get(
      "SELECT * FROM user_tags WHERE user_id = ? AND tag_id = ?",
      (uid, tid), UserTag
    )

  def get_all_by_tag(self, tag: TagLike) -> list[UserTag]:
    tid = self.db.tags.get_id(tag)
    if tid is None:
      return False

    return self.db.get_all(
      "SELECT * FROM user_tags WHERE tag_id = ?",
      (tid,), UserTag
    )

  def exists(self, user: UserLike, tag: TagLike) -> bool:
    uid = self.db.users.get_id(user)
    tid = self.db.tags.get_id(tag)
    if uid is None or tid is None:
      return False

    return self.db.get(
      "SELECT 1 FROM user_tags WHERE user_id = ? AND tag_id = ?",
      (uid, tid)
    ) is not None

  def delete(self, user: UserLike, tag: TagLike) -> bool:
    uid = self.db.users.get_id(user)
    tid = self.db.tags.get_id(tag)
    if uid is None or tid is None:
      return False

    return self.db.exec(
      "DELETE FROM user_tags WHERE user_id = ? AND tag_id = ?",
      (uid, tid)
    ) > 0


@dataclass
class AccessKey:
  id: str
  user_id: int
  outline_id: str
  expires_at: datetime | None

  @property
  def is_expired(self) -> bool:
    if self.expires_at is None:
      return False
    return self.expires_at <= datetime.now(timezone.utc)

  def __post_init__(self):
    self.expires_at = _parse_date(self.expires_at)

class AccessKeyRepository(Repository):
  def initialize(self) -> None:
    self.db.exec("""
      CREATE TABLE IF NOT EXISTS "access_keys" (
        "id" TEXT NOT NULL,
        "user_id" INTEGER NOT NULL,
        "outline_id" TEXT NOT NULL,
        "expires_at" TEXT DEFAULT NULL,
        PRIMARY KEY("id","user_id"),
        FOREIGN KEY("user_id") REFERENCES "users"("id")
          ON DELETE CASCADE ON UPDATE CASCADE
      )
    """)

  def create(self, user: UserLike, outline_id: str, expires_at: datetime = None) -> AccessKey:
    id = base64.b64encode(uuid.uuid4().bytes, b"-_")[:22].decode("utf-8")
    uid = self.db.users.get_id(user)
    self.db.exec(
      "INSERT INTO access_keys (id, user_id, outline_id, expires_at) VALUES (?, ?, ?, ?)",
      (id, uid, outline_id, _format_date(expires_at))
    )
    return AccessKey(id=id, user_id=uid, outline_id=outline_id, expires_at=expires_at)

  def get(self, user: UserLike, id: str) -> AccessKey | None:
    uid = self.db.users.get_id(user)
    if uid is None:
      return None

    return self.db.get(
      "SELECT * FROM access_keys WHERE id = ? and user_id = ?",
      (id, uid), AccessKey
    )

  def get_all(self) -> list[AccessKey]:
    return self.db.get_all(
      "SELECT * FROM access_keys",
      (), AccessKey
    )

  def get_all_by_user(self, user: UserLike) -> list[AccessKey]:
    uid = self.db.users.get_id(user)
    if uid is None:
      return []

    return self.db.get_all(
      "SELECT * FROM access_keys WHERE user_id = ?",
      (uid,), AccessKey
    )

  def get_all_expired(self) -> list[AccessKey]:
    return self.db.get_all(
      "SELECT * FROM access_keys WHERE expires_at <= CURRENT_TIMESTAMP",
      (), AccessKey
    )

  def update(self, user: UserLike, id: str, expires_at: datetime | None = ...) -> bool:
    if expires_at is ...:
      return False

    uid = self.db.users.get_id(user)
    if uid is None:
      return False

    return self.db.exec(
      "UPDATE access_keys SET expires_at = ? WHERE id = ? AND user_id = ?",
      (_format_date(expires_at), id, uid)
    ) > 0

  def delete(self, user: UserLike, id: str) -> bool:
    uid = self.db.users.get_id(user)
    if uid is None:
      return False

    return self.db.exec(
      "DELETE FROM access_keys WHERE id = ? and user_id = ?",
      (id, uid)
    ) > 0
