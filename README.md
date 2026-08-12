# Satel Link Companion

<img src="https://raw.githubusercontent.com/barloew/satel_link_companion/main/custom_components/satel_link_companion/brand/icon.png" alt="Satel Link Companion" width="120">

[![Validate](https://github.com/barloew/satel_link_companion/actions/workflows/validate.yml/badge.svg)](https://github.com/barloew/satel_link_companion/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/barloew/satel_link_companion?display_name=tag)](https://github.com/barloew/satel_link_companion/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

**Bring your Satel Integra alarm and Home Assistant closer together: use any Home Assistant
sensor as a real Satel zone, control your whole system from one HomeKit-friendly panel, and
automate the rest.**

Satel Link Companion sits on top of the Satel base integration you already use and adds the
things it can't do on its own. It never opens a second connection to your panel — the Satel
network module allows only one — so it works entirely through your existing integration.

## Is this for you?

**① You have a Satel Integra with an ETHM-1 module (not the Plus) — so you have no "virtual zones".**
Normally that means Home Assistant can *read* your Satel zones, but can't turn a Home
Assistant sensor into a real Satel one. Satel Link Companion gives you exactly that: pick any
Home Assistant sensor — a Zigbee door contact, a Z-Wave smoke or CO alarm, a motion sensor —
and it becomes a genuine Satel zone, supervised by the panel and armed together with its
partition. (ETHM-1 Plus owners can use this too.)

**② You use HomeKit and want one alarm tile for your whole house.**
HomeKit only controls one Satel partition per accessory, so with several partitions you're
stuck arming them one at a time. Satel Link Companion gives you a single **master alarm panel**
that arms and disarms all the partitions you choose as one unit — with its own set of
partitions for Home, Away and Night — and it's fully HomeKit-compatible.

**③ You want smarter arming, notifications and automations.**
Before it arms, it checks every partition and tells you — all at once — which doors or windows
are still open, so you're not fixing one and then discovering the next. It fires **events** you
can build automations on (an alarm went off; an arm was blocked; an arm failed) and mirrors
them as sensors, so a WhatsApp or Sonos notification is easy to wire up.

**④ You just want to control a roller shutter.**
If your shutters run on Satel output pairs, Satel Link Companion bundles each up/down pair into
a single Home Assistant **cover** you can open, close and stop like any other.

### Why not just connect the sensor to Satel directly?

Suppose you let a Home Assistant sensor switch a Satel output, and you link a Satel zone to that
output. That zone would be a **24-hour** zone — and a 24-hour zone goes straight into alarm the
moment it's tripped, whether the alarm is armed or not.

- For a **hazard sensor** (smoke, CO, gas, water) that's exactly right — you always want it to go
  off, at home or away.
- For **burglary** it's no good — a motion sensor or a door would trip the alarm while you're
  sitting on the couch.

Satel Link Companion does the smart part in Home Assistant: it only forwards a burglary sensor to
the panel **after you've armed that partition** (optionally with an entry/exit delay), so it acts
like a normal alarm zone. Hazard sensors you simply set to “always”, and they work exactly like a
direct connection — now all in one place.

## Requirements

- Home Assistant **2025.7 or newer**
- A Satel **INTEGRA** or **INTEGRA Plus** panel with an **ETHM-1** or **ETHM-1 Plus** module,
  with *Integration* enabled
- A working Satel base integration —
  [`satel_integra`](https://www.home-assistant.io/integrations/satel_integra/) (core) or
  `ha_satel_integra_ext`

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=barloew&repository=satel_link_companion&category=integration)

1. In HACS, add this repository as a custom repository
   (`https://github.com/barloew/satel_link_companion`, category *Integration*).
2. Install **Satel Link Companion** and restart Home Assistant.
3. Add it under *Settings → Devices & Services → Add Integration → Satel Link Companion*.

### Manual

Copy `custom_components/satel_link_companion/` into your Home Assistant
`config/custom_components/` folder and restart.

## Setup

Setup adopts your existing Satel base integration automatically. From the integration page you
then add what you need — each becomes its own device:

- **Link a sensor** — turn a Home Assistant sensor into a Satel zone
- **Roller shutter** — bundle an up/down output pair into one cover
- **Master panel** — one alarm tile for several partitions

There's a one-off **“Map Satel Integra system structure”** scan first, so it knows your panel's
layout.

> **Before your first link:** a few things need to be set correctly on the Satel side (output
> type, zone wiring, user rights). The **[Advanced guide](Advanced.md)** has a short checklist —
> worth two minutes before you start.

## Learn more

- **[Advanced guide](Advanced.md)** — the DLOADX checklist, the master panel in depth, how to
  verify a link, and how links behave at the edges (fail-silent, entry/exit)
- **[Events & automation](EVENTS.md)** — event payloads and example automations
- **[Satel object types](SATEL_TYPES.md)** — zone functions, wiring types and output functions,
  taken from the Satel manuals

## A note on safety

This drives a real alarm system. It's built to fail safe — if a sensor drops out or Home
Assistant restarts, a linked zone returns to rest rather than raising a false alarm — but always
confirm the behaviour against your own hardware before you rely on it.

## License

Released under the [MIT License](LICENSE). Not affiliated with SATEL sp. z o.o. “Satel” and
“Integra” are trademarks of their respective owner.
