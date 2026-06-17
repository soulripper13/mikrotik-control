"""Base entity class for Mikrotik Control integration."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

PHYSICAL_INTERFACE_TYPES = {
    "ether",
    "lte",
    "wlan",
    "wifi",
    "wifiwave2",
}


def is_enabled(value) -> bool:
    """Return true for RouterOS yes/true values."""
    return value in ("true", "yes", True)


def is_physical_interface(interface: dict) -> bool:
    """Return true when an interface is likely user-facing hardware."""
    interface_type = str(interface.get("type", "")).lower()
    return interface_type in PHYSICAL_INTERFACE_TYPES


def has_interface_address(coordinator, interface_name: str, ip_version: str) -> bool:
    """Return true if an interface has at least one enabled address."""
    for address in coordinator.data.get(f"{ip_version}_addresses", []):
        if address.get("interface") != interface_name:
            continue
        if address.get("address") and not is_enabled(address.get("disabled")):
            return True
    return False


class MikrotikEntity(CoordinatorEntity):
    """Base class for all Mikrotik entities."""

    _device_group = "system"

    def __init__(self, coordinator, entry_id):
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entry_id = entry_id
        
        # Determine unique IDs
        self.serial = coordinator.data.get("routerboard", {}).get("serial-number")
        self.host = coordinator.client.host
        self.device_id = self.serial if self.serial else self.host

        # Set up DeviceInfo
        self.board_name = coordinator.data.get("resource", {}).get("board-name", "RouterOS Device")
        self.identity = coordinator.data.get("identity", {}).get("name", "MikroTik")
        self.version = coordinator.data.get("resource", {}).get("version", "Unknown")

        if self._device_group == "system":
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.device_id)},
                name=self.identity,
                manufacturer="MikroTik",
                model=self.board_name,
                sw_version=self.version,
            )
        else:
            group_name = self._device_group.replace("_", " ").title()
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{self.device_id}_{self._device_group}")},
                name=f"{self.identity} {group_name}",
                manufacturer="MikroTik",
                model=group_name,
                via_device=(DOMAIN, self.device_id),
            )
