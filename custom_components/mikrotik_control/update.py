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

    def __init__(self, coordinator, entry_id, backup_before_risky=False):
        """Initialize update entity."""
        super().__init__(coordinator, entry_id)
        self.backup_before_risky = backup_before_risky
        supported = UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
        if hasattr(UpdateEntityFeature, "BACKUP"):
            supported |= UpdateEntityFeature.BACKUP
        self._attr_supported_features = supported

    @property
    def release_summary(self) -> str | None:
        """Return update status text."""
        status = self.coordinator.data.get("updates", {}).get("status")
        installed = self.installed_version
        latest = self.latest_version
        if installed and latest and installed != latest:
            return status or f"Update available: {installed} → {latest}"
        return status or "Up to date"


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
        return (
            self.coordinator.data.get("updates", {}).get("installed-version")
            or self.coordinator.data.get("resource", {}).get("version")
        )

    @property
    def latest_version(self) -> str | None:
        """Return latest RouterOS version."""
        latest = self.coordinator.data.get("updates", {}).get("latest-version")
        if not latest:
            return self.installed_version
        return latest

    @property
    def release_notes(self) -> str | None:
        """Return release notes / changelog for RouterOS update."""
        updates = self.coordinator.data.get("updates", {})
        changelog = (
            updates.get("changelog")
            or updates.get("latest-changelog")
            or updates.get("notes")
            or updates.get("release-notes")
        )
        installed = self.installed_version
        latest = self.latest_version
        channel = updates.get("channel", "")

        lines = []
        if latest and installed and installed != latest:
            header = f"## RouterOS {latest}"
            if channel:
                header += f" ({channel} channel)"
            lines.append(header)
            lines.append(f"An update from RouterOS **{installed}** to **{latest}** is available.\n")
        elif latest:
            lines.append(f"## RouterOS {latest}")
            lines.append("RouterOS is up to date.\n")

        if changelog:
            lines.append("### Changelog\n")
            lines.append(changelog)
        elif latest and installed and installed != latest:
            lines.append("*No changelog details provided by the router.*")

        return "\n".join(lines) if lines else None

    async def async_release_notes(self) -> str | None:
        """Fetch and return release notes."""
        updates = self.coordinator.data.get("updates", {})
        changelog = (
            updates.get("changelog")
            or updates.get("latest-changelog")
            or updates.get("notes")
            or updates.get("release-notes")
        )
        if not changelog:
            try:
                await self.coordinator.client.check_updates()
                await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.debug("Could not refresh update changelog: %s", err)
        return self.release_notes

    async def async_install(self, version: str | None = None, backup: bool = False, **kwargs: Any) -> None:
        """Install RouterOS update."""
        _LOGGER.warning("RouterOS update install command sent to Mikrotik router: %s", self.host)
        
        self._attr_in_progress = True
        self.async_write_ha_state()

        if backup or self.backup_before_risky:
            try:
                await self.coordinator.client.create_backup("ha-pre-routeros-update")
            except Exception as err:
                _LOGGER.error("Failed to create backup before RouterOS update: %s", err)

        await self.coordinator.client.install_updates()
        
        # Pause coordinator updates for 60 seconds to allow the router to reboot
        self.coordinator.pause_updates(60)
        
        try:
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.debug("Post-install refresh skipped (router rebooting/offline): %s", err)
            
        self._attr_in_progress = False
        self.async_write_ha_state()


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
        return (
            self.coordinator.data.get("routerboard", {}).get("upgrade-firmware")
            or self.installed_version
        )

    @property
    def release_notes(self) -> str | None:
        """Return release notes for RouterBOARD firmware update."""
        installed = self.installed_version
        latest = self.latest_version
        updates = self.coordinator.data.get("updates", {})
        changelog = (
            updates.get("changelog")
            or updates.get("latest-changelog")
            or updates.get("notes")
            or updates.get("release-notes")
        )

        lines = []
        if installed and latest and installed != latest:
            lines.append(f"## RouterBOARD Firmware {latest}")
            lines.append(f"Firmware upgrade available: **{installed}** → **{latest}**.\n")
            lines.append("> **Note**: RouterBOARD firmware updates are included with RouterOS releases. Installing this update will flash the bootloader firmware and reboot the router to complete the upgrade process.\n")
        elif latest:
            lines.append(f"## RouterBOARD Firmware {latest}")
            lines.append("RouterBOARD firmware is up to date.\n")

        if changelog:
            lines.append("### RouterOS Changelog\n")
            lines.append(changelog)

        return "\n".join(lines) if lines else None

    async def async_release_notes(self) -> str | None:
        """Fetch and return release notes."""
        updates = self.coordinator.data.get("updates", {})
        changelog = (
            updates.get("changelog")
            or updates.get("latest-changelog")
            or updates.get("notes")
            or updates.get("release-notes")
        )
        if not changelog:
            try:
                await self.coordinator.client.check_updates()
                await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.debug("Could not refresh update changelog: %s", err)
        return self.release_notes

    async def async_install(self, version: str | None = None, backup: bool = False, **kwargs: Any) -> None:
        """Install RouterBOARD firmware update."""
        _LOGGER.warning("RouterBOARD upgrade command sent to Mikrotik router: %s", self.host)
        
        self._attr_in_progress = True
        self.async_write_ha_state()

        if backup or self.backup_before_risky:
            try:
                await self.coordinator.client.create_backup("ha-pre-routerboard-upgrade")
            except Exception as err:
                _LOGGER.error("Failed to create backup before RouterBOARD upgrade: %s", err)

        await self.coordinator.client.upgrade_routerboard()
        _LOGGER.warning("Rebooting Mikrotik router to apply RouterBOARD firmware upgrade: %s", self.host)
        await self.coordinator.client.reboot()

        # Pause coordinator updates for 60 seconds to allow the router to reboot
        self.coordinator.pause_updates(60)

        try:
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.debug("Post-upgrade reboot refresh skipped (router offline): %s", err)

        self._attr_in_progress = False
        self.async_write_ha_state()

