#!/usr/bin/env python3
"""
Solution 2 Enhanced: VNet/Subnet IP Query with Periodic Polling
================================================================

Updated baseline approach with configurable polling intervals.
Queries Azure repeatedly to track IP state changes over time.

Modes:
- One-shot: Run once and exit (original)
- Periodic: Poll on interval (new)
- Continuous: Keep polling until stopped (new)
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Optional, List
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.mgmt.network import NetworkManagementClient


class PollingIPMonitor:
    """Query VNet/Subnet IP state on a schedule."""

    def __init__(self, subscription_id: str, resource_group: str, vnet_name: str, subnet_name: str):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.vnet_name = vnet_name
        self.subnet_name = subnet_name
        self.poll_count = 0
        self.history: List[dict] = []

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
        """Query subnet and return IP state."""
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
                        if ip_config.subnet and ip_config.subnet.id.lower() == subnet.id.lower():
                            used_ips += 1

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
                'nic_details': nic_details,
                'poll_number': self.poll_count
            }

        except Exception as e:
            print(f"❌ Error querying subnet: {e}")
            return None

    def poll_once(self) -> Optional[dict]:
        """Execute one poll cycle."""
        self.poll_count += 1
        state = self.get_subnet_ip_state()

        if state:
            self.history.append(state)
            return state
        return None

    def poll_periodic(self, interval_seconds: int, max_polls: Optional[int] = None) -> List[dict]:
        """
        Poll at regular intervals.

        Args:
            interval_seconds: Seconds between polls
            max_polls: Stop after N polls (None = infinite)

        Returns:
            List of all poll results
        """
        print(f"\n🔄 Starting periodic polling")
        print(f"   Interval: {interval_seconds}s")
        print(f"   Max polls: {max_polls if max_polls else 'infinite'}")
        print(f"   Press Ctrl+C to stop\n")

        try:
            while True:
                if max_polls and self.poll_count >= max_polls:
                    print(f"\n✅ Reached max polls ({max_polls})")
                    break

                state = self.poll_once()
                if state:
                    self._display_poll(state)

                if max_polls is None:
                    time.sleep(interval_seconds)
                elif self.poll_count < max_polls:
                    time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print(f"\n\n⏸️  Polling stopped by user")

        return self.history

    def detect_changes(self) -> dict:
        """Analyze history for IP changes."""
        if len(self.history) < 2:
            return {'changes': []}

        changes = []
        for i in range(1, len(self.history)):
            prev = self.history[i - 1]
            curr = self.history[i]

            if prev['used_ips'] != curr['used_ips']:
                changes.append({
                    'poll': i,
                    'timestamp': curr['timestamp'],
                    'previous_used': prev['used_ips'],
                    'current_used': curr['used_ips'],
                    'delta': curr['used_ips'] - prev['used_ips'],
                    'previous_free': prev['free_ips'],
                    'current_free': curr['free_ips']
                })

        return {
            'total_polls': self.poll_count,
            'total_changes': len(changes),
            'changes': changes,
            'utilization_trend': {
                'start': self.history[0]['utilization_percent'],
                'end': self.history[-1]['utilization_percent'],
                'delta': round(self.history[-1]['utilization_percent'] - self.history[0]['utilization_percent'], 2)
            }
        }

    def _display_poll(self, state: dict) -> None:
        """Display poll result in compact format."""
        print(f"[{state['poll_number']:03d}] {state['timestamp']} | " +
              f"Used: {state['used_ips']:3d}/251 | " +
              f"Free: {state['free_ips']:3d}/251 | " +
              f"Util: {state['utilization_percent']:6.2f}%")

    @staticmethod
    def _calculate_usable_ips(cidr_block: str) -> int:
        """Calculate usable IPs from CIDR block."""
        try:
            _, prefix = cidr_block.split('/')
            prefix_len = int(prefix)
            total_hosts = 2 ** (32 - prefix_len)
            return max(total_hosts - 5, 1)
        except Exception as e:
            print(f"❌ Error calculating IPs: {e}")
            return 0


def main():
    """Main entry point."""

    # Configuration
    subscription_id = os.getenv('SUBSCRIPTION_ID')
    resource_group = os.getenv('RESOURCE_GROUP', 'ipmonitor-rg')
    vnet_name = os.getenv('VNET_NAME', 'ipmonitor-dev-vnet')
    subnet_name = os.getenv('SUBNET_NAME', 'ipmonitor-dev-subnet')
    poll_interval = int(os.getenv('POLL_INTERVAL', '300'))  # 5 minutes default
    max_polls = os.getenv('MAX_POLLS')

    if max_polls:
        max_polls = int(max_polls)

    if not subscription_id:
        print("❌ SUBSCRIPTION_ID environment variable not set")
        print("\nUsage:")
        print("  export SUBSCRIPTION_ID='<your-subscription-id>'")
        print("  export RESOURCE_GROUP='ipmonitor-rg'          # optional")
        print("  export VNET_NAME='ipmonitor-dev-vnet'         # optional")
        print("  export SUBNET_NAME='ipmonitor-dev-subnet'     # optional")
        print("  export POLL_INTERVAL='300'                    # optional, seconds")
        print("  export MAX_POLLS='10'                         # optional, stop after N")
        print("  python app_polling.py")
        sys.exit(1)

    print("🔍 Solution 2 Enhanced: Periodic IP Query")
    print(f"   Subscription: {subscription_id}")
    print(f"   RG: {resource_group}, VNet: {vnet_name}, Subnet: {subnet_name}")

    # Create monitor
    monitor = PollingIPMonitor(subscription_id, resource_group, vnet_name, subnet_name)

    # Poll with periodic interval
    history = monitor.poll_periodic(poll_interval, max_polls)

    # Analyze results
    if history:
        print("\n\n" + "=" * 70)
        print("Polling Summary")
        print("=" * 70)
        print(f"Total polls: {len(history)}")
        print(f"Duration: {len(history) * poll_interval}s")

        # Change analysis
        analysis = monitor.detect_changes()
        print(f"\nIP Changes: {analysis['total_changes']}")
        print(f"Utilization trend: {analysis['utilization_trend']['start']}% → {analysis['utilization_trend']['end']}% " +
              f"({analysis['utilization_trend']['delta']:+.2f}%)")

        if analysis['changes']:
            print("\nDetailed changes:")
            for change in analysis['changes']:
                direction = "↑" if change['delta'] > 0 else "↓"
                print(f"  Poll {change['poll']}: {direction} {change['previous_used']} → {change['current_used']} " +
                      f"({change['delta']:+d} IPs, {change['previous_free']} → {change['current_free']} free)")

        print("=" * 70)

        # Export results
        print("\nJSON Export:")
        print(json.dumps({
            'monitor_config': {
                'subscription_id': subscription_id,
                'resource_group': resource_group,
                'vnet_name': vnet_name,
                'subnet_name': subnet_name
            },
            'polling_config': {
                'interval_seconds': poll_interval,
                'total_polls': len(history),
                'duration_seconds': len(history) * poll_interval
            },
            'analysis': analysis,
            'history': history
        }, indent=2))


if __name__ == '__main__':
    main()
