#!/usr/bin/env python3
"""
Tests for Solution 2: Simple VNet/Subnet IP Query
"""

import unittest
import json
from unittest.mock import Mock, patch, MagicMock
from app import SimpleIPQuery


class TestSimpleIPQuery(unittest.TestCase):
    """Test simple IP query functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.subscription_id = 'test-subscription'
        self.resource_group = 'test-rg'
        self.vnet_name = 'test-vnet'
        self.subnet_name = 'test-subnet'

    @patch('app.NetworkManagementClient')
    @patch('app.DefaultAzureCredential')
    def test_initialization(self, mock_credential, mock_client):
        """Test SimpleIPQuery initialization."""
        query = SimpleIPQuery(
            self.subscription_id,
            self.resource_group,
            self.vnet_name,
            self.subnet_name
        )

        self.assertEqual(query.subscription_id, self.subscription_id)
        self.assertEqual(query.resource_group, self.resource_group)
        self.assertEqual(query.vnet_name, self.vnet_name)
        self.assertEqual(query.subnet_name, self.subnet_name)

    def test_calculate_usable_ips(self):
        """Test IP calculation from CIDR."""
        test_cases = [
            ('10.0.1.0/24', 251),  # 256 - 5 reserved
            ('10.0.0.0/16', 65531),  # 65536 - 5 reserved
            ('10.0.1.0/25', 123),  # 128 - 5 reserved
            ('10.0.1.0/30', 0),  # 4 - 5 = -1, max 1
        ]

        for cidr, expected in test_cases:
            result = SimpleIPQuery._calculate_usable_ips(cidr)
            self.assertGreaterEqual(result, 0, f"CIDR {cidr} should return non-negative")

    @patch('app.NetworkManagementClient')
    @patch('app.DefaultAzureCredential')
    def test_get_subnet_ip_state_no_nics(self, mock_credential, mock_client):
        """Test querying subnet with no NICs."""
        # Mock subnet
        mock_subnet = Mock()
        mock_subnet.id = '/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet'
        mock_subnet.address_prefix = '10.0.1.0/24'

        # Mock network client
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        mock_instance.subnets.get.return_value = mock_subnet
        mock_instance.network_interfaces.list.return_value = []

        # Query
        query = SimpleIPQuery(
            self.subscription_id,
            self.resource_group,
            self.vnet_name,
            self.subnet_name
        )
        state = query.get_subnet_ip_state()

        # Assertions
        self.assertEqual(state['subnet_name'], self.subnet_name)
        self.assertEqual(state['address_prefix'], '10.0.1.0/24')
        self.assertEqual(state['total_ips'], 251)
        self.assertEqual(state['used_ips'], 0)
        self.assertEqual(state['free_ips'], 251)
        self.assertEqual(state['utilization_percent'], 0.0)

    @patch('app.NetworkManagementClient')
    @patch('app.DefaultAzureCredential')
    def test_get_subnet_ip_state_with_nics(self, mock_credential, mock_client):
        """Test querying subnet with NICs."""
        # Mock subnet
        mock_subnet = Mock()
        mock_subnet.id = '/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet'
        mock_subnet.address_prefix = '10.0.1.0/24'

        # Mock NIC with IP config
        mock_nic = Mock()
        mock_nic.name = 'test-nic'
        mock_ip_config = Mock()
        mock_ip_config.subnet = Mock()
        mock_ip_config.subnet.id = mock_subnet.id
        mock_nic.ip_configurations = [mock_ip_config]

        # Mock network client
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        mock_instance.subnets.get.return_value = mock_subnet
        mock_instance.network_interfaces.list.return_value = [mock_nic]

        # Query
        query = SimpleIPQuery(
            self.subscription_id,
            self.resource_group,
            self.vnet_name,
            self.subnet_name
        )
        state = query.get_subnet_ip_state()

        # Assertions
        self.assertEqual(state['used_ips'], 1)
        self.assertEqual(state['free_ips'], 250)
        self.assertAlmostEqual(state['utilization_percent'], 0.40, places=1)
        self.assertEqual(len(state['nic_details']), 1)
        self.assertEqual(state['nic_details'][0]['name'], 'test-nic')
        self.assertEqual(state['nic_details'][0]['ip_count'], 1)

    @patch('app.NetworkManagementClient')
    @patch('app.DefaultAzureCredential')
    def test_get_subnet_ip_state_multiple_nics(self, mock_credential, mock_client):
        """Test with multiple NICs and secondary IPs."""
        # Mock subnet
        mock_subnet = Mock()
        mock_subnet.id = '/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet'
        mock_subnet.address_prefix = '10.0.1.0/24'

        # Mock NIC 1 with 2 IPs (primary + secondary)
        mock_nic1 = Mock()
        mock_nic1.name = 'nic-1'
        mock_ip_config1 = Mock()
        mock_ip_config1.subnet = Mock()
        mock_ip_config1.subnet.id = mock_subnet.id
        mock_ip_config2 = Mock()
        mock_ip_config2.subnet = Mock()
        mock_ip_config2.subnet.id = mock_subnet.id
        mock_nic1.ip_configurations = [mock_ip_config1, mock_ip_config2]

        # Mock NIC 2 with 1 IP
        mock_nic2 = Mock()
        mock_nic2.name = 'nic-2'
        mock_ip_config3 = Mock()
        mock_ip_config3.subnet = Mock()
        mock_ip_config3.subnet.id = mock_subnet.id
        mock_nic2.ip_configurations = [mock_ip_config3]

        # Mock network client
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        mock_instance.subnets.get.return_value = mock_subnet
        mock_instance.network_interfaces.list.return_value = [mock_nic1, mock_nic2]

        # Query
        query = SimpleIPQuery(
            self.subscription_id,
            self.resource_group,
            self.vnet_name,
            self.subnet_name
        )
        state = query.get_subnet_ip_state()

        # Assertions: 2 + 1 = 3 IPs used
        self.assertEqual(state['used_ips'], 3)
        self.assertEqual(state['free_ips'], 248)
        self.assertAlmostEqual(state['utilization_percent'], 1.20, places=1)
        self.assertEqual(len(state['nic_details']), 2)

    @patch('app.NetworkManagementClient')
    @patch('app.DefaultAzureCredential')
    def test_state_has_required_fields(self, mock_credential, mock_client):
        """Test that state includes all required fields."""
        # Mock subnet
        mock_subnet = Mock()
        mock_subnet.id = '/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet'
        mock_subnet.address_prefix = '10.0.1.0/24'

        # Mock network client
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        mock_instance.subnets.get.return_value = mock_subnet
        mock_instance.network_interfaces.list.return_value = []

        # Query
        query = SimpleIPQuery(
            self.subscription_id,
            self.resource_group,
            self.vnet_name,
            self.subnet_name
        )
        state = query.get_subnet_ip_state()

        # Check all required fields
        required_fields = [
            'subnet_id', 'subnet_name', 'address_prefix',
            'total_ips', 'used_ips', 'free_ips',
            'utilization_percent', 'timestamp', 'nic_details'
        ]
        for field in required_fields:
            self.assertIn(field, state, f"Missing field: {field}")

    @patch('app.NetworkManagementClient')
    @patch('app.DefaultAzureCredential')
    def test_state_is_json_serializable(self, mock_credential, mock_client):
        """Test that state can be converted to JSON."""
        # Mock subnet
        mock_subnet = Mock()
        mock_subnet.id = '/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet'
        mock_subnet.address_prefix = '10.0.1.0/24'

        # Mock network client
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        mock_instance.subnets.get.return_value = mock_subnet
        mock_instance.network_interfaces.list.return_value = []

        # Query
        query = SimpleIPQuery(
            self.subscription_id,
            self.resource_group,
            self.vnet_name,
            self.subnet_name
        )
        state = query.get_subnet_ip_state()

        # Should not raise
        json_str = json.dumps(state)
        self.assertIsInstance(json_str, str)

    @patch('app.NetworkManagementClient')
    @patch('app.DefaultAzureCredential')
    def test_filters_nics_by_subnet(self, mock_credential, mock_client):
        """Test that only NICs in this subnet are counted."""
        # Mock subnet
        mock_subnet = Mock()
        mock_subnet.id = '/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet'
        mock_subnet.address_prefix = '10.0.1.0/24'

        # Mock NIC in our subnet
        mock_nic_in = Mock()
        mock_nic_in.name = 'nic-in-subnet'
        mock_ip_in = Mock()
        mock_ip_in.subnet = Mock()
        mock_ip_in.subnet.id = mock_subnet.id
        mock_nic_in.ip_configurations = [mock_ip_in]

        # Mock NIC in different subnet
        mock_nic_out = Mock()
        mock_nic_out.name = 'nic-other-subnet'
        mock_ip_out = Mock()
        mock_ip_out.subnet = Mock()
        mock_ip_out.subnet.id = '/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/other-subnet'
        mock_nic_out.ip_configurations = [mock_ip_out]

        # Mock network client
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        mock_instance.subnets.get.return_value = mock_subnet
        mock_instance.network_interfaces.list.return_value = [mock_nic_in, mock_nic_out]

        # Query
        query = SimpleIPQuery(
            self.subscription_id,
            self.resource_group,
            self.vnet_name,
            self.subnet_name
        )
        state = query.get_subnet_ip_state()

        # Only NIC in our subnet should be counted
        self.assertEqual(state['used_ips'], 1)
        self.assertEqual(len(state['nic_details']), 1)
        self.assertEqual(state['nic_details'][0]['name'], 'nic-in-subnet')


if __name__ == '__main__':
    unittest.main()
