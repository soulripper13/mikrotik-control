# Mikrotik Control for Home Assistant

A custom Home Assistant integration providing **full control** and **monitoring** of MikroTik RouterOS devices via the RouterOS API. It operates **100% locally** and supports both RouterOS v6 and v7.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

---

## Features

- **Network Interfaces**: Exposes all network interfaces as switches so they can be enabled or disabled, and binary sensors for their active link status (running state).
- **Firewall Rule Control**: Exposes NAT rules, Firewall Filter rules, and Mangle rules as switches, allowing you to activate/deactivate port forwards, traffic shaping, block lists, or routing rules dynamically.
- **Dynamic Script Execution**: Automatically creates a button entity for every script configured on your MikroTik device under `/system/script`. Clicking the button runs the script.
- **Update Checks**: Tells you if a RouterOS firmware update is available and includes a button to trigger update checks.
- **Hardware Health**: Automatically tracks temperature and voltage (supports CCR, hAP, RB series on RouterOS v6 and v7).
- **System Metrics**: Exposes CPU load, free/total memory, free/total disk space, uptime timestamp, and cumulative RX/TX traffic bytes per interface.

---

## Security Best Practice (Highly Recommended)

Do **NOT** use your main `admin` account for this integration. Instead, create a dedicated user with limited permissions on your MikroTik router.

Run the following commands in the MikroTik Terminal:

1. **Create a limited-permission group**:
   ```routeros
   /user group add name=ha-api policy=read,write,api,reboot,policy,test
   ```
   *Note: `reboot` is required for the reboot button. `policy` and `write` are required to check for updates and toggle interfaces/rules. `api` is required for connection.*

2. **Add a new user assigned to this group**:
   ```routeros
   /user add name=homeassistant group=ha-api password="YourSecurePasswordHere"
   ```

3. **Verify API service is enabled**:
   Ensure the API service (`api` or `api-ssl`) is enabled under **IP -> Services**:
   ```routeros
   /ip service enable api
   # Or if using SSL:
   /ip service enable api-ssl
   ```

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in Home Assistant.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Enter the URL of your repository: `https://github.com/soulripper13/mikrotik-control` (or the URL you push this to).
4. Select category **Integration** and click **Add**.
5. Find **Mikrotik Control** in the list, click **Download**, and restart Home Assistant.

### Method 2: Manual Installation

1. Copy the `custom_components/mikrotik_control` directory to your Home Assistant's `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, go to **Settings** -> **Devices & Services**.
2. Click **Add Integration** in the bottom right.
3. Search for **Mikrotik Control** and select it.
4. Enter the connection settings:
   - **IP Address or Hostname**: Your router's IP (e.g., `192.168.88.1`).
   - **Username**: The dedicated username created above (e.g., `homeassistant`).
   - **Password**: The password for that user.
   - **Port**: Default is `8728` (or `8729` for SSL).
   - **Use SSL**: Check if you are using `api-ssl`.
   - **Verify SSL Certificate**: Check if you have a valid CA-signed certificate loaded on the router.

### Options Flow (Dynamic Configuration)

Once added, you can click **Configure** on the integration card to modify the polling interval:
- **Update Interval (seconds)**: Controls how often Home Assistant fetches statistics from the router (default is `30` seconds).
