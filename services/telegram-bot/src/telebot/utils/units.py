import datetime
import re

Unit = tuple[tuple[tuple[str, ...], float], ...]

def format_unit(value: float, unit: Unit, format_spec: str = None) -> str:
  format_spec = format_spec or ""
  abs_value = abs(value)
  units = (x for x in unit if x[1] <= abs_value)
  max_unit = max(units, key=lambda x: x[1], default=unit[0])
  unit_value = float(f"{value / max_unit[1]:{format_spec}}")

  value = unit_value * max_unit[1]
  abs_value = abs(value)
  units = (x for x in unit if x[1] <= abs_value)
  max_unit = max(units, key=lambda x: x[1], default=unit[0])
  unit_value = value / max_unit[1]

  unit_name = f" {max_unit[0][0]}" if max_unit[0][0] else ""
  return f"{unit_value:{format_spec}}{unit_name}"

def parse_unit(format: str, unit: Unit) -> float:
  try:
    match = re.match(r"^\s*([-+]?(?:\d*\.\d+|\d+))\s*(\S*)\s*$", format)
    value = float(match[1])
    unit_name = match[2].casefold()
    chosen_unit = next((u for u in unit if unit_name in (n.casefold() for n in u[0])))
    return value * chosen_unit[1]
  except:
    raise ValueError("could not convert string to the specified unit")


BYTE: Unit = (
  (("B", "byte", "bytes", ""), 1.0),
  (("kB", "kilobyte", "kilobytes"), 10.0**3),
  (("MB", "megabyte", "megabytes"), 10.0**6),
  (("GB", "gigabyte", "gigabytes"), 10.0**9),
  (("TB", "terabyte", "terabytes"), 10.0**12),
  (("PB", "petabyte", "petabytes"), 10.0**15),
  (("EB", "exabyte", "exabytes"), 10.0**18),
  (("ZB", "zettabyte", "zettabytes"), 10.0**21),
  (("YB", "yottabyte", "yottabytes"), 10.0**24),
  (("RB", "ronnabyte", "ronnabytes"), 10.0**27),
  (("QB", "quettabyte", "quettabytes"), 10.0**30),
)

class DataSpan(float):
  def __new__(cls, x=0.0) -> "DataSpan":
    if isinstance(x, str):
      x = parse_unit(x, BYTE)
    return super().__new__(cls, x)

  def __str__(self) -> str:
    return format_unit(float(self), BYTE)

  def __format__(self, format_spec: str) -> str:
    return format_unit(float(self), BYTE, format_spec)


SECOND: Unit = (
  (("seconds", "second", "sec", "s", ""), 1.0),
  (("minutes", "minute", "min", "m"), 60.0),
  (("hours", "hour", "h"), 60.0 * 60),
  (("days", "day", "d"), 60.0 * 60 * 24),
  (("weeks", "week", "w"), 60.0 * 60 * 24 * 7),
  (("months", "month", "mon"), 60.0 * 60 * 24 * 30),
  (("years", "year", "y"), 60.0 * 60 * 24 * 365),
)

class TimeSpan(datetime.timedelta):
  def __new__(
      cls, format: str = None, *, days=0.0, seconds=0.0, microseconds=0.0,
      milliseconds=0.0, minutes=0.0, hours=0.0, weeks=0.0) -> "TimeSpan":
    if isinstance(format, str):
      seconds = parse_unit(format, SECOND)
    return super().__new__(
      cls, days=days, seconds=seconds, microseconds=microseconds,
      milliseconds=milliseconds, minutes=minutes, hours=hours, weeks=weeks,
    )

  def __str__(self) -> str:
    return format_unit(self.total_seconds(), SECOND)

  def __format__(self, format_spec: str) -> str:
    return format_unit(self.total_seconds(), SECOND, format_spec)
