# Neakasa Riko — wet meal feeder wire protocol

Captured live from a personal account on branch `riko-wet-feeder` (identifiers below are anonymized).
Source of truth: `/uc/listBindingByAccount`, `/thing/productInfo/getByAppKey`
and `/thing/properties/get` over the Aliyun IoT gateway (`app_key=32715650`).

The Riko is bound to the **same** account, app key and gateway transport as the
M1 litter box — only its `categoryKey`, `productKey` and property set differ.

Findings here are written as **observed operation**: what the machine and the gateway
do when we call them. The product's own software is not quoted, named or referenced.

## Identity

| Field | Value |
|---|---|
| `categoryKey` | `petFeeder` (note: lowercase `p`, not `CatFoodFeeder`) |
| `categoryName` | 宠物喂食机 ("pet feeder machine") |
| `productName` | `Riko` |
| `productKey` | `a1ccEqBcaUD` |
| `netType` | `NET_WIFI` (same IoT gateway pattern as CatLitter) |
| `deviceName` (wire) | `WL…SERIAL` — machine serial, **not** user-facing |
| `nickName` | `PETLABEL` — the user-facing label lives here, not in `deviceName` |

> Contrast: the M1's wire `deviceName` is a machine serial with its own `nickName`.
> The existing `_get_device_name()` reads `deviceName`, so for Riko it would surface
> the serial. See §Naming.

## Property set (`/thing/properties/get`)

Every property is wrapped as `{"time": <ms>, "value": …}` like CatLitter.

### Read-only / status
| Key | Shape | Notes |
|---|---|---|
| `foodLvl` | int enum (observed `2`) | food hopper level state (0–N), not a percent |
| `waterLvl` | int enum (observed `3`) | water tank level state |
| `pwrStatus` | `{batPercentage, batLevel, batVoltage, batTemp, pwrType, batStatus}` | battery; `batPercentage`=90, `batLevel`=4, `batVoltage`=12209 (mV×?), `batStatus`=2 |
| `bowlStatus` | `{bowlGram, curWeight, bBowlIn}` | bowl weight in grams; `bBowlIn`=1 bowl present |
| `bCoverAbsent` | int 0/1 | cover/lid state — **inverted**: `1` = cover present/OK, `0` = absent (verified against device with cover in place) |
| `deviceState` | `{state, param}` | operating state machine (observed 0/0) |
| `drierEffeDays` / `leftDrierDays` | int days (observed 40) | desiccant pack effective / remaining days |
| `drierResetTs` | str unix-seconds | last desiccant reset |
| `NetWorkStatus` | `{WiFi_RSSI, WiFi_Name, IP_Addr, MAC_Addr}` | same key as CatLitter → reuse RSSI sensor |
| `DeviceVer` | `{FW_Version, HW_Version, type, bRegionLock}` | firmware/HW versions |
| `disconn` | `{lockCnt, rssi, disconnReason, reconnFailed, ts}` | connectivity diagnostics |
| `timestamp` | str ms | device clock |
| `userOpenId`, `regionBaseurl`, `region`, `timeZoneMsg` | routing/identity metadata |

### Controls (settable — writable via `/thing/properties/set`)
| Key | Shape | Likely control |
|---|---|---|
| `defFdCfg` | `{mixMin, water, food}` | the machine's default meal: `food` in grams, **`water` in grams of water** (portion × ratio), `mixMin` mixing minutes |
| `feedAudCfg` | `{volume, audIdx}` | feed audio/sound config |
| `freshMgrCfg` | `{monitorTime, leftOverTTH, bOnOff}` | freshness manager on/off + leftover thresholds |
| `deepCleanCfg` | `{bOnOff, cleanState}` | deep-clean (bowl wash) toggle/state |
| `displayCfg` | `{displayParam, displayType, bDisplayIfIdle}` | front display config |
| `childLockOnOff` | int 0/1 | child lock — same key as CatLitter → reuse switch |

## Feeding: observed operation

`/thing/service/invoke`, **identifier `feedOnce`**, args
`{food: <g of food>, water: <g of water>, bSaveAsDef: 0|1}`.

- **`water` is an amount of water in grams**, never the ratio index. Observed operation
  shows the amount follows the chosen ratio: `water = food × ratio`, and editing the water
  amount instead gives `food = water / ratio`. Over the product UI ranges (3–15 g of food,
  ratio 1–5) `water` spans 3–75 g. A real machine has been seen holding
  `defFdCfg = {food:5, water:15, mixMin:1}` — 5 g of food with 15 g of water, a ratio of 3.
  That is the machine's own starting point, read from the device; it is not a fallback.
- **`bSaveAsDef`** says whether the amounts just used become the machine's defaults: `1`
  stores them, `0` leaves `defFdCfg` untouched. Omitting the key behaves like `1` (the call
  below rewrote `defFdCfg`), so the integration always sends the flag explicitly.
- `food = 0` is accepted — the machine waters without grinding (observed:
  `{food:0, water:10, bSaveAsDef:0}`).
- Verified: `feedOnce {food:5, water:2}` → gateway OK; `defFdCfg` became
  `{food:5,water:2,mixMin:1}` and `bowlStatus.curWeight` rose 67→139 g (a meal was
  dispensed).
- **v1.5.0-beta1 regression:** beta1 sent `water` as the ratio index (1–5). Observed on the
  machine: it ground the food and then kept adding water until it reported an error of
  **clogged water sprays**. Sending the water amount in grams is what the official app does
  and clears it.
- Ranges per product UI: **food 3–15 g**, **water ratio 1–5** (1:1–1:5 food to water).
- Not real commands: `feedNow`, `doFeed`, `startFeed`, `manualFeed` → "service not found".
  `feedCtrl` exists but is a different auto-feed control and times out with these args —
  it is not used for feeding one meal.

## How the integration feeds (v1.5.0-beta2)

The Food quantity and Water ratio numbers are **staged locally**: they choose the amounts for
the next Feed now and never write the machine by themselves. `coordinator.feed_once` resolves
the effective amounts (staged → the machine's `defFdCfg` → the documented fallbacks), turns
the ratio into grams of water and invokes `feedOnce {food, water: food × ratio, bSaveAsDef}`.

The **Save feed as default** switch on each Riko decides what happens to the
machine's defaults:

- off → `bSaveAsDef: 0`; nothing is stored, and after the feed the numbers show the
  machine's previous defaults again;
- on → `bSaveAsDef: 1`, and `defFdCfg` is also written through
  `coordinator.set_feed_config` (read-modify-write preserving `mixMin`). Confirmed on a live
  device that writing `{"defFdCfg": {food, water, mixMin}}` through `/thing/properties/set`
  updates the value; writing it makes the storage unambiguous even if a firmware ignores the
  flag.

The switch state lives in the coordinator, so a restart returns it to the account option
`feed_keep_as_new_defaults`, which only seeds that default. Amounts a feed stored on the
machine survive a restart because they are stored there.

Reading is the inverse: `feed_config` divides `defFdCfg.value.water` grams by `food` to get
the ratio. When the machine reports no configured defaults — `defFdCfg` is `{food: 0, water: 0}`,
which is a state and not a ratio of 0/0 — the integration uses its own documented fallback: 5 g
of food at ratio 1, the smallest water amount on offer. The machine's stored values above always
win when they exist; the fallback only covers the never-configured case.

`coordinator.async_get_device_schema` reports, per device, the raw `defFdCfg`, the parsed
`default_food_g` and `default_water_ratio`, the staged `pending_feed`, `keep_as_new_defaults`
and `last_feed` (the exact args the last `feedOnce` used and whether it stored them). Each feed
also logs `Riko feedOnce <iot_id>: {…}` at debug level, and when storing, `Riko stored defaults
<iot_id>: food N g, water M g` — so a press can be read either in the Diagnostics view or in the
Home Assistant log with `custom_components.neakasa: debug`.

## Per-device entity registration

Every platform module branches on `snap.category_key`, so a device never receives another
category's controls. Registration runs on each coordinator update behind a `_seen_iot_ids`
guard: a device that appears later gets its entities without restarting Home Assistant.
Unique ids are `{iot_id}-{control}`.

| Platform | Both categories | `petFeeder` (Riko) | `CatLitter` (M1) |
|----------|-----------------|--------------------|------------------|
| sensor | `label` | `food_level`, `water_level`, `battery`, `wifi_rssi` | `sand_percent`, `wifi_rssi`, `stay_time`, `last_usage`, `bucket_status`, `sand_level_state`, `bin_state`, `cat_weight` per cat |
| binary_sensor | — | `cover_absent` | `bin_full` |
| button | — | `feed_now` | `clean`, `level` |
| number | — | `food_grams`, `water_ratio` | — |
| switch | — | `feed_keep_as_new_defaults` | `auto_clean`, `young_cat_mode`, `child_lock`, `auto_bury`, `auto_level`, `silent_mode`, `auto_recovery`, `unstoppable_cycle` |

`wifi_rssi` is deliberately offered for both categories: the same wire key is present on both
devices.

## Naming note

The current `NeakasaCoordinator._get_device_name()` returns wire `deviceName`.
For Riko that is the machine serial. Prefer `nickName` when present so HA shows
the user-facing label. Decide whether to change this globally or per-product.
