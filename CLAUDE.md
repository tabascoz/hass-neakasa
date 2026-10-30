# CLAUDE.md

Guidance for Claude Code agents working in this repository.

## Always read `CODE_STYLE.md` first

Before creating, renaming or restructuring any file/class/function, **read
[`CODE_STYLE.md`](./CODE_STYLE.md)**. It is the single source of truth for
conventions: language, file organisation, naming, typing, docstrings,
comments, translations, commit messages, release records, lint workflow.

A `v<version>` tag is an annotated tag whose message **is** the release record, and
the GitHub release reuses that same text. §Release records in `CODE_STYLE.md` fixes
its style, and the newest tag is the exemplar — read it (`git cat-file tag v<latest>`)
before writing one, and follow that style unless the user says something different.

For user-facing topics (what's included, how to install, supported devices),
see [`README.md`](./README.md).

## Operational rules live in `.clinerules`

Alongside the style/architecture documents (`CODE_STYLE.md`, `CLAUDE.md`),
this checkout may carry a root `.clinerules` file — the agent-facing layer on
top of them: the gate command and its order, when publishing is allowed, the
deploy-and-verify loop on the Home Assistant box, the probe and scratch
discipline, and the shell timings this project uses. It is git-excluded on
purpose (rules for agents, not part of the shipped integration), so a fresh
clone will not have it. Read it when present; where it and these documents
disagree, these documents win.

## Verification workflow

**After every code change, always run lint then tests, in that order, before
declaring the task done:**

```bash
uv run ruff format . && uv run ruff check . --fix && uv run mypy custom_components/neakasa && uv run pytest
```

- The lint commands run `ruff format`, `ruff check --fix` and `mypy` (config
  in `pyproject.toml`). Fix any failure and re-run before moving on.
- Both gates mirror CI.

## Architecture

The integration follows the HA `DataUpdateCoordinator` + `entry.runtime_data` pattern. There is
**one config entry per account**; every device that account holds is discovered at runtime, and each
platform adds its entities from the coordinator's payload. Current layout:

```
config_flow.py     → single-step credentials, VERSION = 2, unique_id `account:{username}`;
                     async_step_user / async_step_reauth / async_step_reauth_confirm / async_step_reconfigure
options_flow.py    → scan_interval (10–300 s, default 60) and stats_lookback_days (1–30 d, default 7)
__init__.py        → async_migrate_entry for pre-V2 entries, creates the coordinator, forwards to platforms,
                     clears the shared client on unload
api_manager.py     → shared client cache keyed by credentials (`_shared_clients`, `_shared_locks`)
                     and the get_shared_api / clear_shared_api / force_reconnect_api helpers
api_client.py      → NeakasaApiClient facade — call context per request, translates low-level
                     failures into the typed errors under exceptions/
api.py             → NeakasaAPI — sign-in, device list, properties, records, property and service writes
iot_gateway.py     → async Aliyun IoT Gateway client (aiohttp + manual HMAC-SHA256 signing);
                     this replaced the alibabacloud SDKs and the vendored client.py
api_encryption.py  → AES-CBC helpers for login-token decryption
coordinator.py     → NeakasaCoordinator(DataUpdateCoordinator[NeakasaPayload]) with
                     NeakasaPayload = dict[iot_id, NeakasaDeviceSnapshot]; per-device ValueCacher
                     caches, state fingerprints for "did the model change", and the write helpers
                     (set_property, invoke_service, feed_once)
data/              → typed shapes: NeakasaConfigData, NeakasaConfigEntry, NeakasaData
                     (what entry.runtime_data holds), Json* aliases
exceptions/        → one file per error class: api_client_error plus
                     authentication / communication / device-busy / session-expired
value_cacher.py    → time-based cache with refresh and discard windows
base_entity.py     → write_state_if_changed: an unchanged device model writes no entity state
log_redact.py      → journal redaction — account, device and entry names become stable hashes
const.py           → DOMAIN, SUPPORTED_CATEGORY_KEYS = {"CatLitter", "petFeeder"}, feed/portion bounds
diagnostics.py     → integration diagnostics for the config entry
brand/             → icon.png, icon@2x.png, logo.png, logo@2x.png
sensor/ switch/ button/ binary_sensor/ number/ select/ text/
                     → one class per entity per file (e.g. sensor/sand_percent.py, switch/auto_clean.py);
                       the package __init__.py adds account-level entities once per entry and
                       per-device entities chosen by snap.category_key, re-discovered through
                       coordinator.async_add_listener
translations/      → en, de, es, fr, pl, pt, pt-BR JSON
quality_scale.yaml → per-rule record of the HA code-quality checklist (done / exempt + why)
```

### No external SDK

Nothing outside Home Assistant is required at runtime: `manifest.json` declares
`"requirements": []`. The old `alibabacloud_iot_api_gateway` + `alibabacloud_tea_util`
dependency and the 296-line vendored `client.py` were removed in the `v1.4.0` line — all HTTP
now goes through an HA-managed `aiohttp.ClientSession` in `iot_gateway.py`, with the
HMAC-SHA256 signing done here. `grep -rn alibabacloud custom_components` matches only the
`iot_gateway.py` docstring that says what it replaced.

### Config entry and data flow

One step only: username + password. Devices are **not** picked in the config flow; the
coordinator lists every device the account reports in a supported category and the platform
packages discover entities from that payload. `async_migrate_entry` in `__init__.py` rewrites
older entries to V2. `entry.runtime_data` holds `NeakasaData(coordinator=…)`; no state lives in
`hass.data`.

### Coordinator data

`NeakasaCoordinator.async_update_data()` returns `NeakasaPayload` — `dict[iot_id,
NeakasaDeviceSnapshot]`, one snapshot per device, fetched concurrently. Properties, records and
the device list each have their own `ValueCacher`; entity state is only written when the
snapshot's fingerprint changes (`state_fingerprint`).

## Modernization waves (the `v1.4.0` line) — finished

The 2026-08-26 → 2026-08-27 restructuring was modelled on the **shape** of
[roquerodrigo/ha-neakasa-litterbox](https://github.com/roquerodrigo/ha-neakasa-litterbox)
— an independent Neakasa M1 integration built on its companion
[neakasa-litterbox-sdk](https://pypi.org/project/neakasa-litterbox-sdk/). That project had
already reached the structure this one was heading for, and its tree is where the wave order
came from. [`README.md`](./README.md) credits it in *Credits and Related Projects*.

| wave | what it moved | commit on `main` | shipped in |
|---|---|---|---|
| wave 0 | project tooling (`pyproject.toml`, pre-commit, `.editorconfig`, `CODE_STYLE.md`, `CLAUDE.md`), `exceptions/` package, `quality_scale.yaml` | `f7ed289a8f8d72656da542853392808a249787d7` | `v1.4.0-beta1` |
| wave 1 | `data/` package, `entry.runtime_data`, `diagnostics.py` | `7e2a64d9be6b63a0a1784e3292067df771d163d0` | `v1.4.0-beta2` |
| wave 2 | `NeakasaApiClient` facade with the typed error hierarchy | `32b55120b7583bee6b69e669b5ec3ac432160e25` | `v1.4.0-beta2` |
| wave 3 | multi-device coordinator (`NeakasaPayload`), single-step config flow, options flow | `0cbfc71feb624463eff1af87c36efa496ee229bd` | `v1.4.0-beta3` |
| wave 4 | one class per entity, platform packages per `CODE_STYLE.md` | `436c2e9c100073a4c6f939355a0971899633b200` | `v1.4.0-beta4` |
| wave 5 | reauth flow, reconfigure flow, exponential backoff | `44f9ba46e923548499f0354b038a2ef6d4c2abf1` | `v1.4.0-beta4` |
| final step | async-native IoT gateway, zero Aliyun SDK dependencies | `d7816981c5df808c27050eed3627807b0e6d09e7` | `v1.4.0-beta5` |

Waves 1 and 2 carry no `waveN` scope in their subject, so the tag notes on `v1.4.0-beta1`
… `v1.4.0-beta5` ("waves 0+1+2 — tooling, data package, entry.runtime_data, …") are the
record of the order. There was never a PR for this work: it was pushed straight to `main`,
so any pointer to a "PR description" is dead — read this table instead.

Nothing was taken *from* that project: no file, class, string or commit of theirs is in this
tree, the two repositories share no history, and this integration keeps its own cloud client
(`iot_gateway.py`, `aiohttp` + manual signing) instead of their SDK and MQTT push client.
It is inspiration for the architecture, not a dependency, and not something users need.