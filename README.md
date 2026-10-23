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
- Neakasa Riko (Wet Meal Feeder) — read-write (beta, `v1.5.0-beta1`)

#### Riko (wet meal feeder) features
|Type|Name|Notes|
|----|------|-----|
|Sensor|Food level / Water level|ordinal hopper/tank state|
|Sensor|Battery|% and level from `pwrStatus`|
|Sensor|WiFi RSS|network signal strength in dB (closer to 0 = stronger); diagnostic — off by default|
|Sensor|Device label|the friendly name set in the Neakasa app (all devices)|
|Binary sensor|Cover missing|`bCoverAbsent`|
|Button|Feed now|dispense one wet meal via `feedOnce` (`{food, water}`)|
|Number|Food quantity|default portion per feed, 3–15 g (writes `defFdCfg.food`)|
|Number|Water ratio|water-to-food ratio, 1–5 (writes `defFdCfg.water`)|

> The Feed now button uses the currently configured food/water defaults; setting
> either number writes the device's `defFdCfg` via read-modify-write and preserves
> `mixMin`. Other Riko controls (`freshMgrCfg`, `deepCleanCfg`, audio/display) are
> not exposed yet — see `docs/riko-protocol.md`.

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

### Getting the Riko beta (`v1.5.0-beta1`)

The Riko support ships as a pre-release. To try it before the next stable release:

**Via HACS** — in Home Assistant, open HACS → *Integrations* → Neakasa → use the
version selector to download `v1.5.0-beta1`, then restart Home Assistant.

**Manually (zip)** — download this beta's asset and extract into your config dir:

```bash
wget https://github.com/tabascoz/hass-neakasa/releases/download/v1.5.0-beta1/neakasa.zip
mkdir -p custom_components/neakasa && unzip neakasa.zip -d custom_components/neakasa && rm neakasa.zip
```

Then restart Home Assistant. The beta is opt-in — HACS keeps the latest *stable*
(`v1.4.2`) as default until `v1.5.0` is released; pick the beta explicitly to test Riko now.

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
