# Satel Link Companion — events

Satel Link Companion fires three events on the Home Assistant event bus. Use them in
automations (Settings → Automations → Trigger → *Event*), or read the last
breach directly from the diagnostic **Last breach** sensor.

All three carry a `partition` (the Satel partition number) and, where relevant, a
`zones` list. Each zone is `{"number": <int>, "name": <str>, "function": <str|null>}`.

> The notify examples use `notify.send_message`, the entity notify action
> ([docs](https://www.home-assistant.io/integrations/notify/)). Replace
> `notify.your_notifier` with one of your own notify entities (for example your
> mobile app or `notify.persistent_notification`).

---

## `satel_link_companion_breach`

Fired when a partition becomes **triggered** (an alarm). It reports every zone
that was violated in the guard-time window just before the trigger — the "who set
it off" snapshot. The window is the value you set under *Set the Home Assistant
guard time window for Satel* (system-wide, or per partition).

```yaml
event_type: satel_link_companion_breach
data:
  partition: 1
  window_s: 8.0
  zones:
    - { number: 23, name: "Living room", function: "Interior" }
    - { number: 27, name: "Garage", function: "Interior" }
```

Example — notify which zones tripped the alarm:

```yaml
automation:
  - alias: "Alarm — report breached zones"
    triggers:
      - trigger: event
        event_type: satel_link_companion_breach
    actions:
      - action: notify.send_message
        data:
          entity_id: notify.your_notifier
          title: "Alarm in partition {{ trigger.event.data.partition }}"
          message: >
            {{ trigger.event.data.zones | map(attribute='name') | join(', ') }}
```

The **Last breach** sensor mirrors this event: its state is the time of the last
breach, and its attributes hold `partition`, `window_s`, `zones` and
`zone_count`.

---

## `satel_link_companion_arm_blocked`

Fired when an arm is refused because one or more zones are currently violated
(open door, active motion). Raised by the pre-arm check, including the master
panel's per-partition check before it arms.

```yaml
event_type: satel_link_companion_arm_blocked
data:
  partition: 1
  zones:
    - { number: 24, name: "Back door", function: "Delay" }
```

Example — tell the user why arming did nothing:

```yaml
automation:
  - alias: "Arm blocked — say which zones"
    triggers:
      - trigger: event
        event_type: satel_link_companion_arm_blocked
    actions:
      - action: notify.send_message
        data:
          entity_id: notify.your_notifier
          message: >
            Cannot arm partition {{ trigger.event.data.partition }} —
            open: {{ trigger.event.data.zones | map(attribute='name') | join(', ') }}
```

---

## `satel_link_companion_arm_failed`

Fired by the master panel when a sequential arm could not complete, after it has
rolled back whatever it already armed (so the system is never left half-armed).

```yaml
event_type: satel_link_companion_arm_failed
data:
  partition: 2               # the partition that failed
  reason: "no_confirmation"  # or "blocked"
  zones: []                  # present only when reason == "blocked"
```

`reason` is:

- `blocked` — a zone was violated (the same zones as `satel_link_companion_arm_blocked`);
- `no_confirmation` — the partition did not report back as armed within the
  timeout, so the master rolled the whole attempt back.

Example — alert on a failed master arm:

```yaml
automation:
  - alias: "Master arm failed"
    triggers:
      - trigger: event
        event_type: satel_link_companion_arm_failed
    actions:
      - action: notify.send_message
        data:
          entity_id: notify.your_notifier
          message: >
            Arming failed for partition {{ trigger.event.data.partition }}
            ({{ trigger.event.data.reason }}). Everything was rolled back.
```
