# Solution 3: In-App IP Monitoring Decorator

## Overview

**Solution 3** is the simplest approach: a Python decorator that checks subnet IP availability **before** creating network resources. It's built into your application code, requiring no external infrastructure.

**Key characteristic:** Proactive, built-in, lowest cost.

### How It Works

```
Your App (FastAPI)
    ↓
@monitor_ip_status decorator
    ↓ (checks subnet IPs)
Query Azure REST API
    ↓
IPs available? → YES → Create NIC
                 ↓ NO
            Raise IPAvailabilityError
```

### Core Components

| Component | Purpose |
|-----------|---------|
| `solution3_ip_monitor_decorator.py` | Decorator module: IP status queries, calculations |
| `solution3_app.py` | FastAPI demo app using the decorator |
| `test_solution3.py` | Unit + integration tests |

---

## Architecture

### The Decorator

```python
@monitor_ip_status(
    subscription_id="...",
    resource_group="my-rg",
    vnet_name="my-vnet",
    subnet_name="my-subnet",
    min_free_ips=1  # Fail if < 1 free IP
)
def create_nic(nic_name: str):
    """Wraps NIC creation with IP availability check."""
    # Azure SDK call to create NIC
    return nic
```

**Before the wrapped function executes:**
1. Decorator queries Azure for current subnet IP usage
2. Calculates free IPs: `free = total - used`
3. Compares: `free >= min_free_ips`?
4. If YES → runs function; if NO → raises `IPAvailabilityError`

### IP Calculation

Azure reserves ~5 IPs per subnet (network, gateway, broadcast, etc.):
- `/24` → 256 total → 251 usable
- `/25` → 128 total → 123 usable
- `/28` → 16 total → 11 usable

---

## Installation & Setup

### 1. Install Dependencies

```bash
# Add FastAPI and uvicorn to requirements.txt
pip install fastapi uvicorn

# Or, using existing requirements:
pip install -r function-app/requirements.txt
pip install fastapi uvicorn
```

### 2. Configure Environment

```bash
export SUBSCRIPTION_ID="your-subscription-id"
export RESOURCE_GROUP="your-resource-group"
export VNET_NAME="your-vnet"
export SUBNET_NAME="your-subnet"

# For Managed Identity in production:
export AZURE_CLIENT_ID="your-managed-identity-id"
```

### 3. Run the App Locally

```bash
uvicorn solution3_app:app --reload --host 0.0.0.0 --port 8000
```

Output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Usage Examples

### Check Subnet Status (Pre-flight)

No NIC creation—just check IP availability:

```bash
curl http://localhost:8000/subnet-status
```

Response:
```json
{
  "subnet_name": "my-subnet",
  "total_ips": 251,
  "used_ips": 100,
  "free_ips": 151,
  "utilization_percent": 39.84,
  "address_prefix": "10.0.1.0/24"
}
```

### Create NIC (With Decorator Protection)

```bash
curl -X POST http://localhost:8000/create-nic \
  -H "Content-Type: application/json" \
  -d '{"nic_name": "app-nic-1"}'
```

**Success (200):**
```json
{
  "status": "success",
  "nic_name": "app-nic-1",
  "message": "NIC created successfully: /subscriptions/.../networkInterfaces/app-nic-1"
}
```

**Failure - No IPs (409 Conflict):**
```json
{
  "detail": "Insufficient IPs in subnet: Insufficient free IPs in my-subnet. Required: 1, Available: 0. Utilization: 100.0%"
}
```

### Create NIC (Without Decorator - Bypass for Testing)

```bash
curl -X POST http://localhost:8000/create-nic-unsafe \
  -H "Content-Type: application/json" \
  -d '{"nic_name": "app-nic-2"}'
```

This endpoint bypasses the decorator, useful for testing/comparison.

---

## Testing

### Run All Tests

```bash
pytest test_solution3.py -v
```

### Test Output Example

```
test_solution3.py::TestIPCalculation::test_calculate_usable_ips_24 PASSED
test_solution3.py::TestMonitorIPStatusDecorator::test_decorator_blocks_execution_without_free_ips PASSED
test_solution3.py::TestSolution3API::test_create_nic_exhausted_ips PASSED
...
```

### Test Categories

1. **Unit Tests: IP Calculations**
   - CIDR calculations (/24, /25, /28)
   - Edge cases (invalid CIDR, minimum values)

2. **Unit Tests: Decorator**
   - Allows execution with free IPs
   - Blocks execution when IPs exhausted
   - Respects `min_free_ips` threshold
   - Handles Azure query failures gracefully
   - Passes args/kwargs correctly

3. **Integration Tests: FastAPI**
   - Health check endpoint
   - Subnet status queries
   - NIC creation success/failure paths
   - Error handling for missing config

---

## Pros & Cons vs. Other Solutions

### Solution 3 (In-App Decorator) ✅

**Pros:**
- ✅ **Simplest** — No external services (Event Grid, scheduled functions)
- ✅ **Cheapest** — Only Azure SDK calls, no queue/Event Grid fees
- ✅ **Proactive** — Catches exhaustion before resource creation fails
- ✅ **Fast feedback** — Immediate response to caller
- ✅ **Easy to test** — Decorator logic isolated, easy mocking
- ✅ **Built-in** — Part of application code, no separate monitoring

**Cons:**
- ❌ **Application-dependent** — Only works if app uses the decorator
- ❌ **No historical tracking** — Doesn't log IP usage over time
- ❌ **Reactive to state only** — Doesn't observe external changes
- ❌ **Requires code changes** — Must decorate resource-creation functions

### Solution 1 (Event-Driven: Activity Log → Event Grid) vs Solution 3

| Aspect | Solution 1 | Solution 3 |
|--------|-----------|-----------|
| **Cost** | Medium (Event Grid, Queue) | Low (API calls only) |
| **Latency** | ~seconds (event async) | Immediate (sync call) |
| **Historical data** | ✅ Yes (all events logged) | ❌ No (on-demand only) |
| **Monitoring** | ✅ Reactive + continuous | ❌ On-demand only |
| **Setup** | Complex (bicep, event subscriptions) | Simple (decorator) |
| **Visibility** | ✅ Detailed event stream | ❌ Limited to requests |

### Solution 2 (REST Polling: Scheduled Function) vs Solution 3

| Aspect | Solution 2 | Solution 3 |
|--------|-----------|-----------|
| **Cost** | Low (scheduled function) | Very low (decorator only) |
| **Latency** | ~5-10 min (poll interval) | Immediate |
| **Overhead** | Polling all subnets periodically | Only checks on demand |
| **Real-time** | ❌ No (delayed by poll interval) | ✅ Yes |
| **Setup** | Medium (function, timer trigger) | Simple (one file) |

---

## When to Use Solution 3

**Use Solution 3 when:**
- You control the application creating resources
- You need immediate feedback before resource creation
- You want minimal infrastructure/cost
- You don't need historical IP usage tracking
- You want to prevent failures, not monitor them retroactively

**Don't use Solution 3 when:**
- You need to monitor external applications
- You require historical audit trails
- You need centralized monitoring dashboard
- Multiple applications need coordination

---

## Integration with Existing Project

### Option A: Standalone FastAPI App
Run `solution3_app.py` as a separate service:

```bash
uvicorn solution3_app:app --port 8001
```

Call it from your main app:
```python
import requests

status = requests.get("http://localhost:8001/subnet-status")
if status.json()["free_ips"] > 0:
    # Safe to create NIC
    create_nic()
```

### Option B: Embed Decorator in Existing App
Import the decorator into your existing codebase:

```python
from solution3_ip_monitor_decorator import monitor_ip_status

@monitor_ip_status(
    subscription_id=config.subscription_id,
    resource_group=config.resource_group,
    vnet_name=config.vnet_name,
    subnet_name=config.subnet_name
)
def create_network_interface(name):
    # Your NIC creation logic
    return network_client.create_interface(name)
```

---

## Example: Production Integration

```python
# my_app.py

from fastapi import FastAPI, HTTPException
from solution3_ip_monitor_decorator import (
    monitor_ip_status,
    IPAvailabilityError
)

app = FastAPI()

@app.post("/provision-vm")
def provision_vm(vm_config: dict):
    """Provision a VM with network interface."""
    
    try:
        # Decorator ensures subnet has free IPs before creating NIC
        nic = create_nic_with_check(
            vm_config["nic_name"],
            vm_config["vnet"],
            vm_config["subnet"]
        )
        
        # If we reach here, IP is allocated
        vm = create_vm_with_nic(vm_config, nic)
        
        return {"status": "success", "vm_id": vm.id}
        
    except IPAvailabilityError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot provision: {str(e)}"
        )

@monitor_ip_status(
    subscription_id="...",
    resource_group="...",
    vnet_name="...",
    subnet_name="..."
)
def create_nic_with_check(nic_name, vnet, subnet):
    # Azure SDK call
    return network_client.create_nic(nic_name, vnet, subnet)
```

---

## Troubleshooting

### "Missing configuration" Error

```bash
# Ensure all env vars are set:
echo $SUBSCRIPTION_ID
echo $RESOURCE_GROUP
echo $VNET_NAME
echo $SUBNET_NAME

# If empty, set them:
export SUBSCRIPTION_ID="your-id"
# ... etc
```

### "Could not query subnet IP status"

Check:
1. Credentials are configured (local dev: `az login`)
2. Subscription ID is correct
3. Resource group exists
4. VNet and subnet exist

### "Insufficient free IPs" on First Request

The subnet may actually be full. Check:

```bash
curl http://localhost:8000/subnet-status
# Check the "free_ips" field
```

Or via Azure CLI:
```bash
az network vnet subnet show \
  -g my-rg \
  -n my-subnet \
  --vnet-name my-vnet
```

---

## Next Steps

1. ✅ Review the decorator in `solution3_ip_monitor_decorator.py`
2. ✅ Run tests: `pytest test_solution3.py -v`
3. ✅ Start the app: `uvicorn solution3_app:app --reload`
4. ✅ Test endpoints (see Usage Examples above)
5. ✅ Compare with Solution 1 & 2 in the pros/cons table
6. ⏳ Integration in production app (embed decorator in your code)

---

## References

- [Azure VNet and Subnet Concepts](https://docs.microsoft.com/azure/virtual-network/concepts-and-best-practices)
- [Azure Python SDK: NetworkManagementClient](https://docs.microsoft.com/python/api/azure-mgmt-network/azure.mgmt.network.networkmanagementclient)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Python Decorators](https://docs.python.org/3/glossary.html#term-decorator)
