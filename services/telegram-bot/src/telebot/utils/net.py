import hashlib
import ssl

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
