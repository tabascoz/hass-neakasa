# The Home Assistant clients losing their websocket connection

Symptom this documents: Home Assistant's own clients (its apps and the browser
tabs on the tablets) drop their websocket connection and re-authenticate. The
Neakasa app's "device offline, please log in" looks the same to you but comes
from the cloud account's sessions, not from this queue — that is documented
separately in [cloud-session-churn.md](cloud-session-churn.md). Both were
reported at the same time, so both are measured on this branch together.

## What is happening

Home Assistant keeps a queue of messages per websocket connection and cancels the
connection when the client cannot drain it:

```python
# homeassistant/components/websocket_api/const.py
MAX_PENDING_MSG = 4096  # "effectively the upper limit of the number of entities
# that can fire state changes within ~1 second"
```

In ``websocket_api/http.py`` the queue is appended by ``_send_message`` and the
connection is cancelled at that limit. The log says so directly:

```text
ERROR [homeassistant.components.websocket_api.http.connection] tablet from ...:
Client unable to keep up with pending messages. Reached 4096 pending messages.
The system.load is too high or an integration is misbehaving
WARNING [homeassistant.components.http.ban] Login attempt or request with invalid
authentication from Anna-iphone-2.local ... Requested URL: /api/websocket
```

The second line is the visible effect: the app re-authenticates, so it shows the
login page.

## Why this integration is a large share of the queue

This install has thousands of entities and this integration registers 33 of them
(2 devices, plus one entity per cat). Every entity reacts to a coordinator update
by writing its state, and the update happens every scan interval, 60 s by default.
Home Assistant fires an event even for a state which did not change, so an idle
machine still spends 33 messages every minute:

```python
# homeassistant/core.py, in StateMachine.async_set_internal
if same_state and same_attr:
    self._bus.async_fire_internal(EVENT_STATE_REPORTED, ...)
```

Nothing on the machine changed in most scans, so those reports are pure overhead.
Cloud polling at one minute for 33 entities is what keeps the queue at the limit.

## What the branch changes

- ``base_entity.py`` holds one guard, ``write_state_if_changed``, which writes
  state only when ``coordinator.state_fingerprint(iot_id)`` differs from the value
  the entity last wrote.
- ``state_fingerprint`` covers the wire payload the model was built from and the
  values this integration stages locally (pending amounts, the store-as-default
  switch, the last stored feed), so a real change or a user action still writes.
- An unknown model keeps writing, so entities report being unavailable.
- The guard logs one line per state it reports so the residual can be counted
  with a journal grep; that line is a measuring aid, removed if the branch is kept.
- The branch does not change the scan interval. The entry's `scan_interval`
  option was raised to 300 s on the production box by hand, which divides both
  this queue and the cloud session churn by five; it is shared with
  [cloud-session-churn.md](cloud-session-churn.md) and the code here stays the
  other variable.

## Measured before

Current log of the production server, 2026-10-25, and the rotated log of 2026-10-15
(before the Riko work), counted with:

```bash
grep -c "unable to keep up with pending messages" /var/log/homeassistant/warnings.log
grep -c "Login attempt or request with invalid authentication" /var/log/homeassistant/warnings.log
```

- 2026-10-25: 26 of the first, 3 of the second, at 01:34, 02:02, 02:04, 21:24, 21:44, 22:00
- 2026-10-15: 22 of the first
- 2026-10-16 until 2026-10-24: 0 of the first

## Measured after (fill in on the day after publishing)

Same commands, per hour, with the branch build running:

- TODO

## Decision

Keep it if the reports stop while the device is idle and the entities still update
when the machine is used (a press must still log Riko feedOnce, and the numbers
must still show staged values). Discard the branch and re-publish the shipped beta
otherwise. Nothing on main refers to this file.
## Counting what the guard still writes

The guard logs one line per state it actually reports, tagged like the rest of
the integration, so the residual can be counted separately from the app-side errors:

```bash
journalctl -u homeassistant --since "-1 hour" | grep -c "Reported state for"
```

An idle machine should show a short burst (the first scan after a start, then the
real changes only). If that count is small while the apps still reconnect, the rest
of the queue belongs to other integrations of this install, not to this one. That
line is a measuring aid: raise it back to debug when this branch is kept, and it
is at INFO now only so the count is visible without enabling debug logging.

Window used: 23:06:30 until 23:08:26 on 2026-10-25, two of our own scans.

- states reported by the guard: 29 in total, and the count per entity is exactly 1
  (that is the first scan after a start; the second scan reported nothing)
- websocket overflows in that window: 0, whereas the start before this change had 8
  inside its first minute, and the day before had 26 across the hours
- our own fetches in that window: 2, both successful

The next day this file gets the steady-state numbers, both sides of the same
command, before the branch is kept or discarded.
