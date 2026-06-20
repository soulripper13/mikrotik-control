# Mikrotik Control for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Mikrotik Control is a local Home Assistant integration for monitoring and controlling MikroTik RouterOS devices through the RouterOS API.

It is designed to be smaller and more deliberate than the large all-in-one MikroTik integrations: core diagnostic sensors are enabled by default, while higher-risk control surfaces such as interface switches, firewall switches, script buttons, and reboot are opt-in from the integration options.

## Why This Integration

Home Assistant's built-in `mikrotik` integration is mainly for device tracking. Popular HACS alternatives such as `tomaae/homeassistant-mikrotik_router` and `ha-mikrotik-extended` cover many RouterOS subsystems, but they can create a large number of entities and expose a broad management surface.

Mikrotik Control focuses on practical router operations:

- Local RouterOS API connection, no cloud service or MQTT bridge.
- Config flow setup from the Home Assistant UI.
- Conservative defaults: monitoring first, controls enabled only when selected.
- RouterOS v6 and v7 health parsing.
- Control entities for interfaces, firewall rules, scripts, containers, updates, and reboot.
- Clear entity grouping so optional controls can be enabled or disabled later.
- Redacted diagnostics export for easier bug reports.
- Native update entities, backup helpers, WireGuard peer controls, Netwatch status, firewall profiles, router health scoring, and lightweight configuration audit.

## Features

### Always-On Monitoring

- CPU load.
- Free and total memory.
- Free and total disk space.
- Uptime.
- RouterBOARD current and upgrade firmware.
- RouterOS package update availability.
- Dynamic health sensors such as temperature, voltage, current, fan, and power when exposed by the router.

### Optional Interface Details

When enabled, physical interfaces get:

- RX/TX byte counters.
- IPv4 and IPv6 address sensors when addresses are assigned.
- Link/running binary sensors.

### Optional Controls

The following groups can be enabled from **Configure** after setup:

- Interface enable/disable switches.
- Firewall NAT, filter, and mangle rule switches.
- RouterOS script run buttons.
- RouterOS container start/stop switches and restart buttons.
- Router reboot button.
- WireGuard peer enable/disable switches, traffic sensors, and stale-handshake problem sensors.
- Netwatch host connectivity sensors.
- Firewall profile switches from RouterOS comments such as `ha:guest` or `ha:vpn`.

Firewall and container controls expose RouterOS attributes such as chain, action, protocol, ports, interfaces, marks, comments, image, root directory, and start-on-boot state where available. That makes it easier to confirm what an entity controls before toggling it.

Container controls are enabled by default because they are a common Home Assistant use case; all other destructive or broad controls default to off.

### Safety And Operations

- Entity presets: `minimal`, `recommended`, `advanced`, and `full`.
- Native Home Assistant update entities for RouterOS packages and RouterBOARD firmware.
- Manual RouterOS backup button.
- Optional backup before risky actions such as firmware updates, reboot, and firewall changes.
- Router health summary sensor with warning/critical reasons.
- Configuration audit sensor for common risks such as default admin, unrestricted API services, or weak input firewall visibility.

Firewall profiles are controlled by comment tags. Add a tag to one or more NAT, filter, or mangle rules:

```routeros
/ip firewall filter set [find comment~"Guest access"] comment="ha:guest Guest access"
```

The integration will create one `Firewall Profile guest` switch that controls all enabled rules tagged with `ha:guest`.

## Feature Comparison

| Capability | HA core `mikrotik` | Large HACS router integrations | Mikrotik Control |
| --- | --- | --- | --- |
| UI config flow | Yes | Yes | Yes |
| Local RouterOS API | Yes | Yes | Yes |
| Presence/device tracking | Yes | Yes | No |
| System health sensors | Limited | Yes | Yes |
| Interface traffic sensors | No | Yes | Optional |
| Interface switches | No | Yes | Optional |
| Firewall rule switches | No | Yes | Optional |
| Firewall profile switches | No | Rare | Yes |
| Script execution | No | Yes | Optional buttons |
| RouterOS containers | No | Some support | Start/stop/restart controls |
| WireGuard peer controls | No | Some support | Yes |
| Netwatch sensors | No | Some support | Yes |
| Native HA update entities | No | Varies | Yes |
| Backup before risky actions | No | Rare | Yes |
| Health score and config audit | No | Rare | Yes |
| Conservative default entity count | Yes | Varies | Yes |
| RouterOS v6 support | Yes | Varies | Basic v6/v7 support |

## Installation

### HACS

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add `https://github.com/soulripper13/mikrotik-control`.
4. Select category **Integration**.
5. Install **Mikrotik Control**.
6. Restart Home Assistant.

### Manual

Copy `custom_components/mikrotik_control` into your Home Assistant `config/custom_components/` directory, then restart Home Assistant.

## RouterOS Setup

Do not use your main `admin` account. Create a dedicated API user instead.

```routeros
/user group add name=ha-api policy=read,write,api,reboot,policy,test
/user add name=homeassistant group=ha-api password="YourSecurePasswordHere"
```

Enable the RouterOS API service:

```routeros
/ip service enable api
```

For API over SSL:

```routeros
/ip service enable api-ssl
```

Permission notes:

- `read` and `api` are required to connect and read router data.
- `write` and `policy` are required for most toggles and update checks.
- `reboot` is required only for the reboot button.
- Script buttons execute existing RouterOS scripts, so review script policies on the router.

## Configuration

1. In Home Assistant, go to **Settings -> Devices & Services**.
2. Select **Add Integration**.
3. Search for **Mikrotik Control**.
4. Enter the router host, username, password, port, and SSL settings.

Defaults:

- Plain API port: `8728`.
- SSL API port: `8729`.
- Update interval: `30` seconds.
- SSL certificate verification is off unless you enable it.

## Options

Open **Settings -> Devices & Services -> Mikrotik Control -> Configure** to change:

- Update interval from 5 to 300 seconds.
- Entity preset.
- Safe mode and backup-before-risky-actions behavior.
- Interface detail entities.
- Interface control switches.
- Firewall rule switches.
- Firewall profile switches and profile prefix.
- Script run buttons.
- Container controls.
- Reboot button.
- WireGuard peer entities.
- Netwatch entities.
- Router health summary.
- Configuration audit sensor.

Changing options reloads the integration so entity groups match the saved settings.

## Troubleshooting

### Integration Does Not Connect

- Confirm the API service is enabled with `/ip service print`.
- Confirm the port matches the selected SSL mode.
- Check that Home Assistant can reach the router IP or hostname.
- Use a dedicated API user and verify its permissions.

### SSL Fails

- Use port `8729` for `api-ssl`.
- Leave certificate verification disabled for self-signed RouterOS certificates.
- Enable certificate verification only when the router has a valid CA-signed certificate trusted by Home Assistant.

### Missing Entities

- Optional entity groups are intentionally disabled until enabled in **Configure**.
- Some sensors depend on RouterOS model, installed packages, and RouterOS version.
- Firewall, script, and container entities are created only when the router returns matching items from the API.

### Too Many Entities

Keep optional interface details, interface controls, firewall controls, and script buttons disabled unless you actively use them. This keeps the entity registry and recorder history smaller.

### Reporting Bugs

Download diagnostics from **Settings -> Devices & Services -> Mikrotik Control -> three-dot menu -> Download diagnostics**. The export includes entry options, router model/version summary, update status, and entity source counts with sensitive fields redacted.

## Development

Useful local checks:

```bash
python3 -m json.tool hacs.json
python3 -m json.tool custom_components/mikrotik_control/manifest.json
python3 -m json.tool custom_components/mikrotik_control/strings.json
python3 -m json.tool custom_components/mikrotik_control/translations/en.json
python3 -m compileall -q custom_components/mikrotik_control
```
