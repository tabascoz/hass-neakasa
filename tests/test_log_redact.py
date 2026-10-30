"""Tests for log_redact."""

from __future__ import annotations

from custom_components.neakasa.log_redact import (
    account_label,
    device_label,
    entry_label,
    redact_entity_id,
    redact_text,
)

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


def test_a_machine_is_logged_as_one_word_per_machine() -> None:
    """Which machine a call touched stays; its serial does not."""
    label = device_label("4TQDtRLglcQJ5goDNlug000000")
    assert label.startswith("dev-")
    assert "4TQD" not in label
    assert device_label("4TQDtRLglcQJ5goDNlug000000") == label
    assert device_label("EUZLwdsC7Kr8D6I3v0Km000000") != label


def test_a_wire_name_keeps_its_machine_label() -> None:
    """The same machine stays one word however it is named in a line."""
    assert device_label(" WL03002G26270011577 ") == device_label("wl03002g26270011577")


def test_an_entry_is_logged_as_one_word_per_entry() -> None:
    """Home Assistant prints the name we give it, so the id stays masked."""
    label = entry_label("01M0YRP208AK3WEBZ8DXJN2D7B")
    assert label.startswith("entry-")
    assert "01M0YRP" not in label
    assert entry_label("01M0YRP208AK3WEBZ8DXJN2D7B") != entry_label(
        "02N0YRP208AK3WEBZ8DXJN2D7B"
    )


def test_the_three_kinds_never_look_alike() -> None:
    """An account, a machine and an entry are distinguishable in the log."""
    assert account_label("x").startswith("acct-")
    assert device_label("x").startswith("dev-")
    assert entry_label("x").startswith("entry-")


def test_a_quoted_iot_id_becomes_the_machine_label() -> None:
    """A rejection that names a machine still says which one."""
    redacted = redact_text('{"iotId":"4TQDtRLglcQJ5goDNlug000000","code":0}')
    assert "4TQD" not in redacted
    assert device_label("4TQDtRLglcQJ5goDNlug000000") in redacted
    assert '"code":0' in redacted


def test_an_entity_id_keeps_its_entity_and_loses_its_serial() -> None:
    """Which entity presented stays countable; the machine becomes its label."""
    redacted = redact_entity_id(
        "switch.wl03002g26270011577_store_feed_as_machine_defaults",
        "4TQDtRLglcQJ5goDNlug000000",
    )
    assert redacted.startswith("switch." + device_label("4TQDtRLglcQJ5goDNlug000000"))
    assert "wl03002g26270011577" not in redacted
    assert "WL03002G26270011577" not in redacted
    assert redacted.endswith("_store_feed_as_machine_defaults")


def test_a_wire_name_renames_its_own_segment() -> None:
    """A machine renamed in the app still loses whatever word it left."""
    assert redact_entity_id(
        "switch.living_room_cat_store_feed_as_machine_defaults",
        "4TQDtRLglcQJ5goDNlug000000",
        "Living Room Cat",
    ) == (
        "switch."
        + device_label("4TQDtRLglcQJ5goDNlug000000")
        + "_store_feed_as_machine_defaults"
    )


def test_two_machines_stay_two_words_inside_entity_ids() -> None:
    """Two entities of one kind on two machines keep two labels."""
    feeder = redact_entity_id(
        "switch.wl03002g26270011577_store_feed_as_machine_defaults",
        "4TQDtRLglcQJ5goDNlug000000",
    )
    litter = redact_entity_id(
        "switch.jq01909g25430010947_auto_clean",
        "EUZLwdsC7Kr8D6I3v0Km000000",
    )
    assert device_label("4TQDtRLglcQJ5goDNlug000000") in feeder
    assert device_label("EUZLwdsC7Kr8D6I3v0Km000000") in litter
    assert "wl03002g26270011577" not in feeder
    assert "jq01909g25430010947" not in litter


def test_an_account_entity_id_is_left_whole() -> None:
    """No machine is named there, so there is no segment to replace."""
    assert (
        redact_entity_id(
            "sensor.neakasa_account_cloud_session_status",
            "4TQDtRLglcQJ5goDNlug000000",
        )
        == "sensor.neakasa_account_cloud_session_status"
    )


def test_a_value_that_is_not_an_entity_id_is_left_alone() -> None:
    """There is no segment here to replace, so the value stays as it is."""
    unchanged = redact_entity_id("wl03002g26270011577", "4TQDtRLglcQJ5goDNlug000000")
    assert unchanged == "wl03002g26270011577"
