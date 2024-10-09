import asyncio
from aioimaplib import IMAP4_SSL
from aiosmtplib import SMTP
from datetime import datetime
from email import message_from_bytes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable
from utils.url import extract_url

class Message:
  def __init__(
      self, sender="", to: str | Iterable[str] = "", subject="",
      body="", html_body="", date: datetime = None) -> None:
    self.sender = sender
    self.to = to if isinstance(to, str) else ", ".join(to)
    self.subject = subject
    self.body = body
    self.html_body = html_body
    self.date = date or datetime.now()

  @staticmethod
  def from_bytes(bytes: bytes | bytearray) -> "Message":
    msg = message_from_bytes(bytes)
    sender = msg["From"]
    to = msg["To"]
    subject = msg["Subject"]
    try:
      date = datetime.strptime(msg["Date"], "%a, %d %b %Y %H:%M:%S %z")
    except:
      date = datetime.min

    body = ""
    html_body = ""
    if msg.is_multipart():
      for part in msg.get_payload():
        content_type = part.get_content_type()
        content_disposition = part.get_content_disposition()
        if content_type == "text/plain" and not content_disposition:
          body += part.get_payload(decode=True).decode("utf-8")
        elif content_type == "text/html" and not content_disposition:
          html_body += part.get_payload(decode=True).decode("utf-8")
    else:
      body = msg.get_payload(decode=True).decode("utf-8")

    return Message(sender, to, subject, body, html_body, date)

class Mail:
  def __init__(
      self, user="", password="", host="", *,
      smtp_user="", smtp_password="", smtp_host="", smtp_port=587,
      imap_user="", imap_password="", imap_host="", imap_port=993) -> None:
    host = user.split("@")[1] if "@" in user else ""

    smtp_user = smtp_user or user or ""
    smtp_base = host or (smtp_user.split("@")[1] if "@" in smtp_user else "")
    self.smtp_user = smtp_user
    self.smtp_password = smtp_password or password or ""
    self.smtp_host = smtp_host or (f"smtp.{smtp_base}" if smtp_base else "")
    self.smtp_port = smtp_port

    imap_user = imap_user or user or ""
    imap_base = host or (imap_user.split("@")[1] if "@" in imap_user else "")
    self.imap_user = imap_user
    self.imap_password = imap_password or password or ""
    self.imap_host = imap_host or (f"imap.{imap_base}" if imap_base else "")
    self.imap_port = imap_port

  async def send(self, message: Message) -> None:
    msg = MIMEMultipart()
    msg.preamble = message.subject
    msg["Subject"] = message.subject
    msg["From"] = message.sender or self.smtp_user
    msg["To"] = message.to
    if message.html_body:
      msg.attach(MIMEText(message.html_body, "html", "utf-8"))
    if message.body or not message.html_body:
      msg.attach(MIMEText(message.body or "", "plain", "utf-8"))

    smtp = SMTP()
    await smtp.connect(hostname=self.smtp_host, port=self.smtp_port)
    await smtp.login(self.smtp_user, self.smtp_password) if self.smtp_user else None
    await smtp.send_message(msg)
    await smtp.quit()

  async def receive(self, *criteria: str, mailbox="INBOX", delete=True, timeout=300.0) -> list[Message]:
    return await asyncio.wait_for(self._receive(*criteria, mailbox=mailbox, delete=delete), timeout=timeout)

  async def _receive(self, *criteria: str, mailbox: str, delete: bool) -> list[Message]:
    imap = IMAP4_SSL(host=self.imap_host, port=self.imap_port)
    await imap.wait_hello_from_server()
    await imap.login(self.imap_user, self.imap_password) if self.imap_user else ""
    await imap.select(mailbox)

    while True:
      status, id_data = await imap.search(*criteria)
      ids: list[str] = id_data[0].decode("utf-8").split() if status == "OK" else []
      if ids:
        break

      idle = await imap.idle_start(timeout=10)
      await imap.wait_server_push()
      imap.idle_done()
      await asyncio.wait_for(idle, 10)

    messages: list[Message] = []
    for id in ids:
      status, msg_data = await imap.fetch(id, "(RFC822)")
      if status != "OK": continue
      if delete: await imap.store(id, "+FLAGS", "\\Deleted")
      messages.append(Message.from_bytes(msg_data[1]))

    await imap.logout()
    return messages

async def request_url(mail: Mail, address: str, timeout: int) -> str | None:
  try:
    await mail.send(Message(to=address))
    messages = await mail.receive(f"(UNSEEN FROM \"{address}\")", timeout=timeout)
    message = messages and messages[-1].body
    return extract_url(message)
  except:
    return None
