"""Binary sensor platform for Mikrotik Control integration."""
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_NETWATCH,
    CONF_ENABLE_WIREGUARD,
    DEFAULT_ENABLE_NETWATCH,
    DEFAULT_ENABLE_WIREGUARD,
    DOMAIN,
)
from .entity import MikrotikEntity, is_enabled, is_physical_interface, safe_key
from .helpers import wireguard_peer_name

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mikrotik binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    enable_wireguard = entry.options.get(CONF_ENABLE_WIREGUARD, DEFAULT_ENABLE_WIREGUARD)
    enable_netwatch = entry.options.get(CONF_ENABLE_NETWATCH, DEFAULT_ENABLE_NETWATCH)
    entities = []

    # 1. Add Interface Link running state
    for interface in coordinator.data.get("interfaces", []):
        if "name" in interface and is_physical_interface(interface):
            entities.append(MikrotikInterfaceLinkSensor(coordinator, entry.entry_id, interface["name"]))

    # 2. Add Firmware Update available state
    entities.append(MikrotikUpdateAvailableSensor(coordinator, entry.entry_id))

    if enable_wireguard:
        for peer in coordinator.data.get("wireguard_peers", []):
            if ".id" in peer:
                entities.append(MikrotikWireGuardPeerStaleSensor(coordinator, entry.entry_id, peer[".id"]))

    if enable_netwatch:
        for item in coordinator.data.get("netwatch", []):
            if ".id" in item:
                entities.append(MikrotikNetwatchSensor(coordinator, entry.entry_id, item[".id"]))

    async_add_entities(entities)


class MikrotikBinarySensor(MikrotikEntity, BinarySensorEntity):
    """Base class for all Mikrotik binary sensors (classified as diagnostics)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC


class MikrotikInterfaceLinkSensor(MikrotikBinarySensor):
    """Representation of interface link status (running state)."""

    _device_group = "interfaces"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, entry_id, interface_name):
        """Initialize the link sensor."""
        super().__init__(coordinator, entry_id)
        self.interface_name = interface_name
        self._attr_name = f"Interface {interface_name} Link"
        self._attr_unique_id = f"{self.device_id}_interface_{safe_key(interface_name)}_link"

    @property
    def _interface_data(self):
        """Get latest interface data."""
        for interface in self.coordinator.data.get("interfaces", []):
            if interface.get("name") == self.interface_name:
                return interface
        return None

    @property
    def is_on(self) -> bool:
        """Return True if the interface is running (cable connected / active)."""
        data = self._interface_data
        if data:
            return is_enabled(data.get("running"))
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details of the link."""
        data = self._interface_data
        if data:
            attrs = {
                "type": data.get("type", "unknown"),
                "disabled": is_enabled(data.get("disabled")),
                "comment": data.get("comment", ""),
            }
            # Add IPv4 and IPv6 if available
            ipv4_list = [
                addr.get("address")
                for addr in self.coordinator.data.get("ipv4_addresses", [])
                if addr.get("interface") == self.interface_name
            ]
            ipv6_list = [
                addr.get("address")
                for addr in self.coordinator.data.get("ipv6_addresses", [])
                if addr.get("interface") == self.interface_name
            ]
            if ipv4_list:
                attrs["ipv4_addresses"] = ipv4_list
            if ipv6_list:
                attrs["ipv6_addresses"] = ipv6_list
            return attrs
        return {}


class MikrotikUpdateAvailableSensor(MikrotikBinarySensor):
    """Representation of RouterOS firmware update availability."""

    _attr_name = "Firmware Update Available"
    _attr_device_class = BinarySensorDeviceClass.UPDATE

    def __init__(self, coordinator, entry_id):
        """Initialize update sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{self.device_id}_update_available"

    @property
    def is_on(self) -> bool:
        """Return True if an update is available."""
        updates = self.coordinator.data.get("updates", {})
        installed = updates.get("installed-version")
        latest = updates.get("latest-version")
        
        if installed and latest:
            return installed != latest
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return update details."""
        updates = self.coordinator.data.get("updates", {})
        return {
            "installed_version": updates.get("installed-version", "unknown"),
            "latest_version": updates.get("latest-version", "unknown"),
            "status": updates.get("status", "unknown"),
            "channel": updates.get("channel", "unknown"),
        }


class MikrotikWireGuardPeerStaleSensor(MikrotikBinarySensor):
    """Binary sensor indicating WireGuard peer handshake staleness."""

    _device_group = "wireguard"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, entry_id, peer_id):
        """Initialize peer stale sensor."""
        super().__init__(coordinator, entry_id)
        self.peer_id = peer_id
        peer = self._peer_data or {}
        self._attr_name = f"WireGuard {wireguard_peer_name(peer)} Stale"
        self._attr_unique_id = f"{self.device_id}_wireguard_peer_{safe_key(peer_id)}_stale"

    @property
    def _peer_data(self):
        """Get latest peer data."""
        for peer in self.coordinator.data.get("wireguard_peers", []):
            if peer.get(".id") == self.peer_id:
                return peer
        return None

    @property
    def is_on(self) -> bool:
        """Return true when the peer has never handshaked or is inactive."""
        peer = self._peer_data
        if not peer:
            return False
        handshake = str(peer.get("last-handshake", "")).lower()
        if not handshake or handshake == "never":
            return True
        return handshake.startswith("0s") is False and "d" in handshake

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return peer details."""
        peer = self._peer_data
        if not peer:
            return {}
        return {
            "interface": peer.get("interface"),
            "allowed_address": peer.get("allowed-address"),
            "endpoint_address": peer.get("endpoint-address"),
            "last_handshake": peer.get("last-handshake"),
            "comment": peer.get("comment", ""),
        }


class MikrotikNetwatchSensor(MikrotikBinarySensor):
    """Representation of Netwatch host status."""

    _device_group = "netwatch"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, entry_id, item_id):
        """Initialize Netwatch sensor."""
        super().__init__(coordinator, entry_id)
        self.item_id = item_id
        item = self._netwatch_data or {}
        name = item.get("comment") or item.get("host") or item_id
        self._attr_name = f"Netwatch {name}"
        self._attr_unique_id = f"{self.device_id}_netwatch_{safe_key(item_id)}"

    @property
    def _netwatch_data(self):
        """Get latest Netwatch data."""
        for item in self.coordinator.data.get("netwatch", []):
            if item.get(".id") == self.item_id:
                return item
        return None

    @property
    def is_on(self) -> bool:
        """Return true when Netwatch reports the host as up."""
        item = self._netwatch_data
        if not item:
            return False
        status = str(item.get("status", "")).lower()
        return status == "up"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return Netwatch details."""
        item = self._netwatch_data
        if not item:
            return {}
        attrs = {
            "host": item.get("host"),
            "status": item.get("status"),
            "type": item.get("type"),
            "interval": item.get("interval"),
            "timeout": item.get("timeout"),
            "comment": item.get("comment", ""),
        }
        return {key: value for key, value in attrs.items() if value not in (None, "")}
