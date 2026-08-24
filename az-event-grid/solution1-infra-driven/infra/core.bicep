metadata description = 'Deploy Event Grid IP monitoring core infrastructure (no Function App - deploy separately on subscription with VM quota)'

param location string = resourceGroup().location
param projectName string = 'ipmonitor'
param environment string = 'dev'
param vnetAddressPrefix string = '10.0.0.0/16'
param subnetAddressPrefix string = '10.0.1.0/24'

var resourceNamePrefix = '${projectName}${environment}'
var vnetName = '${projectName}-${environment}-vnet'
var subnetName = '${projectName}-${environment}-subnet'
var eventGridTopicName = '${projectName}-${environment}-topic'

// VNet
resource vnet 'Microsoft.Network/virtualNetworks@2023-04-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: subnetName
        properties: {
          addressPrefix: subnetAddressPrefix
          delegations: []
          privateEndpointNetworkPolicies: 'Disabled'
          privateLinkServiceNetworkPolicies: 'Enabled'
        }
      }
    ]
  }
}

// Event Grid Custom Topic
resource eventGridTopic 'Microsoft.EventGrid/topics@2023-12-15-preview' = {
  name: eventGridTopicName
  location: location
  kind: 'Azure'
  identity: {
    type: 'None'
  }
  properties: {
    inputSchema: 'EventGridSchema'
    publicNetworkAccess: 'Enabled'
    inboundIpRules: []
  }
  sku: {
    name: 'Basic'
  }
}

// Outputs
output vnetId string = vnet.id
output vnetName string = vnetName
output subnetId string = subnet.id
output subnetName string = subnetName
output eventGridTopicId string = eventGridTopic.id
output eventGridEndpoint string = eventGridTopic.properties.endpoint
output eventGridTopicKey string = listKeys(eventGridTopic.id, eventGridTopic.apiVersion).key1

// Subnet reference
resource subnet 'Microsoft.Network/virtualNetworks/subnets@2023-04-01' existing = {
  name: '${vnet.name}/${subnetName}'
}
