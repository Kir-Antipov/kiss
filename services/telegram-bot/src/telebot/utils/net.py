import hashlib
import inspect
import json
import ssl
from tornado.httpserver import HTTPServer
from tornado.routing import AnyMatches
from tornado.web import Application, RequestHandler
from typing import Any, Callable

class FingerprintSSLSocket(ssl.SSLSocket):
  def do_handshake(self, block: bool = False) -> None:
    super().do_handshake(block=block)
    self.verify_fingerprint()

  def verify_fingerprint(self) -> None:
    cert_der = self.getpeercert(binary_form=True)
    fingerprint = cert_der and hashlib.sha256(cert_der).digest() or bytes()
    if fingerprint != self.context.fingerprint:
      raise ssl.SSLCertVerificationError(f"invalid fingerprint: '{fingerprint.hex()}'")

class FingerprintSSLContext(ssl.SSLContext):
  def __new__(cls, protocol: int, fingerprint: str | bytes,  *args, **kwargs):
    context = super().__new__(cls, protocol, *args, **kwargs)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.sslsocket_class = FingerprintSSLSocket
    if isinstance(fingerprint, str):
      context.fingerprint = bytes.fromhex(fingerprint.replace(":", " "))
    else:
      context.fingerprint = bytes(fingerprint)
    return context

def create_ssl_context(fingerprint: str | bytes = None, **kwargs) -> ssl.SSLContext:
  if fingerprint:
    return FingerprintSSLContext(ssl.PROTOCOL_TLS_CLIENT, fingerprint)
  else:
    return ssl.create_default_context(**kwargs)


class DelegateRequestHandler(RequestHandler):
  def initialize(self, delegate: Callable[[str, str], Any]) -> None:
    self.delegate = delegate or (lambda _, __: None)

  def compute_etag(self) -> str | None:
    return None

  async def prepare(self) -> None:
    result = self.delegate(self.request.path, self.request.method)
    if inspect.isawaitable(result):
      result = await result

    if isinstance(result, tuple):
      response_value = result[0] if len(result) > 0 else ""
      response_code = int(result[1]) if len(result) > 1 else 0
      content_type = str(result[2]) if len(result) > 2 else ""
    else:
      response_value = result or ""
      response_code = 0
      content_type = ""

    if isinstance(response_value, dict):
      content = json.dumps(response_value)
      content_type = "application/json"
    else:
      content = str(response_value) if response_value is not None else ""

    self.set_status(response_code or (200 if content else 404))
    self.set_header("Access-Control-Allow-Origin", "*")
    self.set_header("Content-Type", content_type or "text/plain; charset=utf-8")
    self.write(bytes(content, "utf8"))
    self.finish()

def create_http_server(handler: Callable[[str, str], Any]) -> HTTPServer:
  return HTTPServer(Application([
    (AnyMatches(), DelegateRequestHandler, dict(delegate=handler)),
  ]))
