# CLAUDE.md

Guidance for Claude Code agents working in this repository.

## Always read `CODE_STYLE.md` first

Before creating, renaming or restructuring any file/class/function, **read
[`CODE_STYLE.md`](./CODE_STYLE.md)**. It is the single source of truth for
conventions: language, file organisation, naming, typing, docstrings,
comments, translations, lint workflow.

For user-facing topics (what's included, how to install, supported devices),
see [`README.md`](./README.md).

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

The integration follows the HA `DataUpdateCoordinator` pattern:

```
config_flow.py    → validates credentials and creates the ConfigEntry
__init__.py       → instantiates the shared API, creates the coordinator, forwards to platforms
coordinator.py    → polls every 60s; returns NeakasaAPIData dataclass
api.py            → NeakasaAPI — authentication, Aliyun IoT gateway, device properties, records
client.py         → Custom HTTP client with Aliyun API Gateway HMAC signing
api_encryption.py → AES-CBC encryption helpers for login token decryption
value_cacher.py   → Time-based cache with refresh/discard windows
sensor.py         → All sensor entities (generic NeakasaSensor, NeakasaMapSensor, NeakasaTimestampSensor, NeakasaCatSensor)
switch.py         → NeakasaSwitch — generic switch with optional dict subkey support
button.py         → NeakasaButton — triggers clean/level services
binary_sensor.py  → NeakasaBinarySensor — e.g. bin_full
```

### API dependency

The integration depends on `alibabacloud_iot_api_gateway` and
`alibabacloud_tea_util` (the Alibaba Cloud "Tea" framework). The custom
`client.py` wraps Aliyun API Gateway HMAC signing. The long-term plan
is to isolate or replace this with a dedicated SDK package.

### Shared API pattern

`__init__.py` maintains `_shared_apis: dict[str, NeakasaAPI]` and
`_shared_locks: dict[str, asyncio.Lock]` keyed by `"username:password"`.
Multiple config entries for the same account share one authenticated API
instance. This is a transitional pattern — the goal is single-entry
multi-device architecture.

### Config flow

Two-step: username/password → device picker (filtered to `CatLitter` devices).
Each device gets its own config entry with `iotId` as unique_id.
Account-level dedup uses `account:{email}`.

### Coordinator data

`NeakasaCoordinator.data` returns `NeakasaAPIData` — a single flat dataclass
with ~20 fields covering device properties + cat/record lists. Properties
are cached for 30min via `ValueCacher`; records are cached for 30min and
invalidated when `lastUse` changes.

## Wave migration plan

This integration is being incrementally modernised against the reference
implementation at `ha-neakasa-litterbox`. See the Wave plan in the PR
description for the ordered migration steps.