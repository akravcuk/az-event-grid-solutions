# Azure Event Grid IP Usage Monitoring

Monitor Azure VNet/Subnet IP address consumption with real-time Event Grid notifications. Automatically emit events when resources deploy and consume IPs, including free/consumed/utilization metrics.

## Architecture

**Event-Driven (No Polling):**

```
Azure Activity Log (Subscription-level)
    ↓
ResourceWriteSuccess for Microsoft.Network resources
    ↓
Event Grid Subscription (Activity log → Function trigger)
    ↓
Azure Function (instant execution)
  1. Extract resource ID from event (NIC, IP, etc.)
  2. Find subnet (if NIC, query its subnet)
  3. Query subnet IP state via Azure SDK
  4. Publish custom event
    ↓
Event Grid Custom Topic
    ↓
Event Subscriptions (webhook, queue, service bus, etc.)
```

## Prerequisites

- **Azure Subscription** with active login
- **Azure CLI** (v2.50+): [Install](https://learn.microsoft.com/cli/azure)
- **Bicep CLI** (installed via `az bicep install`)
- **Python 3.11+** (for local testing)

### Quick Setup

```bash
# Login to Azure
az login

# Install Bicep
az bicep install

# Verify prerequisites
az account show
bicep --version
```

## Deployment

### 1. Navigate to Project

```bash
cd /path/to/az-event-grid
```

### 2. Customize Parameters (Optional)

Edit `infra/parameters.bicepparam`:

```bicep
param location = 'eastus'  # Change region if needed
param projectName = 'ipmonitor'
param environment = 'dev'
param vnetAddressPrefix = '10.0.0.0/16'  # Your VNet CIDR
param subnetAddressPrefix = '10.0.1.0/24'  # Your Subnet CIDR
```

### 3. Deploy

```bash
# Using the deployment script (recommended)
./scripts/deploy.sh

# Or manually with Azure CLI
RESOURCE_GROUP="ipmonitor-rg"
LOCATION="eastus"

az group create --name $RESOURCE_GROUP --location $LOCATION

az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/parameters.bicepparam
```

**Deployment takes ~2-3 minutes.**

### 4. Verify Deployment

```bash
# Check Resource Group
az group show --name ipmonitor-rg

# Check Function App
az functionapp show --name ipmonitor-dev-func --resource-group ipmonitor-rg

# Check Event Grid Topic
az eventgrid topic show --name ipmonitor-dev-topic --resource-group ipmonitor-rg

# View Function App Logs
az functionapp log tail --name ipmonitor-dev-func --resource-group ipmonitor-rg
```

## Testing

### Option 1: Deploy a Test VM (Automatically Triggers Monitoring)

```bash
RESOURCE_GROUP="ipmonitor-rg"
VNET_NAME="ipmonitor-dev-vnet"
SUBNET_NAME="ipmonitor-dev-subnet"

az vm create \
  --resource-group $RESOURCE_GROUP \
  --name test-vm \
  --image UbuntuLTS \
  --vnet-name $VNET_NAME \
  --subnet $SUBNET_NAME \
  --generate-ssh-keys \
  --size Standard_B1s
```

**Result:** Azure Function triggers instantly when the NIC is created, queries subnet IP usage, and publishes event to Event Grid. Check logs immediately:

```bash
az functionapp log tail --name ipmonitor-dev-func --resource-group ipmonitor-rg
```

### Option 2: Create NICs Directly

```bash
az network nic create \
  --resource-group ipmonitor-rg \
  --name test-nic-1 \
  --vnet-name ipmonitor-dev-vnet \
  --subnet ipmonitor-dev-subnet
```

### Option 3: Query Event Grid Metrics

```bash
# View metrics in Event Grid topic
az eventgrid topic show \
  --name ipmonitor-dev-topic \
  --resource-group ipmonitor-rg \
  --query properties

# Expected output shows "publishedEventCount" increasing
```

## Event Payload Example

When a resource deploys to the subnet, the Function publishes:

```json
{
  "eventType": "ipUsageChanged",
  "data": {
    "subnet_id": "/subscriptions/.../subnets/ipmonitor-dev-subnet",
    "subnet_name": "ipmonitor-dev-subnet",
    "address_prefix": "10.0.1.0/24",
    "total_ips": 251,
    "used_ips": 2,
    "free_ips": 249,
    "utilization_percent": 0.8,
    "resource_group": "ipmonitor-rg",
    "vnet_name": "ipmonitor-dev-vnet",
    "timestamp": "2026-08-20T08:30:00Z"
  },
  "subject": "/subscriptions/.../subnets/ipmonitor-dev-subnet",
  "dataVersion": "1.0",
  "eventTime": "2026-08-20T08:30:00Z"
}
```

## Monitoring & Alerts

### View Events in Event Grid Topic

```bash
az eventgrid topic show \
  --name ipmonitor-dev-topic \
  --resource-group ipmonitor-rg
```

### Create Event Subscription (Webhook Example)

```bash
TOPIC_ID=$(az eventgrid topic show \
  --name ipmonitor-dev-topic \
  --resource-group ipmonitor-rg \
  --query id -o tsv)

az eventgrid event-subscription create \
  --name webhook-subscription \
  --source-resource-id $TOPIC_ID \
  --endpoint https://your-webhook-endpoint/webhook \
  --endpoint-type webhook
```

### Create Event Subscription (Storage Queue Example)

```bash
TOPIC_ID=$(az eventgrid topic show \
  --name ipmonitor-dev-topic \
  --resource-group ipmonitor-rg \
  --query id -o tsv)

QUEUE_ID=$(az storage queue show \
  --name ip-events \
  --account-name yourstorageaccount \
  --query id -o tsv)

az eventgrid event-subscription create \
  --name queue-subscription \
  --source-resource-id $TOPIC_ID \
  --endpoint $QUEUE_ID \
  --endpoint-type storagequeue
```

## Troubleshooting

### Function App Not Running

```bash
# Check status
az functionapp show --name ipmonitor-dev-func --resource-group ipmonitor-rg --query state

# View detailed logs
az functionapp log tail --name ipmonitor-dev-func --resource-group ipmonitor-rg --provider Application --level Error
```

### No Events Published

1. **Check Event Grid Subscription:**
   ```bash
   az eventgrid event-subscription list --source-resource-id /subscriptions/YOUR_SUB --output table
   ```

2. **Verify Managed Identity Permissions:**
   ```bash
   az role assignment list \
     --scope /subscriptions/{sub} \
     --assignee {principalId} \
     --output table
   ```

3. **Check Function Logs for Errors:**
   ```bash
   az functionapp log tail --name ipmonitor-dev-func --resource-group ipmonitor-rg
   ```

4. **Test NIC Creation Manually:**
   ```bash
   # This should trigger the function immediately
   az network nic create \
     --resource-group ipmonitor-rg \
     --name debug-nic \
     --vnet-name ipmonitor-dev-vnet \
     --subnet ipmonitor-dev-subnet
   ```

### Event Grid Topic Not Receiving Events

1. Verify Event Grid topic exists:
   ```bash
   az eventgrid topic list --resource-group ipmonitor-rg
   ```

2. Check Event Grid topic metrics (should show "Publish Requests"):
   ```bash
   az monitor metrics list \
     --resource /subscriptions/{sub}/resourceGroups/ipmonitor-rg/providers/Microsoft.EventGrid/topics/ipmonitor-dev-topic
   ```

## Advanced Configuration

### Monitor Multiple Subnets

Edit the Event Grid subscription filter in `infra/main.bicep` to accept multiple subnets (currently filters by operation type only):

```bicep
// In activityEventSubscription, add subnet-specific filter:
{
  operatorType: 'StringContains'
  key: 'data.resourceId'
  values: [
    '/subnets/production-subnet/'
    '/subnets/staging-subnet/'
  ]
}
```

### Change Monitored Operations

Edit `infra/main.bicep` `activityEventSubscription` filter to monitor different operations:

```bicep
"Microsoft.Network/virtualNetworks/subnets/write"
"Microsoft.Network/networkInterfaces/write"
"Microsoft.Network/publicIPAddresses/write"
"Microsoft.Network/virtualMachines/write"
```

### Filter by Resource Group

Add to Event Grid subscription filter in Bicep:

```bicep
{
  operatorType: 'StringContains'
  key: 'data.resourceGroupName'
  values: [
    'ipmonitor-rg'
  ]
}
```

## Cost Estimation (Monthly)

| Service | Tier | Cost |
|---------|------|------|
| Event Grid Topic | Basic (1M events) | ~$0.50 |
| Azure Function | Consumption | ~$0.20 (based on executions) |
| Storage Account | Standard LRS | ~$0.50 |
| **Total** | | **~$1.20** |

*Costs vary by region. See [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator).*

## Cleanup

To remove all resources:

```bash
az group delete --name ipmonitor-rg --yes --no-wait
```

## Security Considerations

✅ **Implemented:**
- Managed Identity (no hardcoded credentials)
- RBAC with minimal Reader role on subscription
- HTTPS-only Function App
- Event Grid Basic tier (TLS encrypted)
- No secrets stored in code
- Event-driven (no continuous polling)

⚠️ **Recommendations:**
- Enable Key Vault for Event Grid topic key rotation
- Configure Private Endpoints for Function App if using private networks
- Enable audit logging via Azure Monitor
- Set up budget alerts for cost monitoring
- Restrict Event Grid subscription to specific resource groups

## Support & Next Steps

### Integrate with Other Services

- **Webhook → Logic App:** Auto-remediation on high IP utilization
- **Event Hub:** Stream events for real-time analytics
- **Service Bus:** Queue for downstream processing
- **Azure DevOps:** Trigger pipelines on IP capacity warnings

### Examples

**Alert when utilization exceeds 80%:**
```bash
# Add Logic App as Event Grid subscriber
# Configure condition: if utilization_percent > 80
# Action: Send email/Teams notification
```

**Auto-scale VNet:**
```bash
# Subscribe to events in Logic App
# Trigger: ipUsageChanged with utilization > 85%
# Action: Add secondary subnet, update routing
```

## License

MIT

## Contributing

See CONTRIBUTING.md (or create as needed for your portfolio).
