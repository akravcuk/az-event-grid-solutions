import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import azure.functions as func
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from azure.mgmt.network import NetworkManagementClient
from azure.eventgrid import EventGridPublisherClient, EventGridEvent
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger("MonitorIPUsage")

def monitor_ip_usage(event: func.EventGridEvent) -> None:
    try:
        # Configuration
        subscription_id = os.getenv("SUBSCRIPTION_ID")
        event_grid_endpoint = os.getenv("EVENT_GRID_TOPIC_ENDPOINT")
        event_grid_key = os.getenv("EVENT_GRID_TOPIC_KEY")
        client_id = os.getenv("AZURE_CLIENT_ID")

        if not all([subscription_id, event_grid_endpoint, event_grid_key]):
            logger.error("Missing required environment variables")
            return

        # Extract resource info from incoming event
        event_data = event.get_json()
        resource_id = event_data.get("resourceId", "")

        if not resource_id:
            logger.warning(f"No resourceId in event: {event_data}")
            return

        # Extract subnet ID from the resource that triggered the event
        resource_type = extract_subnet_id(resource_id)

        if not resource_type:
            logger.debug(f"Event not for subnet-related resource: {resource_id}")
            return

        logger.info(f"Processing deployment event for resource: {resource_id}")

        # Get credentials first (needed for NIC lookup)
        try:
            if client_id:
                credential = ManagedIdentityCredential(client_id=client_id)
            else:
                credential = DefaultAzureCredential()
        except Exception as e:
            logger.error(f"Failed to get credential: {e}")
            return

        # If resource is a NIC, get its subnet
        if "/networkInterfaces/" in resource_id:
            subnet_id = get_subnet_from_nic(subscription_id, resource_id, credential)
            if not subnet_id:
                logger.warning(f"Could not find subnet for NIC: {resource_id}")
                return
        else:
            subnet_id = resource_id

        # Get subnet IP usage
        ip_usage = get_subnet_ip_usage(subscription_id, subnet_id, credential)

        if ip_usage:
            # Publish event to Event Grid
            publish_event(event_grid_endpoint, event_grid_key, ip_usage)
            logger.info(f"Published event: {json.dumps(ip_usage)}")
        else:
            logger.warning("Failed to retrieve subnet IP usage")

    except Exception as e:
        logger.error(f"Error in monitor_ip_usage: {e}", exc_info=True)

def extract_subnet_id(resource_id: str) -> Optional[str]:
    """
    Extract subnet ID from various resource types (NIC, IP, VM).

    Examples:
    - NIC: /subscriptions/.../networkInterfaces/my-nic
    - IP: /subscriptions/.../publicIPAddresses/my-ip
    - Subnet: /subscriptions/.../virtualNetworks/vnet/subnets/subnet

    For NIC/IP, we need to query to find the subnet. For subnet itself, return as-is.
    """
    if "/subnets/" in resource_id:
        return resource_id
    elif "/networkInterfaces/" in resource_id:
        return resource_id  # Will query NIC details to find subnet
    elif "/publicIPAddresses/" in resource_id:
        return resource_id  # May be associated with NIC
    else:
        return None

def get_subnet_from_nic(subscription_id: str, nic_id: str, credential) -> Optional[str]:
    """
    Query a NIC to find which subnet it belongs to.
    """
    try:
        network_client = NetworkManagementClient(credential, subscription_id)
        parts = nic_id.split('/')
        resource_group = parts[4]
        nic_name = parts[8]

        nic = network_client.network_interfaces.get(resource_group, nic_name)
        if nic.ip_configurations and nic.ip_configurations[0].subnet:
            return nic.ip_configurations[0].subnet.id
        return None
    except Exception as e:
        logger.error(f"Error getting subnet from NIC {nic_id}: {e}")
        return None

def get_subnet_ip_usage(subscription_id: str, subnet_id: str, credential) -> Optional[Dict[str, Any]]:
    """
    Query subnet and calculate IP usage metrics.

    Args:
        subscription_id: Azure subscription ID
        subnet_id: Full resource ID of the subnet
        credential: Azure credential for authentication

    Returns:
        Dict with IP usage metrics or None if failed
    """
    try:
        network_client = NetworkManagementClient(credential, subscription_id)

        # Parse subnet_id: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}
        parts = subnet_id.split('/')
        resource_group = parts[4]
        vnet_name = parts[8]
        subnet_name = parts[10]

        # Get subnet details
        subnet = network_client.subnets.get(resource_group, vnet_name, subnet_name)

        # Extract address prefix and calculate total IPs
        address_prefix = subnet.address_prefix
        total_ips = calculate_usable_ips(address_prefix)

        # Count used IPs by querying network interfaces with IP configurations in this subnet
        used_ips = 0
        nics = network_client.network_interfaces.list(resource_group)

        for nic in nics:
            if nic.ip_configurations:
                for ip_config in nic.ip_configurations:
                    if ip_config.subnet and ip_config.subnet.id.lower() == subnet_id.lower():
                        used_ips += 1

        free_ips = max(0, total_ips - used_ips)
        utilization_percent = (used_ips / total_ips * 100) if total_ips > 0 else 0

        return {
            "subnet_id": subnet_id,
            "subnet_name": subnet_name,
            "address_prefix": address_prefix,
            "total_ips": total_ips,
            "used_ips": used_ips,
            "free_ips": free_ips,
            "utilization_percent": round(utilization_percent, 2),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "resource_group": resource_group,
            "vnet_name": vnet_name
        }

    except Exception as e:
        logger.error(f"Error getting subnet IP usage: {e}", exc_info=True)
        return None

def calculate_usable_ips(cidr_block: str) -> int:
    """
    Calculate number of usable IPs in a CIDR block.
    Assumes no reserved IPs (first network, last broadcast for simplicity).

    Args:
        cidr_block: CIDR notation (e.g., '10.0.1.0/24')

    Returns:
        Number of usable IPs
    """
    try:
        _, prefix = cidr_block.split('/')
        prefix_len = int(prefix)
        total_hosts = 2 ** (32 - prefix_len)
        # In Azure subnets, first and last are reserved, but Azure allows using them
        # For /24, total is 256, Azure typically shows 251 usable (excluding network, gateway, broadcast)
        # This is a simplification; Azure's actual calculation is more complex
        return max(total_hosts - 5, 1)  # Conservative estimate
    except Exception as e:
        logger.error(f"Error calculating usable IPs for {cidr_block}: {e}")
        return 0

def publish_event(endpoint: str, key: str, ip_usage: Dict[str, Any]) -> bool:
    """
    Publish custom event to Event Grid topic.

    Args:
        endpoint: Event Grid topic endpoint URL
        key: Event Grid topic access key
        ip_usage: Event payload with IP usage data

    Returns:
        True if published successfully, False otherwise
    """
    try:
        client = EventGridPublisherClient(endpoint, AzureKeyCredential(key))

        event = EventGridEvent(
            event_type="ipUsageChanged",
            data=ip_usage,
            subject=f"/subscriptions/{ip_usage.get('subnet_id', 'unknown')}",
            event_time=datetime.utcnow(),
            data_version="1.0"
        )

        client.send([event])
        return True

    except Exception as e:
        logger.error(f"Error publishing event to Event Grid: {e}", exc_info=True)
        return False
