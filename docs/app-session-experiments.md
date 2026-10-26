# Experiments: which of our calls take the app's session, and which take ours

Both symptoms in [cloud-session-churn.md](cloud-session-churn.md) and
[app-websocket-flood.md](app-websocket-flood.md) are about who owns the
account's session. This integration and the Neakasa mobile app authenticate the
same account, so a call that changes that ownership breaks one side while the
other is busy. What is needed is a measured answer to two questions:

1. **HA to app:** which of our calls makes the app ask to sign in again?
2. **App to HA:** which of the app's calls makes our next scan fail?

## What is already measured

From `journalctl -u homeassistant` on 2026-10-26:

```text
10:14:37.876  Authenticating shared API client for tabascoz@gmail.com
10:14:40      the mobile app was found on its login page by the user
10:14:45.890  Finished fetching neakasa ... data in 8.014 seconds (success: True)
```

A sign-in is followed 2-3 seconds later by the app losing its session. That is
the only single-sign-in event in the log for that period, so the reading is
narrow: one `apiLogin` is enough. The opposite direction has never been
observed while a scan was running, and the matrix below settles it.

Also measured in the same period: `Reported state` lines appear 0 times for the
feeder (`wl03002g26270011577`) and 19 times per scan for the litter box
(`jq01909g25430010947`) — the guard works, but its stamp covers the whole
device model, and the model changes whenever a cat is recorded.

## Why the journal had to be extended first

A write that the gateway accepts is invisible in the log: `api.py:_iot_request`
logs only errors, so "did this press touch the cloud" cannot be answered, and
without that an app observation cannot be attributed to a press. The two lines
the instrumented build adds are the measurement, not a behaviour change:

```text
Account session minted #1 for tabascoz@gmail.com: cause=coordinator asked for a client (nothing cached for these credentials yet)
Cloud write: /thing/service/invoke iotId=4TQDtRLglcQJ5goDNlug000000 identifier=cleanNow args={'bStartClean': 1}
```

## Second instrument: the accepted account calls

The run of 16:2x on the same unit showed the first instrument was not enough: a
sign-in and a write are visible, but the calls that only *read* the account -
`/uc/listBindingByAccount` and `/catbox/record` - return 200 and logged nothing,
so the half of the lever that is always accepted could only be counted by
inference. The build now names those too, beside the write line:

```text
Account presentation: /uc/listBindingByAccount
Account presentation: /catbox/record device=T1 Plus
```

`api.py:_PRESENTATION_PATHS` and `api.py:_describe_presentation` are the whole
change: a log line, no behaviour, so the count of presentations per hour - what
the app's re-asks follow - can be read instead of guessed.

A third instrument is for the one quantity the runs kept hitting: how long a
session lives once it stops being presented. The login answer is the only place
the cloud could state it for free - every start already pays one sign-in - so the
build also names the fields it received, values never:

```text
Login fields: code data data.login_token data.user_info data.user_info.sid
```

`api.py:_describe_fields` is the whole change. What to read for is a lifetime: a
field under `data` or `data.user_info` whose name words a duration
(`session_over_time`, `expires_in`, `ttl`, a seconds count). If one is there,
`SESSION_EVIDENCE_HOLD_MINUTES` stops being a placeholder and becomes what the
cloud says it is; if none is, the number stays as open as X9 says it is, and the
only way to know it is to watch the app ask - which is also the only way that
costs the account a session.

## Running the matrix

On the unit, paste these once:

```bash
check() {   # what our code asked of the cloud in the last N minutes
  since=$(date -d "$2 min" '+%Y-%m-%d %H:%M')
  printf '== %s since %s ==\n' "$1" "$since"
  journalctl -u homeassistant --since "$since" --no-pager |
    grep -E 'Account session minted|Account presentation|Cloud write|IoT cloud error|Session expired|TokenInvalid|identityId|Renewed the cloud|Reconnect|Authenticating|Debug tokens' |
    tail -15
}
states() {  # entity states written, counted per minute
  journalctl -u homeassistant --since "$2 min" --no-pager |
    grep -E 'Reported state' | grep -oE '[0-9]{2}:[0-9]{2}' | sort | uniq -c
}
```

Before **every** experiment: sign into the app, make it show a value that only
exists now (feed the Riko, or read the last-activity timestamp), and note that
time as `T0`. Act at `T1`, read the app at `T1+30s`. Run each id twice about
20 minutes apart: the app's own session ages on its own schedule, so only a
cause that reproduces at both of our timestamps is ours.

| id | what to do | `check` must show | app after |
|----|-----------|-------------------|-----------|
| X1 | let two scans run, touch nothing | nothing at all | ok |
| X2 | press **clean** on the litter box | one `Cloud write ... /thing/service/invoke ... cleanNow` | ? |
| X3 | press **level** | one `Cloud write ... sandLeveling` | ? |
| X4 | press **Feed now** on the Riko | one `Cloud write ... feedOnce` | ? |
| X5 | toggle a switch (`auto_clean`) twice | two `Cloud write ... /thing/properties/set` | ? |
| X6 | set a number (food quantity) | one `Cloud write ... defFdCfg` | ? |
| X7 | press/trigger **invalidate** (breaks our tokens) | `Debug tokens invalidated`, no `Cloud write`; at the next scan `Session expired...` then `Account session minted` | ? at the press, ? after the recovery |
| X8 | `systemctl stop` then `systemctl start` | exactly 1 `Account session minted ... cause=coordinator asked for a client (nothing cached...)` | re-asks (already measured) |
| Y1 | sign into the **app**, touch nothing in HA | clean scan, no failure lines | - |
| Y2 | same, look for the failure signature | `IoT cloud error ... identityId is blank` then a minted session | - |
| Y3 | sign into the app 3 times in a row | whether our access fails after the 1st or after the 3rd | - |
| Y4 | do a **write in the app** (feed there) rather than a login | whether our next scan still works | - |
| Z1 | leave everything untouched for one hour | expect 0 minted sessions - that is the natural rate | ok |
| X10 | read one boot's `Login fields:` line | the field names of the login answer, values never | names a session lifetime only if the cloud sends one |
| X9 | sign into the app, then leave both clients alone for 20 minutes | only our own `Account presentation` lines, at the cadence the caches set | the first minute the app asks again is a session's own lifetime |

## Reading the results

| if the matrix shows | the change that follows |
|---------------------|-------------------------|
| X2-X6 break the app, X1 does not | the write is the cause. Keep the buttons, proactively renew our IoT token after a write (`api.py:_refresh_iot_token`, which costs no session), and say in the log that a press used the shared account session. |
| only X8 breaks it | sign-ins are the cause: do not sign in automatically outside startup; renew the token, else raise `UpdateFailed` and use `config_entry.async_start_reauth` so the handover is a user choice. |
| both X and Y break the other client | the account has one usable session. A `session_owner: ha | app` option decides which client we are willing to keep deaf; the counter makes a silent ping-pong visible instead of invisible. |
| Y2 shows blank-identity then a minted session | `api.py:331-332` marks the client disconnected on an aged IoT token, which is what forces the full sign-in at `api_manager.py:37-38`. Fixing that path removes those sign-ins entirely. |
| Z1 shows more than one mint per hour | something still signs in on the healthy path, and the `cause=` in the new line names it. |

## State writes, counted by the same runs

`states()` gives the number for the other axis. 19 states per scan for a box the
cats are using is not the queue flood that [app-websocket-flood.md](app-websocket-flood.md)
describes, but it is the same kind of noise; the fix is a stamp per entity rather
than per device model, so a new cat record refreshes `last_usage` and the cat
sensors only.

## Results, filled from the runs of 2026-10-26

| id | app | evidence from `check` | reproduced |
|----|-----|------------------------|------------|
| X1 / C0 / C0b | ok, data loads | our log empty between the sign-in and the read; the scans at 11:14:43 and 11:24:43 attempted no account call | twice, 11:15 and 11:25 |
| XS - an ordinary scan | re-ask at 11:22, 11:29:55, ~11:36, ~11:41, ~11:56, 12:01:30 | `/uc/listBindingByAccount code=401` at 11:29:43, 11:35:43, 11:40:43, 11:55:45, 12:00:46 and an accepted call at 11:19:43, each scan `Finished fetching ... success: True`, no mint | six times |
| X2 - Clean press in HA | re-ask 11:22 | `11:21:11.507 Cloud write: /thing/service/invoke ... cleanNow` | once |
| X5 - switch flip in HA | re-ask 11:31:05 | `11:30:39.890 Cloud write: /thing/properties/set ... cleanCfg active:0` and `11:30:43.754 ... active:1` | once |
| XH - the machine's own button | **ok, no re-ask**, and the app lists the manual event it created | nothing at all from our client between 11:51:00 and 11:55:30; the physical press at 11:51:30 made no `Cloud write` | once, in a window with no scan in it |
| X7 - debug invalidate in HA | ok at 11:58:30, re-ask at 12:01:30 | `11:57:18.611 Debug tokens invalidated`; the next scan `12:00:46 ... code=401` + `TokenInvalid ... does not contain the @ sign` then `Finished fetching ... success: True` - no `Session expired, reconnecting silently`, no mint | once |

## The run of 16:20 - 16:32, and what it says about a session's own life

Restart at 16:20, app signed into at 16:22:15, app found needing a sign-in again
at 16:29. What our client did in that window, from the journal:

| time | lines | account presentations |
|------|-------|------------------------|
| 16:20:33 | `Account session minted #1 ... (nothing cached for these credentials yet)`, `Login response - Status: 200`, boot scan 28.3 s | sign-in, then list and records, all accepted |
| 16:26:02 | `Reusing shared API client`, two `Getting device properties`, `0.385 seconds (success: True)` | none - the caches served the list and the records |
| 16:31:02 | same shape, `0.486 s`, no `The account refused` line | the device list again (its cache was due at ~16:30:47), accepted |

What that settles:

- The app losing its session at 16:29 has no cause in our client: nothing between
  the login at 16:22:15 and 16:29 presented the account. A session that nobody
  presents ages out on its own, minutes after being handed over.
- A claim about the owner is only true near the observation that made it. The
  whole basis for reporting `home_assistant` at 16:29 is an accepted call at 16:20,
  which is why the value now decays to `unknown` past `SESSION_EVIDENCE_HOLD_MINUTES`
  and the attributes carry `last_presented_at`, `last_presented_call` and `refused_at`.
- What it opens: the lifetime itself. 16:2x shows minutes, the hour of 12:02-13:02
  shows less than an hour. X9 measures it; the constant stays a placeholder until
  then.

## The rule the runs support

Presenting the account to the cloud moves the session, whether the request is
accepted or refused. Every scan that attempted `/uc/listBindingByAccount` left the
mobile app needing a sign-in about a minute later - the refusals did it exactly as
the accepted call at 11:19:43 did. A scan that attempted no account call left the
app alone, which is what the two control runs measured. Writes from HA move it too
(X2, X5). The machine's own physical action does not (XH), and the app's own
activity does not hurt the app - it hurts our client, which is what the 401s are.
So the lever is the number of account presentations per unit of time; the number of
sign-ins is not a lever at all (one mint in the whole run, at the HA start).

## The hour with nobody using either client, 12:02 - 13:02

12 completed scans, all reporting `success: True`, and 0 mints. The records call
was refused on all 12 (`Error getting data: TokenInvalid ... token does not contain
the @ sign`), so for one hour Home Assistant reported cat weights, `last_usage` and
bin states that the cloud had refused, and nothing ever asked the session back. No
`Reported state` line appeared in that hour: the writes at 11:55 (38) and 12:00 (0)
differ only because the model changed in the first one.

## The settings that followed the rule

Two options exist now, both per config entry (options flow, applied on a
reload of the entry, which the integration already does for its update
listener):

Three things now set the rate at which the account is presented, all of them
per config entry or in code where no user chooses it:

- `account_session_window_minutes` (5-720, default 30): how long a refusal keeps
  the account from being presented again.
- `session_regain_policy` (`never` | `window` | `always`, default `window`): how
  control is taken back - never (the account button is the only way), at the end
  of the window (default), or on every scan while the session is elsewhere.

Expected sessions per hour while the app is being used, on the 5-minute cadence
this entry runs (measured before the change: 12 account presentations an hour,
0 sign-ins, and the records refused on all 12):

| window | `never` | `window` | `always` |
|--------|---------|----------|----------|
| 30 min | 0 | <=2 | <=12 |
| 5 min | 0 | <=12 | <=12 |

The cadence no user chooses: the account device list is cached for six hours
(`coordinator.py:DEVICE_LIST_REFRESH_MINUTES`) instead of ten minutes, because a
list call is a presentation and ten minutes costs six an hour on its own. A device
added to the account is found by the `Refresh data now` button or on a config
reload, which is the manual path that already exists.

Those are predictions to be measured, not measurements. The runs that set them are
the ones above, and the `Account presentation:` lines are what turns them into
measurements: count them with `grep -c 'Account presentation'` over a fixed period
instead of inferring them from the app asking to sign in.
