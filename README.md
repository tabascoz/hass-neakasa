# Neakasa Integration for Home Assistant 🏠

[![GitHub Release](https://img.shields.io/github/v/release/tabascoz/hass-neakasa?sort=semver&style=for-the-badge&color=green)](https://github.com/tabascoz/hass-neakasa/releases/)
[![GitHub Release Date](https://img.shields.io/github/release-date/tabascoz/hass-neakasa?style=for-the-badge&color=green)](https://github.com/tabascoz/hass-neakasa/releases/)
![GitHub Downloads (all assets, latest release)](https://img.shields.io/github/downloads/tabascoz/hass-neakasa/latest/total?style=for-the-badge&label=Downloads%20latest%20Release)
![HA Analytics](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.neakasa.total&style=for-the-badge&label=Active%20Installations&color=red)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/tabascoz/hass-neakasa?style=for-the-badge)
[![hacs](https://img.shields.io/badge/HACS-Integration-blue.svg?style=for-the-badge)](https://github.com/hacs/integration)

## Important note ##

This is a copy of original Neakasa integration from @timniklas . Unfortunatelly, the original repository has vanished and I'll do my best to maintain it from now on. Will need some time to understand the code and take it over, allow me some time for it as i do it on my free time only. 

## Overview

The Neakasa Home Assistant Custom Integration allows you to integrate your Neakasa devices with your Home Assistant setup.

### Currently supported devices
- Neakasa M1 (Cat Litter Box)
- Neakasa Riko (Wet Meal Feeder) — read-write (`v1.5.0`)

#### Riko (wet meal feeder) features
|Type|Name|Notes|
|----|------|-----|
|Sensor|Food level / Water level|ordinal hopper/tank state|
|Sensor|Battery|% and level from `pwrStatus`|
|Sensor|WiFi RSS|network signal strength in dB (closer to 0 = stronger); diagnostic — off by default|
|Sensor|Device label|the friendly name set in the Neakasa app (all devices)|
|Binary sensor|Cover missing|`bCoverAbsent`|
|Button|Feed now|dispense one wet meal via `feedOnce` (`{food, water, bSaveAsDef}`)|
|Number|Food quantity|portion used by the next Feed now, 3–15 g|
|Number|Water ratio|water-to-food ratio used by the next Feed now, 1–5 (water amount = portion × ratio)|
|Switch|Save feed as default|whether a Feed now stores the amounts it used on the machine; default off|
|Sensor|Bowl weight|grams the bowl holds - the machine's scale reading with its own tare subtracted; the machine is asked for a current weighing (its 称重 read) each scan, so when it answers the figure is that reading and both answers keep their own moments in the state attributes|
|Sensor|Device status|the operating state the machine states for itself (`deviceState`): idle, preparing a meal, dispensing a meal, paused, fault, sleeping, freshness protection, deep cleaning - only "idle" has been seen on this unit, the others are named by the machine's own definition; the moment that report was made travels with it|
|Binary sensor|Serving food|whether the machine states it is preparing or dispensing a meal - the same key as the state above, so it follows the machine's report and not the scale|
|Binary sensor|Bowl in place|whether the bowl is on the scale (`bowlStatus`), with the age of that reading beside it|
|Sensor|Deep clean state|the bowl wash the machine says it is in (`deepCleanCfg`); this unit has only ever answered "not washing"|
|Sensor|Battery state|whether the battery is fitted, being charged or in use (`pwrStatus.batStatus`)|
|Sensor|Desiccant days left|the countdown the machine keeps for its desiccant pack|
|Number|Desiccant days|the day budget for a fresh pack, 1–60|
|Button|Desiccant pack is changed|restarts that countdown on the machine (`resetDrierTime`)|
|Switch|Keep the meal fresh|the freshness manager: it watches the bowl and re-hydrates what is left (`freshMgrCfg.bOnOff`); the hours it watches and the leftover threshold stay as the machine states them|
|Number|Rehydration time|minutes the machine takes to rehydrate a wet meal, 0–30 (`defFdCfg.mixMin`)|
|Number|Meal sound volume|how loud the machine plays the sound of a delivered meal, 0–100; 0 is silence|
|Switch|Show the display when idle|the front display while the machine is idle|
|Selector|Standby display kind|what the front shows when idle; the kinds are named here, the machine's own codes for them have not been confirmed|
|Text|Standby display message|the message the front display shows when idle, up to 50 characters|
|Sensor|Device serial / Firmware version|the identifier the machine states for itself, and its firmware and hardware versions|
|Sensor|Food delivered today|grams the machine recorded as delivered today; no delivery has been recorded on this account yet, so it shows nothing until one is|
|Sensor / Button|Water tank last cleaned / Mark the water tank clean|the cleaning reminders: the mark the machine holds and a press that writes it now|
|Sensor / Button|Food bin last cleaned / Mark the food bin clean|the same for the food bin|
|Button|Zero the bowl scale|re-zero the scale with the bowl weight the machine states (`resetScaleZero`)|
|Button|Calibrate the food scale|ask the machine to recalibrate how it reads food weight (`fdCalbration`)|
|Switch|Do not disturb|the machine's quiet window (`DND_Mode`); its start, end and repeat days stay as the machine states them|
|Sensor|Cloud session status|which client holds the account's session (`Unknown` / `Home Assistant` / `Not Home Assistant`), with `last_presented_at`, `last_presented_call`, `refused_at`, `records_as_cached` as state attributes; lives on the account device|
|Button|Refresh data now|present the account to the cloud again so the next scan reads it; costs one session, so the Neakasa app has to sign in again afterwards|

> On setup the integration reads the machine's own `defFdCfg` and shows it (the water
> amount in grams is turned back into the ratio). Editing a number only stages the next
> feed; the machine is never written by itself. The **Save feed as default**
> switch on the Riko decides whether a Feed now stores the amounts it used; it starts
> off and the account option `feed_keep_as_new_defaults` only seeds that default.
> The settings that name one part of a machine's own config write only that part and
> keep the rest as the machine stated it. A control the machine has never stated a
> value for shows nothing rather than a guess, and the presses whose effect on this
> firmware has not been seen yet are labelled in `docs/riko-protocol.md`.

### Currently supported features
#### Sensors:
|Sensor|Unit|Example Value|Enabled by default|
|------|-------------|------|------|
|Cat litter level|percent|80 %|yes|
|WiFi RSS|dB|-60 dB|no (debug information)|
|Last stay time|seconds|45 s|no|
|Last usage|datetime|2024-12-07 14:52|yes|
|Device status|idle / cleaning / leveling / flipover / cat_present / paused / side_bin_locking_panels_missing / cleaning_interrupted|idle|yes|
|Cat litter state|insufficient / moderate / sufficient|sufficient|yes|
|Bin state|normal / full / missing|normal|yes|
|Cat {name}|kg|3.8|yes|

#### Binary sensors:
|Binary Sensor|Example Value|Enabled by default|
|-------------|-------------|------------------|
|Garbage can full|off|yes|

#### Buttons:
|Button|Action|Enabled by default|
|------|------|------------------|
|Clean|Cleans the litter box|yes|
|Level|Initiates the leveling process|yes|

#### Switches:
|Switch|Enabled by default|
|------|------------------|
|Kitten mode|no (rare edgecase)|
|Child lock|yes|
|Automatic cover|yes|
|Automatic leveling|yes|
|Silent mode|yes|
|Automatic recovery|no (potentialy dangerous!)|
|Unstoppable cycle|yes|

## Installation

### Getting the Riko support (`v1.5.0`)

The Riko support is in the current stable release, so HACS hands it to you as the
default version and there is nothing to opt into. To take it manually:

```bash
wget https://github.com/tabascoz/hass-neakasa/releases/download/v1.5.0/neakasa.zip
mkdir -p custom_components/neakasa && unzip neakasa.zip -d custom_components/neakasa && rm neakasa.zip
```

Then restart Home Assistant. The pre-releases `v1.5.0-beta1` … `v1.5.0-beta6` stay
downloadable if you want to compare a machine against the step that changed it;
`v1.5.0` carries that whole line, so the notes below are history rather than
something to install.

**Beta notes** — `v1.5.0-beta1` sent the water amount as a ratio index, which made the
machine keep adding water and report an error of clogged water sprays. `v1.5.0-beta2`
sends the amount in grams, the way the official app does, and adds the account option
`feed_keep_as_new_defaults` for storing the amounts a feed used as the machine's
defaults. `v1.5.0-beta3` keeps that feeding behaviour and adds the account side of the
fight over the account's session: the **Cloud session status** sensor says which client
the account last presented itself to and shows when we last presented it, when it
refused us and whether the record values on screen are ones we are holding; the
**Refresh data now** button takes the session back on request, which costs one session
and so asks the Neakasa app to sign in again; the per-scan reads stay at the
`scan_interval` you set, because any cloud call - a device read or the IoT token
exchange - is what moves the session. Feeding is unchanged from beta2: the numbers
still only stage a feed, the machine is written by a Feed now alone.

Two more things `v1.5.0-beta3` cleans up. The integration no longer writes the
account's or its machines' names into the log: the account appears as
`acct-<hash>`, a machine as `dev-<hash>` and a config entry as `entry-<hash>` -
stable labels, so the sign-in counts and any comparison between two accounts or
two machines stay readable while no login, machine serial, iotId or entry id
reaches the journal, including in Home Assistant's own line about the update
manager; and the text the cloud returns in an error is redacted before it is
logged. And a device that the config entry no longer describes is forgotten when
the entry is set up again, so configuring the entry with other credentials leaves
one account device in the UI rather than one per set-up. The two
temporary debug buttons on the feeder (**Debug token churn**, **Debug invalidate
token**) and the `debug_probe` option are still there to measure the token
paths; `v1.5.0-beta5` dropped the two token-press buttons, and `debug_probe`
remains as an advanced option for measuring one command on a machine.

What `v1.5.0-beta4` adds is the rest of what the feeder holds, and it changes
nothing about feeding: the numbers still only stage a meal, and the machine is
written by a **Feed now** alone. The settings it exposes are the ones the machine
states values for today - the freshness manager switch, the rehydration minutes of
a wet meal (0-30, as the machine's own definition bounds it), the volume of the
meal sound (this integration offers 0-100, where the definition allows 200, and 0
is silence), the front display (whether it is up while idle, the message it shows,
and the kind of display - the kinds are named here, their codes on this machine
have not been confirmed), the machine's quiet window, the desiccant day budget and
the countdown that reads it back, the bowl weight the scale reads, and the marks
for cleaning the water tank and the food bin. The calibration presses (**Zero the
bowl scale**, **Calibrate the food scale**) and the desiccant reset (**Desiccant
pack is changed**) ask for the machine's own commands; those have not been run
here, so a press is what says whether this firmware takes them. Nothing is
invented: a control the machine has never answered with a value shows nothing,
which is what the same section of `docs/riko-protocol.md` says for each key.

### Beta notes (`v1.5.0-beta5`)

What `v1.5.0-beta5` changes is the device's own filing and one control's
presentation, not the machine. The settings you tune once and leave alone (**Calibrate
the food scale**, **Desiccant days**, **Desiccant pack is changed**, **Food bin was
cleaned**, **Keep the meal fresh**, **Meal sound volume**, **Rehydration time**,
**Show the display when idle**, **Standby display kind**, **Standby display custom
message**, **Water tank was cleaned**, **Zero the bowl scale**) are marked as
configuration and the two that only identify the machine (**Device serial**,
**Firmware version**) as diagnostics, so Home Assistant presents them apart from the
actions you press often. The standby message is also renamed to **Standby display
custom message** and now presents the message the machine states (empty when the
machine states none), which is what lets a message be typed into it at all - the
entity had been defined on a property Home Assistant does not read, which left it
with no state and the control unreachable. The message is sent upper-case on the
write, because the front panel is a fixed LED matrix with no lower-case glyphs:
this unit drew `teste1` as a bare `1` and drew `TESTE1` in full, and the Neakasa
app does the same normalisation. Settings that name one part of a nested config
(the display kind and message, the freshness manager, the meal-sound volume, the
rehydration minutes, the portion and water defaults) now read the machine first and
carry *that* state's other parts, because the entry scans every five minutes and an
older model copy used to be written back over a change made in the app - this unit
had presses pushing `custom`/`N/A` onto a machine the app had set to time. The token
debug buttons are
gone: they existed only to watch the token path for these notes. Nothing else moved:
no
unique id, unit, default or wire call changed, so an install that already has the
entities keeps every one of them and only re-files them. Presses now cost one extra
read of the machine, which is what makes them carry the machine's own state instead
of a copy that is up to five minutes old.

**Bowl weight** now publishes the bowl's **contents** - the scale reading with the
machine's own tare subtracted and clamped at zero, so this unit's 67 g on the scale
against a 68 g tare is an empty bowl - and it travels with the age of its reading,
because the cloud only holds what the machine last reported for `bowlStatus`. The
wording of that reason was wrong in this note when it was first written and has
been corrected against the measurements of 2026-10-27: the machine does push that
key again - this unit re-reported it at 2026-10-27T00:56:40Z, inside a whole-set
report in which `pwrStatus`, `foodLvl`, `waterLvl`, `NetWorkStatus` and `deviceState`
carry the same moment - but the numbers in that report are the ones the machine had
stored, still 67 g on the scale against a 68 g tare with about 22 g of food in the
bowl while the app showed 22-23 g. Nothing this integration reached then re-read
the scale: `get` is answered with "service not found" and asking for the key
restates what it held. What does answer freshly is the machine's own read
command, and that is the next release's change - written up there rather than
patched into this note, because this release shipped the age and nothing more.
So the sensor carries `scale_state_as_of`,
`scale_state_age_minutes`, the raw reading and the tare as attributes, and an old
number is read as old rather than as the present.

What that release also records is the one thing it cannot make better: with the
integration running, the Neakasa mobile app (iOS and the Android APK) reports the
machine as offline about once a minute and goes back to its login page, because the
integration and the app sign in to the same Neakasa account and that account keeps
the session of whichever client authenticated last - a sign-in from one side costs
the other side its session, and any touch of the cloud from our client does it, not
only the account calls. The tests taken against that and why none of them changed
the result are written out in `docs/cloud-session-churn.md` and
`docs/app-session-experiments.md`. The workaround that removes the shared resource
entirely is to give Home Assistant its own Neakasa account: create a second one in
the app, share the machines to it, and configure this integration with that account -
the app and Home Assistant then describe different accounts and there is no session
left to fight over. If that split is not yours and the app's stability matters more
than the integration, disabling this entry is the switch that keeps the app normal.

### The state the machine reports for itself (`v1.5.0`)

What the feeder says about its own working state is now read and shown, from the
keys its own definition names and this unit answers: a **Device status** sensor
for the operating state (`deviceState`), a **Serving food** binary sensor for the
two codes the definition names as a meal (preparing and dispensing), **Bowl in
place** from `bowlStatus`, **Deep clean state** from `deepCleanCfg` and
**Battery state** from `pwrStatus`. The names of those states are the definition's;
the only values this unit has ever answered are idle, no wash, the battery in use,
and the bowl in place - the other states are shown with the names the definition
gives them and have not been seen here.

Unlike the scale, these keys are re-pushed while the machine works: this unit's
`deviceState` report moved across 2026-10-26T11:05:05Z, 2026-10-27T00:40:17Z,
2026-10-27T00:56:40Z and 2026-10-27T09:44:57Z while the value stayed at idle, so
each of these values carries its own `*_as_of` and `*_age_minutes` naming the
moment the machine stated that key, rather than presenting it as the present. The
bowl number stayed at the replay for the reason given above until the read command
below answered it; these keys are reads either way, and none of them writes the
machine.

The bowl number, however, was wrong for a reason we can now answer. The cloud's
copy of `bowlStatus` is a replay: seven reads across 2026-10-27 all restated 67
g on the scale against a 68 g tare - a published 0 g - while the app showed 22 g
and the machine's display moved. The machine's own read command answers freshly.
The product's definition names `iotRead` (远程读取) and its `readType` 2 is 称重 (the
weighing); this unit replied `{"type": "scale", "str": {"bowlGram": 68, "gram":
89.08}}` and, fourteen seconds later, `89.1` - 21 g above the tare that same
answer states. So the integration asks that command once per scan for the feeder,
through the same call path it already uses, and prefers the answer taken more
recently: `scale_live_g`, `scale_live_tare_g` and `scale_live_as_of` travel
beside the stored copy's own `scale_state_as_of` and `scale_state_age_minutes`,
never dressed up as one claim. A machine that refuses the ask states nothing and
the stored figure keeps its age. This is one extra cloud call per feeder per
scan, which is what the mobile app does as well, and it is why the app's session
has to be signed in again after us.

The same command answers the machine's other live states - the power state
(this unit said 85 % and `"state": "Using"` against the stored 90 %), the
hopper's raw detection value, the water level and the device clock - and
`getVoltage` reads a channel value; only the weighing is read today, with the
rest written up in `docs/riko-protocol.md` so they do not have to be
rediscovered.

### HACS (recommended)

This integration is available in HACS (Home Assistant Community Store).

1. Install HACS if you don't have it already
2. Open HACS in Home Assistant
3. Go to any of the sections (integrations, frontend, automation).
4. Click on the 3 dots in the top right corner.
5. Select "Custom repositories"
6. Add following URL to the repository `https://github.com/tabascoz/hass-neakasa`.
7. Select Integration as category.
8. Click the "ADD" button
9. Search for "Neakasa"
10. Click the "Download" button

### Manual installation

#### from downloaded zip archive
To install this integration manually you have to download [_neakasa.zip_](https://github.com/tabascoz/hass-neakasa/releases/latest/) and extract its contents to `config/custom_components/neakasa` directory:

```bash
mkdir -p custom_components/neakasa
cd custom_components/neakasa
wget https://github.com/tabascoz/hacs_blitzerde/releases/latest/download/neakasa.zip
unzip neakasa.zip
rm neakasa.zip
```
restart Home Assistant.

#### Installation from git repository

with this variant, you can easily update the integration from the github repository.

##### First installation:

```bash
cd <to your Home Assistant config directory>
git clone https://github.com/tabascoz/hass-neakasa
mkdir custom_components
cd custom_components
ln -s ../hass-neakasa/custom_components/neakasa/ .
```

restart Home Assistant.

##### update the existing installation:

```bash
cd <to your Home Assistant config directory>
cd hass-neakasa/
git pull
```

restart Home Assistant.


## Configuration

### Using UI

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=neakasa)

From the Home Assistant front page go to `Configuration` and then select `Devices & Services` from the list.
Use the `Add Integration` button in the bottom right to add a new integration called `Neakasa`.

### Riko feeding controls

The Food quantity and Water ratio numbers set the amounts used by the **next** Feed now; they
never write the machine on their own. The **Save feed as default** switch, listed with
the Riko's other entities, decides whether a feed stores the amounts it used on the machine. It
starts off; the account option `feed_keep_as_new_defaults` only seeds that starting value and
lives in the options dialog of the account card (Devices & Services → Integrations → the Neakasa
card, whose title is the account or a device serial → `⋮` → Configure settings).

To see what a feed sent, open the integration's Diagnostics — per device it reports `defFdCfg`,
the parsed defaults, `pending_feed`, `keep_as_new_defaults` and `last_feed` — or enable
`custom_components.neakasa: debug` in the logging configuration and read the log line
`Riko feedOnce …`.

## Troubleshooting Tips / Known Issues

1. When you discover  that the mobile app is starting over and over, beginning again with the login steps, then you should use this HA integration with a different account than with the app. Create a second account and use the share function in the app - simply share the device with the second account
2. powercycle the litterbox
3. reset the litterbox and reintegrate it
4. open an issue

## Help and Contribution

If you find a problem, feel free to report it and I will do my best to help you.
If you have something to contribute, your help is greatly appreciated!
If you want to add a new feature, add a pull request first so we can discuss the details.

## Disclaimer

This custom integration is not officially endorsed or supported by Neakasa.
Use it at your own risk and ensure that you comply with all relevant terms of service and privacy policies.
