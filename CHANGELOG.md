# Changelog

This integration is released by hand: the tag `v<version>` **is** the release, the tag message is
the record of what shipped, and GitHub publishes the same text as the release notes. Version
numbers are the `manifest.json` version. `release-please-config.json` names this file
(`"changelog-path": "CHANGELOG.md"`) but no release-please workflow runs here, so this file is
the written record of the line — entries must keep matching the tags, newest first.

No `v1.2` was ever cut; the line goes `v1.1` → `v1.3.0`.

## [1.5.2](https://github.com/tabascoz/hass-neakasa/compare/v1.5.1...v1.5.2) (2026-10-30)

### Features

* **Food served today reads the machine it belongs to** — the control read the account's records,
  which belong to the litter box and answer an empty list for a feeder name, so it could only
  ever be Unknown. A pet feeder keeps its own meal records and they answer: on 2026-10-29 this
  unit returned 24 rows over 30 days, one inside the day running, 10 g solid and 9 g liquid, the
  figure the product's own day panel showed. The control reports what the machine served today,
  grouped by the day Home Assistant runs rather than UTC, states nothing for a day with no
  recorded meal and never counts a planned meal as served. The total is on by default, and the
  two halves are offered as separate controls that are off by default. The total also names the
  meals it grouped - each with its own moment - and the moment the rows were read with how long
  ago that was, because a grouped figure has to state its own age rather than pose as the
  present. The records path is asked at most once an hour per feeder, since a served meal states
  no signal that says read again, and the Refresh data now button reads it straight away.

### Fixes

* **The journal no longer spells out each machine's serial** — the lines that report an entity's
  state named the device by its wire name, which is the serial, so 1225 of the 1279 such lines
  measured on the unit on 2026-10-29 carried it. An entity's state line now keeps its platform
  prefix and its own name and names the machine with the same hash word the other lines already
  use, so the counts stay attributable per device and per control (2119 lines measured after, one
  keeping an older Home Assistant device word beside the label, none carrying a serial). Entity
  ids, unique ids, the entity registry and the cloud calls are unchanged by this change.

## [1.5.1](https://github.com/tabascoz/hass-neakasa/compare/v1.5.0...v1.5.1) (2026-10-29)

### Fixes

* **The integration sets up again on Home Assistant 2026.11** — one label that marks the
  settings and diagnostics controls is no longer where it was read from, so the entry failed
  and the devices showed with none of their controls (seen on the unit on 2026-10-29). It is
  now taken from where Home Assistant defines it; controls, names, ids and reports are
  unchanged, no cloud call is added, and older versions keep working.

## [1.5.0](https://github.com/tabascoz/hass-neakasa/compare/v1.4.2...v1.5.0) (2026-10-27)

### Features

* **Riko (wet meal feeder) is supported by default** — the whole `v1.5.0-beta1` … `v1.5.0-beta6`
  line, every part of it proved against a real machine, is carried into the first stable release
  of that line, so HACS hands Riko to users without opting in.
* **The bowl reports what it holds** — `0 g` is never presented as an empty bowl (`v1.5.0-beta6`),
  and the published value is the bowl's contents rather than the scale's raw reading.
* **Cloud session status** sensor says whether Home Assistant still holds the account session;
  a refused call cannot tell the mobile app holding the session from the session ageing out,
  so the sensor reports only what can be proved.

## [1.4.2](https://github.com/tabascoz/hass-neakasa/compare/v1.4.1...v1.4.2) (2026-10-21)

### Fixes

* **Configure / options flow opens again (#10)** — `OptionsFlow.config_entry` is read-only, so the
  flow no longer assigns it; `scan_interval` (10–300 s) and `stats_lookback_days` (1–30 d) change
  and the entry reloads with them.
* **Clean / Level buttons work again** — a blank `identityId` from the Aliyun gateway means the
  `iotToken` aged out; the request now refreshes the token and retries once, wire format unchanged.
* **Cat weight reports unknown** instead of a stale value when there is no recent record (#8).
* **French translation** (`fr.json`) added and made valid (#7, #9); journal output redacts the
  account email and device ids.
* CI pinned to Python 3.14 with `uv.lock` committed; the coverage gate moved 100% → 90% while a
  separate test run reached 100% and was enforced.

## [1.4.1](https://github.com/tabascoz/hass-neakasa/compare/v1.4.0...v1.4.1) (2026-09-12)

### Fixes

* **WiFi RSSI reported 0 dBm** — the v1.4.0 uplift renamed the wire key `WiFi_RSSI` → `WiFiRSSI`,
  which the cloud never returns. Reverted in `coordinator.py` and the test fixtures. Affected v1.4.0
  only.

## [1.4.0](https://github.com/tabascoz/hass-neakasa/compare/v1.3.1...v1.4.0) (2026-09-12)

The stable release of the modernization line. The line was cut in steps, each step tagged
`v1.4.0-betaN`; the tag messages name the wave numbers, and that is the authoritative record of
the order.

### Features

* **Modernization: the Aliyun SDKs are gone** — `alibabacloud_iot_api_gateway` and
  `alibabacloud_tea_util`, plus the 296-line vendored `client.py`, replaced by an async-native
  `iot_gateway.py` client (plain `aiohttp`, manual HMAC-SHA256 signing).
* **Typed exception hierarchy** — `NeakasaApiClientAuthenticationError`,
  `NeakasaApiClientSessionExpiredError`, `NeakasaApiClientCommunicationError` and
  `NeakasaApiClientDeviceBusyError`, one file each under `exceptions/`.
* **Multi-device, one entry per account** — `NeakasaPayload` (`dict[iot_id, snapshot]`) fetched
  concurrently replaces the single-device `NeakasaAPIData`; config flow is single-step; options
  flow offers `scan_interval` and `stats_lookback_days`; entities are discovered dynamically.
* **One class per entity, platform packages** — `sensor/`, `switch/`, `button/`,
  `binary_sensor/`, `number/`, `select/`, `text/` per `CODE_STYLE.md`.
* **Reauth and reconfigure flows**, exponential backoff on transient communication errors.
* **`entry.runtime_data`** replaces `hass.data`; `data/` package for the typed shapes;
  `diagnostics.py` and `quality_scale.yaml` for the HA code-quality checklist.
* **Test suite and quality gates** — ruff format/check and mypy in `pre-commit` and CI, pytest on
  every push, statement coverage of `custom_components/neakasa` enforced.
* **Fixes carried in this line** — `self.config_entry` was `None` at runtime (`DataUpdateCoordinator`
  now gets `config_entry=`), the WiFi wire key, the `value_cacher` typo, the auto-clean switch crash,
  and silent session-expiry recovery inside the same poll cycle.

### Inspiration and related projects

* **The shape of this line was modelled on
  [roquerodrigo/ha-neakasa-litterbox](https://github.com/roquerodrigo/ha-neakasa-litterbox)** — an
  independent Neakasa M1 integration maintained by [@roquerodrigo](https://github.com/roquerodrigo)
  and built on its companion [neakasa-litterbox-sdk](https://pypi.org/project/neakasa-litterbox-sdk/).
  That project had already settled on the structure this integration was heading for — one entry per
  account with devices discovered at runtime, one class per entity inside platform packages, a
  `data/` package, `entry.runtime_data`, reauth/reconfigure flows and an `exceptions/` package of
  one-file-per-error — and its tree is where the wave order came from. The file names that reading
  produced are still shared between the two trees (`exceptions/api_client_*.py`, `data/config.py`,
  `data/json_types.py`, `data/runtime.py`, `sensor/sand_percent.py`, `switch/auto_clean.py`, …).
* **Nothing was copied.** No file, class, string or commit of theirs is in this integration; the two
  repositories share no git history; that project drives a published SDK and an MQTT push stream while
  this one keeps its own `aiohttp` gateway client; `manifest.json` declares `"requirements": []`, so
  nothing of theirs is installed, imported or needed at runtime. The reference is one-way and is a
  credit for design inspiration, not a dependency. See
  [Credits and Related Projects](./README.md#credits-and-related-projects) in the README.

### The steps that cut this line

| wave | what it moved | shipped in |
|---|---|---|
| wave 0 | project tooling, `exceptions/` package, `quality_scale.yaml` | `v1.4.0-beta1` |
| wave 1 | `data/` package, `entry.runtime_data`, `diagnostics.py` | `v1.4.0-beta2` |
| wave 2 | `NeakasaApiClient` facade, typed error hierarchy | `v1.4.0-beta2` |
| wave 3 | multi-device coordinator, single-step config flow, options flow | `v1.4.0-beta3` |
| wave 4 | one class per entity, platform packages | `v1.4.0-beta4` |
| wave 5 | reauth flow, reconfigure flow, exponential backoff | `v1.4.0-beta4` |
| final step | async-native IoT gateway, zero Aliyun SDK dependencies | `v1.4.0-beta5` |

Waves 0, 3, 4 and 5 carry the `waveN` scope in their commit subject; waves 1 and 2 do not, which is
why the tag notes on `v1.4.0-beta1` … `v1.4.0-beta5` are the record of the order. None of this work
went through a pull request: it was pushed straight to `main`.

## [1.4.0-beta7](https://github.com/tabascoz/hass-neakasa/compare/v1.4.0-beta6...v1.4.0-beta7) (2026-09-04)

* Diagnostic logging for IoT cloud errors.

## [1.4.0-beta6](https://github.com/tabascoz/hass-neakasa/compare/v1.4.0-beta5...v1.4.0-beta6) (2026-08-27)

* Missing `x-ca-signature-headers` fixed; error logging improved.

## [1.4.0-beta5](https://github.com/tabascoz/hass-neakasa/compare/v1.4.0-beta4...v1.4.0-beta5) (2026-08-27)

* Zero Aliyun SDK dependencies; async-native IoT gateway client; zero ruff errors.

## [1.4.0-beta4](https://github.com/tabascoz/hass-neakasa/compare/v1.4.0-beta3...v1.4.0-beta4) (2026-08-27)

* Waves 4 and 5 — one class per entity and platform packages; reauth, reconfigure and exponential
  backoff; zero ruff errors, `DTZ006` fix.

## [1.4.0-beta3](https://github.com/tabascoz/hass-neakasa/compare/v1.4.0-beta2...v1.4.0-beta3) (2026-08-27)

* Wave 3 — multi-device coordinator, single-step config flow, options flow.

## [1.4.0-beta2](https://github.com/tabascoz/hass-neakasa/compare/v1.4.0-beta1...v1.4.0-beta2) (2026-08-26)

* Waves 1 and 2 — `data/` package, `entry.runtime_data`, diagnostics, `NeakasaApiClient` facade
  with typed errors.

## [1.4.0-beta1](https://github.com/tabascoz/hass-neakasa/compare/v1.3.1...v1.4.0-beta1) (2026-08-26)

* Wave 0 — project tooling, `exceptions/` package, quality tracking.

## [1.3.1](https://github.com/tabascoz/hass-neakasa/compare/v1.3.0...v1.3.1) (2026-08-26)

### Fixes

* **Crashes when Neakasa omits properties** (`cleanCfg`, `catLeft`, …) — handled instead of failing
  the whole coordinator refresh; fixes #2 and the gap in #3.
* **`last_usage` reports unavailable** rather than the Unix epoch (1970) when no cat has entered yet.

## [1.3.0](https://github.com/tabascoz/hass-neakasa/compare/v1.1...v1.3.0) (2026-07-14)

### Fixes

* Compatibility with recent `pyOpenSSL` versions.

## [v1.1](https://github.com/tabascoz/hass-neakasa/releases/tag/v1.1) (2026-06-23)

### Features

* The code of the original integration, cloned. History merged in from the `madmartin` fork of
  [@timniklas](https://github.com/timniklas)'s repository — it had disappeared — so the whole
  upstream history is still here: `Initial commit` on 2024-12-03, the `sliwma` translations and
  configuration pull requests, and the `quality_scale`/HACS scaffolding. The release notes say
  "This release is the same from Timniklas' old repository".


