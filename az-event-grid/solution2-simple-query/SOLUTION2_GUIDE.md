# Solution 2: Simple VNet/Subnet IP Query

## Overview

**The Stupid Solution** - Query Azure to get current VNet/Subnet IP state. That's it.

- ❌ No events
- ❌ No subscriptions  
- ❌ No automation
- ✅ Just query and display free IPs

This is the baseline "dumb" approach to contrast with event-driven solutions. You ask Azure "how many free IPs do I have?" and it tells you.

## Architecture

```
┌──────────────────┐
│   Your Script    │
│   "Get Free IPs" │
└────────┬─────────┘
         │ Azure SDK
         ▼
┌──────────────────────────────────────┐
│      Azure VNet/Subnet/NIC API       │
│  "Here are your current free IPs"    │
└────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│         Display to Console           │
│   Free: 248/251 (98.8%)              │
│   Used NICs:                         │
│   - nic-1: 2 IPs                     │
│   - nic-2: 1 IP                      │
└──────────────────────────────────────┘
```

## Pros & Cons

### Pros ✅
- **Simple**: No infrastructure, no subscriptions, just query
- **Portable**: Runs anywhere (local, container, cloud)
- **Instant**: One-shot query, no waiting
- **Transparent**: See exact NIC-to-IP mapping
- **Safe**: Read-only, no side effects

### Cons ❌
- **No Real-Time**: Snapshot only, outdated immediately
- **Manual Polling**: You must run manually or on schedule
- **No Automation**: Can't trigger alerts or events
- **No History**: No audit trail of changes
- **Stupid**: Doesn't react to anything

## Usage

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
export SUBSCRIPTION_ID='your-subscription-id'
export RESOURCE_GROUP='ipmonitor-rg'          # optional, defaults shown
export VNET_NAME='ipmonitor-dev-vnet'         # optional
export SUBNET_NAME='ipmonitor-dev-subnet'     # optional
```

### 3. Run the Query

```bash
python app.py
```

### Expected Output

```
🔍 Solution 2: Simple VNet/Subnet IP Query
   Subscription: c0f2d877-380c-48d2-a99b-73c93fd29735
   RG: ipmonitor-rg, VNet: ipmonitor-dev-vnet, Subnet: ipmonitor-dev-subnet

======================================================================
VNet/Subnet IP State
======================================================================
Subnet:           ipmonitor-dev-subnet
Address Prefix:   10.0.1.0/24
Timestamp:        2026-08-20T18:50:00.123456Z

Total IPs:        251
Used IPs:         3
Free IPs:         248
Utilization:      1.20%

NICs in this subnet:
  - test-nic-1: 2 IP(s)
  - test-nic-2: 1 IP(s)
======================================================================

JSON Output:
{
  "subnet_id": "/subscriptions/.../virtualNetworks/ipmonitor-dev-vnet/subnets/ipmonitor-dev-subnet",
  "subnet_name": "ipmonitor-dev-subnet",
  "address_prefix": "10.0.1.0/24",
  "total_ips": 251,
  "used_ips": 3,
  "free_ips": 248,
  "utilization_percent": 1.20,
  "timestamp": "2026-08-20T18:50:00.123456Z",
  "nic_details": [
    {
      "name": "test-nic-1",
      "ip_count": 2
    },
    {
      "name": "test-nic-2",
      "ip_count": 1
    }
  ]
}
```

## Use Cases

### When to Use This Solution ✅

- ✅ **One-off checks**: "Do I have enough IPs left?"
- ✅ **Debugging**: "Which NICs are using IPs?"
- ✅ **Manual inspection**: Manual verification before deployment
- ✅ **Learning**: Understanding IP allocation basics
- ✅ **Non-critical systems**: Quarterly IP audits

### When NOT to Use This ❌

- ❌ **Production alerting**: Needs real-time events
- ❌ **Compliance**: Needs audit trail of changes
- ❌ **Automation**: Needs event triggers
- ❌ **High-frequency**: Needs efficiency of events
- ❌ **Capacity planning**: Needs historical trends

## Testing

```bash
# Run all tests
python -m pytest test_app.py -v

# Run specific test
python -m pytest test_app.py::TestSimpleIPQuery::test_calculate_usable_ips -v

# With coverage
python -m pytest test_app.py --cov=app --cov-report=html
```

### Test Coverage

```
test_initialization              ✅ Verifies object setup
test_calculate_usable_ips        ✅ CIDR → usable IPs
test_get_subnet_ip_state_no_nics ✅ Empty subnet
test_get_subnet_ip_state_with_nics ✅ One NIC with one IP
test_get_subnet_ip_state_multiple_nics ✅ Multiple NICs with secondary IPs
test_state_has_required_fields   ✅ All fields present
test_state_is_json_serializable  ✅ Can serialize to JSON
test_filters_nics_by_subnet      ✅ Ignores NICs in other subnets
```

**Test Results**: 8/8 ✅

## Comparison with Other Solutions

| Aspect | Solution 1 | Solution 2 | Solution 3 |
|--------|-----------|-----------|-----------|
| **Architecture** | Infrastructure-driven | Query-only | Decorator-based |
| **Real-Time** | Yes (events) | No (snapshot) | Yes (events) |
| **Automation** | Yes | No | Yes |
| **Complexity** | High | Low | Medium |
| **Production Ready** | Yes | No | Yes |
| **Use Case** | Enterprise | Debugging | Development |

## Why This Solution is "Stupid"

Because it has **zero intelligence**:

1. **No Reactivity** — Doesn't react to anything
2. **No History** — No memory of previous states
3. **No Automation** — Manual execution only
4. **No Efficiency** — Calls Azure API for every query
5. **No Audit Trail** — No log of who checked what

But it's **brutally simple** and shows the baseline approach.

## Example: Running on Schedule

If you want to manually poll (defeating the purpose), use cron:

```bash
# Check free IPs every 5 minutes
*/5 * * * * cd /path/to/solution2 && python app.py >> /var/log/ip-check.log 2>&1
```

This still won't be event-driven, but at least it's automated.

## Code Structure

### `SimpleIPQuery` Class

```python
class SimpleIPQuery:
    """Query VNet/Subnet IP state."""
    
    def __init__(subscription_id, resource_group, vnet_name, subnet_name):
        # Initialize Azure credentials and client
    
    def get_subnet_ip_state() -> dict:
        # Query current state and return
    
    @staticmethod
    def _calculate_usable_ips(cidr_block: str) -> int:
        # CIDR to usable IP count
```

### Main Flow

```python
def main():
    # 1. Read environment variables
    # 2. Create SimpleIPQuery
    # 3. Call get_subnet_ip_state()
    # 4. Display results
    # 5. Print JSON for automation
```

## FAQ

### Q: Why call this "stupid"?
A: Because it doesn't react to events, doesn't publish events, doesn't automate anything. It's just a status check. This is fine for one-off queries but terrible for production monitoring.

### Q: Can I schedule this?
A: Yes, use cron or Azure Functions Timer. But then you're back to **polling** — which defeats the event-driven purpose.

### Q: What's better?
A: **Solution 1** (pure event-driven) or **Solution 3** (elegant events). This is just the baseline for comparison.

### Q: Can I extend this?
A: Sure. Add alerting if utilization > 80%, publish to Slack, etc. But you've reinvented polling.

## Takeaway

This solution shows why event-driven architecture exists:

- **This approach**: "Let me ask Azure every 5 minutes if anything changed"
- **Event-driven**: "Tell me automatically when something changes"

The first is inefficient. The second is elegant.

---

**Conclusion**: Solution 2 is intentionally simple to show the "dumb" baseline. Use it for debugging. Use Solution 1 or 3 for production.
