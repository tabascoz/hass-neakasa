# Neakasa Integration for Home Assistant 🏠

[![GitHub Release](https://img.shields.io/github/v/release/tabascoz/hass-neakasa?sort=semver&style=for-the-badge&color=green)](https://github.com/tabascoz/hass-neakasa/releases/)
[![GitHub Release Date](https://img.shields.io/github/release-date/tabascoz/hass-neakasa?style=for-the-badge&color=green)](https://github.com/tabascoz/hass-neakasa/releases/)
![GitHub Downloads (all assets, latest release)](https://img.shields.io/github/downloads/tabascoz/hass-neakasa/latest/total?style=for-the-badge&label=Downloads%20latest%20Release)
![HA Analytics](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.neakasa.total&style=for-the-badge&label=Active%20Installations&color=red)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/tabascoz/hass-neakasa?style=for-the-badge)
[![hacs](https://img.shields.io/badge/HACS-Integration-blue.svg?style=for-the-badge)](https://github.com/hacs/integration)

## Important Note

This is a maintained fork of the original Neakasa integration by [@timniklas](https://github.com/timniklas).  
The original repository disappeared, so I am continuing development in my free time.  
Please be patient while I fully take over the codebase.

The `v1.4.0` line — the `wave0` … `wave5` refactors of 2026-08-26 → 2026-08-27 — was modelled
on the shape of [roquerodrigo/ha-neakasa-litterbox](https://github.com/roquerodrigo/ha-neakasa-litterbox),
a separate Neakasa integration developed in parallel. That is credited as **inspiration, not as a
dependency**: none of it runs here, and nothing of theirs was copied. See
[Credits and Related Projects](#credits-and-related-projects) near the end of this file.

> **Strong recommendation:**  
> Use a **separate Neakasa account** for Home Assistant.  
> Share your devices from the official app to the second account.  
> This avoids constant session conflicts that force the mobile app to log out.

---

## Overview

This custom integration lets you control and monitor Neakasa devices from Home Assistant.

### Currently Supported Devices

| Device           | Type            | Support Level                   |
|------------------|-----------------|---------------------------------|
| **Neakasa M1**   | Cat Litter Box  | Full                            |
| **Neakasa Riko** | Wet Meal Feeder | Full (read + write) – `v1.5.0`  |

Devices are matched by the category the cloud reports (`CatLitter`, `petFeeder`), so
Riko variants in that category are handled the same way as the unit this integration
was developed against.

> **Honest reporting:**  
> A few Riko controls were named by the machine's own definition but never answered
> with a value during development (see the notes further down). Those entities are
> offered and written, but they show **nothing** until a real machine reports them —
> the integration never invents a value.

---

## What's new in the v1.5.0 line (compared with `v1.4.2`)

Riko shipped across the `v1.5.0-beta1` … `v1.5.0-beta6` releases; `v1.5.0` is the
first stable release that carries all of it, and HACS gives you that by default.
If you installed a beta, some of this you already have.

- **Feeding matches the machine** – Food quantity and Water ratio only stage the next
  meal. The machine is only written when you press **Feed now**.
- **Water is sent in grams** – you still set the ratio (1–5); the integration multiplies
  it by the portion and sends the amount in grams, the same unit the official app uses.
  Sending the ratio index instead made real machines report clogged water sprays.
- New **Save feed as default** switch – decides whether the amounts a feed used become
  the machine's defaults.
- **Cloud session status** sensor – says whether Home Assistant still holds the account
  session (`Home Assistant` / `Not Home Assistant` / `Unknown`). A refused call cannot
  tell the mobile app holding the session from the session ageing out on its own, so the
  sensor reports what can be proved, and its attributes carry the timestamps.
- **Refresh data now** button – takes the session back to Home Assistant and re-reads.
  Presenting the account moves the session, so the mobile app has to sign in again
  after a press.
- Many more settings exposed: freshness manager, rehydration time, meal sound volume,
  standby display options, desiccant day budget and countdown, bowl weight (with the
  machine's own live weighing), the cleaning marks for the water tank and food bin.
- **Standby display custom message** is now fully readable and writable. The panel is a
  fixed LED matrix with no lower-case glyphs, so the text is uppercased before it is
  sent — what the entity holds is what the panel draws.
- Better privacy: account and device identifiers are replaced by hashes in log lines.
- Device-state entities (**Device status**, **Serving food**, **Bowl in place**,
  **Battery state**) publish the state beside the moment the machine stated it.

---

## Riko (Wet Meal Feeder) Entities

### Feeding

| Type   | Name                 | Description                                 |
|--------|----------------------|---------------------------------------------|
| Button | Feed now             | Dispenses one wet meal                      |
| Number | Food quantity        | Portion for the next feed (3–15 g)          |
| Number | Water ratio          | Water-to-food ratio for the next feed (1–5) |
| Switch | Save feed as default | Store the amounts used as new defaults      |

> **Note:** Changing the numbers only stages the next meal. The machine is only written when you press **Feed now**.

### Status & Monitoring

| Type          | Name                    | Description                                    |
|---------------|-------------------------|------------------------------------------------|
| Sensor        | Food level              | Hopper state                                   |
| Sensor        | Water level             | Tank state                                     |
| Sensor        | Bowl weight             | Current contents (tare subtracted) + live reading |
| Sensor        | Device status           | Operating state (idle, preparing, dispensing…) |
| Binary sensor | Serving food            | True while preparing or dispensing a meal      |
| Binary sensor | Bowl in place           | Whether the bowl is on the scale               |
| Binary sensor | Cover missing           | True when the feeder's lid/cover is absent   |
| Sensor        | Battery                 | Battery percentage                             |
| Sensor        | Battery state           | Fitted / charging / in use                     |
| Sensor        | Deep clean state        | Current bowl wash status                       |
| Sensor        | Desiccant days left     | Remaining days on the desiccant pack           |
| Sensor        | Food served today          | Grams the machine served since the day began  |
| Sensor        | Food served today (solid)   | Solid grams of that figure (off by default)   |
| Sensor        | Food served today (liquid)  | Liquid grams of that figure (off by default)  |
| Sensor        | Water tank last cleaned | The cleaning mark the machine holds            |
| Sensor        | Food bin last cleaned   | The same mark for the food bin                 |
| Sensor        | Cloud session status    | Whether this account's session is still ours   |

> **Account-level, not device-level:** **Cloud session status** and **Refresh data now**
> describe the account, so they exist once per configured account — including an account
> that only holds a litter box. They sit on their own "Neakasa account" device.

> **Never answered on a real machine during development:** the meal states beyond
> `idle`, the deep-clean steps beyond `not washing`, the battery states beyond `in use`,
> and the two cleaning marks (no record was ever returned for them). Those entities are
> offered and written, but they stay empty until a machine reports them — the
> integration never invents a value.

### Settings & Actions

| Type   | Name                        | Description                            |
|--------|-----------------------------|----------------------------------------|
| Switch | Keep the meal fresh         | Freshness manager                      |
| Number | Rehydration time            | Minutes to rehydrate a wet meal (0–30) |
| Number | Meal sound volume           | 0–100 (0 = silence)                    |
| Switch | Show the display when idle  | Front display while idle               |
| Select | Standby display kind        | What the display shows when idle       |
| Text   | Standby display custom message | Custom message (auto uppercased)       |
| Switch | Do not disturb                 | Quiet window                           |
| Number | Desiccant days                 | Day budget for a new pack (1–60)       |
| Button | Desiccant pack is changed      | Reset desiccant countdown              |
| Button | Zero the bowl scale            | Re-zero the scale                      |
| Button | Calibrate the food scale       | Recalibrate food weight reading        |
| Button | Water tank was cleaned         | Write the water tank cleaning mark     |
| Button | Food bin was cleaned           | Write the food bin cleaning mark       |
| Button | Refresh data now               | Take the cloud session back and re-read |

### Diagnostics

| Type   | Name             | Description                            |
|--------|------------------|----------------------------------------|
| Sensor | Device serial    | Machine serial number                  |
| Sensor | Firmware version | Firmware + hardware version            |
| Sensor | WiFi RSSI        | Signal strength, closer to 0 = stronger (off by default) |
| Sensor | Device label     | Friendly name from the Neakasa app     |

> **Device label** is added for every supported device, litter box included.

---

## M1 (Cat Litter Box) Entities

> The account-level **Cloud session status** and **Refresh data now** described above
> belong here too — they are offered once per configured account, whatever it holds.

### Sensors

| Sensor           | Unit     | Enabled by default | Example          |
|------------------|----------|--------------------|------------------|
| Cat litter level | %        | Yes                | 80 %             |
| Device status    | -        | Yes                | idle             |
| Cat litter state | -        | Yes                | sufficient       |
| Bin state        | -        | Yes                | normal           |
| Last usage       | datetime | Yes                | 2024-12-07 14:52 |
| Cat {name}       | kg       | Yes                | 3.8              |
| Device label     | -        | Yes                | My litter box    |
| WiFi RSSI        | dB       | No                 | -60 dB           |
| Last stay time   | seconds  | No                 | 45 s             |

### Binary Sensors

| Binary Sensor    | Enabled by default |
|------------------|--------------------|
| Garbage can full | Yes                |

### Buttons

| Button | Action                 | Enabled by default |
|--------|------------------------|--------------------|
| Clean  | Start cleaning cycle   | Yes                |
| Level  | Start leveling process | Yes                |

### Switches

| Switch             | Enabled by default | Notes                 |
|--------------------|--------------------|-----------------------|
| Child lock         | Yes                |                       |
| Auto clean         | Yes                | Automatic cleaning    |
| Automatic cover    | Yes                |                       |
| Automatic leveling | Yes                |                       |
| Silent mode        | Yes                |                       |
| Unstoppable cycle  | Yes                |                       |
| Kitten mode        | No                 | Rare edge case        |
| Automatic recovery | No                 | Potentially dangerous |

---

## Installation

### HACS (Recommended)

1. Open HACS → Integrations
2. Click the three dots (top right) → **Custom repositories**
3. Add repository: `https://github.com/tabascoz/hass-neakasa`
4. Category: **Integration**
5. Search for **Neakasa** and download it
6. Restart Home Assistant

### Manual Installation (from release)

```bash
cd config
wget https://github.com/tabascoz/hass-neakasa/releases/latest/download/neakasa.zip
mkdir -p custom_components/neakasa
unzip neakasa.zip -d custom_components/neakasa
rm neakasa.zip
```

Restart Home Assistant.

### Installation from Git (for development)

```bash
cd config
git clone https://github.com/tabascoz/hass-neakasa.git
mkdir -p custom_components
ln -s ../hass-neakasa/custom_components/neakasa custom_components/neakasa
```

To update later:

```bash
cd config/hass-neakasa
git pull
```

Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for **Neakasa** and follow the setup

Or use this button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=neakasa)

### Riko Feeding Tip

- **Food quantity** and **Water ratio** only prepare the next meal.
- The machine is only written when you press **Feed now**.
- Enable **Save feed as default** if you want the amounts you just used to become the new defaults.

---

## Troubleshooting

1. **Mobile app keeps logging out**  
   → Use a separate Neakasa account for Home Assistant (share the devices to it).

2. **Litter box not responding**  
   → Power cycle the device, or reset and re-add it.

3. **Still having issues?**  
   → Open an issue on GitHub.

---

## Help & Contribution

Found a bug or want to contribute?  

Feel free to open an issue or a pull request. All help is welcome!

---

## Credits and Related Projects

### The integration this one forked

- **[@timniklas](https://github.com/timniklas)** wrote the original Neakasa integration. Its whole
  history is still in this repository: `Initial commit` on 2024-12-03, carried in through the
  `sliwma` and `madmartin` forks and merged on 2026-06-23 as `v1.1 - initial clone from old repo`.
  The `LICENSE` keeps that copyright alongside mine, and 128 of the commits here are theirs.

### The project that shaped the `v1.4.0` refactors

- **[roquerodrigo/ha-neakasa-litterbox](https://github.com/roquerodrigo/ha-neakasa-litterbox)** —
  an independent Neakasa M1 integration maintained by [@roquerodrigo](https://github.com/roquerodrigo),
  built on its companion **[neakasa-litterbox-sdk](https://pypi.org/project/neakasa-litterbox-sdk/)** —
  is the **reference implementation the `wave0` … `wave5` modernization was modelled on**
  (2026-08-26 → 2026-08-27, shipped as `v1.4.0-beta1` … `v1.4.0-beta5` and the `v1.4.0` release).

  That project had already settled on the structure this integration was heading for, so its tree
  decided the shape of the wave plan: one config entry per account with every device discovered at
  runtime, one class per entity inside platform packages (`sensor/`, `switch/`, `button/`,
  `binary_sensor/`, `number/`, `select/`, `text/`), a `data/` package for the typed shapes,
  `entry.runtime_data` instead of `hass.data`, reauth/reconfigure flows and an `exceptions/`
  package of one-file-per-error. The file names that reading produced are still shared between the
  two trees — `exceptions/api_client_error.py`, `exceptions/api_client_authentication_error.py`,
  `exceptions/api_client_communication_error.py`, `exceptions/api_client_device_busy_error.py`,
  `exceptions/api_client_session_expired_error.py`, `data/config.py`, `data/json_types.py`,
  `data/runtime.py`, `sensor/sand_percent.py`, `sensor/cat_weight.py`, `switch/auto_clean.py`,
  `switch/child_lock.py`, `switch/silent_mode.py`.

**Inspiration, not code, not a dependency.** What was taken is the architecture, never the content:

- no file, class, string or commit of theirs exists in this integration, and the two repositories
  share no git history;
- this integration keeps its own cloud client — `iot_gateway.py` signs Aliyun IoT requests with
  plain `aiohttp` and manual HMAC-SHA256 — while that one drives the published `neakasa-litterbox-sdk`
  and an MQTT push stream;
- `custom_components/neakasa/manifest.json` declares `"requirements": []`, so nothing of theirs is
  installed, imported or needed at runtime;
- the reference is one-way: that project says nothing about this one.

Both are unofficial community integrations, and neither is endorsed by Neakasa.

The full release line — which step of it was inspired by what — is written up in
[CHANGELOG.md](./CHANGELOG.md).

---

## Disclaimer

This is an unofficial community integration and is **not** endorsed or supported by Neakasa.  

Use at your own risk.