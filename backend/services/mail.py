import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from ..crypto import decrypt_secret, encrypt_secret
from ..models import SystemSetting
from .scheduling import utc_now


class SmtpSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    host: str = Field(default="", max_length=253, pattern=r"^[a-zA-Z0-9.-]*$")
    port: int = Field(default=587, ge=1, le=65535)
    security: Literal["STARTTLS", "SSL"] = "STARTTLS"
    username: str = Field(default="", max_length=254)
    from_email: str = Field(default="", max_length=254)

    @field_validator("from_email")
    @classmethod
    def sender_email(cls, value: str) -> str:
        value = value.strip()
        if value and (value.count("@") != 1 or any(c.isspace() or c in "<>,;:" for c in value)
                      or value.startswith("@") or value.endswith("@")):
            raise ValueError("invalid sender address")
        return value


class SmtpUpdate(SmtpSettings):
    # Omitted means preserve; empty means explicitly clear.
    password: str | None = Field(default=None, max_length=1024)


class SmtpOut(SmtpSettings):
    password_configured: bool = False


class MailIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=160, pattern=r"^[^\r\n]+$")
    body: str = Field(min_length=1, max_length=20000)


class MailError(Exception):
    pass


def load_smtp(db: Session) -> SmtpUpdate:
    row = db.get(SystemSetting, "smtp")
    return SmtpUpdate.model_validate_json(decrypt_secret(row.value_encrypted)) if row else SmtpUpdate()


def smtp_public(config: SmtpUpdate) -> SmtpOut:
    return SmtpOut(**config.model_dump(exclude={"password"}), password_configured=bool(config.password))


def save_smtp(db: Session, payload: SmtpUpdate) -> SmtpOut:
    old = load_smtp(db)
    if payload.password is None:
        if (old.host, old.port, old.security, old.username) != (payload.host, payload.port, payload.security, payload.username) and old.password:
            raise ValueError("SMTP connection changed; enter the password again")
        payload = payload.model_copy(update={"password": old.password})
    if payload.enabled and (not payload.host or not payload.from_email or (payload.username and not payload.password)):
        raise ValueError("Enabled SMTP requires host, sender, and credentials when authenticating")
    row = db.get(SystemSetting, "smtp")
    if row is None:
        row = SystemSetting(key="smtp")
        db.add(row)
    row.value_encrypted = encrypt_secret(payload.model_dump_json())
    row.updated_at = utc_now()
    return smtp_public(payload)


def send_mail(db: Session, recipient: str, payload: MailIn) -> str:
    config = load_smtp(db)
    if not config.enabled or not config.host or not config.from_email:
        raise MailError("SMTP 尚未启用或配置不完整")
    message = EmailMessage()
    message["From"] = config.from_email
    message["To"] = recipient
    message["Subject"] = payload.subject
    message["Date"] = formatdate(localtime=False)
    message_id = make_msgid()
    message["Message-ID"] = message_id
    message.set_content(payload.body)
    context = ssl.create_default_context()
    try:
        connection = (smtplib.SMTP_SSL(config.host, config.port, timeout=15, context=context)
                      if config.security == "SSL" else smtplib.SMTP(config.host, config.port, timeout=15))
        with connection as smtp:
            if config.security == "STARTTLS":
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
            if config.username:
                smtp.login(config.username, config.password or "")
            refused = smtp.send_message(message, from_addr=config.from_email, to_addrs=[recipient])
            if refused:
                raise MailError("SMTP 拒绝收件人")
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        # Never expose server replies, which may include credentials or content.
        raise MailError("SMTP 发送未确认，请检查配置；不要直接重发，以免重复投递") from None
    return message_id
