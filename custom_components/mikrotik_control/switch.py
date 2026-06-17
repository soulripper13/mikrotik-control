"""Switch platform for Mikrotik Control integration."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_CONTAINER_CONTROLS,
    CONF_ENABLE_FIREWALL_CONTROLS,
    CONF_ENABLE_INTERFACE_CONTROLS,
    DEFAULT_ENABLE_CONTAINER_CONTROLS,
    DEFAULT_ENABLE_FIREWALL_CONTROLS,
    DEFAULT_ENABLE_INTERFACE_CONTROLS,
    DOMAIN,
)
from .entity import MikrotikEntity, is_enabled, is_physical_interface

_LOGGER = logging.getLogger(__name__)


def _enable_by_option(entity):
    """Mark an option-created entity enabled by default."""
    entity._attr_entity_registry_enabled_default = True
    return entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mikrotik switches."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    enable_interface_controls = entry.options.get(
        CONF_ENABLE_INTERFACE_CONTROLS,
        DEFAULT_ENABLE_INTERFACE_CONTROLS,
    )
    enable_firewall_controls = entry.options.get(
        CONF_ENABLE_FIREWALL_CONTROLS,
        DEFAULT_ENABLE_FIREWALL_CONTROLS,
    )
    enable_container_controls = entry.options.get(
        CONF_ENABLE_CONTAINER_CONTROLS,
        DEFAULT_ENABLE_CONTAINER_CONTROLS,
    )
    entities = []

    # 1. Add Interface switches
    if enable_interface_controls:
        for interface in coordinator.data.get("interfaces", []):
            if "name" in interface and ".id" in interface and is_physical_interface(interface):
                entities.append(
                    _enable_by_option(
                        MikrotikInterfaceSwitch(coordinator, entry.entry_id, interface["name"])
                    )
                )

    # 2. Add NAT rules switches
    if enable_firewall_controls:
        for rule in coordinator.data.get("nat", []):
            if ".id" in rule:
                entities.append(_enable_by_option(MikrotikNatSwitch(coordinator, entry.entry_id, rule[".id"])))

        # 3. Add Filter rules switches
        for rule in coordinator.data.get("filter", []):
            if ".id" in rule:
                entities.append(_enable_by_option(MikrotikFilterSwitch(coordinator, entry.entry_id, rule[".id"])))

        # 4. Add Mangle rules switches
        for rule in coordinator.data.get("mangle", []):
            if ".id" in rule:
                entities.append(_enable_by_option(MikrotikMangleSwitch(coordinator, entry.entry_id, rule[".id"])))

    # 5. Add container start/stop switches
    if enable_container_controls:
        for container in coordinator.data.get("containers", []):
            if ".id" in container:
                entities.append(
                    _enable_by_option(MikrotikContainerSwitch(coordinator, entry.entry_id, container[".id"]))
                )

    async_add_entities(entities)


class MikrotikSwitch(MikrotikEntity, SwitchEntity):
    """Base class for all Mikrotik switches (classified as config)."""

    _attr_entity_category = EntityCategory.CONFIG


class MikrotikInterfaceSwitch(MikrotikSwitch):
    """Switch representation of a Mikrotik Interface."""

    _device_group = "interfaces"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, interface_name):
        """Initialize the interface switch."""
        super().__init__(coordinator, entry_id)
        self.interface_name = interface_name
        self._attr_name = f"Interface {interface_name}"
        self._attr_unique_id = f"{self.device_id}_interface_{interface_name}"

    @property
    def _interface_data(self):
        """Get latest interface data."""
        for interface in self.coordinator.data.get("interfaces", []):
            if interface.get("name") == self.interface_name:
                return interface
        return None

    @property
    def is_on(self) -> bool:
        """Return True if interface is enabled."""
        data = self._interface_data
        if data:
            return not is_enabled(data.get("disabled"))
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return interface details."""
        data = self._interface_data
        if data:
            attrs = {
                "type": data.get("type", "unknown"),
                "running": is_enabled(data.get("running")),
                "mtu": data.get("actual-mtu"),
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the interface."""
        data = self._interface_data
        if data and ".id" in data:
            await self.coordinator.client.set_interface_state(data[".id"], True)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the interface."""
        data = self._interface_data
        if data and ".id" in data:
            await self.coordinator.client.set_interface_state(data[".id"], False)
            await self.coordinator.async_request_refresh()


class MikrotikNatSwitch(MikrotikSwitch):
    """Switch representation of a Mikrotik Firewall NAT Rule (disabled by default)."""

    _device_group = "firewall"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, rule_id):
        """Initialize the NAT rule switch."""
        super().__init__(coordinator, entry_id)
        self.rule_id = rule_id
        
        # Name formulation
        rule = self._rule_data
        comment = rule.get("comment") if rule else None
        chain = rule.get("chain", "unknown") if rule else "unknown"
        action = rule.get("action", "unknown") if rule else "unknown"
        
        if comment:
            self._attr_name = f"NAT: {comment}"
        else:
            self._attr_name = f"NAT {action} ({chain}) {rule_id}"
            
        self._attr_unique_id = f"{self.device_id}_nat_{rule_id}"

    @property
    def _rule_data(self):
        """Get latest rule data."""
        for rule in self.coordinator.data.get("nat", []):
            if rule.get(".id") == self.rule_id:
                return rule
        return None

    @property
    def is_on(self) -> bool:
        """Return True if rule is enabled."""
        data = self._rule_data
        if data:
            return not is_enabled(data.get("disabled"))
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return NAT rule details."""
        data = self._rule_data
        if data:
            attrs = {
                "chain": data.get("chain"),
                "action": data.get("action"),
                "protocol": data.get("protocol", "any"),
            }
            if "dst-port" in data:
                attrs["dst_port"] = data["dst-port"]
            if "to-addresses" in data:
                attrs["to_addresses"] = data["to-addresses"]
            if "to-ports" in data:
                attrs["to_ports"] = data["to-ports"]
            if "comment" in data:
                attrs["comment"] = data["comment"]
            return attrs
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the NAT rule."""
        await self.coordinator.client.set_nat_state(self.rule_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the NAT rule."""
        await self.coordinator.client.set_nat_state(self.rule_id, False)
        await self.coordinator.async_request_refresh()


class MikrotikFilterSwitch(MikrotikSwitch):
    """Switch representation of a Mikrotik Firewall Filter Rule (disabled by default)."""

    _device_group = "firewall"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, rule_id):
        """Initialize the filter rule switch."""
        super().__init__(coordinator, entry_id)
        self.rule_id = rule_id
        
        rule = self._rule_data
        comment = rule.get("comment") if rule else None
        chain = rule.get("chain", "unknown") if rule else "unknown"
        action = rule.get("action", "unknown") if rule else "unknown"
        
        if comment:
            self._attr_name = f"Filter: {comment}"
        else:
            self._attr_name = f"Filter {action} ({chain}) {rule_id}"
            
        self._attr_unique_id = f"{self.device_id}_filter_{rule_id}"

    @property
    def _rule_data(self):
        """Get latest rule data."""
        for rule in self.coordinator.data.get("filter", []):
            if rule.get(".id") == self.rule_id:
                return rule
        return None

    @property
    def is_on(self) -> bool:
        """Return True if rule is enabled."""
        data = self._rule_data
        if data:
            return not is_enabled(data.get("disabled"))
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return filter rule details."""
        data = self._rule_data
        if data:
            attrs = {
                "chain": data.get("chain"),
                "action": data.get("action"),
                "protocol": data.get("protocol", "any"),
            }
            if "comment" in data:
                attrs["comment"] = data["comment"]
            return attrs
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the Filter rule."""
        await self.coordinator.client.set_filter_state(self.rule_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the Filter rule."""
        await self.coordinator.client.set_filter_state(self.rule_id, False)
        await self.coordinator.async_request_refresh()


class MikrotikMangleSwitch(MikrotikSwitch):
    """Switch representation of a Mikrotik Firewall Mangle Rule (disabled by default)."""

    _device_group = "firewall"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, rule_id):
        """Initialize the mangle rule switch."""
        super().__init__(coordinator, entry_id)
        self.rule_id = rule_id
        
        rule = self._rule_data
        comment = rule.get("comment") if rule else None
        chain = rule.get("chain", "unknown") if rule else "unknown"
        action = rule.get("action", "unknown") if rule else "unknown"
        
        if comment:
            self._attr_name = f"Mangle: {comment}"
        else:
            self._attr_name = f"Mangle {action} ({chain}) {rule_id}"
            
        self._attr_unique_id = f"{self.device_id}_mangle_{rule_id}"

    @property
    def _rule_data(self):
        """Get latest rule data."""
        for rule in self.coordinator.data.get("mangle", []):
            if rule.get(".id") == self.rule_id:
                return rule
        return None

    @property
    def is_on(self) -> bool:
        """Return True if rule is enabled."""
        data = self._rule_data
        if data:
            return not is_enabled(data.get("disabled"))
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return mangle rule details."""
        data = self._rule_data
        if data:
            attrs = {
                "chain": data.get("chain"),
                "action": data.get("action"),
            }
            if "comment" in data:
                attrs["comment"] = data["comment"]
            return attrs
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the Mangle rule."""
        await self.coordinator.client.set_mangle_state(self.rule_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the Mangle rule."""
        await self.coordinator.client.set_mangle_state(self.rule_id, False)
        await self.coordinator.async_request_refresh()


class MikrotikContainerSwitch(MikrotikSwitch):
    """Switch representation of a RouterOS container."""

    _device_group = "containers"
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:docker"

    def __init__(self, coordinator, entry_id, container_id):
        """Initialize the container switch."""
        super().__init__(coordinator, entry_id)
        self.container_id = container_id

        container = self._container_data
        name = self._container_name(container)
        self._attr_name = f"Container {name}"
        self._attr_unique_id = f"{self.device_id}_container_{container_id}"

    @staticmethod
    def _container_name(container):
        """Return the best available display name for a container."""
        if not container:
            return "unknown"
        return (
            container.get("comment")
            or container.get("hostname")
            or container.get("name")
            or container.get("remote-image")
            or container.get(".id", "unknown")
        )

    @property
    def _container_data(self):
        """Get latest container data."""
        for container in self.coordinator.data.get("containers", []):
            if container.get(".id") == self.container_id:
                return container
        return None

    @property
    def is_on(self) -> bool:
        """Return True if the container is running."""
        data = self._container_data
        if not data:
            return None

        status = str(data.get("status", "")).lower()
        if status:
            return status == "running"

        if "running" in data:
            return is_enabled(data.get("running"))

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return container details."""
        data = self._container_data
        if not data:
            return {}

        attrs = {
            "routeros_id": data.get(".id"),
            "status": data.get("status"),
            "image": data.get("remote-image"),
            "hostname": data.get("hostname"),
            "comment": data.get("comment", ""),
            "interface": data.get("interface"),
            "root_dir": data.get("root-dir"),
            "start_on_boot": data.get("start-on-boot"),
        }
        return {key: value for key, value in attrs.items() if value not in (None, "")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the container."""
        await self.coordinator.client.start_container(self.container_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the container."""
        await self.coordinator.client.stop_container(self.container_id)
        await self.coordinator.async_request_refresh()
