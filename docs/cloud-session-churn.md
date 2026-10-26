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
- The account device list is cached (`ValueCacher`, six hours now, ten minutes in
  the first version) and reused for device names; recovery paths call
  `force_refresh_devices()` so a new device is found after a reconnect. Listing
  the account is an account presentation, so ten minutes cost six of them an
  hour by itself; six hours leaves the records path as the only automatic one. A
  device added to the account appears within six hours unless you press
  `Refresh data now`, which is the manual path this already had.
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

The counters are debug-level lines of the integration, so they need
Home Assistant's debug logging for `custom_components.neakasa` (configured in
`configuration.yaml`), which is how they were read back below.

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

## Measured after (boot at 2026-10-26 00:00:46, read until 00:16:00)

One boot of this build, counted with `journalctl -u homeassistant --since
"2026-10-26 00:00:40"`. Home Assistant's debug logging comes from
`configuration.yaml`; nothing on this branch writes `.storage`.

Three completed fetches: 00:01:01, 00:04:43, 00:13:34 (2 devices, 0.375 s).

| Marker | Count in the window | Per scan |
| --- | --- | --- |
| `Authenticating shared API client` (mints a session) | 2 | one at start, one at 00:04:43 |
| `Reusing shared API client` | 3 | one for the idle scan, two from UI actions |
| `Getting device properties` | 6 | 2 (one per device), as designed |
| `Session expired`, renewals, cooldown refusals | 0 | nothing was rejected |
| `Reported state for` | 115 | the other document breaks it down |

The idle scan at 00:13:33 cost exactly one client acquisition, two property
reads, no full sign-in and no account device list (the previous build asked for
it every scan). Nothing in the window minted more than two sessions and neither
came from a rejected session, so the recovery path never had to run.

The sign-in at 00:04:43 is not one of our error paths: nothing logged
`Session expired`, `Reconnect+retry`, `Cloud session renewal failed` or
`Not signing in again`, and the only code that empties the shared registry
without an error is `async_unload_entry → clear_shared_api` in `__init__.py`.
It coincides with the moment `configuration.yaml` was applied, which reloads
the entry, so it is attributed to that reload rather than to this change. It
does mean one session per entry reload, which is the floor while the entry is
reconfigured.

Not proven yet: sessions per hour over a long window (this window is 16 minutes
and contains a start), and whether the Neakasa app stays connected. Both need a
day of running plus your observation.

## Decision

Keep it if the app stays connected while full sign-ins stay around one per
start rather than one per minute. Discard it otherwise. Nothing on `main` refers
to this file.

## After the decision: the app losing its session is not only our sign-ins

The branch was kept, and the next symptom measured on the same unit (2026-10-26,
restart at 16:20, the app signed into at 16:22:15, the app needing a sign-in at
16:29) is one this document cannot explain: a session that nobody presents ages
out on its own, minutes after being handed over. Nothing our client did in that
window presented the account, so the app lost a session we never took.

See [app-session-experiments.md](app-session-experiments.md) for that run, the
`Account presentation:` instrument that makes the count of presentations per hour
readable instead of inferred, and the vocabulary the account sensor now uses
(`unknown`, `home_assistant`, `not_home_assistant`) with the timestamps behind
every claim in its attributes.

## What was dropped, and what fixed the account device

Two things this branch built were pointed at the wrong lever and were removed
the same day: the back-off window for refusals
(`account_session_window_minutes`) and the policy for taking control back
(`session_regain_policy`), plus the decay that made the account sensor forget an
old claim. They exist to trade freshness for silence about the account, and the
measurements show the app is kicked by *any* cloud call - the device reads at
17:10:14 were followed by the app asking at 17:14:10, and the token exchange at
17:15:15 by one 15 seconds later - so keeping the reads at the configured
`scan_interval` is what the entry does, and the only control that matters is
that interval. The refusal is still reported and the values held are served, and
`records_refused` plus the sensor's attributes say so; records are re-read only
when the device reports a new `catLeft.time`, which cannot miss a change.

What was kept from the same work is everything that does not trade freshness:
the error classification (an account-token rejection goes to a sign-in, never to
an IoT exchange), one client per scan, the device-list cache, the state-write
guard, and the whole measurement instrument - `Account session minted` with its
`cause=`, `Account presentation:`, `Cloud write:`, `Login fields:` and the new
`Session moved by a token exchange:` line, since
`/account/createSessionByAuthCode` moves the session too. The claim that the
IoT exchange "adds no session to the account" was wrong, and the log at 17:15:15
→ 17:15:30 is what proved it.

The account device bug: reconfiguring the entry to a second Neakasa account left
the previous account's device in the registry next to the current one, with an
orphaned entity that could only read `unavailable` - the identifiers embedded the
username (`account:{username}`, `{username}-cloud_session`). The device and the
account entities are now named by the config entry instead, and the entry prunes
devices it created and no longer describes, so changing credentials changes no
device at all. The machines never duplicated because their identifiers are the
stable iotIds, which is also why the second account keeps the same entity ids.
