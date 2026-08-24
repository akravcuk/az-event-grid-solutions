#!/bin/bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INFRA_DIR="$PROJECT_DIR/infra"
FUNCTION_APP_DIR="$PROJECT_DIR/function-app"

# Default values (can be overridden by env vars or args)
RESOURCE_GROUP="${RESOURCE_GROUP:-ipmonitor-rg}"
LOCATION="${LOCATION:-eastus}"
SUBSCRIPTION_ID="${SUBSCRIPTION_ID:-}"

echo -e "${YELLOW}=== Azure Event Grid IP Monitoring Deployment ===${NC}\n"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI not found. Install it from https://docs.microsoft.com/cli/azure${NC}"
    exit 1
fi

if ! command -v bicep &> /dev/null; then
    echo -e "${YELLOW}Warning: Bicep CLI not found. Trying to upgrade Azure CLI...${NC}"
    az bicep install
fi

# Check Azure login
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Not logged in to Azure. Starting login...${NC}"
    az login
fi

# Get subscription ID if not provided
if [ -z "$SUBSCRIPTION_ID" ]; then
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
fi

echo -e "${GREEN}✓ Using subscription: $SUBSCRIPTION_ID${NC}"
echo -e "${GREEN}✓ Resource Group: $RESOURCE_GROUP${NC}"
echo -e "${GREEN}✓ Location: $LOCATION${NC}\n"

# Create resource group if it doesn't exist
echo -e "${YELLOW}Creating resource group...${NC}"
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --query properties.provisioningState -o tsv

# Deploy Bicep template
echo -e "\n${YELLOW}Deploying infrastructure with Bicep...${NC}"
DEPLOYMENT_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$INFRA_DIR/main.bicep" \
    --parameters "$INFRA_DIR/parameters.bicepparam" \
    --output json)

# Extract outputs
FUNCTION_APP_NAME=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.properties.outputs.functionAppName.value')
EVENT_GRID_ENDPOINT=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.properties.outputs.eventGridEndpoint.value')
EVENT_GRID_TOPIC_ID=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.properties.outputs.eventGridTopicId.value')

echo -e "${GREEN}✓ Infrastructure deployed successfully${NC}"
echo -e "${GREEN}  Function App: $FUNCTION_APP_NAME${NC}"
echo -e "${GREEN}  Event Grid Topic: $EVENT_GRID_ENDPOINT${NC}\n"

# Deploy Function App code
echo -e "${YELLOW}Deploying Function App code...${NC}"

# Create deployment package
cd "$FUNCTION_APP_DIR"

# Install dependencies in local folder
python3 -m pip install -q -r requirements.txt --target .

# Deploy to Function App
az functionapp deployment source config-zip \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FUNCTION_APP_NAME" \
    --src <(zip -q - -r . -x "*.git*" ".venv*" "__pycache__*" "*.pyc" ".pytest_cache*")

echo -e "${GREEN}✓ Function App code deployed${NC}\n"

# Wait for Function App to start
echo -e "${YELLOW}Waiting for Function App to initialize...${NC}"
sleep 10

# Verify Function App is running
if az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${GREEN}✓ Function App is running${NC}\n"
else
    echo -e "${RED}Error: Function App failed to start${NC}"
    exit 1
fi

# Display next steps
echo -e "${GREEN}=== Deployment Complete ===${NC}\n"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Verify deployment:"
echo "   az functionapp show --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "2. Check Function App logs:"
echo "   az functionapp log tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "3. Monitor Event Grid topic:"
echo "   az eventgrid topic show --name ipmonitor-dev-topic --resource-group $RESOURCE_GROUP"
echo ""
echo "4. Create Event Grid subscription (example - webhook):"
echo "   az eventgrid event-subscription create \\"
echo "     --name my-subscription \\"
echo "     --source-resource-id $EVENT_GRID_TOPIC_ID \\"
echo "     --endpoint https://your-webhook-endpoint"
echo ""
echo "5. Test by deploying a VM to trigger IP monitoring:"
echo "   az vm create --name test-vm --resource-group $RESOURCE_GROUP --image UbuntuLTS --generate-ssh-keys"
echo ""
echo -e "${YELLOW}Check Event Grid Metrics in 5 minutes for 'Event Published' count${NC}\n"
