# Neakasa Riko — wet meal feeder wire protocol

Captured live from account `tabascoz@gmail.com` on branch `riko-wet-feeder`.
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
| `deviceName` (wire) | `WL03002G26270011577` — machine serial, **not** user-facing |
| `nickName` | `Catchief` — the user-facing label lives here, not in `deviceName` |

> Contrast: the M1's wire `deviceName` is `JQ01909G25430010947` with
> `nickName` `Caixinha`. The existing `_get_device_name()` reads `deviceName`,
> so for Riko it would surface the serial. See `docs/riko-protocol.md` §Naming.

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

## Not yet captured (needs a service invoke / app dump)

- **Service identifiers** for `/thing/service/invoke`: dispense-one-meal, start
  deep-clean, reset desiccant. `get_product_list()` returned only the account's
  products' high-level schema (no command list here); confirm via an Android
  capture dump or by trying candidate identifiers against `productKey=a1ccEqBcaUD`.
- **Feeding schedule / meal history**: no per-meal record endpoint seen in
  properties. CatLitter uses web paths `/catbox/record` and
  `/catbox/toilet/statistics`; Riko likely has analogous `baseurl + /feeder/...`
  or `/petFeeder/...` paths — must be captured from the app (baseurl here is
  `https://euapi.neakasapet.com/api`).

## Naming note

The current `NeakasaCoordinator._get_device_name()` returns wire `deviceName`.
For Riko that is the machine serial. Prefer `nickName` when present so HA shows
"Catchief". Decide whether to change this globally or per-product.
