param eventGridTopicId string
param subscriptionId string = subscription().subscriptionId
param resourceGroupName string = resourceGroup().name

// Event Grid subscription on Activity Log (subscription-level)
// Captures ResourceWriteSuccess for Microsoft.Network resources
resource activityEventSubscription 'Microsoft.EventGrid/eventSubscriptions@2023-12-15-preview' = {
  name: 'activity-to-custom-topic'
  scope: subscription()
  properties: {
    destination: {
      endpointType: 'EventGrid'
      properties: {
        resourceId: eventGridTopicId
      }
    }
    filter: {
      subjectBeginsWith: ''
      subjectEndsWith: ''
      includedEventTypes: [
        'Microsoft.Resources.ResourceWriteSuccess'
      ]
      isSubjectCaseSensitive: false
      advancedFilters: [
        {
          operatorType: 'StringContains'
          key: 'data.resourceProvider'
          values: [
            'Microsoft.Network'
          ]
        }
        {
          operatorType: 'StringContains'
          key: 'data.operationName'
          values: [
            'Microsoft.Network/networkInterfaces/write'
            'Microsoft.Network/publicIPAddresses/write'
          ]
        }
        {
          operatorType: 'StringContains'
          key: 'data.resourceGroupName'
          values: [
            resourceGroupName
          ]
        }
      ]
    }
    eventDeliverySchema: 'EventGridSchema'
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
}

output subscriptionId string = activityEventSubscription.id
output subscriptionName string = activityEventSubscription.name
