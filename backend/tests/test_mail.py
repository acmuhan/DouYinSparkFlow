import smtplib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db import Base
from backend.models import SystemSetting
from backend.services.mail import MailError, MailIn, SmtpUpdate, load_smtp, save_smtp, send_mail


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def config(**updates):
    return SmtpUpdate(**{
        "enabled": True, "host": "smtp.example.com", "port": 587,
        "username": "sender", "from_email": "sender@example.com",
        "password": "secret-password", **updates,
    })


def test_config_encrypted_and_password_preservation(db):
    output = save_smtp(db, config())
    db.commit()
    assert output.password_configured
    assert "password" not in output.model_dump()
    assert "secret-password" not in db.get(SystemSetting, "smtp").value_encrypted
    save_smtp(db, config(password=None))
    db.commit()
    assert load_smtp(db).password == "secret-password"
    with pytest.raises(ValueError):
        save_smtp(db, config(host="other.example.com", password=None))
    save_smtp(db, config(enabled=False, password=""))
    db.commit()
    assert load_smtp(db).password == ""


@pytest.mark.parametrize("security", ["STARTTLS", "SSL"])
def test_encrypted_send_order_and_recipient(db, monkeypatch, security):
    save_smtp(db, config(security=security))
    db.commit()
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, **kwargs):
            calls.append("connect")
            assert host == "smtp.example.com"
            assert kwargs["timeout"] == 15
            if security == "SSL":
                assert kwargs["context"].check_hostname

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self, *, context):
            assert context.check_hostname
            calls.append("tls")

        def login(self, username, password):
            assert (username, password) == ("sender", "secret-password")
            calls.append("login")

        def send_message(self, message, *, from_addr, to_addrs):
            calls.append("send")
            assert from_addr == "sender@example.com"
            assert to_addrs == ["recipient@example.com"]
            assert str(message["Subject"]) == "Test"
            return {}

    monkeypatch.setattr("backend.services.mail.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("backend.services.mail.smtplib.SMTP_SSL", FakeSMTP)
    message_id = send_mail(db, "recipient@example.com", MailIn(subject="Test", body="Message"))
    assert message_id.startswith("<")
    assert calls == (["connect", "ehlo", "tls", "ehlo", "login", "send"] if security == "STARTTLS" else ["connect", "login", "send"])


def test_disabled_and_transport_failures_are_safe(db, monkeypatch):
    with pytest.raises(MailError):
        send_mail(db, "recipient@example.com", MailIn(subject="Test", body="Message"))
    save_smtp(db, config())
    db.commit()

    def fail(*_, **__):
        raise smtplib.SMTPAuthenticationError(535, b"secret-password")

    monkeypatch.setattr("backend.services.mail.smtplib.SMTP", fail)
    with pytest.raises(MailError) as error:
        send_mail(db, "recipient@example.com", MailIn(subject="Test", body="Message"))
    assert "secret-password" not in str(error.value)


def test_header_injection_rejected():
    with pytest.raises(ValueError):
        MailIn(subject="Subject\r\nBcc: other@example.com", body="Message")
    with pytest.raises(ValueError):
        config(from_email="sender@example.com\nBcc: other@example.com")
