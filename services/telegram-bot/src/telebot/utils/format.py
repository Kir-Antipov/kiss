import html
import itertools
import numbers
import re
from collections.abc import Iterable, Sized

def _len(obj) -> int:
  if isinstance(obj, numbers.Number):
    return int(obj)
  if isinstance(obj, Sized):
    return len(obj)
  if isinstance(obj, Iterable):
    return itertools.count(obj)
  return 1 if obj else 0

def _to_dict(obj) -> dict:
  if obj is None or isinstance(obj, (str, numbers.Number)):
    return {}
  if isinstance(obj, dict):
    return obj
  return dict((x, getattr(obj, x)) for x in dir(obj) if not x.startswith("_"))

def _to_map(obj) -> "FormatMap":
  it = {"_": obj}
  it.update(_to_dict(obj))
  return FormatMap(it)


class Formattable:
  def __init__(self, value) -> None:
    self.value = value

  def __getattr__(self, name: str) -> "Formattable":
    if hasattr(self.value, name):
      return Formattable(getattr(self.value, name))
    else:
      return Formattable("")

  def __format__(self, format_spec: str) -> str:
    if not format_spec:
      return str(self.value)

    custom_format = format_spec[0]

    if custom_format == "?":
      format = format_spec[1:]
      return format.format_map(_to_map(self.value)) if self.value else ""

    elif custom_format == "!":
      format = format_spec[1:]
      return format.format_map(_to_map(self.value)) if not self.value else ""

    elif custom_format == ":":
      formats = format_spec[1:].split(":", maxsplit=1)
      truthy_format = formats[0]
      falsy_format = formats[1] if len(formats) > 1 else ""
      map_value = _to_map(self.value)
      return (truthy_format if self.value else falsy_format).format_map(map_value)

    elif custom_format == "*":
      format_end = (format_spec.find("*", 1) + 1) or 1
      separator = format_spec[1:format_end - 1]
      format = format_spec[format_end:]
      values = self.value if isinstance(self.value, Iterable) else [self.value]
      return separator.join(format.format_map(_to_map(x)) for x in values)

    elif custom_format == "\\":
      str_value = f"{self:{format_spec[1:]}}"
      return re.sub(r"<>(.*?)</>", lambda x: html.escape(x[1]), str_value)

    elif custom_format == "~":
      return f"{self.value:{format_spec[1:]}}"

    else:
      return f"{self.value:{format_spec}}"


class FormatMap(dict):
  def __init__(self, obj) -> None:
    super().__init__(_to_dict(obj))

  def __getitem__(self, key: str) -> Formattable:
    if key in self:
      return Formattable(super().get(key))

    if key.endswith("(#)"):
      value = super().get(key[:-3], 0)
      return Formattable(_len(value))

    if key.endswith("(s?)"):
      value = super().get(key[:-4], 0)
      return Formattable(_len(value) != 1)

    return Formattable("")
