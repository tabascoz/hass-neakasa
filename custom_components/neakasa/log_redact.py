"""Journal redaction: the account's own words never reach the log."""

from __future__ import annotations

import hashlib
import re

# What the account is logged as instead of its login: the login is an email in
# every account the app has, and the instrument that counts sign-ins and
# presentations has to be read per account, so the replacement keeps being
# *one* thing per account rather than becoming blank.
_LABEL_PREFIX = "acct-"
_CREDENTIAL_PLACEHOLDER = "[credential]"
_OPAQUE_PLACEHOLDER = "[redacted]"

# A login-shaped run of characters: what the cloud echoes back about an account.
_EMAIL_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# A named value that belongs to the account rather than to a machine. The names
# are the ones `api.py:_describe_fields` measured in the login answer on 2026-10-26
# (`avatar`, `nick_name`, `phone`, `user_name`, `last_login_ip`, the tokens);
# `email` is absent on purpose, the label rule above gives it a name that stays
# the same in every other line. Keywords stay lower-case so a cloud message
# saying `TokenInvalid:` is left whole and readable.
_CREDENTIAL_PAIR = re.compile(
    r"[\"']?[A-Za-z_]*(?:token|secret|password|auth_?code|api_?key|"
    r"nick_?name|user_?name|avatar|phone|last_login_ip)[A-Za-z_]*[\"']?"
    r"\s*[:=]\s*[\"']?[^\s\"',}]+[\"']?"
)
# Anything long enough and closed-shaped enough to be an opaque value: a
# signature, a session token, an encoded body. `=` stays out of the class so a
# `name=value` keeps its name and only the value is dropped.
_OPAQUE_RUN = re.compile(r"[A-Za-z0-9+/_-]{20,}")


def _label_of(value: str) -> str:
    """Return the label an account name is logged as."""
    digest = hashlib.blake2s(value.strip().lower().encode(), digest_size=4).hexdigest()
    return f"{_LABEL_PREFIX}{digest}"


def account_label(username: str) -> str:
    """
    Return the label to log an account by in place of its login.

    The label is a hash of the login, normalised the way the config entry's
    unique_id is (`account:{username.lower()}` in config_flow.py), so the same
    account is the same label in every line and in every run: an experiment
    that counts this account's sign-ins, or that watches two accounts against
    each other, is still readable end to end. Nothing of the login survives.
    """
    return _label_of(username)


def redact_text(value: object) -> str:
    """
    Return *value* with the account's own words removed.

    Lines that quote what the cloud said - a rejected message, an undecoded
    body - carry fields the integration does not choose, and the login answer
    is where the account itself is: its email, nickname and phone, its tokens.
    An email-shaped word becomes the same label the rest of the journal uses,
    so a body that mentions the account still lines up with its sign-ins;
    the account's other named fields and anything opaque are dropped.
    """
    text = _EMAIL_SHAPE.sub(lambda match: _label_of(match.group()), str(value))
    text = _CREDENTIAL_PAIR.sub(_CREDENTIAL_PLACEHOLDER, text)
    return _OPAQUE_RUN.sub(_OPAQUE_PLACEHOLDER, text)
