# Mikrotik Control for Home Assistant

A 100% local, high-performance integration to monitor and control Mikrotik RouterOS devices through Home Assistant.

## Key Features

- **Toggles**: Enable/disable network interfaces (ethernet, SFP, wireless, CAP, bridges, tunnels, etc.) and firewall rules (NAT, filter rules, mangle rules) directly.
- **Sensors**: CPU load, free/total memory, free/total HDD space, uptime timestamp, and cumulative RX/TX bytes for all interfaces.
- **Dynamic Health Sensors**: Automatically discovers temperature, voltage, and health metrics supporting both RouterOS v6 and v7 structures.
- **Binary Sensors**: Tracks interface connectivity states (cable plugged in / link active) and package update availability.
- **Buttons**: Triggers instant reboots, requests package update checks, and dynamically registers buttons for all RouterOS scripts found on the device.
