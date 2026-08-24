# Local Testing Guide

Test the Azure Function locally before deploying to Azure.

## Prerequisites

- Python 3.11+
- Azure Functions Core Tools: `npm install -g azure-functions-core-tools@4`
- Azure CLI with active login: `az login`

## Setup Local Environment

### 1. Create Virtual Environment

```bash
cd function-app
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install azure-functions-core-tools
```

### 3. Create `local.settings.json`

Create this file in the `function-app` directory:

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "SUBSCRIPTION_ID": "your-subscription-id",
    "RESOURCE_GROUP": "ipmonitor-rg",
    "SUBNET_ID": "/subscriptions/your-sub/resourceGroups/ipmonitor-rg/providers/Microsoft.Network/virtualNetworks/ipmonitor-dev-vnet/subnets/ipmonitor-dev-subnet",
    "EVENT_GRID_TOPIC_ENDPOINT": "https://ipmonitor-dev-topic.eastus-1.eventgrid.azure.net/api/events",
    "EVENT_GRID_TOPIC_KEY": "your-event-grid-topic-key",
    "AZURE_CLIENT_ID": "your-managed-identity-client-id"
  }
}
```

**Get these values:**

```bash
# Subscription ID
az account show --query id -o tsv

# After deploying infrastructure:
# Subnet ID
az network vnet subnet show \
  --resource-group ipmonitor-rg \
  --vnet-name ipmonitor-dev-vnet \
  --name ipmonitor-dev-subnet \
  --query id -o tsv

# Event Grid Topic Endpoint & Key
az eventgrid topic show \
  --name ipmonitor-dev-topic \
  --resource-group ipmonitor-rg \
  --query properties.endpoint -o tsv

az eventgrid topic key list \
  --name ipmonitor-dev-topic \
  --resource-group ipmonitor-rg \
  --query key1 -o tsv
```

## Run Locally

### Start the Azure Functions Runtime

```bash
cd function-app
func start
```

Expected output:
```
Azure Functions Core Tools (4.x.x) Function Runtime (python, 3.11)
...
MonitorIPUsage: timerTrigger
  Cron expression: '0 */5 * * * *'
```

### Trigger Manually

**Option 1: HTTP POST (via curl)**

```bash
curl -X POST http://localhost:7071/admin/functions/MonitorIPUsage
```

**Option 2: Wait for Timer**

The function runs every 5 minutes. Watch the console output.

**Option 3: Via Azure Functions Core Tools**

```bash
func run MonitorIPUsage --now
```

## Expected Output

Check logs in console. You should see:

```
[2026-08-20T08:30:00.123Z] Executing 'Functions.MonitorIPUsage' (Reason='Timer fired at 2026-08-20T08:30:00.0000000Z', Id=abc123...)
[2026-08-20T08:30:00.456Z] Published event: {'subnet_id': '...', 'used_ips': 2, 'free_ips': 249, 'utilization_percent': 0.8, ...}
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'azure'"

Ensure virtual environment is activated:
```bash
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows
```

### "Unable to reach Event Grid Topic"

- Verify `EVENT_GRID_TOPIC_ENDPOINT` and `EVENT_GRID_TOPIC_KEY` in `local.settings.json`
- Ensure you're logged in: `az login`
- Check network connectivity

### "No subnet found"

Verify the subnet exists:
```bash
az network vnet subnet show \
  --resource-group ipmonitor-rg \
  --vnet-name ipmonitor-dev-vnet \
  --name ipmonitor-dev-subnet
```

### "Authentication failed"

- If using managed identity locally, ensure you're logged in: `az login`
- Function uses `DefaultAzureCredential` which uses CLI login for local development
- Check RBAC: User must have Reader role on the subscription

## Debugging with VS Code

### Install Extension

```bash
code --install-extension ms-azuretools.vscode-azurefunctions
```

### Debug Configuration

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Attach to Python Functions",
      "type": "python",
      "request": "attach",
      "preLaunchTask": "func: host start",
      "pythonPath": "${workspaceFolder}/function-app/.venv/bin/python",
      "port": 9091,
      "host": "127.0.0.1"
    }
  ]
}
```

Set breakpoints and press F5 to debug.

## Performance Testing

### Test Subnet with Multiple NICs

Create test resources to increase IP usage:

```bash
RESOURCE_GROUP="ipmonitor-rg"
VNET_NAME="ipmonitor-dev-vnet"
SUBNET_NAME="ipmonitor-dev-subnet"

for i in {1..5}; do
  az network nic create \
    --resource-group $RESOURCE_GROUP \
    --name test-nic-$i \
    --vnet-name $VNET_NAME \
    --subnet $SUBNET_NAME
done
```

Then trigger the function locally:
```bash
curl -X POST http://localhost:7071/admin/functions/MonitorIPUsage
```

Expected output shows `used_ips: 5`.

## Production Readiness Checklist

- [ ] Function runs locally without errors
- [ ] Correctly queries subnet IP state
- [ ] Publishes events to Event Grid topic
- [ ] Error handling works (logs don't crash)
- [ ] Performance acceptable (<5 sec per execution)
- [ ] No secrets in code (all via env vars / Key Vault)

## Next Steps

1. Deploy to Azure: `./scripts/deploy.sh`
2. Monitor Function App logs: `az functionapp log tail --name ipmonitor-dev-func --resource-group ipmonitor-rg`
3. Create Event Grid subscriptions to consume events
4. Set up alerts on Event Grid metrics
