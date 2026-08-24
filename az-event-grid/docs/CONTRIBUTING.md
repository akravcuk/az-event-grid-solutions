# Contributing

This project is part of a portfolio demonstrating Azure infrastructure patterns.

## Development Workflow

### 1. Local Testing

Before making changes, test locally:

```bash
cd function-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
func start
```

See [LOCAL_TESTING.md](LOCAL_TESTING.md) for detailed instructions.

### 2. Code Style

**Python:**
- Follow [PEP 8](https://pep8.org/)
- Use type hints for function signatures
- Add docstrings for public functions

**Bicep:**
- Use descriptive parameter names
- Add metadata descriptions
- Organize resources logically (managed identity, VNet, compute, etc.)

### 3. Testing Changes

- Test Bicep: `bicep build infra/main.bicep`
- Test Python: `pytest function-app/` (if tests added)
- Test deployment: Run `./scripts/deploy.sh` in dev subscription

### 4. Documentation

- Update README.md if adding features
- Add troubleshooting sections for known issues
- Include examples for new capabilities

## Common Changes

### Add a New Subnet to Monitor

1. Edit `infra/parameters.bicepparam`: add subnet CIDR
2. Update `function-app/monitor_ip_usage.py`: loop over multiple subnets
3. Update environment variables in Bicep
4. Test locally, then deploy

### Change Function Trigger Interval

Edit `function-app/function_app.py`:
```python
@app.timer_trigger(arg_name="myTimer", schedule="0 */10 * * * *")  # Every 10 min
```

CRON format: `second minute hour day-of-month month day-of-week`

### Add Metrics/Alerting

1. Update event payload in `monitor_ip_usage.py`
2. Create Azure Monitor alert rules via Azure Portal or ARM/Bicep
3. Subscribe Event Grid topic to trigger alerts

## Known Limitations

- **Activity Log delay:** 1-2 minute latency before events appear
- **IP count:** Azure reserves ~5 IPs per subnet (network, gateway, DNS, broadcast, reserved)
- **Scale:** Currently queries single subscription (extendable for cross-subscription)

## Future Enhancements

- Multi-subscription support
- Webhook for IP threshold alerts
- Dashboard showing IP trends over time
- Integration with IPAM systems
- Lambda/serverless for cost optimization on other clouds

## License

MIT - See LICENSE file
