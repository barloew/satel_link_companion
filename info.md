# Satel Link Companion

<img src="https://raw.githubusercontent.com/barloew/satel_link_companion/main/custom_components/satel_link_companion/brand/icon.png" alt="Satel Link Companion" width="96" align="right" />

A Home Assistant companion for the Satel Integra Panel. It links Home Assistant sensors into
the panel as real, panel-supervised Satel zones, bundles roller-shutter output pairs into a single
Home Assistant `cover`, and exposes one HomeKit-compatible master alarm panel that arms and
disarms several Satel Integra partitions as one unit.

It leverages an existing Satel base integration (`satel_integra` or `ha_satel_integra_ext`)
and holds no second connection to the panel at runtime — it actuates the base integration's
output switches and reads arm state from its `alarm_control_panel` entities.

**What it adds on top of the base integration**
- A **link** — actuate a Satel zone with any Home Assistant sensor, turning it into a real Satel zone that arms with its partition (with fail-silent handling and entry/exit delay)
- A **roller-shutter cover** — a shutter's up/down output pair as one `cover`
- A **master alarm panel** — arms several partitions as one HomeKit-compatible tile, per mode, with rollback on failure
- Diagnostic **event sensors** plus an active **pre-arm blocker check**, breach and arm-failed events

Requires **Home Assistant 2025.7+**. See the
[README](https://github.com/barloew/satel_link_companion) for requirements, the DLOADX
checklist, and how the link edge-cases (fail-silent `not_from`, entry/exit window) work.
