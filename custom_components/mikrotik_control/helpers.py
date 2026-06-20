"""Shared helpers for Mikrotik Control entities."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .entity import is_enabled


FIREWALL_COLLECTIONS = ("nat", "filter", "mangle")


def parse_firewall_profile(comment: str | None, prefix: str) -> str | None:
    """Return a profile name from a RouterOS comment such as ``ha:guest``."""
    if not comment:
        return None

    for token in str(comment).replace(",", " ").split():
        if token.startswith(prefix) and len(token) > len(prefix):
            return token[len(prefix) :].strip()
    return None


def firewall_profiles(data: dict[str, Any], prefix: str) -> dict[str, list[dict[str, Any]]]:
    """Return firewall rules grouped by profile tag."""
    profiles: dict[str, list[dict[str, Any]]] = {}
    for collection in FIREWALL_COLLECTIONS:
        for rule in data.get(collection, []):
            profile = parse_firewall_profile(rule.get("comment"), prefix)
            if not profile:
                continue
            profiles.setdefault(profile, []).append({**rule, "_collection": collection})
    return profiles


def wireguard_peer_name(peer: dict[str, Any]) -> str:
    """Return a friendly WireGuard peer name."""
    return (
        peer.get("comment")
        or peer.get("name")
        or peer.get("interface")
        or peer.get("public-key", "")[:12]
        or peer.get(".id", "unknown")
    )


def parse_routeros_datetime(value: str | None) -> datetime | None:
    """Parse the most common RouterOS date/time values."""
    if not value or value == "never":
        return None

    value = str(value)
    now = dt_util.now()
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%b/%d/%Y %H:%M:%S",
        "%b/%d/%Y %H:%M",
        "%b/%d %H:%M:%S",
        "%b/%d %H:%M",
    )

    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if "%Y" not in fmt:
            parsed = parsed.replace(year=now.year)
        return dt_util.as_local(parsed)

    return None


def health_summary(data: dict[str, Any]) -> tuple[str, list[str]]:
    """Return a high-level router health state and reasons."""
    reasons: list[str] = []
    resource = data.get("resource", {})

    cpu = _float(resource.get("cpu-load"))
    if cpu is not None and cpu >= 90:
        reasons.append("cpu_critical")
    elif cpu is not None and cpu >= 75:
        reasons.append("cpu_warning")

    free_memory = _float(resource.get("free-memory"))
    total_memory = _float(resource.get("total-memory"))
    if free_memory is not None and total_memory:
        used_pct = 100 - ((free_memory / total_memory) * 100)
        if used_pct >= 95:
            reasons.append("memory_critical")
        elif used_pct >= 85:
            reasons.append("memory_warning")

    free_disk = _float(resource.get("free-hdd-space"))
    total_disk = _float(resource.get("total-hdd-space"))
    if free_disk is not None and total_disk:
        used_pct = 100 - ((free_disk / total_disk) * 100)
        if used_pct >= 95:
            reasons.append("disk_critical")
        elif used_pct >= 85:
            reasons.append("disk_warning")

    for item in data.get("health", []):
        values = item.items() if "name" not in item else ((item.get("name"), item.get("value")),)
        for name, value in values:
            if "temp" not in str(name).lower():
                continue
            temperature = _float(value)
            if temperature and temperature > 150:
                temperature = temperature / 10
            if temperature is not None and temperature >= 85:
                reasons.append("temperature_critical")
            elif temperature is not None and temperature >= 70:
                reasons.append("temperature_warning")

    updates = data.get("updates", {})
    if updates.get("installed-version") and updates.get("latest-version"):
        if updates["installed-version"] != updates["latest-version"]:
            reasons.append("routeros_update_available")

    for container in data.get("containers", []):
        status = str(container.get("status", "")).lower()
        if status and status not in ("running", "stopped"):
            reasons.append("container_attention")
            break

    if any(reason.endswith("_critical") for reason in reasons):
        return "critical", reasons
    if reasons:
        return "warning", reasons
    return "healthy", reasons


def audit_findings(data: dict[str, Any]) -> list[str]:
    """Return lightweight configuration audit findings."""
    findings: list[str] = []

    for service in data.get("services", []):
        name = service.get("name")
        disabled = is_enabled(service.get("disabled"))
        address = service.get("address", "")
        if name == "api" and not disabled:
            findings.append("plain_api_enabled")
        if name in ("api", "api-ssl") and not disabled and address in ("", "0.0.0.0/0", "::/0"):
            findings.append(f"{name}_not_address_restricted")

    for user in data.get("users", []):
        if user.get("name") == "admin" and not is_enabled(user.get("disabled")):
            findings.append("default_admin_enabled")
            break

    input_rules = [
        rule
        for rule in data.get("filter", [])
        if rule.get("chain") == "input" and not is_enabled(rule.get("disabled"))
    ]
    if not input_rules:
        findings.append("no_enabled_input_firewall_rules_seen")
    elif not any(rule.get("action") == "drop" for rule in input_rules):
        findings.append("no_enabled_input_drop_rule_seen")

    return sorted(set(findings))


def _float(value: Any) -> float | None:
    """Return value as float when possible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
