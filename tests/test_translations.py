"""Ensure translations keys are symmetric across all languages."""

from __future__ import annotations

import json
from pathlib import Path

TRANSLATIONS_DIR = Path("custom_components/neakasa/translations")

EXPECTED_FILES = sorted(["en.json", "de.json", "pl.json"])


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
