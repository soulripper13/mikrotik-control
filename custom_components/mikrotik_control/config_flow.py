"""Config flow for Mikrotik Control integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback

from .const import (
    CONF_ENABLE_CONTAINER_CONTROLS,
    CONF_ENABLE_FIREWALL_CONTROLS,
    CONF_ENABLE_INTERFACE_CONTROLS,
    CONF_ENABLE_INTERFACE_DETAILS,
    CONF_ENABLE_REBOOT_BUTTON,
    CONF_ENABLE_SCRIPT_BUTTONS,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
    DEFAULT_ENABLE_CONTAINER_CONTROLS,
    DEFAULT_ENABLE_FIREWALL_CONTROLS,
    DEFAULT_ENABLE_INTERFACE_CONTROLS,
    DEFAULT_ENABLE_INTERFACE_DETAILS,
    DEFAULT_ENABLE_REBOOT_BUTTON,
    DEFAULT_ENABLE_SCRIPT_BUTTONS,
    DEFAULT_PORT,
    DOMAIN,
)
from .mikrotik_client import CannotConnect, InvalidAuth, MikrotikClient

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_USERNAME, default="admin"): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_USE_SSL, default=False): bool,
    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
})

class MikrotikControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mikrotik Control."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            client = MikrotikClient(
                hass=self.hass,
                host=user_input[CONF_HOST],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                port=user_input[CONF_PORT],
                use_ssl=user_input.get(CONF_USE_SSL, False),
                verify_ssl=user_input.get(CONF_VERIFY_SSL, False),
            )
            try:
                await client.connect()
                data = await client.fetch_data()
                await client.disconnect()

                serial = data.get("routerboard", {}).get("serial-number")
                identity = data.get("identity", {}).get("name", "MikroTik")
                
                unique_id = serial if serial else f"{user_input[CONF_HOST]}_{user_input[CONF_PORT]}"
                
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=identity,
                    data=user_input,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MikrotikControlOptionsFlowHandler(config_entry)

class MikrotikControlOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Mikrotik Control."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "scan_interval",
                    default=self._config_entry.options.get("scan_interval", 30),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                vol.Optional(
                    CONF_ENABLE_INTERFACE_DETAILS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_INTERFACE_DETAILS,
                        DEFAULT_ENABLE_INTERFACE_DETAILS,
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_INTERFACE_CONTROLS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_INTERFACE_CONTROLS,
                        DEFAULT_ENABLE_INTERFACE_CONTROLS,
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_FIREWALL_CONTROLS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_FIREWALL_CONTROLS,
                        DEFAULT_ENABLE_FIREWALL_CONTROLS,
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_SCRIPT_BUTTONS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_SCRIPT_BUTTONS,
                        DEFAULT_ENABLE_SCRIPT_BUTTONS,
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_CONTAINER_CONTROLS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_CONTAINER_CONTROLS,
                        DEFAULT_ENABLE_CONTAINER_CONTROLS,
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_REBOOT_BUTTON,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_REBOOT_BUTTON,
                        DEFAULT_ENABLE_REBOOT_BUTTON,
                    ),
                ): bool,
            }),
        )
