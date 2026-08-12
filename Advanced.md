# Satel Link Companion — Advanced guide

The [README](README.md) covers what Satel Link Companion is for and how to install it. This
guide is the detail: how it works, what to set on the Satel side, and how each feature behaves
at the edges. You don't need any of it to get started, but it's here when you want it.

## How it works

Your Satel base integration already exposes the panel's objects in Home Assistant. Satel Link
Companion does **not** duplicate those — it leverages and extends them.

| Satel object | Base integration | Direction | What you get |
|---|---|---|---|
| Zone | `binary_sensor` | Satel → HA | monitor a Satel detection point in Home Assistant |
| Virtual Zone | `switch` | HA → Satel | actuate a Satel zone from HA (ETHM-1 **Plus** only) |
| Output | `binary_sensor` | Satel → HA | read a Satel device / event status in Home Assistant |
| Switchable output | `switch` | HA → Satel | actuate a Satel switch from Home Assistant |

On top of that, Satel Link Companion adds:

| Built from | Adds | Direction | What you get |
|---|---|---|---|
| Switchable output + a zone that follows it | `link` | HA → Satel | actuate a Satel zone with any HA sensor (works on plain ETHM-1) |
| Switchable output pair | `cover` | HA → Satel | a Satel roller shutter as one Home Assistant unit |
| Several partitions | `alarm_control_panel` | (HomeKit) → HA → Satel | one alarm tile that arms several partitions together |

Plus diagnostic **event sensors** and an active **pre-arm blocker check**.

**No second connection.** The Satel network module (ETHM-1) accepts only one integration client,
so at runtime Satel Link Companion holds no connection of its own: it calls the base
integration's `switch` services to drive outputs and reads partition state from the base
`alarm_control_panel` entities. The only direct connection is a one-off scan to map the panel's
structure, which briefly unloads and reloads the base integration.

The protocol client used for that scan is bundled (vendored), so you need no extra library
beyond `cryptography` (already part of Home Assistant). It is MIT-licensed; see its NOTICE and
LICENSE for credit to the upstream `satel_integra2` projects.

## Preparation (the Satel side)

A little groundwork up front — first in **DLOADX**, then in your **base integration** — makes
everything after it smooth. This is aimed mainly at the **link** feature.

### In DLOADX (the panel)

- **Switchable outputs.** For every zone you want to drive from Home Assistant, create a
  switchable output with function **24 (MONO)** or **25 (BI)**.
- **Follow-output zones.** Give each such zone wiring type **8 (Follow output)**, pointing at
  its output. That is what makes the Satel zone mirror the output — and therefore your sensor.
- **Use 24-hour zone functions.** Every follow-output zone should use a **24-hour**
  (continuously monitored) function, because the *when to alarm* decision is made in Home
  Assistant by Satel Link Companion, not by the Satel partition. Use **88 (24H Burglary)** for
  the motion / door / window zones you gate through arming in Home Assistant, and the matching
  24-hour fire / gas / water functions for hazard sensors. A non-24-hour zone would only alarm
  while its partition is armed — double-gating against the link's own mode.
- **Polarity (POL.+).** Set the output polarity correctly. The protocol can't read it back, so
  if it's wrong the zone reads violated at rest; you can correct that per link with *Invert*, but
  getting POL.+ right in DLOADX is cleaner.
- **Same number for a zone and its output.** By convention the zone that follows output *N* is
  zone *N*. Numbering them identically keeps the mapping obvious.
- **Roller shutters.** For a shutter cover, use a roller-shutter output pair (outputs
  **type 105/106**).
- **Not-bypassable off** on any zone you want to run the active link test against — the test
  bypasses the zone so it can toggle the output without setting off a real alarm.
- **Partitions for HomeKit modes.** Divide zones over partitions that map onto the arm modes you
  want — typically interior (Home/Away), perimeter, and a 24-hour / emergency partition. A master
  panel later drives **Home → arm_home**, **Away → arm_away** and **Night → arm_night**, each over
  its own partition set.
- **A user with the right rights.** Actuating a switchable output needs a Satel user with rights
  to that output; arming from a master needs a user with rights on exactly those partitions.
  Create a dedicated Home Assistant user rather than sharing your own code.

See **[SATEL_TYPES.md](SATEL_TYPES.md)** for the full list of zone functions, wiring types and
output functions.

### In the base integration

Before you touch Satel Link Companion, create and configure the partitions, zones and
(switchable) outputs in your Satel base integration first. Two reasons:

- **They must exist there first** — the link flow only offers zones and outputs that already
  exist in the base integration.
- **Give them recognizable names and areas** — Satel Link Companion adopts those for its own
  devices, so naming and placing them well once makes the whole device tree readable later.

## Configuration

From the integration page you **add** links, roller shutters and master panels (each its own
device), and use the options menu for discovery and the guard-time settings:

- **Map Satel Integra system structure** — the one-off scan (cached afterwards).
- **Link a sensor** — pick a Home Assistant source sensor, a switchable output and the zone that
  follows it. It validates the combination and lets you choose when the zone is actuated.
- **HA roller shutter** — bundle an up/down output pair into one `cover`.
- **Master panel** — one `alarm_control_panel` that arms several partitions as a unit.
- **Settings** — the breach guard-time window, system-wide with an optional per-partition
  override.

### When a link actuates its zone

Each link can actuate its Satel zone in three ways:

- **Continuously** — a breached sensor immediately violates the zone and always triggers an
  alarm, even when disarmed. Best for heat / smoke / gas / moisture hazards.
- **Via partition arming** — a breached sensor violates the zone, which triggers an alarm only
  once the partition is armed. Best for burglary protection — and the way to get "virtual zone"
  behaviour on a plain ETHM-1.
- **Via partition arming, with entry/exit delay** — as above, but breach status is blocked during
  a configurable entry/exit delay. Best for entry/exit doors.

A minimum on-time keeps brief pulses (a flickering PIR) visible to the panel.

### Devices

Everything you add is its own device, organised to mirror your Satel layout:

- The **hub** takes the name and area of your Satel base central device.
- Each **link** takes the name and area of the base zone it drives, and nests under a
  **partition** grouping node.
- Names and areas are defaults you can override — rename or move a device and Satel Link
  Companion leaves your change alone.

Each link also carries two status sensors: **Forwarding unblocked** (whether it's currently
allowed to forward — always for continuous links, only while armed for arming-based links) and
**Forwarding active** (whether a violation is being forwarded right now).

## Master panel

HomeKit couples one accessory to one alarm panel, so with several partitions you can normally
control only one at a time. A master panel aggregates several into one tile.

- Each mode drives **its own set of partitions**, in the order you set: **Home** → `alarm_arm_home`
  (following your `arm_home_mode`), **Away** → `alarm_arm_away`, **Night** → `alarm_arm_night`.
  Leave a mode empty and the panel doesn't offer it. Disarm clears every partition any mode uses.
- **One pre-flight blocker check.** Before arming anything, it checks *all* of the mode's
  partitions at once and, if any zone is open, fires a single `arm_blocked` listing every open
  zone across those partitions — then arms nothing. You fix everything in one pass.
- **Rollback.** Once arming starts, partitions arm one by one and each is confirmed; if one never
  confirms, the master disarms whatever it already armed and fires `arm_failed`, so the tile never
  claims "armed" while the system is only half-armed.

**Code handling.** Arming needs a user code. Satel Link Companion never stores it — it passes
through whatever Home Assistant supplies. In the normal UI, Home Assistant prompts for it. HomeKit
can't prompt, so supply it in the HomeKit bridge config:

```yaml
homekit:
  - name: HA Bridge
    entity_config:
      alarm_control_panel.alarm_master:
        code: !secret alarm_panel_usercode
```

Use a dedicated Satel user with rights on exactly the master's partitions.

## Events and services

Satel Link Companion fires events you can build automations on — `arm_blocked`, `breach` and
`arm_failed` — and each is mirrored as a diagnostic sensor (**Last breach**, **Last arm blocked**,
**Last arm failed**). It also offers a `satel_link_companion.check_arm` service that returns the
zones blocking an arm for a partition. See **[EVENTS.md](EVENTS.md)** for the full payloads and
example automations.

## Verifying a link

Two things that carry a link can't be read over the protocol — the wiring type and the output
polarity — so Satel Link Companion verifies them instead:

- A **passive coherence check** compares output and zone at rest; inverted polarity shows up as a
  zone violated while idle.
- An **active link test** bypasses the zone (so it can't alarm), toggles the output, and checks the
  zone follows.

## How links behave at the edges

All of this follows a fail-silent principle: whenever something breaks, the zone returns to rest
(off) — never to a spurious alarm.

**Fail-silent rest state.** A link mirrors its source onto the output: source `on` → zone violated;
anything else (including `unavailable`/`unknown`) → zone at rest. So a dropped sensor, a restart or
a hiccup returns the zone to rest rather than alarming. A source coming back *from* `unavailable`
and reporting `on` is treated as a reconnect, not a fresh detection, so it doesn't raise the zone;
a source dropping *to* `unavailable` while detecting *does* return the zone to rest.

**Entry / exit window.** On arming, an entry-delay link forces the output off and opens an exit
window: all motion is ignored while you walk to the door, and the forced-off persists as long as
the source stays on, so you're never caught mid-exit. After the window closes and the source
returns to rest, a fresh violation starts the entry delay; disarm within it and no alarm fires. A
restart while armed is treated like an arming moment, so a reboot can never instantly alarm an
entry zone.

**Other behaviours.** *Continuously* forwards always; *via partition arming* forwards only while
the partition is armed. A minimum on-time stretches brief pulses so the panel doesn't miss them.
*Invert* corrects an output polarity the protocol can't read. When a partition goes to
*triggered*, the companion looks back over the guard-time window to report which zones were
involved.
