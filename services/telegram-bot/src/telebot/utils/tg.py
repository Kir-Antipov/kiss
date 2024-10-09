from functools import partial
from inspect import Parameter, signature, isawaitable, isgenerator, isasyncgen
from telegram import Message, Update, User
from telegram.ext import CallbackContext

async def reply(update: Update, message) -> None:
  while isawaitable(message):
    message = await message

  if isgenerator(message) or isinstance(message, list):
    for part in message:
      await reply(update, part)
    return

  if isasyncgen(message):
    async for part in message:
      await reply(update, part)
    return

  if not (message and update and update.message):
    return

  if isinstance(message, str):
    await update.message.reply_text(message)
    return

  raise ValueError("could not determine a suitable method to send the message")


def create_parameter_factory(parameter: Parameter):
  hint = parameter.annotation
  parameter_type = hint if isinstance(hint, type) else type(hint)

  if parameter.name.startswith("user_"):
    field_name = parameter.name[5:]
    factory = lambda n: lambda u, _: u and u.message and getattr(u.message.from_user, n)
    return factory(field_name)

  elif issubclass(parameter_type, Update):
    return lambda u, _: u

  elif issubclass(parameter_type, CallbackContext):
    return lambda _, c: c

  elif issubclass(parameter_type, Message):
    return lambda u, _: u and u.message

  elif issubclass(parameter_type, User):
    return lambda u, _: u and u.message and u.message.from_user

  else:
    factory = lambda n, d, t: lambda _, c: t(c.match[n]) if c and c.match and c.match[n] is not None else d
    return factory(parameter.name, parameter.default, parameter_type)


def wrap_handler(handler, positional_factories, keyword_factories):
  async def wrapper(update: Update, context: CallbackContext):
    result = handler(
      *(f(update, context) for f in positional_factories),
      **{k: f(update, context) for k, f in keyword_factories.items()}
    )
    await reply(update, result)
  return wrapper

def prepare_handler(handler):
  keyword_args = {}
  if isinstance(handler, tuple):
    handler = partial(handler[0], *handler[1:])
  elif isinstance(handler, dict):
    keyword_args = {k: v for k, v in handler.items() if k != "_"}
    handler = partial(handler["_"], **keyword_args)

  sig = signature(handler)
  is_positional = (Parameter.POSITIONAL_ONLY,)
  positional_factories = [
    create_parameter_factory(p)
      for p in sig.parameters.values()
      if p.kind in is_positional
  ]
  is_keyword = (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
  keyword_factories = {
    p.name: create_parameter_factory(p)
      for p in sig.parameters.values()
      if p.kind in is_keyword and p.name not in keyword_args
  }
  return wrap_handler(handler, positional_factories, keyword_factories)
