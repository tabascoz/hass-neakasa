# Neakasa Riko — wet meal feeder wire protocol

Captured live from a personal account on branch `riko-wet-feeder` (identifiers below are anonymized).
Source of truth: `/uc/listBindingByAccount`, `/thing/productInfo/getByAppKey`
and `/thing/properties/get` over the Aliyun IoT gateway (`app_key=32715650`).

The Riko is bound to the **same** account, app key and gateway transport as the
M1 litter box — only its `categoryKey`, `productKey` and property set differ.

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
| `defFdCfg` | `{mixMin, water, food}` | default feeding portion + water-to-food ratio (`water`/`food`, `mixMin`) |
| `feedAudCfg` | `{volume, audIdx}` | feed audio/sound config |
| `freshMgrCfg` | `{monitorTime, leftOverTTH, bOnOff}` | freshness manager on/off + leftover thresholds |
| `deepCleanCfg` | `{bOnOff, cleanState}` | deep-clean (bowl wash) toggle/state |
| `displayCfg` | `{displayParam, displayType, bDisplayIfIdle}` | front display config |
| `childLockOnOff` | int 0/1 | child lock — same key as CatLitter → reuse switch |

## Confirmed write mechanism (live-tested against a real Riko)

`/thing/service/invoke`, **identifier `feedOnce`**, args `{food: <grams>, water: <ratio>}`.
- Verified: `feedOnce {food:5, water:2}` → gateway OK; `defFdCfg` updated to `{food:5,water:2,mixMin:1}` and `bowlStatus.curWeight` rose 67→139 g (a meal was dispensed).
- Ranges per product UI: **food 3–15 g**, **water ratio 1–5** (1:1–1:5 food/water).
- `feedNow`, `doFeed`, `startFeed`, `manualFeed` → "service not found" (not real commands).
- `feedCtrl` exists but is a different (auto-feed control) command, times out with these args — not used for manual feed.

## Default feed config write path (implemented)

The Feed Now button dispenses using the device's current `defFdCfg` defaults. Two HA **number** entities (food grams 3–15, water ratio 1–5) set those defaults via read-modify-write of the nested `defFdCfg` object (`coordinator.set_feed_config`, preserving `mixMin`). Confirmed on live device that writing `{"defFdCfg": {food, water, mixMin}}` through `/thing/properties/set` updates the value.

## Naming note

The current `NeakasaCoordinator._get_device_name()` returns wire `deviceName`.
For Riko that is the machine serial. Prefer `nickName` when present so HA shows
the user-facing label. Decide whether to change this globally or per-product.
