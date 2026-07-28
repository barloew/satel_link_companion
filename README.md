# Satel Link Companion

<img src="https://raw.githubusercontent.com/barloew/satel_link_companion/main/custom_components/satel_link_companion/brand/icon.png" alt="Satel Link Companion" width="120" align="right" />

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=barloew&repository=satel_link_companion&category=integration)

A Home Assistant companion for the Satel Integra Panel. Satel Link Companion links Home
Assistant sensors into the Satel Integra Panel as real Satel zones — supervised by
the panel and armed together with their partition — bundles
available Satel roller-shutter output pairs into a single Home Assistant cover unit, and
lets you expose one (HomeKit-compatible) master alarm panel that arms and disarms several
Satel Integra partitions as a single unit.

It leverages an existing Satel base integration rather than replacing it. The Satel ETHM-1
module accepts only one client on its integration port, so at runtime Satel Link Companion
holds no connection of its own: it actuates the base integration's output switches and
reads arm state from its `alarm_control_panel` entities. The only direct connection is a
one-off scan to map the Satel Integra system structure.

## Existing Satel Integra base integration capabilities

Your Satel Integra base integration already exposes the panel's objects in Home Assistant.
Satel Link Companion does **not** duplicate those; it leverages and extends them.

| Satel object | Base integration | Direction | Capability |
|---|---|---|---|
| Zone | `binary_sensor` | Satel → HA | monitor a Satel detection / temperature point in Home Assistant |
| Virtual Zone | `switch` | HA → Satel | actuate a Satel zone from Home Assistant (ETHM-1 Plus only) |
| Output | `binary_sensor` | Satel → HA | read-only Satel device / event status in Home Assistant |
| Switchable output | `switch` | HA → Satel | actuate a Satel switch from Home Assistant |

## What Satel Link Companion adds on top

| Built from | Satel Link Companion | Direction | Capability |
|---|---|---|---|
| Switchable output + zone that follows it | `link` | HA → Satel | actuate a Satel zone with any Home Assistant sensor (ETHM-1-compatible) |
| Switchable output pair | `cover` | HA → Satel | control a Satel roller shutter as a single unit from Home Assistant |
| Partitions | `alarm_control_panel` | (HomeKit) → HA → Satel | a single alarm-panel tile in Home Assistant (HomeKit compatible) |

Plus diagnostic **event sensors** and an active **pre-arm blocker check** (see below).

## Requirements

- **Home Assistant 2025.7 or newer** (the integration uses config sub-entries).
  The integration icon shows automatically on HA 2026.3+; on older versions it
  falls back to a default icon.
- An **INTEGRA** or **INTEGRA Plus** panel (not VERSA/PERFECTA).
- An **ETHM-1** or **ETHM-1 Plus** module, with *Integration* enabled in DLOADX.
- A working Satel base integration in Home Assistant — either
  [`satel_integra`](https://www.home-assistant.io/integrations/satel_integra/)
  (core) or `ha_satel_integra_ext`.
- For linking: a switchable output (function **24 MONO** or **25 BI**) and a zone
  with wiring type **8 (follow output)**, plus a user with rights to that output.

The protocol client that performs Satel Integra system-structure mapping and zone bypass
is bundled (vendored) in `custom_components/satel_link_companion/vendor/`, so no extra
library is required beyond `cryptography` (already a Home Assistant dependency). The
vendored client is MIT-licensed; see its NOTICE and LICENSE for credit to the upstream
`satel_integra2` projects.

See the wiki/docs for the full DLOADX checklist, including the polarity (POL.+) and
user-rights pitfalls.

> **Note.** The runtime architecture and the link test leverage the Satel integration
> protocol. As with anything alarm-related, confirm the behaviour against your own Satel
> alarm panel hardware before you rely on it.

## Installation

### HACS (recommended)

1. In HACS, add this repository as a custom repository
   (`https://github.com/barloew/satel_link_companion`, category *Integration*).
2. Install **Satel Link Companion**.
3. Restart Home Assistant.
4. Add the integration under *Settings → Devices & Services → Add Integration →
   Satel Link Companion*.

### Manual

Copy `custom_components/satel_link_companion/` into your Home Assistant
`config/custom_components/` directory and restart.

## Configuration

Setup adopts your Satel Integra base integration (host, port, code) automatically. From the
integration page you then **add** links, roller shutters and master panels — each becomes
its own device — and use the options menu for discovery and the guard-time window settings:

- **Map Satel Integra system structure** — a one-off scan of the panel. It briefly unloads
  the base integration (one client at a time), then reloads it. The result is cached.
- **Link a sensor** — pick a Home Assistant source sensor, a Satel switchable output and the
  Satel zone that follows it. Satel Link Companion validates the combination (function,
  device class) and lets you select when to actuate the linked Satel zone.
- **HA roller shutter** — bundle a roller-shutter output pair (up/down) into one `cover`.
  Plain switches and read-only outputs are not duplicated here: your Satel base integration
  already provides those, and Satel Link Companion references them rather than creating a
  second copy.
- **Master panel** — one `alarm_control_panel` that arms several partitions as a unit
  (see below).
- **Settings** — the breach guard-time window, system-wide with an optional per-partition
  override.

### Satel zone actuation

Each **link** (from a Home Assistant source sensor) can actuate its Satel zone in three ways:

- **Continuously** — a breached source sensor immediately violates the Satel zone and always
  triggers an alarm, even when the partition is disarmed. Best for monitoring heat / smoke /
  gas / moisture hazards.
- **Via partition arming** — a breached source sensor violates the Satel zone, which then
  triggers an alarm only after the partition is armed. Best for burglary protection; in
  particular a solution for ETHM-1-based panels that lack the ETHM-1 Plus Virtual Zone capability.
- **Via partition arming — with entry/exit delay** — as above, but breach status is blocked
  during a configurable entry/exit delay. Best for entry/exit zones.

A minimum on-time keeps brief pulses (a flickering PIR) visible to the panel.

### Master panel

HomeKit couples one accessory to one alarm panel, so with several partitions you can
normally control only one at a time from HomeKit. A master panel aggregates several
partitions into one `alarm_control_panel` tile.

- Partitions arm **in the order you set** (interior before perimeter, say), each verified
  before the next. The pre-arm blocker check (see below) runs first for every partition.
- If a partition does not confirm, the master **rolls back** — it disarms whatever it already
  armed and fires `satel_link_companion_arm_failed` — so the tile never claims "armed" while
  the system is only half-armed.
- Each mode drives **its own set of partitions**, in arm order: **Home** → `alarm_arm_home`
  (the Satel mode follows your `arm_home_mode`), **Away** → `alarm_arm_away`, **Night** →
  `alarm_arm_night`. Leave a mode empty and the panel does not offer it. Disarm ("off")
  disarms every partition any mode uses, in numeric order.

**Code handling.** Arming a partition needs a user code. Satel Link Companion never stores
it — it passes through whatever Home Assistant supplies:

- In the normal HA UI, HA prompts for the code and passes it on. The user whose code is
  entered must have rights on **all** partitions in the master.
- HomeKit cannot prompt for a code, so supply it in the HomeKit bridge config:

  ```yaml
  homekit:
    - name: HA Bridge
      # ...
      entity_config:
        alarm_control_panel.alarm_master:
          code: !secret alarm_panel_usercode
  ```

  Use a dedicated Satel user with arm/disarm rights on exactly the master's partitions,
  rather than sharing your own code.

## Events and services

Satel Link Companion fires events you can build automations on:

- `satel_link_companion_arm_blocked` — partition plus the burglary zones that would block an arm.
- `satel_link_companion_breach` — partition plus the zones breached in the guard-time window
  before the partition was triggered.
- `satel_link_companion_arm_failed` — partition plus the reason a master arm was rolled back
  (blocked, or no confirmation).

Each event is also surfaced as a diagnostic sensor — **Last breach**, **Last arm blocked**
and **Last arm failed** — whose state is the time of the last such event and whose
attributes carry the partition and the zones involved. See [`EVENTS.md`](EVENTS.md) for the
full payloads and example automations.

And a service for an active pre-arm check:

- `satel_link_companion.check_arm` — returns the zones blocking an arm for a partition (and
  fires `satel_link_companion_arm_blocked`). Use it to notify or to hold off before arming.

## Verifying a link

Two parameters that carry a link cannot be read over the Satel Integra integration protocol
— the wiring type and the output polarity — so Satel Link Companion verifies them instead:

- A **passive coherence check** compares the output and zone at rest; an inverted polarity
  shows up as a zone violated while idle.
- An **active link test** bypasses the zone (so it cannot trigger an alarm), toggles the
  output, and checks the zone follows.

## Inner workings

For the advanced Home Assistant user who wants to know exactly how a link behaves at the
edges. All of this follows a fail-silent principle: whenever something breaks, the Satel
zone returns to rest (off) — never to a spurious alarm.

### Fail-silent rest state — `not_from`, no `not_to`

A link mirrors its Home Assistant source onto the switchable output: source `on` → output
actuated (the zone is violated); anything else → output at rest. "Anything else"
deliberately includes `unavailable` and `unknown`, so a dropped sensor, a Home Assistant
restart, or an ETHM-1 hiccup returns the zone to rest rather than raising an alarm.

Two edge rules make this robust (mirrored from a hand-tuned production automation):

- **`not_from` — ignore recovery.** A source transition *from* `unavailable` / `unknown` is
  skipped. A sensor that reconnects and happens to report `on` is not a fresh detection, so
  it does not raise the output. Without this, every reconnect that lands on `on` would trip
  the zone.
- **No `not_to` — honour dropout.** A source transition *to* `unavailable` / `unknown` is
  **not** skipped: it falls through to "not on" and drives the output off. A sensor that
  drops out while detecting therefore returns the zone to rest, instead of leaving it stuck
  violated.

Net rule: `off → on` raises; every other change (including any transition *to* unavailable)
lowers; transitions *from* unavailable are ignored.

### Entry / exit zones — the exit window

An **entry-delay** link is the entry/exit-zone mode, and it treats the arming moment
specially so that walking out and in never false-triggers:

- **On arming**, the output is forced off and an **exit window** of `entry_delay_s` opens.
  During that window *all* motion is ignored — even motion that starts after you armed (you
  walking to the door). The forced-off then **persists as long as the source stays on**, so
  you are never caught mid-exit.
- **After** the exit window closes *and* the source has returned to rest, a fresh violation
  starts the **entry delay** (`entry_delay_s`). Disarm within it and no alarm fires;
  otherwise the zone violates.
- **On a restart while armed**, the link treats startup like an arming moment — it starts at
  rest and ignores motion already present — so a reboot can never instantly alarm an entry
  zone.

### Other behaviours

- **Forwarding gate.** *Continuously* forwards always; *via partition arming* forwards only
  while the zone's partition is armed; *entry delay* is the mode above.
- **Minimum on-time (`min_on_s`).** Holds the output on for at least this long, so a brief
  pulse (a flickering PIR, a fast reed contact) stays visible to the panel instead of being
  missed.
- **Invert.** Corrects the output polarity (DLOADX `POL.+`), which the protocol cannot read;
  an inverted link reports "violated" when the output is off.
- **No runtime socket.** The ETHM-1 allows one client, so at runtime the companion never
  connects: it calls the base integration's `switch` services to drive outputs and reads
  partition state from the base `alarm_control_panel` entities, reacting to Home Assistant
  state-change events. The single direct connection is the one-off structure scan.
- **Master arming.** Partitions arm sequentially in your set order; each is checked for
  blockers and confirmed before the next, and any failure rolls the whole attempt back so
  the tile never reports a half-armed system.
- **Breach snapshot.** When a partition goes to *triggered*, the companion looks back over
  the guard-time window at recent zone violations to report which zones were involved.

## License

Released under the [MIT License](LICENSE).

Not affiliated with SATEL sp. z o.o. "Satel" and "Integra" are trademarks of their
respective owner.
