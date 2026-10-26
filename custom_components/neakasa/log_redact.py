"""Journal redaction: the account's own words never reach the log."""

from __future__ import annotations

import hashlib
import re

# One prefix per kind of thing the log names in place of the real value. Each
# replacement is a hash, so one account, one machine and one config entry keep
# one word across a whole run: the counts the instrument exists for - sign-ins,
# presentations, writes, feeds - stay attributable once the names are gone.
_ACCOUNT_PREFIX = "acct-"
_DEVICE_PREFIX = "dev-"
_ENTRY_PREFIX = "entry-"
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
# An iotId named inside quoted cloud text (`iotId=…`, `"iotId":"…"`): it gets the
# same label the machine lines use rather than being dropped, so which machine a
# rejection was about stays readable. Runs before the opaque rule, which would
# otherwise swallow a 24-character iotId.
_DEVICE_PAIR = re.compile(
    r"[\"']?iot_?[Ii][Dd][\"']?\s*[:=]\s*[\"']?([A-Za-z0-9]{8,})[\"']?"
)
# Anything long enough and closed-shaped enough to be an opaque value: a
# signature, a session token, an encoded body. `=` stays out of the class so a
# `name=value` keeps its name and only the value is dropped.
_OPAQUE_RUN = re.compile(r"[A-Za-z0-9+/_-]{20,}")


def _label_of(value: str, prefix: str) -> str:
    """Return the label *value* is logged as, keyed by *prefix*."""
    digest = hashlib.blake2s(value.strip().lower().encode(), digest_size=4).hexdigest()
    return f"{prefix}{digest}"


def account_label(username: str) -> str:
    """
    Return the label to log an account by in place of its login.

    The label is a hash of the login, normalised the way the config entry's
    unique_id is (`account:{username.lower()}` in config_flow.py), so the same
    account is the same label in every line and in every run: an experiment
    that counts this account's sign-ins, or that watches two accounts against
    each other, is still readable end to end. Nothing of the login survives.
    """
    return _label_of(username, _ACCOUNT_PREFIX)


def device_label(identifier: str) -> str:
    """
    Return the label to log a machine by in place of its iotId or wire name.

    A machine is named in the log by two of its own identifiers: the iotId the
    cloud and the device registry use, and the wire `deviceName`, which on both
    units measured is the machine's serial (`JQ01909G25430010947`,
    `WL03002G26270011577`). They say which of the household's machines a read,
    a write or a feed was about, and that is what the counters need - so the
    replacement is a hash of the identifier, one word per machine, and it
    survives a rename in the app because the iotId does not change.
    """
    return _label_of(identifier, _DEVICE_PREFIX)


def entry_label(config_entry_id: str) -> str:
    """
    Return the label to log a config entry by in place of its id.

    Home Assistant puts the id in its own lines the moment we name anything after
    the entry: the update manager prints `Finished fetching <name> data in …`, and
    a reauth or a migration line names the entry. Masking here is what keeps an
    integration that never says the account's login from spelling out which of its
    entries a line belongs to, while two entries stay two words.
    """
    return _label_of(config_entry_id, _ENTRY_PREFIX)


def redact_text(value: object) -> str:
    """
    Return *value* with the account's and its machines' words removed.

    Lines that quote what the cloud said - a rejected message, an undecoded
    body - carry fields the integration does not choose, and the login answer
    is where the account itself is: its email, nickname and phone, its tokens.
    An email-shaped word becomes the label the rest of the journal uses, an iotId
    named in the text becomes that machine's label, and the account's other named
    fields and anything opaque are dropped.
    """
    text = _EMAIL_SHAPE.sub(
        lambda match: _label_of(match.group(), _ACCOUNT_PREFIX), str(value)
    )
    text = _DEVICE_PAIR.sub(lambda match: f"iotId={device_label(match.group(1))}", text)
    text = _CREDENTIAL_PAIR.sub(_CREDENTIAL_PLACEHOLDER, text)
    return _OPAQUE_RUN.sub(_OPAQUE_PLACEHOLDER, text)
