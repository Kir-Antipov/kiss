import json
import os
from dataclasses import dataclass, asdict

class BaseConfig:
  @classmethod
  def from_dict(cls, value):
    if isinstance(value, cls):
      return value
    return cls(**(value or dict()))

  def to_dict(self):
    return asdict(self)

@dataclass
class BotConfig(BaseConfig):
  token: str = ""
  api_url: str = ""
  api_address: str = ""
  api_port: int = 80
  webhook_url: str = ""
  webhook_address: str = ""
  webhook_port: int = 8080

@dataclass
class OutlineConfig(BaseConfig):
  api_url: str = ""
  cert_sha256: str = ""
  access_config: str = ""
  prefer_localhost: bool = True

@dataclass
class MailConfig(BaseConfig):
  user: str = ""
  password: str = ""
  host: str = ""
  smtp_user: str = ""
  smtp_password: str = ""
  smtp_host: str = ""
  smtp_port: int = 587
  imap_user: str = ""
  imap_password: str = ""
  imap_host: str = ""
  imap_port: int = 993

@dataclass
class Config(BaseConfig):
  language: str = None
  bot: BotConfig = None
  outline: OutlineConfig = None
  mail: MailConfig = None

  def __post_init__(self) -> None:
    self.bot = BotConfig.from_dict(self.bot)
    self.outline = OutlineConfig.from_dict(self.outline)
    self.mail = MailConfig.from_dict(self.mail)

  def save(self, path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
      os.makedirs(directory, exist_ok=True)
    with open(path, "w") as file:
      json.dump(self.to_dict(), file, indent=2)

  @staticmethod
  def load(path: str) -> "Config":
    try:
      with open(path, "r") as file:
        cfg = Config(**json.load(file))
    except:
      cfg = Config()
      cfg.save(path)
    return cfg
