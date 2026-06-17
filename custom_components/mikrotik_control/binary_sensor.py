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

from .const import DOMAIN
from .entity import MikrotikEntity, is_enabled, is_physical_interface

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mikrotik binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = []

    # 1. Add Interface Link running state
    for interface in coordinator.data.get("interfaces", []):
        if "name" in interface and is_physical_interface(interface):
            entities.append(MikrotikInterfaceLinkSensor(coordinator, entry.entry_id, interface["name"]))

    # 2. Add Firmware Update available state
    entities.append(MikrotikUpdateAvailableSensor(coordinator, entry.entry_id))

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
        self._attr_unique_id = f"{self.device_id}_interface_{interface_name}_link"

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
