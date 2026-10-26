"""Tests for log_redact."""

from __future__ import annotations

from custom_components.neakasa.log_redact import account_label, redact_text

_LOGIN_BODY = (
    '{"code":0,"data":{"login_token":"abcdefghij0123456789KLMNOPQRST",'
    '"user_info":{"email":"tabascoz@gmail.com","nick_name":"Fernando",'
    '"ali_authentication_token":"ghijkl0123456789MNOPQRSTUVWX"}}}'
)


def test_the_label_is_short_and_carries_no_login() -> None:
    """An account is logged as a fixed-shape label, never as its email."""
    label = account_label("tabascoz@gmail.com")
    assert label.startswith("acct-")
    assert len(label) == 13
    assert "tabascoz" not in label
    assert "@" not in label


def test_one_account_keeps_one_label() -> None:
    """The label is a hash, so the same account is always the same label."""
    assert account_label("tabascoz@gmail.com") == account_label(
        "Tabascoz@Gmail.com ".strip().lower()
    )


def test_two_accounts_stay_two_series() -> None:
    """Watching two accounts is still possible once both are labels."""
    assert account_label("tabascoz@gmail.com") != account_label(
        "consultor.fcunha@gmail.com"
    )


def test_an_email_in_free_text_becomes_the_same_label() -> None:
    """A body that names the account lines up with its own log lines."""
    assert redact_text(
        "Reusing shared API client for consultor.fcunha@gmail.com"
    ) == "Reusing shared API client for " + account_label("consultor.fcunha@gmail.com")


def test_a_login_answer_keeps_its_shape_and_loses_its_values() -> None:
    """The fields the cloud echoes back stay, the account's words do not."""
    redacted = redact_text(_LOGIN_BODY)
    assert "tabascoz" not in redacted
    assert "abcdefghij0123456789KLMNOPQRST" not in redacted
    assert "ghijkl0123456789MNOPQRSTUVWX" not in redacted
    assert "Fernando" not in redacted
    assert '"code":0' in redacted
    assert "user_info" in redacted


def test_a_cloud_phrase_is_left_whole() -> None:
    """Naming a rejection is the measurement; redacting it would break it."""
    assert redact_text("identityId is blank") == "identityId is blank"
    assert redact_text("TokenInvalid: token is abnormal") == (
        "TokenInvalid: token is abnormal"
    )


def test_an_opaque_value_is_dropped_without_a_label() -> None:
    """A signed header or session token has no name to keep, only length."""
    assert redact_text("sid=abcdefghij0123456789KLMNOP") == "sid=[redacted]"
