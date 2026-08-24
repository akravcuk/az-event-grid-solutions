# IP Monitoring Solutions Comparison

Three approaches to monitoring VNet/Subnet IP allocation and availability in Azure. Each solution uses a different architecture with distinct tradeoffs.

---

## Quick Comparison Table

| Aspect | Solution 1: Event-Driven | Solution 2: REST Polling | Solution 3: In-App Decorator |
|--------|--------------------------|--------------------------|------------------------------|
| **Type** | Reactive + Continuous | Periodic Polling | Proactive + On-Demand |
| **Trigger** | Activity Log events | Scheduled timer | Application function call |
| **Architecture** | Activity Log → Event Grid → Queue → Function | Scheduled Function queries REST API | Decorator on resource-creation function |
| **Cost** | Medium | Low | Very Low |
| **Latency** | ~seconds | 5-10 minutes | Immediate (<100ms) |
| **Complexity** | High (Bicep, subscriptions) | Medium (function + timer) | Low (single decorator) |
| **Historical Data** | ✅ Complete event audit trail | ⚠️ Snapshots only | ❌ None |
| **Real-time** | ✅ Yes | ❌ No (delayed by poll interval) | ✅ Yes |
| **Handles External Apps** | ✅ Yes (monitors all resources) | ✅ Yes (queries all subnets) | ❌ No (only integrated apps) |
| **External Infrastructure** | ✅ Required | ✅ Required | ❌ Not needed |
| **Implementation Time** | 2-3 hours | 30-60 min | 15 min |
| **Testing** | Complex (event simulation) | Medium (mock API) | Easy (isolated decorator) |
| **Operational Overhead** | Medium | Low | Very Low |
| **Failure Mode** | Events may be missed if queue backs up | Polling gaps if function fails | Only affects app that calls it |

---

## Detailed Architecture

### Solution 1: Event-Driven (Activity Log → Event Grid)

```
Azure Resource (NIC Created/Updated)
    ↓
Activity Log captures event
    ↓
Event Grid System Topic (receives Activity Log)
    ↓
Event Grid Subscription (filter: Microsoft.Network/networkInterfaces Write)
    ↓
Storage Queue (receives filtered event)
    ↓
Azure Function (triggered by queue message)
    ↓
Query subnet IP usage + Publish custom event to Event Grid
```

**Files:** `infra/activity-subscription.bicep`, `function-app/function_app.py`, `function-app/monitor_ip_usage.py`

**Key Components:**
- System Topic for Activity Log
- Event Grid subscription with filters
- Storage Queue for buffering
- Azure Function for processing

**Deployment:** Bicep infrastructure + Azure Functions

---

### Solution 2: REST Polling (Scheduled Query)

```
Timer Trigger (every 5-10 minutes)
    ↓
Azure Function executes
    ↓
Query Azure REST API for all NICs/subnets
    ↓
Calculate IP usage per subnet
    ↓
Compare with previous state
    ↓
Log differences / Publish events
```

**Implementation:** Would be a separate Python Function with `TimerTrigger`

```python
@app.function_name("PollSubnetIPs")
@app.schedule_trigger(schedule="0 */10 * * * *")  # Every 10 minutes
def poll_subnet_ips(mytimer: func.TimerRequest):
    ip_usage = get_all_subnet_ip_usage()
    detect_and_log_changes(ip_usage)
```

**Key Components:**
- Scheduled function (timer trigger)
- Azure SDK REST calls
- State tracking (database/blob for comparison)

**Deployment:** Single Azure Function with timer trigger

---

### Solution 3: In-App Decorator (Proactive Check)

```
Application (FastAPI / Your Custom App)
    ↓
Calls resource-creation function decorated with @monitor_ip_status
    ↓
Decorator: Query subnet IP status
    ↓
Check: free_ips >= min_free_ips ?
    ├─ YES → Proceed with resource creation
    └─ NO → Raise IPAvailabilityError
```

**Files:** `solution3_ip_monitor_decorator.py`, `solution3_app.py`, `test_solution3.py`

**Key Components:**
- Python decorator (`monitor_ip_status`)
- Subnet IP status query (`get_subnet_ip_status`)
- FastAPI demo app (optional)

**Deployment:** Copy decorator to your application code

---

## Cost Analysis

### Solution 1: Event-Driven
- Event Grid Topic: ~$0.50/month (free tier 100K events)
- Storage Queue: ~$0.01/million operations
- Azure Function: Pay-per-execution (~$0.20/million)
- **Estimated:** $10-20/month (low to moderate traffic)

### Solution 2: REST Polling
- Azure Function: ~$0.20/million executions
- 6 executions/hour × 24 × 30 = 4,320 executions/month
- **Estimated:** $1-5/month

### Solution 3: In-App Decorator
- Azure REST API calls: ~$0.01/million calls
- Depends on how often app checks (typically 100s/month)
- **Estimated:** $0-1/month

---

## Use Cases

### Solution 1: Event-Driven ✅
**Best for:**
- Enterprise requiring complete audit trail of all resource changes
- Centralized monitoring of multiple subscriptions/resource groups
- Need historical data for compliance/troubleshooting
- Reactive dashboards showing real-time IP usage

**Examples:**
- "Show me every IP allocation in the last week"
- "Alert when subnet exceeds 80% utilization"
- "Audit trail of who created what resources when"

---

### Solution 2: REST Polling ✅
**Best for:**
- Periodic health checks (don't need sub-minute latency)
- Limited budget but want centralized monitoring
- Monitoring external/uncontrolled applications
- Scheduled compliance reports

**Examples:**
- "Generate hourly subnet IP usage report"
- "Snapshot current state for cost analysis"
- "Check if any subnet is dangerously full"

---

### Solution 3: In-App Decorator ✅
**Best for:**
- Applications that control their own resource creation
- Need immediate feedback before creating resources
- Fast-fail pattern (prevent errors upstream)
- Development/testing with minimal setup

**Examples:**
- Kubernetes autoscaler checking IPs before scaling up
- IaC tool validating availability before provisioning
- Application preventing NIC creation if subnet full
- "Fail fast: don't try to create NIC if subnet exhausted"

---

## Decision Matrix

**Choose Solution 1 if:**
- [ ] You need complete historical audit trail
- [ ] You monitor resources from multiple applications
- [ ] You want centralized dashboard/alerts
- [ ] Enterprise compliance requires event logging

**Choose Solution 2 if:**
- [ ] You need periodic status checks (not real-time)
- [ ] You want to monitor external applications
- [ ] Budget is tight but want some visibility
- [ ] You need scheduled reports

**Choose Solution 3 if:**
- [ ] Your app creates its own resources
- [ ] You want immediate pre-creation checks
- [ ] You prefer minimal infrastructure
- [ ] Cost is a primary concern

---

## Implementation Effort

### Solution 1: Event-Driven
**Initial Setup:** 2-3 hours
- Write Bicep templates (main.bicep, activity-subscription.bicep)
- Deploy infrastructure
- Configure Event Grid subscription and filters
- Test event flow end-to-end

**Maintenance:** Low (once deployed, mostly automated)

### Solution 2: REST Polling
**Initial Setup:** 1-2 hours
- Create Azure Function with timer trigger
- Implement IP query and state comparison
- Set appropriate polling interval
- Deploy to Azure

**Maintenance:** Low (same as Solution 1)

### Solution 3: In-App Decorator
**Initial Setup:** 30 minutes
- Copy `solution3_ip_monitor_decorator.py` to your project
- Decorate resource-creation functions
- Set environment variables (subscription, RG, VNet, subnet)
- Done!

**Maintenance:** Minimal (just decorator code, no external services)

---

## Testing Comparison

### Solution 1: Testing
```bash
# Need to:
# 1. Deploy real Azure resources
# 2. Simulate events (hard)
# 3. Monitor queue/function execution
# 4. Check logs

az eventgrid domain create --name test-domain ...
# Test by creating actual NIC...
```
**Challenge:** Hard to test without real Azure resources

### Solution 2: Testing
```bash
# Can mock the REST API calls
import unittest.mock as mock

with mock.patch('azure.mgmt.network.NetworkManagementClient'):
    result = poll_subnet_ips()
    assert result == expected
```
**Challenge:** Moderate (need to mock Azure SDK)

### Solution 3: Testing
```bash
# Completely isolated, easy mocking
@patch('solution3_ip_monitor_decorator.get_subnet_ip_status')
def test_decorator_blocks_when_no_ips(mock_get_status):
    mock_get_status.return_value = SubnetIPStatus(..., free_ips=0, ...)
    with pytest.raises(IPAvailabilityError):
        create_nic()
```
**Challenge:** Easy (decorator is isolated unit)

✅ **19/19 tests passing** for Solution 3 with simple mocking

---

## Failure Scenarios

### Solution 1: What if Event Grid is down?
- Events may be delayed or lost
- Function doesn't execute
- IP changes not tracked
- **Impact:** Monitoring gap

### Solution 2: What if Function doesn't run?
- Polling stops
- No new snapshots captured
- Last known state becomes stale
- **Impact:** Delayed detection

### Solution 3: What if decorator query fails?
- Decorator logs warning, proceeds anyway (graceful degradation)
- Resource creation happens (same as no decorator)
- **Impact:** Prevents blocking on network failure

---

## Hybrid Approach

**Recommended: Use all three together**

```
┌─────────────────────────────────────┐
│ Application (with Solution 3)        │
│ @monitor_ip_status                  │
│ Checks before creating resources    │
└─────────────────────────────────────┘
         ↑                   ↓
         │            Create resource?
         │            (with safety check)
         │
         └──► Solution 1 (Audit)
              Activity Log → Event Grid
              (historical tracking)
         └──► Solution 2 (Health Check)
              Scheduled polling
              (periodic reports)
```

**Benefits:**
- **Solution 3:** Fast pre-creation checks (prevents user errors)
- **Solution 1:** Complete audit trail (compliance/debugging)
- **Solution 2:** Periodic health snapshots (trends/reports)

---

## Deployment Instructions by Solution

### Deploying Solution 1
```bash
# Already deployed - see README.md for details
```

### Deploying Solution 2
Would require:
```bash
# Create new Function
az functionapp create ...

# Add timer trigger
# Deploy with appropriate polling interval
```

### Deploying Solution 3
```bash
# Already implemented!
# Files created:
# - solution3_ip_monitor_decorator.py (reusable decorator)
# - solution3_app.py (FastAPI demo)
# - test_solution3.py (19 passing tests)
# - SOLUTION3_GUIDE.md (documentation)

# To use in your app:
cp solution3_ip_monitor_decorator.py /path/to/your/project/
```

---

## Recommendation

| Scenario | Recommendation |
|----------|-----------------|
| **Enterprise with audit requirements** | Solution 1 + Solution 3 (decorator for safety, events for audit) |
| **Cost-conscious monitoring** | Solution 3 (minimal cost, real-time) |
| **Periodic reporting only** | Solution 2 (low frequency, low cost) |
| **Development/Testing** | Solution 3 (easy, no infrastructure) |
| **Production with compliance** | All three (defense in depth) |

---

## References

- [Solution 1 Guide](SOLUTION1_DEPLOYMENT.md) — Event-Driven Architecture
- [Solution 3 Guide](SOLUTION3_GUIDE.md) — In-App Decorator Pattern
- [README](README.md) — Project overview
- [test_solution3.py](test_solution3.py) — 19 comprehensive tests

