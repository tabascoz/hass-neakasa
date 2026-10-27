"""Keep published translations complete and unreviewed placeholders unpublished."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.neakasa.coordinator import CLOUD_SESSION_OWNERS

TRANSLATIONS_DIR = Path("custom_components/neakasa/translations")

# Every language Home Assistant itself offers (its frontend translation
# metadata plus `ne`, which core integrations ship). Only the published ones
# hold a real translation; the rest wait as English copies in the git-excluded
# PENDING_DIR until they are actually translated.
SUPPORTED_LANGUAGES = [
    "af",
    "ar",
    "bg",
    "bn",
    "bs",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "en-GB",
    "eo",
    "es",
    "es-419",
    "et",
    "eu",
    "fa",
    "fi",
    "fr",
    "fy",
    "ga",
    "gl",
    "gsw",
    "he",
    "hi",
    "hr",
    "hu",
    "hy",
    "id",
    "is",
    "it",
    "ja",
    "ka",
    "ko",
    "lb",
    "lt",
    "lv",
    "mk",
    "ml",
    "nb",
    "ne",
    "nl",
    "nn",
    "pl",
    "pt",
    "pt-BR",
    "ro",
    "ru",
    "sk",
    "sl",
    "sq",
    "sr",
    "sr-Latn",
    "sv",
    "ta",
    "te",
    "th",
    "tr",
    "uk",
    "ur",
    "vi",
    "zh-Hans",
    "zh-Hant",
]

PUBLISHED_LANGUAGES = ["de", "en", "fr", "pl", "pt", "pt-BR"]
PENDING_LANGUAGES = [
    language for language in SUPPORTED_LANGUAGES if language not in PUBLISHED_LANGUAGES
]

EXPECTED_FILES = sorted(f"{language}.json" for language in PUBLISHED_LANGUAGES)
PENDING_DIR = Path("tmp/translations")


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _collect_keys(obj: dict | list, prefix: str = "") -> set[str]:
    """Recursively collect all leaf key paths from a nested dict."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            keys.update(_collect_keys(v, path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            path = f"{prefix}[{i}]"
            keys.update(_collect_keys(item, path))
    else:
        keys.add(prefix)
    return keys


def test_translations_files_present() -> None:
    """Verify the expected translation files exist."""
    actual = sorted(p.name for p in TRANSLATIONS_DIR.glob("*.json"))
    assert actual == EXPECTED_FILES, (
        f"Translation files mismatch. Expected {EXPECTED_FILES}, got {actual}"
    )


def test_no_english_placeholder_is_published() -> None:
    """A file that is just an English copy must never ship in the published tree."""
    en_bytes = (TRANSLATIONS_DIR / "en.json").read_bytes()
    published = sorted(
        path.name for path in TRANSLATIONS_DIR.glob("*.json") if path.name != "en.json"
    )
    copies = [
        name for name in published if (TRANSLATIONS_DIR / name).read_bytes() == en_bytes
    ]
    assert not copies, f"English copies published: {copies}"


def test_pending_placeholders_stay_publishable() -> None:
    """Local scaffolding in the excluded dir must match en.json structurally."""
    pending = sorted(path.name for path in PENDING_DIR.glob("*.json"))
    if not pending:
        return
    expected = sorted(f"{language}.json" for language in PENDING_LANGUAGES)
    assert pending == expected, (
        f"Pending placeholders differ: expected {expected}, got {pending}"
    )

    en_keys = _collect_keys(_load_json(TRANSLATIONS_DIR / "en.json"))
    for name in pending:
        keys = _collect_keys(_load_json(PENDING_DIR / name))
        assert keys == en_keys, f"{name} key tree drifted from en.json"


def test_translations_symmetric_keys() -> None:
    """Every translation file must have identical tree structure to en.json."""
    en_data = _load_json(TRANSLATIONS_DIR / "en.json")
    en_keys = _collect_keys(en_data)

    for fname in EXPECTED_FILES:
        if fname == "en.json":
            continue
        lang_data = _load_json(TRANSLATIONS_DIR / fname)
        lang_keys = _collect_keys(lang_data)

        missing_in_lang = en_keys - lang_keys
        extra_in_lang = lang_keys - en_keys

        assert not missing_in_lang, (
            f"{fname} is missing keys: {sorted(missing_in_lang)}"
        )
        assert not extra_in_lang, (
            f"{fname} has extra keys not in en.json: {sorted(extra_in_lang)}"
        )


def test_translations_config_flow_keys() -> None:
    """Verify config-flow translation keys used in config_flow.py exist in en.json."""
    en_data = _load_json(TRANSLATIONS_DIR / "en.json")

    # Keys referenced in config_flow.py error messages
    required_error_keys = {"authentication", "connection", "no_devices_found"}
    actual_error_keys = set(en_data.get("config", {}).get("error", {}).keys())
    missing = required_error_keys - actual_error_keys
    assert not missing, f"en.json missing config.error keys: {missing}"

    # Abort keys
    required_abort_keys = {
        "authentication",
        "connection",
        "no_devices_found",
        "reauth_successful",
        "reconfigure_successful",
    }
    actual_abort_keys = set(en_data.get("config", {}).get("abort", {}).keys())
    missing_abort = required_abort_keys - actual_abort_keys
    assert not missing_abort, f"en.json missing config.abort keys: {missing_abort}"


def test_the_session_states_are_labelled_in_every_language() -> None:
    """Every state the account sensor can report has a label everywhere."""
    for name in EXPECTED_FILES:
        entity = _load_json(TRANSLATIONS_DIR / name)["entity"]["sensor"][
            "cloud_session_status"
        ]
        labels = entity["state"]
        assert sorted(labels) == sorted(CLOUD_SESSION_OWNERS), (
            f"{name}: states differ from what the sensor reports"
        )
        assert all(label.strip() for label in labels.values()), f"{name}: empty label"
        assert entity["state_attributes"]["options"]["state"] == labels, (
            f"{name}: the picker and the state disagree"
        )
