"""
In-app IP monitoring decorator for VNet/Subnet IP tracking.

This module provides a decorator that checks subnet IP availability before
creating network resources. It's integrated into application code as a
preventive measure rather than reactive monitoring.

Design: Decorator wraps resource-creation functions to verify IP availability
before proceeding, failing fast if resources are exhausted.
"""

import os
import logging
from functools import wraps
from typing import Optional, Dict, Any, Callable
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient

logger = logging.getLogger(__name__)


class IPAvailabilityError(Exception):
    """Raised when insufficient IPs are available in the subnet."""
    pass


class SubnetIPStatus:
    """Container for subnet IP usage metrics."""

    def __init__(
        self,
        subnet_id: str,
        subnet_name: str,
        address_prefix: str,
        total_ips: int,
        used_ips: int,
        free_ips: int,
        utilization_percent: float
    ):
        self.subnet_id = subnet_id
        self.subnet_name = subnet_name
        self.address_prefix = address_prefix
        self.total_ips = total_ips
        self.used_ips = used_ips
        self.free_ips = free_ips
        self.utilization_percent = utilization_percent

    def __repr__(self) -> str:
        return (
            f"SubnetIPStatus("
            f"subnet={self.subnet_name}, "
            f"free={self.free_ips}/{self.total_ips}, "
            f"util={self.utilization_percent:.1f}%)"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subnet_id": self.subnet_id,
            "subnet_name": self.subnet_name,
            "address_prefix": self.address_prefix,
            "total_ips": self.total_ips,
            "used_ips": self.used_ips,
            "free_ips": self.free_ips,
            "utilization_percent": self.utilization_percent
        }


def get_subnet_ip_status(
    subscription_id: str,
    resource_group: str,
    vnet_name: str,
    subnet_name: str,
    credential=None
) -> Optional[SubnetIPStatus]:
    """
    Query Azure for current subnet IP usage.

    Args:
        subscription_id: Azure subscription ID
        resource_group: Resource group name
        vnet_name: Virtual network name
        subnet_name: Subnet name
        credential: Azure credential (uses DefaultAzureCredential if None)

    Returns:
        SubnetIPStatus with current metrics, or None if query failed
    """
    try:
        if credential is None:
            try:
                client_id = os.getenv("AZURE_CLIENT_ID")
                credential = (
                    ManagedIdentityCredential(client_id=client_id)
                    if client_id
                    else DefaultAzureCredential()
                )
            except Exception as e:
                logger.error(f"Failed to get credential: {e}")
                return None

        network_client = NetworkManagementClient(credential, subscription_id)

        # Get subnet details
        subnet = network_client.subnets.get(resource_group, vnet_name, subnet_name)
        address_prefix = subnet.address_prefix
        total_ips = calculate_usable_ips(address_prefix)

        # Count used IPs
        used_ips = 0
        nics = network_client.network_interfaces.list(resource_group)
        subnet_id = subnet.id

        for nic in nics:
            if nic.ip_configurations:
                for ip_config in nic.ip_configurations:
                    if ip_config.subnet and ip_config.subnet.id.lower() == subnet_id.lower():
                        used_ips += 1

        free_ips = max(0, total_ips - used_ips)
        utilization_percent = (used_ips / total_ips * 100) if total_ips > 0 else 0

        return SubnetIPStatus(
            subnet_id=subnet_id,
            subnet_name=subnet_name,
            address_prefix=address_prefix,
            total_ips=total_ips,
            used_ips=used_ips,
            free_ips=free_ips,
            utilization_percent=utilization_percent
        )

    except Exception as e:
        logger.error(
            f"Error querying subnet IP status for {resource_group}/{vnet_name}/{subnet_name}: {e}",
            exc_info=True
        )
        return None


def calculate_usable_ips(cidr_block: str) -> int:
    """
    Calculate usable IPs in a CIDR block.

    Args:
        cidr_block: CIDR notation (e.g., '10.0.1.0/24')

    Returns:
        Number of usable IPs (conservative estimate for Azure)
    """
    try:
        _, prefix = cidr_block.split('/')
        prefix_len = int(prefix)
        total_hosts = 2 ** (32 - prefix_len)
        # Azure reserves ~5 IPs per subnet (network, gateway, broadcast, etc.)
        return max(total_hosts - 5, 1)
    except Exception as e:
        logger.error(f"Error calculating usable IPs for {cidr_block}: {e}")
        return 0


def monitor_ip_status(
    subscription_id: str,
    resource_group: str,
    vnet_name: str,
    subnet_name: str,
    min_free_ips: int = 1
) -> Callable:
    """
    Decorator that checks subnet IP availability before executing function.

    If free IPs < min_free_ips, raises IPAvailabilityError.
    If check succeeds, executes the wrapped function and returns its result.

    Args:
        subscription_id: Azure subscription ID
        resource_group: Resource group name
        vnet_name: Virtual network name
        subnet_name: Subnet name
        min_free_ips: Minimum free IPs required to proceed (default: 1)

    Returns:
        Decorator function

    Example:
        @monitor_ip_status(
            subscription_id="...",
            resource_group="my-rg",
            vnet_name="my-vnet",
            subnet_name="my-subnet"
        )
        def create_nic(nic_name: str):
            # Create NIC here
            return nic

    Raises:
        IPAvailabilityError: When insufficient free IPs available
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Query current IP status
            ip_status = get_subnet_ip_status(
                subscription_id,
                resource_group,
                vnet_name,
                subnet_name
            )

            if ip_status is None:
                # Fail closed: cannot verify IP availability - block operation
                raise IPAvailabilityError(
                    "Could not query subnet IP status. "
                    "Blocking resource creation for safety (fail-closed policy)."
                )

            logger.info(f"Subnet IP status: {ip_status}")

            # Check if sufficient IPs available
            if ip_status.free_ips < min_free_ips:
                raise IPAvailabilityError(
                    f"Insufficient free IPs in {ip_status.subnet_name}. "
                    f"Required: {min_free_ips}, Available: {ip_status.free_ips}. "
                    f"Utilization: {ip_status.utilization_percent:.1f}%"
                )

            # If we get here, IP availability verified - proceed with wrapped function
            result = func(*args, **kwargs)
            logger.info(f"Function {func.__name__} completed successfully")
            return result

        return wrapper
    return decorator
