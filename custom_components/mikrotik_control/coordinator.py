"""Data update coordinator for the Mikrotik Control integration."""
from datetime import datetime, timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .mikrotik_client import CannotConnect, InvalidAuth, MikrotikClient

_LOGGER = logging.getLogger(__name__)

class MikrotikDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Mikrotik data."""

    def __init__(self, hass, client: MikrotikClient, scan_interval: int):
        """Initialize the coordinator."""
        self.client = client
        self.pause_updates_until: datetime | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    def pause_updates(self, seconds: int) -> None:
        """Pause data fetching for a specified number of seconds."""
        self.pause_updates_until = datetime.now() + timedelta(seconds=seconds)
        _LOGGER.info("Data fetching paused for %s seconds", seconds)

    async def _async_update_data(self):
        """Fetch data from Mikrotik Router."""
        if self.pause_updates_until and datetime.now() < self.pause_updates_until:
            _LOGGER.debug("Skipping data fetch; coordinator is currently paused")
            return self.data

        try:
            return await self.client.fetch_data()
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with Mikrotik router: {err}") from err
        except InvalidAuth as err:
            raise UpdateFailed(f"Authentication failed for Mikrotik router: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error fetching Mikrotik data: {err}") from err
