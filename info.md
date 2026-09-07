# Mikrotik Control for Home Assistant

Local RouterOS monitoring and controls with conservative defaults.

## Highlights

- UI setup through Home Assistant config flow.
- CPU, memory, disk, uptime, firmware, update, and hardware health sensors.
- Optional interface traffic and IP sensors.
- Optional switches for interfaces and firewall NAT/filter/mangle rules.
- Firewall profile switches from RouterOS comment tags.
- Optional RouterOS script buttons.
- RouterOS container start/stop/restart controls.
- WireGuard peer controls and traffic sensors.
- Netwatch connectivity sensors.
- Native RouterOS and RouterBOARD update entities.
- Manual backup button and optional backups before risky actions.
- Router health summary and configuration audit sensors.
- Optional reboot button.
- RouterOS v6 and v7 health parsing.
- Redacted diagnostics export for bug reports.

## Positioning

Home Assistant's built-in MikroTik integration is mainly for presence tracking. Larger HACS integrations cover more RouterOS subsystems, but can create many entities and expose a broad control surface. Mikrotik Control is intentionally smaller: monitoring works by default, and powerful controls are enabled only when selected in the integration options.

## Install

Add this repository to HACS as an **Integration**:

```text
https://github.com/soulripper13/mikrotik-control
```

After installation, restart Home Assistant and add **Mikrotik Control** from **Settings -> Devices & Services**.
