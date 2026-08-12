# Satel Link Companion

<img src="https://raw.githubusercontent.com/barloew/satel_link_companion/main/custom_components/satel_link_companion/brand/icon.png" alt="Satel Link Companion" width="96" align="right" />

[![Validate](https://github.com/barloew/satel_link_companion/actions/workflows/validate.yml/badge.svg)](https://github.com/barloew/satel_link_companion/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/barloew/satel_link_companion?display_name=tag)](https://github.com/barloew/satel_link_companion/releases)

**Bring your Satel Integra alarm and Home Assistant closer together.** Satel Link Companion sits
on top of the Satel base integration you already use and adds the things it can't do on its own —
without ever opening a second connection to your panel.

**Is this for you?**

- **ETHM-1 (not Plus), so no "virtual zones"?** Turn any Home Assistant sensor — a door contact, a
  smoke or CO alarm, a motion sensor — into a **real Satel zone**, supervised by the panel and
  armed with its partition. (Connect a sensor to Satel yourself — a sensor switching an output
  with a zone following it — and that zone is a 24-hour zone: it alarms the moment it's
  tripped, armed or not. Right for hazard sensors, wrong for burglary. Satel Link Companion
  forwards a burglary sensor only after you arm.)
- **Use HomeKit?** Get one **master alarm panel** that arms and disarms several Satel partitions as
  a single, HomeKit-compatible tile, with its own set for Home, Away and Night.
- **Want smarter arming and automations?** Before it arms, it tells you which doors and windows are
  still open — all at once — and fires **events** (alarm, arm blocked, arm failed) you can notify or
  automate on.
- **Just want a roller shutter?** Bundle a shutter's up/down output pair into one Home Assistant
  **cover**.

Requires **Home Assistant 2025.7+** and a working Satel base integration (`satel_integra` or
`ha_satel_integra_ext`).

See the [README](https://github.com/barloew/satel_link_companion) to get started and the
[Advanced guide](https://github.com/barloew/satel_link_companion/blob/main/Advanced.md) for the
Satel-side checklist and the finer details.
