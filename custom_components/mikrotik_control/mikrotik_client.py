"""Mikrotik API client wrapper (Synchronous under the hood)."""
import logging
import ssl
from librouteros import connect
from librouteros.exceptions import TrapError, FatalError, LibRouterosError

_LOGGER = logging.getLogger(__name__)

# Fallbacks for version-dependent exceptions in librouteros
class DummyLoginError(Exception):
    """Dummy login error for compatibility with older librouteros."""

class DummyConnectionClosed(Exception):
    """Dummy connection closed error for compatibility with older librouteros."""

try:
    from librouteros.exceptions import LoginError
except ImportError:
    LoginError = DummyLoginError

try:
    from librouteros.exceptions import ConnectionClosed
except ImportError:
    ConnectionClosed = DummyConnectionClosed

class CannotConnect(Exception):
    """Exception to indicate connection failure."""

class InvalidAuth(Exception):
    """Exception to indicate authentication failure."""

class MikrotikClient:
    """Wrapper class for Mikrotik RouterOS API using executor."""

    def __init__(self, hass, host, username, password, port, use_ssl, verify_ssl=False):
        """Initialize the client."""
        self.hass = hass
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self.api = None

    def _connect_sync(self):
        """Establish connection (synchronous, run inside executor)."""
        if self.use_ssl:
            ssl_context = ssl.create_default_context()
            if not self.verify_ssl:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
        else:
            ssl_context = None

        try:
            self.api = connect(
                host=self.host,
                username=self.username,
                password=self.password,
                port=self.port,
                ssl_wrapper=ssl_context,
            )
            return True
        except (LoginError, TrapError) as err:
            # In older librouteros, login failures might raise TrapError or LoginError.
            err_str = str(err).lower()
            if "invalid" in err_str or "auth" in err_str or "user" in err_str or "password" in err_str or isinstance(err, LoginError):
                raise InvalidAuth(err) from err
            _LOGGER.error("Invalid credentials or authentication error for Mikrotik router: %s", err)
            raise InvalidAuth(err) from err
        except (FatalError, LibRouterosError, ConnectionClosed, OSError) as err:
            _LOGGER.error("Failed to connect to Mikrotik router: %s", err)
            raise CannotConnect(err) from err

    async def connect(self):
        """Establish connection."""
        return await self.hass.async_add_executor_job(self._connect_sync)

    def _disconnect_sync(self):
        """Close connection (synchronous)."""
        if self.api:
            try:
                self.api.close()
            except Exception as err:
                _LOGGER.debug("Error during close: %s", err)
            self.api = None

    async def disconnect(self):
        """Close connection."""
        if self.api:
            await self.hass.async_add_executor_job(self._disconnect_sync)

    def _fetch_data_sync(self):
        """Fetch all data from the router (synchronous, run inside executor)."""
        if not self.api:
            self._connect_sync()

        try:
            data = {}
            # System Resources
            resources = self._get_all_sync("system", "resource")
            data["resource"] = resources[0] if resources else {}

            # Routerboard
            routerboard = self._get_all_sync("system", "routerboard")
            data["routerboard"] = routerboard[0] if routerboard else {}

            # Identity
            identity = self._get_all_sync("system", "identity")
            data["identity"] = identity[0] if identity else {}

            # Health
            data["health"] = self._get_all_sync("system", "health")

            # Interfaces
            data["interfaces"] = self._get_all_sync("interface")

            # IP Addresses (IPv4 and IPv6)
            data["ipv4_addresses"] = self._get_all_sync("ip", "address")
            data["ipv6_addresses"] = self._get_all_sync("ipv6", "address")

            # NAT Rules
            data["nat"] = self._get_all_sync("ip", "firewall", "nat")

            # Filter Rules
            data["filter"] = self._get_all_sync("ip", "firewall", "filter")

            # Mangle Rules
            data["mangle"] = self._get_all_sync("ip", "firewall", "mangle")

            # Scripts
            data["scripts"] = self._get_all_sync("system", "script")

            # Containers (RouterOS v7)
            data["containers"] = self._get_all_sync("container")

            # Package Updates
            updates = self._get_all_sync("system", "package", "update")
            data["updates"] = updates[0] if updates else {}

            return data

        except (FatalError, LibRouterosError, ConnectionClosed, OSError) as err:
            _LOGGER.warning("Lost connection to Mikrotik router during poll: %s", err)
            self.api = None
            raise CannotConnect(err) from err

    async def fetch_data(self):
        """Fetch all data."""
        return await self.hass.async_add_executor_job(self._fetch_data_sync)

    def _get_all_sync(self, *path_parts):
        """Fetch all items from a RouterOS path (synchronous)."""
        try:
            path = self.api.path(*path_parts)
            items = []
            for item in path:
                if hasattr(item, "items"):
                    items.append({k: v for k, v in item.items()})
                else:
                    items.append(dict(item))
            return items
        except TrapError as err:
            _LOGGER.error("Trap error fetching path %s: %s", path_parts, err)
            return []

    def _set_state_sync(self, enabled, *path_parts, item_id):
        """Update the disabled state of a path item (synchronous)."""
        if not self.api:
            self._connect_sync()
        try:
            path = self.api.path(*path_parts)
            path.update(**{
                ".id": item_id,
                "disabled": "no" if enabled else "yes"
            })
        except (FatalError, LibRouterosError, ConnectionClosed, OSError) as err:
            self.api = None
            raise CannotConnect(err) from err

    async def set_interface_state(self, item_id, enabled):
        """Set interface enabled/disabled state."""
        await self.hass.async_add_executor_job(
            self._set_state_sync, enabled, "interface", item_id=item_id
        )

    async def set_nat_state(self, item_id, enabled):
        """Set NAT rule enabled/disabled state."""
        await self.hass.async_add_executor_job(
            self._set_state_sync, enabled, "ip", "firewall", "nat", item_id=item_id
        )

    async def set_filter_state(self, item_id, enabled):
        """Set filter rule enabled/disabled state."""
        await self.hass.async_add_executor_job(
            self._set_state_sync, enabled, "ip", "firewall", "filter", item_id=item_id
        )

    async def set_mangle_state(self, item_id, enabled):
        """Set mangle rule enabled/disabled state."""
        await self.hass.async_add_executor_job(
            self._set_state_sync, enabled, "ip", "firewall", "mangle", item_id=item_id
        )

    def _run_path_command_sync(self, command, *path_parts, item_id):
        """Run a command against a path item (synchronous)."""
        if not self.api:
            self._connect_sync()
        try:
            path = self.api.path(*path_parts)
            for _ in path(command, **{".id": item_id}):
                pass
        except (FatalError, LibRouterosError, ConnectionClosed, OSError) as err:
            self.api = None
            raise CannotConnect(err) from err

    async def start_container(self, item_id):
        """Start a RouterOS container."""
        await self.hass.async_add_executor_job(
            self._run_path_command_sync, "start", "container", item_id=item_id
        )

    async def stop_container(self, item_id):
        """Stop a RouterOS container."""
        await self.hass.async_add_executor_job(
            self._run_path_command_sync, "stop", "container", item_id=item_id
        )

    async def restart_container(self, item_id):
        """Restart a RouterOS container."""
        await self.stop_container(item_id)
        await self.start_container(item_id)

    def _run_script_sync(self, script_id):
        """Run a script on the router (synchronous)."""
        if not self.api:
            self._connect_sync()
        try:
            path = self.api.path("system", "script")
            for _ in path("run", **{".id": script_id}):
                pass
        except (FatalError, LibRouterosError, ConnectionClosed, OSError) as err:
            self.api = None
            raise CannotConnect(err) from err

    async def run_script(self, script_id):
        """Run a script on the router."""
        await self.hass.async_add_executor_job(self._run_script_sync, script_id)

    def _reboot_sync(self):
        """Reboot the router (synchronous)."""
        if not self.api:
            self._connect_sync()
        try:
            path = self.api.path("system")
            for _ in path("reboot"):
                pass
        except (FatalError, LibRouterosError, ConnectionClosed, OSError):
            # Rebooting closes the connection, which throws a connection exception
            pass
        finally:
            self.api = None

    async def reboot(self):
        """Reboot the router."""
        await self.hass.async_add_executor_job(self._reboot_sync)

    def _check_updates_sync(self):
        """Trigger package update check (synchronous)."""
        if not self.api:
            self._connect_sync()
        try:
            path = self.api.path("system", "package", "update")
            for _ in path("check-for-updates"):
                pass
        except (FatalError, LibRouterosError, ConnectionClosed, OSError) as err:
            self.api = None
            raise CannotConnect(err) from err

    async def check_updates(self):
        """Trigger package update check."""
        await self.hass.async_add_executor_job(self._check_updates_sync)
