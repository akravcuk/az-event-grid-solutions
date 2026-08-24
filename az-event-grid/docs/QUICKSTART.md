# Quick Start (5 Minutes)

Get Event Grid IP monitoring running in your Azure subscription.

## Step 1: Prerequisites Check (1 min)

```bash
# Verify Azure CLI is installed and logged in
az account show

# Install Bicep
az bicep install

# Verify Bicep
bicep --version
```

If any command fails, see [README.md](README.md#prerequisites).

## Step 2: Customize Parameters (1 min)

Edit `infra/parameters.bicepparam`:

```bicep
param location = 'eastus'  # Your region
param vnetAddressPrefix = '10.0.0.0/16'  # Your VNet CIDR
param subnetAddressPrefix = '10.0.1.0/24'  # Your Subnet CIDR
```

## Step 3: Deploy Infrastructure (2 min)

```bash
./scripts/deploy.sh
```

This:
- Creates resource group `ipmonitor-rg`
- Deploys VNet + Subnet
- Creates Event Grid topic
- Creates Azure Function (Python 3.11)
- Configures Managed Identity with proper RBAC

**Expected output:**
```
=== Deployment Complete ===

✓ Using subscription: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
✓ Resource Group: ipmonitor-rg
✓ Location: eastus
✓ Infrastructure deployed successfully
✓ Function App code deployed

Next steps:
1. Verify deployment: az functionapp show --name ipmonitor-dev-func --resource-group ipmonitor-rg
...
```

## Step 4: Verify & Test (1 min)

```bash
# Check Function App is running
az functionapp show --name ipmonitor-dev-func --resource-group ipmonitor-rg --query state

# View logs (wait 10 seconds for initialization)
az functionapp log tail --name ipmonitor-dev-func --resource-group ipmonitor-rg
```

Expected: Function logs show it's running and ready.

## Step 5: Trigger Monitoring (Automatically on Deployment)

Deploy a test VM or NIC — the function triggers **instantly**:

```bash
az vm create \
  --resource-group ipmonitor-rg \
  --name test-vm \
  --image UbuntuLTS \
  --vnet-name ipmonitor-dev-vnet \
  --subnet ipmonitor-dev-subnet \
  --generate-ssh-keys \
  --size Standard_B1s
```

Or create a NIC directly:
```bash
az network nic create \
  --resource-group ipmonitor-rg \
  --name test-nic-1 \
  --vnet-name ipmonitor-dev-vnet \
  --subnet ipmonitor-dev-subnet
```

## Step 6: Verify Events (Immediate)

Check Function App logs immediately:

```bash
az functionapp log tail --name ipmonitor-dev-func --resource-group ipmonitor-rg
```

Expected output:
```
[2026-08-20T08:30:00.123Z] Processing deployment event for resource: /subscriptions/.../networkInterfaces/test-nic-1
[2026-08-20T08:30:00.456Z] Published event: {'subnet_id': '...', 'used_ips': 1, 'free_ips': 250, 'utilization_percent': 0.4, ...}
```

Check Event Grid topic received events:

```bash
az eventgrid topic show \
  --name ipmonitor-dev-topic \
  --resource-group ipmonitor-rg \
  --query properties
```

Look for `"publishedEventCount": 1` (or higher).

## What Just Happened

1. **Infrastructure:** VNet, Subnet, Event Grid Topic, Azure Function deployed via Bicep
2. **Function:** Monitors subnet IP usage every 5 minutes
3. **Event:** When resources deploy (VM, NIC, IP), function publishes custom event showing:
   - Total IPs: 251
   - Used IPs: 2 (your VM)
   - Free IPs: 249
   - Utilization: 0.8%

## Next: Consume Events

Subscribe to events in Event Grid topic:

```bash
# Get topic ID
TOPIC_ID=$(az eventgrid topic show \
  --name ipmonitor-dev-topic \
  --resource-group ipmonitor-rg \
  --query id -o tsv)

# Create webhook subscription (replace with your endpoint)
az eventgrid event-subscription create \
  --name my-subscription \
  --source-resource-id $TOPIC_ID \
  --endpoint https://your-webhook-endpoint
```

Or send events to:
- **Storage Queue** for async processing
- **Service Bus** for pub/sub
- **Logic App** for automation
- **Azure Function** for custom processing

See [README.md](README.md#event-subscription-examples) for more examples.

## Cleanup (Optional)

Delete all resources:

```bash
az group delete --name ipmonitor-rg --yes --no-wait
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "az: command not found" | Install [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| "Bicep not found" | Run `az bicep install` |
| "Not logged in" | Run `az login` |
| "No events in topic" | Wait 5 minutes, check logs: `az functionapp log tail ...` |
| "Deployment fails" | Check resource group quota: `az group create ...` in different region |

## Get Help

- **Detailed docs:** See [README.md](README.md)
- **Local testing:** See [LOCAL_TESTING.md](LOCAL_TESTING.md)
- **Code changes:** See [CONTRIBUTING.md](CONTRIBUTING.md)

## What's Next?

1. Create Event Grid subscriptions to consume IP usage events
2. Build Logic App workflows to auto-respond to high utilization
3. Send events to your monitoring dashboard
4. Integrate with IPAM/CMDB systems
5. Add cost optimization based on IP capacity forecasting

**You now have real-time IP usage monitoring in Azure! 🎉**
