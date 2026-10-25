# The Neakasa app losing its device and its login

Symptom: with this integration enabled, the Neakasa's own app (iOS and the
Android APK) reports the device as offline about once a minute and goes back to
its login page. With the integration disabled it does not happen. This is a
different mechanism from the one in [app-websocket-flood.md](app-websocket-flood.md):
that one is Home Assistant's websocket message queue and affects Home Assistant's
clients; this one is the cloud account's sessions and affects the Neakasa app.

## The shared resource

The integration authenticates against the same account the app uses, and a
re-authentication mints a session on that account:

```python
# api.py, connect(): base url lookup, then
self._session.post(url=self.baseurl + "/login/user", json={...})
...
resp = await client.do_request("/account/createSessionByAuthCode", body)
```

The recovery path in `coordinator.py` used to always do the full chain — six
requests and a new session — whenever the cloud rejected our IoT token.

## What the log shows

Session churn on 2026-10-25, from `journalctl`/`warnings.log` for the unit:

```text
22:56:05 Session expired → 22:56:05 Authenticating shared API client
22:57:08 Session expired → ...
22:58:11 → 23:01:15 → 23:03:17
```

Five re-authentications in eight minutes, each one stacking a session on the
account. Earlier in the day the same thing happened as three simultaneous
logins (19:52:45, 19:52:48, 19:52:50), which is what `api_manager.py` allowed
when the shared client was cleared while a caller was waiting on its lock.

Per scan the integration also spent more requests than it needs: three shared
client acquisitions (measured 18 in six minutes for six scans), an account
device list per scan (the same list `_get_device_name` asks for again), and two
property reads (those must stay live). The 60 s default scan interval turns that
into roughly seven cloud requests a minute.

## What the branch changes

- One API client per scan: `async_update_data` takes the client once and passes
  it to the per-device helpers, so a scan costs one client acquisition.
- The account device list is cached (`ValueCacher`, 10 minutes) and reused for
  device names; recovery paths call `force_refresh_devices()` so a new device is
  found after a reconnect. A device added to the account now appears in the UI
  within ten minutes instead of one minute.
- A rejected session is recovered by renewing the IoT token (`refresh_session`,
  one call) and a full re-login happens at most once per
  `FULL_REAUTH_COOLDOWN_SECONDS`. When the cooldown blocks it, the scan fails
  with `UpdateFailed` and Home Assistant's normal retry applies.
- `api_manager.py` keeps one lock per credentials key behind a registry lock and
  `clear_shared_api` no longer drops it, so concurrent callers cannot each sign
  in.
- The user raised the entry's `scan_interval` to 300 s in the UI. That is an
  option, not code, and it divides both this session churn and the websocket
  flood by five, so it measures against both symptoms at once.

## Counting it

On this branch the counters are logged at INFO so the greps work without
enabling debug logging. They are measuring aids: drop them (back to debug) if
the branch is kept.

```bash
# full sign-ins (each mints a session): expect a handful per hour, not per minute
journalctl -u homeassistant --since "-1 hour" | grep -c \
  "Authenticating shared API client"
# client acquisitions: expect 1 per scan, was 3
journalctl -u homeassistant --since "-1 hour" | grep -c \
  "Reusing shared API client"
# property reads: 2 per scan by design, they must stay live
journalctl -u homeassistant --since "-1 hour" | grep -c \
  "Getting device properties"
```

The account device list has no log line of its own; it is only visible when it
errors (`/uc/listBindingByAccount`). Its caching is covered by
`tests/test_cloud_sessions.py` instead.

## Decision

Keep it if the app stays connected while the count of full sign-ins per hour is
small, and if the entities still report after a press and after the machine is
used. Discard it otherwise. Nothing on `main` refers to this file.
