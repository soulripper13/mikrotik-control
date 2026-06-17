"""Sensor platform for Mikrotik Control integration."""
from datetime import datetime
import logging
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfTemperature,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .const import (
    CONF_ENABLE_INTERFACE_DETAILS,
    DEFAULT_ENABLE_INTERFACE_DETAILS,
)
from .entity import MikrotikEntity, has_interface_address, is_physical_interface

_LOGGER = logging.getLogger(__name__)

def parse_uptime(uptime_str: str) -> Any:
    """Parse Mikrotik uptime string (e.g. 1w2d3h4m5s) to timedelta."""
    if not uptime_str:
        return None
    # RouterOS uptime format can include weeks (w), days (d), hours (h), minutes (m), seconds (s)
    pattern = re.compile(r'(?:(\d+)w)?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?')
    match = pattern.match(uptime_str)
    if not match:
        return None
    
    weeks, days, hours, minutes, seconds = match.groups()
    from datetime import timedelta
    return timedelta(
        weeks=int(weeks) if weeks else 0,
        days=int(days) if days else 0,
        hours=int(hours) if hours else 0,
        minutes=int(minutes) if minutes else 0,
        seconds=int(seconds) if seconds else 0,
    )


def _enable_by_option(entity):
    """Mark an option-created entity enabled by default."""
    entity._attr_entity_registry_enabled_default = True
    return entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mikrotik sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    enable_interface_details = entry.options.get(
        CONF_ENABLE_INTERFACE_DETAILS,
        DEFAULT_ENABLE_INTERFACE_DETAILS,
    )
    entities = []

    # 1. System Resource Sensors
    entities.extend([
        MikrotikCpuLoadSensor(coordinator, entry.entry_id),
        MikrotikMemoryFreeSensor(coordinator, entry.entry_id),
        MikrotikMemoryTotalSensor(coordinator, entry.entry_id),
        MikrotikHddFreeSensor(coordinator, entry.entry_id),
        MikrotikHddTotalSensor(coordinator, entry.entry_id),
        MikrotikUptimeSensor(coordinator, entry.entry_id),
    ])

    # 2. RouterBOARD Firmware
    if coordinator.data.get("routerboard", {}).get("routerboard") in ("true", "yes", True):
        entities.extend([
            MikrotikFirmwareSensor(coordinator, entry.entry_id, "current-firmware", "Current Firmware"),
            MikrotikFirmwareSensor(coordinator, entry.entry_id, "upgrade-firmware", "Upgrade Firmware"),
        ])

    # 3. Dynamic Health Sensors (v6 & v7 compatibility)
    health_data = coordinator.data.get("health", [])
    
    # Case A: list of dicts with 'name' and 'value' keys (v7 style)
    for item in health_data:
        if "name" in item and "value" in item:
            entities.append(MikrotikHealthSensor(coordinator, entry.entry_id, item["name"]))
            
    # Case B: single dict with keys as sensor names (v6 style)
    if len(health_data) == 1 and "name" not in health_data[0]:
        for key in health_data[0].keys():
            if key not in (".id", "disabled"):
                entities.append(MikrotikHealthSensorV6(coordinator, entry.entry_id, key))

    # 4. Interface Traffic and IP Sensors
    if enable_interface_details:
        for interface in coordinator.data.get("interfaces", []):
            if "name" in interface and is_physical_interface(interface):
                entities.extend([
                    _enable_by_option(
                        MikrotikInterfaceTrafficSensor(coordinator, entry.entry_id, interface["name"], "rx")
                    ),
                    _enable_by_option(
                        MikrotikInterfaceTrafficSensor(coordinator, entry.entry_id, interface["name"], "tx")
                    ),
                ])
                if has_interface_address(coordinator, interface["name"], "ipv4"):
                    entities.append(
                        _enable_by_option(
                            MikrotikInterfaceIpSensor(coordinator, entry.entry_id, interface["name"], "ipv4")
                        )
                    )
                if has_interface_address(coordinator, interface["name"], "ipv6"):
                    entities.append(
                        _enable_by_option(
                            MikrotikInterfaceIpSensor(coordinator, entry.entry_id, interface["name"], "ipv6")
                        )
                    )

    async_add_entities(entities)


class MikrotikSensor(MikrotikEntity, SensorEntity):
    """Base class for all Mikrotik sensors (classified as diagnostics)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC


class MikrotikCpuLoadSensor(MikrotikSensor):
    """Representation of CPU Load sensor."""

    _attr_name = "CPU Load"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id):
        """Initialize CPU sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{self.device_id}_cpu_load"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        val = self.coordinator.data.get("resource", {}).get("cpu-load")
        if val is not None:
            try:
                return float(val)
            except ValueError:
                return val
        return None


class MikrotikMemoryFreeSensor(MikrotikSensor):
    """Representation of Free Memory sensor."""

    _attr_name = "Memory Free"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id):
        """Initialize sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{self.device_id}_memory_free"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        val = self.coordinator.data.get("resource", {}).get("free-memory")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                return val
        return None


class MikrotikMemoryTotalSensor(MikrotikSensor):
    """Representation of Total Memory sensor."""

    _attr_name = "Memory Total"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id):
        """Initialize sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{self.device_id}_memory_total"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        val = self.coordinator.data.get("resource", {}).get("total-memory")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                return val
        return None


class MikrotikHddFreeSensor(MikrotikSensor):
    """Representation of Free HDD sensor."""

    _attr_name = "HDD Free"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id):
        """Initialize sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{self.device_id}_hdd_free"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        val = self.coordinator.data.get("resource", {}).get("free-hdd-space")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                return val
        return None


class MikrotikHddTotalSensor(MikrotikSensor):
    """Representation of Total HDD sensor."""

    _attr_name = "HDD Total"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id):
        """Initialize sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{self.device_id}_hdd_total"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        val = self.coordinator.data.get("resource", {}).get("total-hdd-space")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                return val
        return None


class MikrotikUptimeSensor(MikrotikSensor):
    """Representation of Uptime sensor."""

    _attr_name = "Uptime"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry_id):
        """Initialize sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{self.device_id}_uptime"

    @property
    def native_value(self) -> datetime | None:
        """Return the boot time calculated from uptime."""
        uptime_str = self.coordinator.data.get("resource", {}).get("uptime")
        delta = parse_uptime(uptime_str)
        if delta is not None:
            return dt_util.utcnow() - delta
        return None


class MikrotikFirmwareSensor(MikrotikSensor):
    """Representation of RouterBOARD firmware sensor."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, key, label):
        """Initialize sensor."""
        super().__init__(coordinator, entry_id)
        self.key = key
        self._attr_name = f"Routerboard {label}"
        self._attr_unique_id = f"{self.device_id}_routerboard_{key}"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.coordinator.data.get("routerboard", {}).get(self.key)


class MikrotikHealthSensor(MikrotikSensor):
    """Representation of a dynamic Mikrotik Health Sensor (v7 list structure)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id, name):
        """Initialize sensor."""
        super().__init__(coordinator, entry_id)
        self.sensor_name = name
        self._attr_name = name.replace("-", " ").title()
        self._attr_unique_id = f"{self.device_id}_health_{name}"

        # Assign device classes & units
        if "temp" in name:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif "volt" in name:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        for item in self.coordinator.data.get("health", []):
            if item.get("name") == self.sensor_name:
                val = item.get("value")
                if val is not None:
                    try:
                        fval = float(val)
                        if self._attr_device_class == SensorDeviceClass.TEMPERATURE and fval > 150:
                            return fval / 10.0
                        return fval
                    except ValueError:
                        return val
        return None


class MikrotikHealthSensorV6(MikrotikSensor):
    """Representation of a dynamic Mikrotik Health Sensor (v6 dict structure)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id, key):
        """Initialize sensor."""
        super().__init__(coordinator, entry_id)
        self.key = key
        self._attr_name = key.replace("-", " ").title()
        self._attr_unique_id = f"{self.device_id}_health_v6_{key}"

        if "temp" in key:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif "volt" in key:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        health_data = self.coordinator.data.get("health", [])
        if len(health_data) == 1:
            val = health_data[0].get(self.key)
            if val is not None:
                try:
                    fval = float(val)
                    if self._attr_device_class == SensorDeviceClass.TEMPERATURE and fval > 150:
                        return fval / 10.0
                    return fval
                except ValueError:
                    return val
        return None


class MikrotikInterfaceTrafficSensor(MikrotikSensor):
    """Representation of cumulative interface traffic counter (disabled by default)."""

    _device_group = "interfaces"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, interface_name, direction):
        """Initialize traffic sensor."""
        super().__init__(coordinator, entry_id)
        self.interface_name = interface_name
        self.direction = direction
        self._attr_name = f"Interface {interface_name} {direction.upper()} Traffic"
        self._attr_unique_id = f"{self.device_id}_interface_{interface_name}_{direction}"

    @property
    def _interface_data(self):
        """Get latest interface data."""
        for interface in self.coordinator.data.get("interfaces", []):
            if interface.get("name") == self.interface_name:
                return interface
        return None

    @property
    def native_value(self) -> Any:
        """Return cumulative traffic."""
        data = self._interface_data
        if data:
            key = f"{self.direction}-byte"
            alt_key = f"{self.direction}-bytes"
            val = data.get(key) or data.get(alt_key)
            if val is not None:
                try:
                    return int(val)
                except ValueError:
                    return val
        return None


class MikrotikInterfaceIpSensor(MikrotikSensor):
    """Sensor for interface IP addresses."""

    _device_group = "interfaces"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id, interface_name, ip_version):
        """Initialize IP address sensor."""
        super().__init__(coordinator, entry_id)
        self.interface_name = interface_name
        self.ip_version = ip_version  # "ipv4" or "ipv6"
        self._attr_name = f"Interface {interface_name} {ip_version.upper()}"
        self._attr_unique_id = f"{self.device_id}_interface_{interface_name}_{ip_version}"
        self._attr_icon = "mdi:ip" if ip_version == "ipv4" else "mdi:ip-v6"

    @property
    def _addresses(self) -> list[dict]:
        """Get all addresses of the specified version for this interface."""
        key = f"{self.ip_version}_addresses"
        addresses = []
        for addr in self.coordinator.data.get(key, []):
            if addr.get("interface") == self.interface_name:
                addresses.append(addr)
        return addresses

    @property
    def native_value(self) -> str | None:
        """Return primary IP address without subnet mask."""
        addresses = self._addresses
        if not addresses:
            return None
        
        # Take the first non-disabled address
        for addr in addresses:
            if addr.get("disabled") not in ("true", "yes"):
                address_str = addr.get("address")
                if address_str:
                    return address_str.split("/")[0]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all assigned addresses as attributes."""
        addresses = self._addresses
        cidr_addresses = [addr.get("address") for addr in addresses if addr.get("address")]
        dynamic_list = [addr.get("dynamic") in ("true", "yes") for addr in addresses]
        
        return {
            "addresses": cidr_addresses,
            "dynamic": any(dynamic_list) if dynamic_list else False,
        }
