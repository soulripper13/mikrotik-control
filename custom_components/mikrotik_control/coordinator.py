"""Data update coordinator for the Mikrotik Control integration."""
from datetime import timedelta
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
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Fetch data from Mikrotik Router."""
        try:
            return await self.client.fetch_data()
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with Mikrotik router: {err}") from err
        except InvalidAuth as err:
            raise UpdateFailed(f"Authentication failed for Mikrotik router: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error fetching Mikrotik data: {err}") from err
