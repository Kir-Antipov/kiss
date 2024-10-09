#!/usr/bin/env python3
from argparse import ArgumentParser
from os import environ
from os.path import isfile
from telebot import Telebot
from typing import Sequence
from utils.config import Config, MailConfig, OutlineConfig
from utils.db import DB
from utils.mail import Mail
from utils.outline import OutlineAPIClient
from utils.outline import OutlineAPIClient
from utils.url import expand_url

def _parse_args(args: Sequence[str] = None):
  parser = ArgumentParser(prog="telebot", add_help=False, description=(
    "A Telegram bot for managing Outline Server and more."
  ))
  parser.add_argument("-h", "--help", action="help", help=(
    "Show this help message and exit."
  ))
  parser.add_argument("-c", "--config", type=str, default="config.json", help=(
    "Path to the configuration file.\n"
    "Defaults to 'config.json'."
  ))
  parser.add_argument("-d", "--database", type=str, default="db.sqlite3", help=(
    "Path to the SQLite database file.\n"
    "Defaults to 'db.sqlite3'."
  ))
  parser.add_argument("--hostname", type=str, help=(
    "The default hostname for the Tunnel API URL and Webhook URL.\n"
    "This can also be set via the 'TB_HOSTNAME' environment variable."
  ))
  parser.add_argument("--token", type=str, help=(
    "The Telegram bot token used for authenticating API requests.\n"
    "This can also be set via the 'TB_TOKEN' environment variable."
  ))
  parser.add_argument("--api-address", type=str, help=(
    "The IP address where the bot should listen for Tunnel API requests.\n"
    "Defaults to '127.0.0.1'."
  ))
  parser.add_argument("--api-port", type=int, help=(
    "The port number where the bot should listen for Tunnel API requests.\n"
    "Defaults to 80."
  ))
  parser.add_argument("--api-url", type=str, help=(
    "The public URL where Telegram can send webhook requests.\n"
    "This should be reachable from the Internet."
  ))
  parser.add_argument("--webhook-address", type=str, help=(
    "The IP address where the bot should listen for webhook requests from Telegram.\n"
    "Defaults to '127.0.0.1'."
  ))
  parser.add_argument("--webhook-port", type=int, help=(
    "The port number where the bot should listen for webhook requests from Telegram.\n"
    "Defaults to 8080."
  ))
  parser.add_argument("--webhook-url", type=str, help=(
    "The public URL where Telegram can send webhook requests.\n"
    "This must be reachable from the Internet."
  ))
  parser.add_argument("--outline-api-url", type=str, help=(
    "The base URL of the Outline Management API.\n"
    "Required if '--outline-access-config' is not provided."
  ))
  parser.add_argument("--outline-cert-sha256", type=str, help=(
    "The SHA-256 hash of the Outline server certificate.\n"
    "Required if '--outline-access-config' is not provided."
  ))
  parser.add_argument("-a", "--outline-access-config", type=str, help=(
    "Path to the Outline access config to extract the API URL from.\n"
    "Required if '--outline-api-url' is not provided."
  ))
  parser.add_argument("--outline-ignore-localhost", action="store_true", help=(
    "Indicates whether the bot should attempt to send requests to the Outline Management API via localhost."
  ))
  return parser.parse_args(args)

def _patch_config(config: Config, args, env=environ) -> Config:
  token = config.bot.token or args.token or env.get("TB_TOKEN") or ""
  hostname = args.hostname or env.get("TB_HOSTNAME")
  localhost = "http://localhost"

  config.bot.token = token
  config.bot.api_address = args.api_address or config.bot.api_address
  config.bot.api_port = args.api_port or config.bot.api_port
  config.bot.api_url = args.api_url or config.bot.api_url or f"*:{config.bot.api_port}"
  config.bot.webhook_address = args.webhook_address or config.bot.webhook_address
  config.bot.webhook_port = args.webhook_port or config.bot.webhook_port
  config.bot.webhook_url = args.webhook_url or config.bot.webhook_url

  config.outline.api_url = args.outline_api_url or config.outline.api_url
  config.outline.cert_sha256 = args.outline_cert_sha256 or config.outline.cert_sha256
  config.outline.access_config = args.outline_access_config or config.outline.access_config
  config.outline.prefer_localhost = False if args.outline_ignore_localhost else config.outline.prefer_localhost

  api_hostname = hostname or config.bot.api_address or localhost
  webhook_hostname = hostname or config.bot.webhook_address or localhost
  config.bot.api_url = config.bot.api_url and expand_url(config.bot.api_url, domain=api_hostname)
  config.bot.webhook_url = config.bot.webhook_url and expand_url(config.bot.webhook_url, domain=webhook_hostname)

  return config

def _init_outline(config: OutlineConfig) -> OutlineAPIClient:
  if config.api_url:
    return OutlineAPIClient.from_url(config.api_url, config.cert_sha256, config.prefer_localhost)
  elif config.access_config and isfile(config.access_config):
    return OutlineAPIClient.from_access_config(config.access_config, config.prefer_localhost)
  else:
    return None

def _init_mail(config: MailConfig) -> Mail:
  if config.user or config.smtp_user or config.imap_user:
    return Mail(**config.to_dict())
  else:
    return None

def main(args: Sequence[str] = None) -> None:
  parsed_args = _parse_args(args)
  config = _patch_config(Config.load(parsed_args.config), parsed_args)

  db = DB(parsed_args.database)
  outline = _init_outline(config.outline)
  mail = _init_mail(config.mail)
  language = config.language

  bot = Telebot(db, outline=outline, mail=mail, language=language)
  bot.run(**config.bot.to_dict())

if __name__ == "__main__":
  main()
