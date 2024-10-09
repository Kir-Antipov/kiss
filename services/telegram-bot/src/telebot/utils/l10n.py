import glob
import json
from os import path
from typing import TypedDict

DEFAULT_LANGUAGE_CODE = "en"

class L10nTable(TypedDict):
  FEATURE_DISABLED: str
  HELP: str
  HELP_ADMIN: str
  CLEANUP_SUCCESS: str
  INVALID_TOKEN: str
  USER_SELF_TAG_ADD_SUCCESS: str
  USER_SELF_TAG_ADD_FAILURE: str
  USER_TAG_ADD_SUCCESS: str
  USER_TAG_ADD_FAILURE: str
  USER_TAG_REMOVE_SUCCESS: str
  USER_TAG_REMOVE_FAILURE: str
  USER_NICKNAME_SET_SUCCESS: str
  USER_NICKNAME_SET_FAILURE: str
  TELEGRAM_USER_INFO: str
  TELEGRAM_USER_INFO_MISSING: str
  INVALID_USER: str
  USER_INFO: str
  ALL_USERS_INFO: str
  MIRROR_FETCH_IN_PROGRESS: str
  MIRROR_FETCH_FAILURE: str
  MIRROR_FETCH_SUCCESS: str
  SERVER_INFO: str
  SERVER_INFO_UPDATE_SUCCESS: str
  SERVER_INFO_UPDATE_FAILURE: str
  ACCESS_INFO: str
  ACCESS_KEYS_ADD_SUCCESS: str
  ACCESS_KEYS_ADD_FAILURE: str
  ACCESS_KEYS_ADD_NOTIFICATION: str
  ACCESS_KEYS_EDIT_SUCCESS: str
  ACCESS_KEYS_EDIT_FAILURE: str
  ACCESS_KEYS_REMOVE_SUCCESS: str
  ACCESS_KEYS_REMOVE_FAILURE: str
  ACCESS_KEYS_REMOVE_NOTIFICATION: str

def load_l10n_table(lang: str | L10nTable = None) -> L10nTable:
  if (isinstance(lang, dict)):
    return lang

  lang = lang or DEFAULT_LANGUAGE_CODE
  root_dir = path.dirname(path.dirname(path.abspath(__file__)))
  lang_directory = path.join(root_dir, "resources", "lang")

  lang_filename = path.join(lang_directory, f"{lang}.json")
  if not path.isfile(lang_filename):
    lang_candidates = glob.glob(f"{lang}*.json", root_dir=lang_directory)
    lang_filename = path.join(lang_directory, next(iter(lang_candidates), ""))

  if path.isfile(lang_filename):
    with open(lang_filename, "r") as lang_file:
      return json.load(lang_file)

  if lang != DEFAULT_LANGUAGE_CODE:
    return load_l10n_table(DEFAULT_LANGUAGE_CODE)

  raise ValueError(f"invalid language code: {lang}")
