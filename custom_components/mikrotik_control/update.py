"""Update platform for Mikrotik Control integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BACKUP_BEFORE_RISKY_ACTIONS,
    DEFAULT_BACKUP_BEFORE_RISKY_ACTIONS,
    DOMAIN,
)
from .entity import MikrotikEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mikrotik update entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    backup_before_risky = entry.options.get(
        CONF_BACKUP_BEFORE_RISKY_ACTIONS,
        DEFAULT_BACKUP_BEFORE_RISKY_ACTIONS,
    )

    entities = [MikrotikRouterOsUpdate(coordinator, entry.entry_id, backup_before_risky)]
    if coordinator.data.get("routerboard", {}).get("routerboard") in ("true", "yes", True):
        entities.append(MikrotikRouterboardUpdate(coordinator, entry.entry_id, backup_before_risky))

    async_add_entities(entities)


class MikrotikUpdateEntity(MikrotikEntity, UpdateEntity):
    """Base class for MikroTik update entities."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, coordinator, entry_id, backup_before_risky=False):
        """Initialize update entity."""
        super().__init__(coordinator, entry_id)
        self.backup_before_risky = backup_before_risky

    @property
    def release_summary(self) -> str | None:
        """Return update status text."""
        return self.coordinator.data.get("updates", {}).get("status")


class MikrotikRouterOsUpdate(MikrotikUpdateEntity):
    """RouterOS package update entity."""

    _attr_name = "RouterOS Update"
    _attr_title = "RouterOS"

    def __init__(self, coordinator, entry_id, backup_before_risky=False):
        """Initialize RouterOS update entity."""
        super().__init__(coordinator, entry_id, backup_before_risky)
        self._attr_unique_id = f"{self.device_id}_routeros_update"

    @property
    def installed_version(self) -> str | None:
        """Return installed RouterOS version."""
        return self.coordinator.data.get("updates", {}).get("installed-version")

    @property
    def latest_version(self) -> str | None:
        """Return latest RouterOS version."""
        return self.coordinator.data.get("updates", {}).get("latest-version")

    async def async_install(self, version: str | None = None, backup: bool = False, **kwargs: Any) -> None:
        """Install RouterOS update."""
        _LOGGER.warning("RouterOS update install command sent to Mikrotik router: %s", self.host)
        if backup or self.backup_before_risky:
            await self.coordinator.client.create_backup("ha-pre-routeros-update")
        await self.coordinator.client.install_updates()
        await self.coordinator.async_request_refresh()


class MikrotikRouterboardUpdate(MikrotikUpdateEntity):
    """RouterBOARD firmware update entity."""

    _attr_name = "RouterBOARD Firmware Update"
    _attr_title = "RouterBOARD firmware"

    def __init__(self, coordinator, entry_id, backup_before_risky=False):
        """Initialize RouterBOARD update entity."""
        super().__init__(coordinator, entry_id, backup_before_risky)
        self._attr_unique_id = f"{self.device_id}_routerboard_update"

    @property
    def installed_version(self) -> str | None:
        """Return current RouterBOARD firmware."""
        return self.coordinator.data.get("routerboard", {}).get("current-firmware")

    @property
    def latest_version(self) -> str | None:
        """Return upgrade RouterBOARD firmware."""
        return self.coordinator.data.get("routerboard", {}).get("upgrade-firmware")

    async def async_install(self, version: str | None = None, backup: bool = False, **kwargs: Any) -> None:
        """Install RouterBOARD firmware update."""
        _LOGGER.warning("RouterBOARD upgrade command sent to Mikrotik router: %s", self.host)
        if backup or self.backup_before_risky:
            await self.coordinator.client.create_backup("ha-pre-routerboard-upgrade")
        await self.coordinator.client.upgrade_routerboard()
        await self.coordinator.async_request_refresh()
