#!/usr/bin/env python3
"""
Solution 2: Simple VNet/Subnet IP Query
========================================

Naive polling approach: Query Azure to get VNet/Subnet and calculate free IPs.
No events. No subscriptions. Just: ask Azure → get IPs → display.

This is intentionally simple to show the baseline approach.
"""

import os
import sys
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.mgmt.network import NetworkManagementClient
import json
from datetime import datetime


class SimpleIPQuery:
    """Query VNet/Subnet IP state - that's it."""

    def __init__(self, subscription_id: str, resource_group: str, vnet_name: str, subnet_name: str):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.vnet_name = vnet_name
        self.subnet_name = subnet_name

        # Get credentials
        try:
            client_id = os.getenv('AZURE_CLIENT_ID')
            if client_id:
                self.credential = ManagedIdentityCredential(client_id=client_id)
            else:
                self.credential = DefaultAzureCredential()
        except Exception as e:
            print(f"❌ Failed to get credentials: {e}")
            sys.exit(1)

        # Create network client
        self.network_client = NetworkManagementClient(self.credential, subscription_id)

    def get_subnet_ip_state(self) -> dict:
        """
        Query subnet and return IP state.

        Returns:
        {
            'subnet_id': str,
            'subnet_name': str,
            'address_prefix': str,
            'total_ips': int,
            'used_ips': int,
            'free_ips': int,
            'utilization_percent': float,
            'timestamp': str,
            'nic_details': [{name, ip_count}, ...]
        }
        """
        try:
            # Get subnet
            subnet = self.network_client.subnets.get(
                self.resource_group,
                self.vnet_name,
                self.subnet_name
            )

            address_prefix = subnet.address_prefix
            total_ips = self._calculate_usable_ips(address_prefix)

            # Get all NICs in resource group
            used_ips = 0
            nic_details = []
            nics = self.network_client.network_interfaces.list(self.resource_group)

            for nic in nics:
                if nic.ip_configurations:
                    for ip_config in nic.ip_configurations:
                        # Check if this IP belongs to our subnet
                        if ip_config.subnet and ip_config.subnet.id.lower() == subnet.id.lower():
                            used_ips += 1

                    # Track NIC details
                    if any(
                        ip_config.subnet and ip_config.subnet.id.lower() == subnet.id.lower()
                        for ip_config in nic.ip_configurations
                    ):
                        ip_count = sum(
                            1 for ip_config in nic.ip_configurations
                            if ip_config.subnet and ip_config.subnet.id.lower() == subnet.id.lower()
                        )
                        nic_details.append({
                            'name': nic.name,
                            'ip_count': ip_count
                        })

            free_ips = max(0, total_ips - used_ips)
            utilization_percent = (used_ips / total_ips * 100) if total_ips > 0 else 0

            return {
                'subnet_id': subnet.id,
                'subnet_name': self.subnet_name,
                'address_prefix': address_prefix,
                'total_ips': total_ips,
                'used_ips': used_ips,
                'free_ips': free_ips,
                'utilization_percent': round(utilization_percent, 2),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'nic_details': nic_details
            }

        except Exception as e:
            print(f"❌ Error querying subnet: {e}")
            sys.exit(1)

    @staticmethod
    def _calculate_usable_ips(cidr_block: str) -> int:
        """Calculate usable IPs from CIDR block."""
        try:
            _, prefix = cidr_block.split('/')
            prefix_len = int(prefix)
            total_hosts = 2 ** (32 - prefix_len)
            # Subtract 5 reserved IPs (network, gateway, DNS, etc.)
            return max(total_hosts - 5, 1)
        except Exception as e:
            print(f"❌ Error calculating IPs: {e}")
            return 0


def display_ip_state(state: dict) -> None:
    """Pretty-print IP state."""
    print("\n" + "=" * 70)
    print("VNet/Subnet IP State")
    print("=" * 70)
    print(f"Subnet:           {state['subnet_name']}")
    print(f"Address Prefix:   {state['address_prefix']}")
    print(f"Timestamp:        {state['timestamp']}")
    print()
    print(f"Total IPs:        {state['total_ips']}")
    print(f"Used IPs:         {state['used_ips']}")
    print(f"Free IPs:         {state['free_ips']}")
    print(f"Utilization:      {state['utilization_percent']}%")
    print()

    if state['nic_details']:
        print("NICs in this subnet:")
        for nic in state['nic_details']:
            print(f"  - {nic['name']}: {nic['ip_count']} IP(s)")
    else:
        print("No NICs in this subnet")

    print("=" * 70 + "\n")


def main():
    """Query and display subnet IP state."""

    # Get configuration from environment
    subscription_id = os.getenv('SUBSCRIPTION_ID')
    resource_group = os.getenv('RESOURCE_GROUP', 'ipmonitor-rg')
    vnet_name = os.getenv('VNET_NAME', 'ipmonitor-dev-vnet')
    subnet_name = os.getenv('SUBNET_NAME', 'ipmonitor-dev-subnet')

    if not subscription_id:
        print("❌ SUBSCRIPTION_ID environment variable not set")
        print("\nUsage:")
        print("  export SUBSCRIPTION_ID='<your-subscription-id>'")
        print("  export RESOURCE_GROUP='ipmonitor-rg'          # optional")
        print("  export VNET_NAME='ipmonitor-dev-vnet'         # optional")
        print("  export SUBNET_NAME='ipmonitor-dev-subnet'     # optional")
        print("  python app.py")
        sys.exit(1)

    print("🔍 Solution 2: Simple VNet/Subnet IP Query")
    print(f"   Subscription: {subscription_id}")
    print(f"   RG: {resource_group}, VNet: {vnet_name}, Subnet: {subnet_name}")
    print()

    # Query
    query = SimpleIPQuery(subscription_id, resource_group, vnet_name, subnet_name)
    state = query.get_subnet_ip_state()

    # Display
    display_ip_state(state)

    # JSON output for automation
    print("JSON Output:")
    print(json.dumps(state, indent=2))

    return state


if __name__ == '__main__':
    main()
