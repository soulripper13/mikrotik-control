"""Diagnostics support for the Mikrotik Control integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    "host",
    "hostname",
    "interface",
    "mac-address",
    "address",
    "addresses",
    "ipv4_addresses",
    "ipv6_addresses",
    "public-key",
    "private-key",
    "serial-number",
    "to-addresses",
}


def _count_items(data: dict[str, Any], key: str) -> int:
    """Return a safe count for a coordinator collection."""
    value = data.get(key, [])
    return len(value) if isinstance(value, list) else 0


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    domain_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = domain_data.get("coordinator")
    data = coordinator.data if coordinator else {}

    resource = data.get("resource", {})
    routerboard = data.get("routerboard", {})
    identity = data.get("identity", {})
    updates = data.get("updates", {})

    diagnostics = {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "router": {
            "identity": async_redact_data(identity, TO_REDACT),
            "resource": {
                "board_name": resource.get("board-name"),
                "version": resource.get("version"),
                "cpu_count": resource.get("cpu-count"),
                "architecture_name": resource.get("architecture-name"),
            },
            "routerboard": async_redact_data(routerboard, TO_REDACT),
            "updates": async_redact_data(updates, TO_REDACT),
        },
        "counts": {
            "interfaces": _count_items(data, "interfaces"),
            "ipv4_addresses": _count_items(data, "ipv4_addresses"),
            "ipv6_addresses": _count_items(data, "ipv6_addresses"),
            "nat_rules": _count_items(data, "nat"),
            "filter_rules": _count_items(data, "filter"),
            "mangle_rules": _count_items(data, "mangle"),
            "scripts": _count_items(data, "scripts"),
            "containers": _count_items(data, "containers"),
            "wireguard_interfaces": _count_items(data, "wireguard_interfaces"),
            "wireguard_peers": _count_items(data, "wireguard_peers"),
            "netwatch": _count_items(data, "netwatch"),
            "services": _count_items(data, "services"),
            "users": _count_items(data, "users"),
            "routes": _count_items(data, "routes"),
            "ipv6_routes": _count_items(data, "ipv6_routes"),
            "health_items": _count_items(data, "health"),
        },
    }

    return async_redact_data(diagnostics, TO_REDACT)
