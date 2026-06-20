"""Switch platform for Mikrotik Control integration."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BACKUP_BEFORE_RISKY_ACTIONS,
    CONF_ENABLE_CONTAINER_CONTROLS,
    CONF_ENABLE_FIREWALL_CONTROLS,
    CONF_ENABLE_FIREWALL_PROFILES,
    CONF_ENABLE_INTERFACE_CONTROLS,
    CONF_ENABLE_WIREGUARD,
    CONF_FIREWALL_PROFILE_PREFIX,
    DEFAULT_BACKUP_BEFORE_RISKY_ACTIONS,
    DEFAULT_ENABLE_CONTAINER_CONTROLS,
    DEFAULT_ENABLE_FIREWALL_CONTROLS,
    DEFAULT_ENABLE_FIREWALL_PROFILES,
    DEFAULT_ENABLE_INTERFACE_CONTROLS,
    DEFAULT_ENABLE_WIREGUARD,
    DEFAULT_FIREWALL_PROFILE_PREFIX,
    DOMAIN,
)
from .entity import MikrotikEntity, is_enabled, is_physical_interface, safe_key
from .helpers import firewall_profiles, wireguard_peer_name

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
    enable_wireguard = entry.options.get(CONF_ENABLE_WIREGUARD, DEFAULT_ENABLE_WIREGUARD)
    enable_firewall_profiles = entry.options.get(
        CONF_ENABLE_FIREWALL_PROFILES,
        DEFAULT_ENABLE_FIREWALL_PROFILES,
    )
    backup_before_risky = entry.options.get(
        CONF_BACKUP_BEFORE_RISKY_ACTIONS,
        DEFAULT_BACKUP_BEFORE_RISKY_ACTIONS,
    )
    firewall_profile_prefix = entry.options.get(
        CONF_FIREWALL_PROFILE_PREFIX,
        DEFAULT_FIREWALL_PROFILE_PREFIX,
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
                entities.append(
                    _enable_by_option(
                        MikrotikNatSwitch(coordinator, entry.entry_id, rule[".id"], backup_before_risky)
                    )
                )

        # 3. Add Filter rules switches
        for rule in coordinator.data.get("filter", []):
            if ".id" in rule:
                entities.append(
                    _enable_by_option(
                        MikrotikFilterSwitch(coordinator, entry.entry_id, rule[".id"], backup_before_risky)
                    )
                )

        # 4. Add Mangle rules switches
        for rule in coordinator.data.get("mangle", []):
            if ".id" in rule:
                entities.append(
                    _enable_by_option(
                        MikrotikMangleSwitch(coordinator, entry.entry_id, rule[".id"], backup_before_risky)
                    )
                )

    if enable_firewall_profiles:
        for profile in firewall_profiles(coordinator.data, firewall_profile_prefix):
            entities.append(
                _enable_by_option(
                    MikrotikFirewallProfileSwitch(
                        coordinator,
                        entry.entry_id,
                        profile,
                        firewall_profile_prefix,
                        backup_before_risky,
                    )
                )
            )

    # 5. Add container start/stop switches
    if enable_container_controls:
        for container in coordinator.data.get("containers", []):
            if ".id" in container:
                entities.append(
                    _enable_by_option(MikrotikContainerSwitch(coordinator, entry.entry_id, container[".id"]))
                )

    if enable_wireguard:
        for peer in coordinator.data.get("wireguard_peers", []):
            if ".id" in peer:
                entities.append(
                    _enable_by_option(MikrotikWireGuardPeerSwitch(coordinator, entry.entry_id, peer[".id"]))
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
        self._attr_unique_id = f"{self.device_id}_interface_{safe_key(interface_name)}"

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

    def __init__(self, coordinator, entry_id, rule_id, backup_before_risky=False):
        """Initialize the NAT rule switch."""
        super().__init__(coordinator, entry_id)
        self.rule_id = rule_id
        self.backup_before_risky = backup_before_risky
        
        # Name formulation
        rule = self._rule_data
        comment = rule.get("comment") if rule else None
        chain = rule.get("chain", "unknown") if rule else "unknown"
        action = rule.get("action", "unknown") if rule else "unknown"
        
        if comment:
            self._attr_name = f"NAT: {comment}"
        else:
            self._attr_name = f"NAT {action} ({chain}) {rule_id}"
            
        self._attr_unique_id = f"{self.device_id}_nat_{safe_key(rule_id)}"

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
                "routeros_id": data.get(".id"),
                "chain": data.get("chain"),
                "action": data.get("action"),
                "protocol": data.get("protocol", "any"),
                "risky_action": True,
                "backup_before_change": self.backup_before_risky,
            }
            optional_keys = (
                "src-address",
                "dst-address",
                "in-interface",
                "out-interface",
                "connection-state",
                "log",
                "log-prefix",
                "place-before",
            )
            for key in optional_keys:
                if key in data:
                    attrs[key.replace("-", "_")] = data[key]
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
        await self._backup_if_needed("pre-nat-enable")
        await self.coordinator.client.set_nat_state(self.rule_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the NAT rule."""
        await self._backup_if_needed("pre-nat-disable")
        await self.coordinator.client.set_nat_state(self.rule_id, False)
        await self.coordinator.async_request_refresh()

    async def _backup_if_needed(self, name):
        """Create a backup before changing a firewall rule when configured."""
        if self.backup_before_risky:
            await self.coordinator.client.create_backup(name)


class MikrotikFilterSwitch(MikrotikSwitch):
    """Switch representation of a Mikrotik Firewall Filter Rule (disabled by default)."""

    _device_group = "firewall"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, rule_id, backup_before_risky=False):
        """Initialize the filter rule switch."""
        super().__init__(coordinator, entry_id)
        self.rule_id = rule_id
        self.backup_before_risky = backup_before_risky
        
        rule = self._rule_data
        comment = rule.get("comment") if rule else None
        chain = rule.get("chain", "unknown") if rule else "unknown"
        action = rule.get("action", "unknown") if rule else "unknown"
        
        if comment:
            self._attr_name = f"Filter: {comment}"
        else:
            self._attr_name = f"Filter {action} ({chain}) {rule_id}"
            
        self._attr_unique_id = f"{self.device_id}_filter_{safe_key(rule_id)}"

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
                "routeros_id": data.get(".id"),
                "chain": data.get("chain"),
                "action": data.get("action"),
                "protocol": data.get("protocol", "any"),
                "risky_action": True,
                "backup_before_change": self.backup_before_risky,
            }
            optional_keys = (
                "src-address",
                "dst-address",
                "src-port",
                "dst-port",
                "in-interface",
                "out-interface",
                "connection-state",
                "log",
                "log-prefix",
            )
            for key in optional_keys:
                if key in data:
                    attrs[key.replace("-", "_")] = data[key]
            if "comment" in data:
                attrs["comment"] = data["comment"]
            return attrs
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the Filter rule."""
        await self._backup_if_needed("pre-filter-enable")
        await self.coordinator.client.set_filter_state(self.rule_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the Filter rule."""
        await self._backup_if_needed("pre-filter-disable")
        await self.coordinator.client.set_filter_state(self.rule_id, False)
        await self.coordinator.async_request_refresh()

    async def _backup_if_needed(self, name):
        """Create a backup before changing a firewall rule when configured."""
        if self.backup_before_risky:
            await self.coordinator.client.create_backup(name)


class MikrotikMangleSwitch(MikrotikSwitch):
    """Switch representation of a Mikrotik Firewall Mangle Rule (disabled by default)."""

    _device_group = "firewall"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, rule_id, backup_before_risky=False):
        """Initialize the mangle rule switch."""
        super().__init__(coordinator, entry_id)
        self.rule_id = rule_id
        self.backup_before_risky = backup_before_risky
        
        rule = self._rule_data
        comment = rule.get("comment") if rule else None
        chain = rule.get("chain", "unknown") if rule else "unknown"
        action = rule.get("action", "unknown") if rule else "unknown"
        
        if comment:
            self._attr_name = f"Mangle: {comment}"
        else:
            self._attr_name = f"Mangle {action} ({chain}) {rule_id}"
            
        self._attr_unique_id = f"{self.device_id}_mangle_{safe_key(rule_id)}"

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
                "routeros_id": data.get(".id"),
                "chain": data.get("chain"),
                "action": data.get("action"),
                "risky_action": True,
                "backup_before_change": self.backup_before_risky,
            }
            optional_keys = (
                "protocol",
                "src-address",
                "dst-address",
                "src-port",
                "dst-port",
                "in-interface",
                "out-interface",
                "connection-mark",
                "new-connection-mark",
                "packet-mark",
                "new-packet-mark",
                "routing-mark",
                "new-routing-mark",
                "passthrough",
                "log",
                "log-prefix",
            )
            for key in optional_keys:
                if key in data:
                    attrs[key.replace("-", "_")] = data[key]
            if "comment" in data:
                attrs["comment"] = data["comment"]
            return attrs
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the Mangle rule."""
        await self._backup_if_needed("pre-mangle-enable")
        await self.coordinator.client.set_mangle_state(self.rule_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the Mangle rule."""
        await self._backup_if_needed("pre-mangle-disable")
        await self.coordinator.client.set_mangle_state(self.rule_id, False)
        await self.coordinator.async_request_refresh()

    async def _backup_if_needed(self, name):
        """Create a backup before changing a firewall rule when configured."""
        if self.backup_before_risky:
            await self.coordinator.client.create_backup(name)


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
        self._attr_unique_id = f"{self.device_id}_container_{safe_key(container_id)}"

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
            "envlist": data.get("envlist"),
            "mounts": data.get("mounts"),
            "workdir": data.get("workdir"),
            "cmd": data.get("cmd"),
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


class MikrotikWireGuardPeerSwitch(MikrotikSwitch):
    """Switch representation of a WireGuard peer."""

    _device_group = "wireguard"
    _attr_icon = "mdi:vpn"

    def __init__(self, coordinator, entry_id, peer_id):
        """Initialize peer switch."""
        super().__init__(coordinator, entry_id)
        self.peer_id = peer_id
        peer = self._peer_data or {}
        self._attr_name = f"WireGuard Peer {wireguard_peer_name(peer)}"
        self._attr_unique_id = f"{self.device_id}_wireguard_peer_{safe_key(peer_id)}"

    @property
    def _peer_data(self):
        """Get latest peer data."""
        for peer in self.coordinator.data.get("wireguard_peers", []):
            if peer.get(".id") == self.peer_id:
                return peer
        return None

    @property
    def is_on(self) -> bool:
        """Return true when peer is enabled."""
        peer = self._peer_data
        if not peer:
            return False
        return not is_enabled(peer.get("disabled"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return peer details."""
        peer = self._peer_data
        if not peer:
            return {}
        attrs = {
            "routeros_id": peer.get(".id"),
            "interface": peer.get("interface"),
            "allowed_address": peer.get("allowed-address"),
            "endpoint_address": peer.get("endpoint-address"),
            "endpoint_port": peer.get("endpoint-port"),
            "persistent_keepalive": peer.get("persistent-keepalive"),
            "last_handshake": peer.get("last-handshake"),
            "comment": peer.get("comment", ""),
        }
        return {key: value for key, value in attrs.items() if value not in (None, "")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the WireGuard peer."""
        await self.coordinator.client.set_wireguard_peer_state(self.peer_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the WireGuard peer."""
        await self.coordinator.client.set_wireguard_peer_state(self.peer_id, False)
        await self.coordinator.async_request_refresh()


class MikrotikFirewallProfileSwitch(MikrotikSwitch):
    """Switch that controls firewall rules grouped by comment tag."""

    _device_group = "firewall"
    _attr_icon = "mdi:shield-link-variant"

    def __init__(self, coordinator, entry_id, profile, prefix, backup_before_risky=False):
        """Initialize firewall profile switch."""
        super().__init__(coordinator, entry_id)
        self.profile = profile
        self.prefix = prefix
        self.backup_before_risky = backup_before_risky
        self._attr_name = f"Firewall Profile {profile}"
        self._attr_unique_id = f"{self.device_id}_firewall_profile_{safe_key(profile)}"

    @property
    def _rules(self):
        """Return latest rules for this profile."""
        return firewall_profiles(self.coordinator.data, self.prefix).get(self.profile, [])

    @property
    def is_on(self) -> bool:
        """Return true when all profile rules are enabled."""
        rules = self._rules
        if not rules:
            return False
        return all(not is_enabled(rule.get("disabled")) for rule in rules)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return profile details."""
        return {
            "profile": self.profile,
            "tag": f"{self.prefix}{self.profile}",
            "rule_count": len(self._rules),
            "risky_action": True,
            "backup_before_change": self.backup_before_risky,
            "rules": [
                {
                    "routeros_id": rule.get(".id"),
                    "type": rule.get("_collection"),
                    "chain": rule.get("chain"),
                    "action": rule.get("action"),
                    "comment": rule.get("comment", ""),
                }
                for rule in self._rules
            ],
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable all rules in the firewall profile."""
        await self._backup_if_needed("pre-firewall-profile-enable")
        for rule in self._rules:
            await self._set_rule_state(rule, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable all rules in the firewall profile."""
        await self._backup_if_needed("pre-firewall-profile-disable")
        for rule in self._rules:
            await self._set_rule_state(rule, False)
        await self.coordinator.async_request_refresh()

    async def _set_rule_state(self, rule, enabled):
        """Set a grouped firewall rule state."""
        collection = rule.get("_collection")
        item_id = rule.get(".id")
        if collection == "nat":
            await self.coordinator.client.set_nat_state(item_id, enabled)
        elif collection == "filter":
            await self.coordinator.client.set_filter_state(item_id, enabled)
        elif collection == "mangle":
            await self.coordinator.client.set_mangle_state(item_id, enabled)

    async def _backup_if_needed(self, name):
        """Create a backup before changing grouped firewall rules when configured."""
        if self.backup_before_risky:
            await self.coordinator.client.create_backup(name)
