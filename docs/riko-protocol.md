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

Every key below is labelled by where the shape came from:

| Tag | Meaning |
|---|---|
| `[this unit]` | read from the live machine on 2026-10-26 (`/thing/properties/get`) |
| `[definition]` | the gateway's own product definition for `a1ccEqBcaUD`, which `/thing/tsl/get` answers with types and ranges |
| `[unverified]` | named by the definition and never answered by this unit, so its behaviour here is not observed |

| Key | Shape | Notes |
|---|---|---|
| `foodLvl` | int enum (observed `2`) `[this unit]` | food hopper level state; the codes the machine uses are empty=0, lacking=1, full=2 — not a percent |
| `waterLvl` | int enum (observed `3`) `[this unit]` | water tank level state; empty=0, lacking=1, low=2, middle=3, full=4 |
| `pwrStatus` | `{batPercentage, batLevel, batVoltage, batTemp, pwrType, batStatus, batMsg}` | battery; observed `batPercentage`=90, `batLevel`=4, `batVoltage`=12159 mV, `batTemp`=25.0 °C, `batStatus`=2. The definition allows percentage 0–110 %, voltage 0–16000 mV, temperature −30…120 °C, and spells `batStatus` as an enum 不在位=0 battery not fitted, 充电中=1 being charged, 使用中=2 in use — only 2 has been answered here, so the other two names are the definition's; the key's own stamp (2026-10-27T00:56:40Z on this unit) is carried as `battery_as_of` and `battery_age_minutes` |
| `bowlStatus` | `{bowlGram, curWeight, bBowlIn}` | the bowl on the scale: `curWeight` is **the weight the scale reports with the bowl on it** (observed 67; the definition allows −3000…3000), `bowlGram` is the bowl's own tare (observed 68; 0…500 g), `bBowlIn`=1 bowl present (the definition names 0 不在位 not in place and 1 在位 in place). What the bowl holds is `curWeight − bowlGram` clamped at zero (67 g on the scale against a 68 g tare is an empty bowl), which is what the sensor publishes; the raw reading, the tare and whether the bowl is in place travel with it as `scale_reading_g`, `bowl_tare_g` and `bowl_in_place`, and the bowl's presence is a control of its own. The wrapper's `time` is the moment the machine last reported this key, and that report repeats what the machine had stored rather than re-reading the scale: seven reads across 2026-10-27 show the stamp moving to 2026-10-27T00:56:40Z — the same stamp as `pwrStatus`, `foodLvl`, `waterLvl`, `NetWorkStatus`, `bCoverAbsent`, `childLockOnOff`, `leftDrierDays` and `deviceState`, one whole-property-set report — while the value stayed 67 g on the scale against a 68 g tare with about 22 g of food in the bowl and the app showing 22–23 g. Asking this key never refreshes the number: `get` is answered with "service not found" and the `/sys/…/thing/…` forms the product's definition names are 404 on this gateway. What does state a current weighing is the machine's own read command, `iotRead` with `readType` 2 (§Commands) — it replied 89.08 g and, fourteen seconds later, 89.1 g above a 68 g tare on the same day — and that reply is kept apart from this copy as `scale_live_g`, `scale_live_tare_g` and `scale_live_as_of`, so Home Assistant never passes a replay off as the present and never dresses the two answers up as one |
| `bCoverAbsent` | int 0/1 | cover/lid state — **inverted**: `1` = in place, `0` = absent (verified against the device with its cover in place) |
| `deviceState` | `{state, param}` | operating state machine (observed 0/0 on this unit throughout 2026-10-26 and 2026-10-27); the state codes and their names are the definition's enum — 空闲中=0 idle, 备餐中=1 preparing a meal, 出餐中=2 dispensing a meal, 挂起中=3 paused, 故障中=4 fault, 休眠中=5 sleeping, 新鲜度保护中=6 freshness protection, 深度清洁中=7 deep cleaning — and `param` is an int −100000…100000 named 参数 (a parameter), which this unit has only ever stated as 0. Unlike `bowlStatus`, this key **is re-pushed as the machine works**: this unit's copies were stamped 2026-10-26T11:05:05Z, then 2026-10-27T00:40:17Z, 2026-10-27T00:56:40Z and 2026-10-27T09:44:57Z in four reads of the same key, so the value is as fresh as the machine's last report of it — and Home Assistant carries that moment as `state_as_of` and `state_age_minutes` rather than presenting it as the present |
| `drierEffeDays` | int (observed 40) | desiccant pack's effective days; the definition allows 1…60 |
| `leftDrierDays` | int (observed 38) | desiccant days left; the definition allows 0…120 |
| `drierResetTs` | str unix-seconds (observed `1792757949`) | the last desiccant change the machine recorded |
| `lastWaterBinCleanTime` `[definition]` | text ≤100 | when the water tank was last marked clean — this unit has never answered it, so no cleaning has been recorded on it |
| `lastFoodBinCleanTime` `[definition]` | text ≤100 | the same for the food bin |
| `NetWorkStatus` | `{WiFi_RSSI, WiFi_Name, IP_Addr, MAC_Addr}` | same key as CatLitter → the existing RSSI sensor covers it |
| `DeviceVer` | `{FW_Version, HW_Version, type, bRegionLock}` | observed `FW_Version`=`1.0.0-0033`, `HW_Version`=`1.00.01`; the definition caps each version string at 16 characters. `/thing/info/get` repeats the firmware under `firmwareVersion` |
| `disconn` | `{lockCnt, rssi, disconnReason, reconnFailed, ts}` | connectivity record (observed `disconnReason`=200, `rssi`=-62) |
| `timestamp` | str ms | device clock |
| `userOpenId`, `regionBaseurl`, `region`, `timeZoneMsg`, `GenHighSvcEnv`, `httpData`, `catPermit`, `newbieProgress` `[definition]` | account/routing metadata and the onboarding walk-through |
| `unit_pref`, `weightUnit` `[definition]` | the unit the front display and the app print food and water in; this unit has not answered either |
| `is12HourFormat`, `battSavingMode`, `showDisplayAtIdle`, `pwrMode`, `scannerCfg` `[definition]` | clock format, long-battery mode, the display-while-idle switch as the definition spells it, power mode, the multi-pet recognition config |

### Controls (settable — writable through the `set` command of the definition)

| Key | Shape | What it controls |
|---|---|---|
| `defFdCfg` | `{food, water, mixMin}` | the machine's default meal. `food` 0…60 g, **`water` is an amount of water in grams** 0…600 g (never the ratio index: sending the index on 2026-10-25 made the machine keep adding water until it reported clogged water sprays), `mixMin` 0…30 **minutes** — the definition names it as the rehydration time of the wet meal, and this unit reports 3 |
| `feedAudCfg` | `{audIdx, volume}` | the sound the machine plays when it delivers a meal: `audIdx` picks the clip (the machine holds a default clip and clips you record in the app), `volume` is 0…200 in the definition, and this unit reports 100; 0 is silence |
| `freshMgrCfg` | `{bOnOff, monitorTime, leftOverTTH}` | the freshness manager: `bOnOff` starts or stops it, `monitorTime` is how long it watches the bowl in **hours** (definition 1…4, observed 4), `leftOverTTH` is the leftover threshold in **grams** (definition 0…300, observed 20) |
| `leftover` | `{bOnOff, detGramTTh}` `[definition]` | a separate leftover detection switch with a 0…30 g threshold — this unit has never answered it |
| `deepCleanCfg` | `{bOnOff, cleanState}` | the bowl wash: on/off and the state the wash is in (observed 0/0 on this unit). The wash states are the definition's enum: 0 初始状态 not washing, 1 水路清洁中 washing the water channel, 2 水路清洁完成 water channel washed, 3 水路冲洗中 rinsing the water channel — only 0 has been answered here, so the other three are read from the definition and their appearance is untested |
| `displayCfg` | `{displayType, displayParam, bDisplayIfIdle}` | the front display: the kind is the definition's enum `{"0": "time", "1": "graphics", "2": "custom"}` (labelled 时间/图形/自定义 there), the text shown (`displayParam`, ≤50 characters in the definition and stored verbatim by this unit, though the panel draws no lower-case glyphs) and whether the display is up while the machine is idle (`bDisplayIfIdle`, observed 1) |
| `DND_Mode` | `{active, startTime, endTime, weekRept, bAudioDND, bDisplayDND}` | `[definition]` do-not-disturb: on/off, start and end as seconds of the day (0…86400), which days repeat as a 7-bit mask (0…127), and separately whether the silence applies to the sound and to the display |
| `smartPlanCfg` | `{catId, drierFoodId}` | `[definition]` the plan bound to a pet and a desiccant brand (both 0…100000000) |
| `fdPlanStr` | text ≤1024 | `[definition]` the feeding plan as one encoded string |
| `childLockOnOff` | int 0/1 | child lock — same key as CatLitter, and this unit reports it for the feeder too (observed 0) |
| `drierEffeDays`, `leftDrierDays` | int days | writing them is how the desiccant change is recorded; the reset is a command, see below |
| `lastWaterBinCleanTime`, `lastFoodBinCleanTime`, `showDisplayAtIdle`, `unit_pref`, `weightUnit`, `is12HourFormat`, `battSavingMode` | see above | `[definition]` writable in the definition, not answered by this unit |


## Commands (`/thing/service/invoke`)

The definition answers with the commands the machine accepts and their arguments.
Every name below is `[definition]`; only `feedOnce` has been seen working on this
machine (`[this unit]`, see §Feeding).

| Command | Arguments | What it does |
|---|---|---|
| `set` | any of the 39 writable keys above | the write path the integration uses for every setting |
| `get` | — | ask the machine to read its state back — this unit answers `/thing/service/invoke` `get` with "service not found", so the name is not a service on this gateway |
| `feedOnce` `[this unit]` | `{food 0…60 g, water 0…600 g, bSaveAsDef bool}` | deliver one meal; the flag keeps the amounts as the defaults |
| `feedCtrl` | `{ctrlType enum}` | the auto-feeding control; asked with meal amounts it times out, so it is not one-meal feeding |
| `bowlCtrl` | `{ctrlType enum}` | act on the bowl |
| `resetScaleZero` | `{bowlGram int 0…200 g}` | re-zero the scale against a known bowl weight — the bowl-weight calibration |
| `fdCalbration` | `{kVal 0…100, kX100 0…200, objVal/bkgVal/diffVal 0…2000}` | recalibrate the food scale's reading |
| `resetDrierTime` | `{drierEffeDays 1…60}` | record a desiccant change and re-count from the new budget |
| `deepWashing` | `{type enum}` | start the bowl wash |
| `ledScreenDisplay` | `{animeType int 0…24}` | put an animation on the front display |
| `foodProvide`, `waterProvide` | `{bOnOff bool}` | start or stop providing food / water |
| `updateTime` | `{type enum}` | correct the device clock |
| `errorBan` | `{errCode 0…1000, bCleanBan bool}` | mute or unmute a fault the machine keeps reporting |
| `errPostDebug` | `{errCode 0…100, module ≤20, error ≤32, param 0…1000}` | report a fault on demand |
| `getVoltage` | `{chanIdx enum, val 0…10000}` | read one of the machine's own measurements — `[this unit]` answered `chanIdx` 0 with `{"val": 12097}` and `12095` on 2026-10-27, the same order the battery's `batVoltage` states in mV, so the value moves with the ask |
| `iotRead` `[this unit]` | `{readType enum 0 设备时间 / 1 设备唤醒时间 / **2 称重** / 3 电源状态 / 4 粮仓状态 / 5 水位状态}` | ask the machine to read state back, and it answers: `readType` 2 replied `{"type": "scale", "str": {"bowlGram": 68, "gram": 89.08}}` and, fourteen seconds later, `89.1` — 21 g above the tare its own answer states, against the 67 g the cloud's copy of `bowlStatus` held all day. `3` replied `{"bat": {"vol": 12094, "lv": 4, "state": "Using", "percent": 85}, "pwr": "DC"}` (the live percent against the stored 90), `4` replied `{"curLv": 2, "curVal": 312, "displayLv": 2}`, `5` replied `{"vol": 1677, "lv": 3}` and `0` replied `{"time": "2026-10-27 14:44:07", "dst": 0}`, all with `ReturnCode` 0 and a `messageId` but no timestamp of their own. The reply does not refresh the property set — it is a separate answer, kept separately |
| `cfgRead`, `cfgWrite` | `{cfgFile ≤1024, cfgMsg ≤1024}` / `{cfgFile, cfgValStr, bCreate bool}` | read or write one of the machine's config files |
| `fileSrv` | `{keepAliveSec 0…1000, bSW enum, bEncryption enum}` | the file service the machine talks to |
| `udpCmd` | `{bOnOff bool}` | a raw machine command |
| `updateBaseurl` | `{baseURL ≤64}` | re-fetch the regional endpoint |
| `RmReboot` | — | restart the machine |

Two events are defined as well: `post` — whose method is
`thing.event.property.post` and whose output list is the whole property set
above, which is the channel the device reports live state over — and
`ModuleErr{module, error, param, errCode}`. Asking that channel as readable
history does not work: `/thing/events/get` returned only the one `ModuleErr`
record on 2026-10-27 (`module: grinder`, `error: CoverLost`, `errCode: 12`),
`/thing/properties/query` is 404 on this gateway, and the extended-property
endpoint asks for a `dataKey` we have no name for. What does answer on request is
the machine's own read command (`§Commands`, `iotRead`), whose reply is a
separate claim from the property set — and it is the channel the mobile app's
own code reads, whose model classes for the feeder are `data/model/food_machine/…`
fed by `data/model/topic/{IotPropertyTopic,EventTopic,StatusTopic,InvokeServiceReply}`.
The job list the machine numbers cleaning and consumables with is
litter-box clean=0, trash-can clean=1, trash-can wash=2, buy litter=3,
**water-tank clean=4**, **food-bin clean=5**, **desiccant replacement=6**; meal
records are typed meal=0, eating=1, plan=2.

## What the definition says and this unit answers

Measured on 2026-10-26 through this integration's own client: `/thing/properties/get`
for the feeder returns **23 keys**; the definition names **42**. Every reported key is
defined (none is undocumented); **19 are defined and never answered**:
`BatteryPercentage`, `DND_Mode`, `GenHighSvcEnv`, `bRegionLock`,
`battSavingMode`, `catPermit`, `fdPlanStr`, `httpData`, `is12HourFormat`,
`lastFoodBinCleanTime`, `lastWaterBinCleanTime`, `leftover`,
`newbieProgress`, `pwrMode`, `scannerCfg`, `showDisplayAtIdle`,
`smartPlanCfg`, `unit_pref`, `weightUnit`.

The reason matters for the controls being added: a key the machine has no value
for is not a key the machine rejects. Writing it is how this firmware's answer is
found out, so the integration reads these when present, shows nothing when not,
and never claims one works before this unit has answered it.



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
| sensor | `label` | `food_level`, `water_level`, `battery`, `battery_state`, `device_status`, `deep_clean_state`, `wifi_rssi`, `bowl_weight`, `bowl_in_place` as a binary sensor, `desiccant_days_left`, `device_serial`, `firmware_version`, `food_intake_today`, `last_bin_clean_water`, `last_bin_clean_food` | `sand_percent`, `wifi_rssi`, `stay_time`, `last_usage`, `bucket_status`, `sand_level_state`, `bin_state`, `cat_weight` per cat |
| binary_sensor | — | `cover_absent`, `bowl_in_place`, `serving_food` | `bin_full` |
| button | — | `feed_now`, `reset_desiccant`, `reset_bowl_scale`, `calibrate_food_scale`, `mark_water_bin_clean`, `mark_food_bin_clean` | `clean`, `level` |
| number | — | `food_grams`, `water_ratio`, `rehydration_minutes`, `desiccant_days`, `feed_sound_volume` | — |
| switch | — | `feed_keep_as_new_defaults`, `fresh_meal_manager`, `display_standby`, `do_not_disturb` | `auto_clean`, `young_cat_mode`, `child_lock`, `auto_bury`, `auto_level`, `silent_mode`, `auto_recovery`, `unstoppable_cycle` |
| select | — | `display_standby_kind` | — |
| text | — | `display_custom_message` | — |

`wifi_rssi` is deliberately offered for both categories: the same wire key is present
on both devices. The two new platforms are registered only for the feeder, and the
entity names exist in all four translation files with the same key tree, which is
what the translation test checks.

## What the device files them as (v1.5.0-beta5)

Twenty controls on one device mixed the actions you press often, the settings you
tune once and leave alone, and the values that only identify the machine, so
Home Assistant's entity categories are now used and the device presents them apart:

- **Configuration** — `refresh_data` on the account device, and on the feeder the
  settings you set and leave: `calibrate_food_scale`, `desiccant_days`,
  `display_custom_message`, `display_standby`, `display_standby_kind`,
  `feed_sound_volume`, `fresh_meal_manager`,
  `mark_food_bin_clean`, `mark_water_bin_clean`, `rehydration_minutes`,
  `reset_bowl_scale`, `reset_desiccant`.
- **Diagnostics** — `wifi_rssi` (both devices), `device_serial`,
  `firmware_version`.
- **Controls as they are** — `feed_now`, `food_grams`, `water_ratio`,
  `feed_keep_as_new_defaults`, `do_not_disturb`, the level and state sensors and
  the rest: everything you use often stays where it was.

A category is a UI grouping only. No unique id, no unit, no enabled default and no
wire call moved, so an installed browser keeps every entity it has and only re-files
them. The standby message is also renamed in the translations to **Standby display
custom message**; the key stays `display_custom_message`, so the entity is
re-labelled rather than recreated.

## How the integration reads the rest (v1.5.0-beta4)

Read is never invented. A control the machine answered with a value is shown as that
value; a control it has never answered with one shows nothing - `None` for a sensor,
off for a switch only when the machine says off, and unknown for the select. The
standby display message is the exception added in v1.5.0-beta5, and the exception is
deliberate: an entity with no state cannot be typed into, so a device whose display
config holds no message is presented with an empty one, which is what makes writing
a message possible. A device that is not in the model at all still shows nothing.
The keys this unit has never answered are listed above, and the same marker is what
the entities read.

## What this unit's panel draws (v1.5.0-beta5)

Measured through this integration's own write path, with a probe that sends the
`displayCfg` the integration sends and reads the state back:

- The machine stores the message as it is sent. A write of `teste1` left the state
  reading `{"displayType": 2, "displayParam": "teste1", "bDisplayIfIdle": 1}`,
  acknowledged a few seconds after the write - `displayCfg.time` moves on every
  write the machine takes, so a press can be told from a no-op by that stamp.
- The panel draws no lower-case glyphs. That same message showed on the front as a
  bare `1`; sent as `TESTE1` the panel drew all of it. The Neakasa app reaches this
  by upper-casing the text before it sends, so the integration's text entity writes
  `displayParam` upper-case too, and what the entity shows is what the panel draws.
- A kind that is not custom states `displayParam` as the empty string on this unit
  (an earlier round read it as `N/A`), so choosing `custom` with nothing typed
  carries that placeholder and shows nothing new.

`ledScreenDisplay {animeType 0…24}` in the commands table is the machine's own way
of putting a built-in animation ("Led点阵显示") on the front display; it is a
different feature and is not how the custom text is carried.

A setting that names one part of a nested config writes only that part and takes the
other parts from a read of the machine taken at that moment, because the gateway
replaces the whole object: `freshMgrCfg` keeps `monitorTime` and `leftOverTTH` when
the switch is moved, `displayCfg` keeps its kind and message when the display switch
is moved, `feedAudCfg` keeps its clip when the volume is set, and `defFdCfg` keeps
the portion and water amount when the rehydration minutes are set. The values come
from `coordinator.set_property` reading the device first, not from the model: the
model is only as fresh as the last scan, and this unit showed what that costs. The
app set the display to time at 23:39 while the model still held `custom`/`N/A` from
before, and presses at 22:47 and 23:07 pushed that older pair back onto the machine,
which then went back to a kind nobody had asked for. Reading first is what the app
does before writing; it costs one extra GET per press and never one per poll. When
the read states nothing for that object, the write goes out as it was composed and
the log says which path ran. The `set_property` path maps the internal name to the
wire name so the same write shape the definition describes is what goes out, and the
values a press leaves on the model are the ones that were actually sent, so the
entities follow the machine instead of the request.

The commands are asked for, not assumed to work: `resetDrierTime{drierEffeDays}` uses
the day budget the machine states (or the longest the definition allows when it states
none), `resetScaleZero{bowlGram}` uses the bowl weight the machine states and refuses
with a message when it states none, and `fdCalbration` is asked with no coefficients
because this unit has never reported any. What each of those answers is what a press
in Home Assistant finds out, and the answer is written in the journal at debug level
by the same cloud-write line the feeding path already produces.

The daily intake is read from the account's record endpoint, which is now asked for
the feeder as well; no delivery has been recorded on this account, so it currently
answers with nothing and the sensor shows nothing. That is also why the reading is
kept separate from the definition: the record shape is described, not confirmed.

## What the machine reports about its own state (v1.5.0-beta6)

Measured on this unit across 2026-10-27. The state the machine reports for itself
is now read and shown, and every value carries the moment the machine stated it:

- `deviceState` is re-pushed as the machine works — this unit's copies were
  stamped 2026-10-26T11:05:05Z, then 2026-10-27T00:40:17Z, 2026-10-27T00:56:40Z
  and 2026-10-27T09:44:57Z, and all of them said state 0 with param 0. So the
  **Device status** control reads idle here, and only idle has been seen; the other
  seven names come from the definition's enum (§Property set), as does the pair the
  **Serving food** control stands for. A code outside the eight is published as
  that number rather than given an invented name.
- `deepCleanCfg.cleanState` and `pwrStatus.batStatus` are read the same way: this
  unit answered 0 and 2, so the wash control says "not washing" and the battery
  control says "in use". The other names in those enums are the definition's and
  untested here.
- `bowlStatus.bBowlIn` is **Bowl in place** (this unit says in place). It belongs
  to the same cloud copy the bowl number is read from, so the reading's age is
  offered with it — a bowl reported in place is in place at the moment the machine
  stated it, not necessarily now.
- Nothing is invented for a key the machine has never answered: its value stays
  unknown, and each control carries its own `*_as_of` and `*_age_minutes` taken
  from that key's wrapper. The feeder's state is its own field now, not the
  litter box's, so one device's state stops borrowing another device's name.
- These are reads. No control writes the machine, and none of them costs a call
  per scan — the values come from the property set the entry already reads.

### The scale's two answers (v1.5.0-beta6)

Also measured on 2026-10-27. The bowl's weight has two answers, and the
difference between them is the whole reason the number was wrong:

- The cloud's copy of `bowlStatus` is a replay. Seven reads across that day all
  stated 67 g on the scale against a 68 g tare — so the published figure was
  0 g — while the app showed 22 g and the machine's own display moved.
- The machine's read command answers freshly: the definition's `iotRead`
  (远程读取) with `readType` 2 (称重) replied `{"type": "scale", "str": {"bowlGram":
  68, "gram": 89.08}}` and, fourteen seconds later, `89.1` — 21 g above the
  tare the same answer states. That reply is not written back into the property
  set, so it is a separate claim: the model keeps both, `scale_live_g`/`scale_live_tare_g`
  beside `scale_live_ts` (the moment the answer arrived, since the reply carries
  no timestamp of its own), and the sensor prefers the answer taken more recently
  while the attributes show both.
- The app reaches the same answer over its MQTT property/service-reply topics
  (`data/model/topic/IotPropertyTopic`, `InvokeServiceReply` in its own code);
  the integration asks the same command through the REST path it already uses,
  which is why this costs one extra cloud call per feeder per scan and nothing
  more. A refused ask states nothing: the stored copy and its age stand.
- The same command answers the other states too — 电源状态 (this unit said 85 %
  and `"state": "Using"` against the stored 90 %), 粮仓状态 (`curVal` 312 raw
  under `curLv` 2), 水位状态 (`vol` 1677) and 设备时间 (the machine's clock,
  which matched our wall clock) — and `getVoltage` reads one channel's value.
  Only the weighing is read today; the others are recorded so a later release
  does not have to rediscover them.

## Naming note

The current `NeakasaCoordinator._get_device_name()` returns wire `deviceName`.
For Riko that is the machine serial. Prefer `nickName` when present so HA shows
the user-facing label. Decide whether to change this globally or per-product.
